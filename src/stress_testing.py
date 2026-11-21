"""
Fixed-Chain Stress Testing Engine (Punto 52):
Maintains fixed contract symbols and strikes, updates residual maturity tau and moneyness k,
models multi-factor surface deformations (Level, Skew, Curvature, Term Slope),
executes full American PDE revaluation, and contrasts against Taylor Greek expansions.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src.market_data import SPOT_PRICE, CONTRACT_MULTIPLIER, get_zero_rate, get_forward_price
from src.pricing_american_fd import price_american_option
from src.greeks import calculate_option_greeks
from src.surface import VolatilitySurface
from src.portfolio import build_hypothetical_portfolio, PORTFOLIO_LEGS

SCENARIOS = {
    'S1_RollDown_10d': {
        'name': '1. Pure Roll-Down (Time Decay)',
        'dt_days': 10.0,
        'dS_pct': 0.0,
        'dVol_level_pp': 0.0,
        'skew_tilt_pp': 0.0,
        'term_tilt_pp': 0.0,
        'description': '10 days forward time decay with unchanged spot and invariant surface.'
    },
    'S2_Parallel_Drop': {
        'name': '2. Parallel Drop & Vol Spike',
        'dt_days': 5.0,
        'dS_pct': -0.10,
        'dVol_level_pp': 10.0,
        'skew_tilt_pp': 0.0,
        'term_tilt_pp': 0.0,
        'description': 'Spot -10%, parallel surface jump +10 pp after 5 days.'
    },
    'S3_Severe_Crisis': {
        'name': '3. Severe Crisis & Skew Steepening',
        'dt_days': 5.0,
        'dS_pct': -0.20,
        'dVol_level_pp': 12.0,
        'skew_tilt_pp': 8.0,
        'term_tilt_pp': 10.0,
        'description': 'Spot -20%, level +12 pp, put skew +8 pp, short-term tilt +10 pp.'
    },
    'S4_Bullish_Rally': {
        'name': '4. Bullish Rally & Vol Crush',
        'dt_days': 3.0,
        'dS_pct': 0.15,
        'dVol_level_pp': -8.0,
        'skew_tilt_pp': -2.0,
        'term_tilt_pp': -5.0,
        'description': 'Spot +15%, level crush -8 pp, short-tenor crush -5 pp after 3 days.'
    },
    'S5_Short_Tenor_Inversion': {
        'name': '5. Short-Tenor Inversion Shock',
        'dt_days': 2.0,
        'dS_pct': -0.05,
        'dVol_level_pp': 2.0,
        'skew_tilt_pp': 4.0,
        'term_tilt_pp': 15.0,
        'description': 'Spot -5%, short tenors jump +15 pp, flattening the term structure.'
    }
}

def apply_surface_shock(
    base_surface: VolatilitySurface,
    k1: float,
    tau1: float,
    dVol_level_pp: float,
    skew_tilt_pp: float,
    term_tilt_pp: float,
    convention: str = "sticky_moneyness",
    k0: float = 0.0
) -> float:
    """
    Deforms implied volatility according to multi-factor shocks.
    Enforces minimum volatility floor of 10.0% (0.10).
    """
    if convention == "sticky_strike":
        # Under sticky-strike, evaluate base surface at original moneyness k0
        base_iv = base_surface.surface_iv(k0, max(tau1, 1e-4))['iv']
    else:
        # Under sticky-moneyness, evaluate base surface at updated moneyness k1
        base_iv = base_surface.surface_iv(k1, max(tau1, 1e-4))['iv']

    # Exogenous multi-factor shocks (in percentage points)
    # 1. Level shock
    shock_pp = dVol_level_pp

    # 2. Skew tilt: increases volatility for out-of-the-money puts (k1 < 0)
    if k1 < 0.0:
        shock_pp += skew_tilt_pp * min(abs(k1) / 0.20, 2.0)
    else:
        shock_pp += 0.5 * skew_tilt_pp * (k1 / 0.20)

    # 3. Term structure tilt: shock decays exponentially with maturity tau
    # (exp(-tau / 0.3) decays to ~3% at 1 year)
    term_factor = np.exp(-tau1 / 0.30)
    shock_pp += term_tilt_pp * term_factor

    stressed_iv = base_iv + (shock_pp / 100.0)
    return float(max(stressed_iv, 0.10))

def run_stress_testing(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes fixed-chain stress testing across 5 scenarios.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    # Load portfolio and baseline
    port_df, port_summary = build_hypothetical_portfolio(iv_csv, tables_dir)
    surface = VolatilitySurface(pd.read_csv(iv_csv))
    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')

    hedge_shares = port_summary['hedge_shares']
    init_port_val = port_summary['total_portfolio_value_mkt']

    scenario_matrix_records = []
    leg_detail_records = []

    print("\n=======================================================")
    print("RUNNING FIXED-CHAIN STRESS TESTING (POINT 52)")
    print("=======================================================")

    for sc_id, sc_data in SCENARIOS.items():
        sc_name = sc_data['name']
        dt_days = sc_data['dt_days']
        dt_years = dt_days / 365.0
        dS_pct = sc_data['dS_pct']
        S1 = SPOT_PRICE * (1.0 + dS_pct)
        delta_S = S1 - SPOT_PRICE

        # For both conventions: sticky_moneyness and sticky_strike
        for convention in ['sticky_moneyness', 'sticky_strike']:
            total_options_val_new = 0.0
            taylor_options_pnl = 0.0

            for leg in PORTFOLIO_LEGS:
                sym = leg['contractSymbol']
                qty = leg['qty']
                row = df_iv.loc[sym]
                kind = row['type']
                K = float(row['strike'])
                tau0 = float(row['tau_recalc'])
                tau1 = max(tau0 - dt_years, 0.0)
                r1 = get_zero_rate(tau1) if tau1 > 0 else get_zero_rate(0.01)
                fwd1 = get_forward_price(tau1, S1) if tau1 > 0 else S1
                k0 = float(row['k_log_moneyness'])
                k1 = float(np.log(K / fwd1)) if tau1 > 0 else 0.0
                p_init = float(row['lastPrice'])

                # Compute base Greeks at t0
                base_iv = surface.surface_iv(k0, tau0)['iv']
                g = calculate_option_greeks(kind, SPOT_PRICE, K, tau0, get_zero_rate(tau0), base_iv, q=0.0)

                # Stressed volatility
                if tau1 > 1e-4:
                    stressed_iv = apply_surface_shock(
                        surface, k1, tau1,
                        sc_data['dVol_level_pp'],
                        sc_data['skew_tilt_pp'],
                        sc_data['term_tilt_pp'],
                        convention=convention,
                        k0=k0
                    )
                    p_stressed = price_american_option(kind, S1, K, tau1, r1, stressed_iv, q=0.0, method="auto")
                else:
                    # Expired option: intrinsic payoff
                    stressed_iv = 0.0
                    p_stressed = max(S1 - K, 0.0) if kind == 'C' else max(K - S1, 0.0)

                contract_scale = qty * CONTRACT_MULTIPLIER
                leg_pnl_full = contract_scale * (p_stressed - p_init)
                total_options_val_new += contract_scale * p_stressed

                # Taylor Greek Expansion for this leg:
                # Delta * dS + 0.5 * Gamma * dS^2 + Vega * dVol_1pp + Theta_daily * dt_days + Vanna * dS * dVol + 0.5 * Volga * dVol^2
                dVol_1pp = (stressed_iv - base_iv) * 100.0
                leg_taylor_unit = (
                    g['delta'] * delta_S
                    + 0.5 * g['gamma'] * (delta_S ** 2)
                    + g['vega'] * dVol_1pp
                    + g['theta_daily'] * dt_days
                    + g['vanna'] * delta_S * dVol_1pp
                    + 0.5 * g['volga'] * (dVol_1pp ** 2)
                )
                leg_pnl_taylor = contract_scale * leg_taylor_unit
                taylor_options_pnl += leg_pnl_taylor

                if convention == 'sticky_moneyness':
                    leg_detail_records.append({
                        'scenario_id': sc_id,
                        'scenario_name': sc_name,
                        'contractSymbol': sym,
                        'kind': kind,
                        'strike': K,
                        'quantity': qty,
                        'S0': SPOT_PRICE,
                        'S1': round(S1, 3),
                        'tau0_days': round(tau0 * 365, 1),
                        'tau1_days': round(tau1 * 365, 1),
                        'iv0_pct': round(base_iv * 100, 2),
                        'iv1_pct': round(stressed_iv * 100, 2),
                        'p0': p_init,
                        'p1': round(p_stressed, 4),
                        'leg_pnl_full': round(leg_pnl_full, 2),
                        'leg_pnl_taylor': round(leg_pnl_taylor, 2),
                        'discrepancy': round(leg_pnl_full - leg_pnl_taylor, 2)
                    })

            # Underlying stock position P&L
            stock_pnl = hedge_shares * delta_S
            total_port_pnl_full = (total_options_val_new - port_summary['total_options_value_mkt']) + stock_pnl
            total_port_pnl_taylor = taylor_options_pnl + stock_pnl

            scenario_matrix_records.append({
                'scenario_id': sc_id,
                'scenario_name': sc_name,
                'convention': convention,
                'dt_days': dt_days,
                'S1': round(S1, 2),
                'dS_pct': f"{dS_pct*100:+.1f}%",
                'stock_hedge_pnl': round(stock_pnl, 2),
                'options_pnl_full': round(total_options_val_new - port_summary['total_options_value_mkt'], 2),
                'total_port_pnl_full': round(total_port_pnl_full, 2),
                'total_port_pnl_taylor': round(total_port_pnl_taylor, 2),
                'taylor_discrepancy': round(total_port_pnl_full - total_port_pnl_taylor, 2),
                'return_pct_of_capital': round((total_port_pnl_full / abs(init_port_val)) * 100, 2)
            })

    sc_df = pd.DataFrame(scenario_matrix_records)
    legs_df = pd.DataFrame(leg_detail_records)

    sc_csv = out_t / "stress_test_matrix.csv"
    legs_csv = out_t / "stress_test_leg_breakdown.csv"
    sc_df.to_csv(sc_csv, index=False)
    legs_df.to_csv(legs_csv, index=False)

    print(f"Exported stress matrix: {sc_csv}")
    print(f"Exported leg breakdown: {legs_csv}")

    print("\n--- Stress Test Scenarios Results (Sticky Moneyness) ---")
    sticky_m = sc_df[sc_df['convention'] == 'sticky_moneyness']
    print(sticky_m[['scenario_name', 'S1', 'dS_pct', 'stock_hedge_pnl', 'options_pnl_full', 'total_port_pnl_full', 'total_port_pnl_taylor', 'taylor_discrepancy']].to_string())

    # Visualizations
    # 1. P&L Waterfall / Bar Plot across Scenarios
    plt.figure(figsize=(12, 6))
    x = np.arange(len(sticky_m))
    width = 0.35

    plt.bar(x - width/2, sticky_m['total_port_pnl_full'], width=width, label='Full American Revaluation (PDE)', color='#2b83ba')
    plt.bar(x + width/2, sticky_m['total_port_pnl_taylor'], width=width, label='Greek Taylor Approximation', color='#fdae61')

    plt.axhline(0, color='black', linewidth=0.8, linestyle='--')
    plt.xticks(x, [s.split('. ')[1] for s in sticky_m['scenario_name']], rotation=15, ha='right', fontsize=10)
    plt.ylabel("Portfolio Net P&L (USD)", fontsize=11)
    plt.title("Fixed-Chain Stress Testing: Full American Revaluation vs Taylor Greek Approximation", fontsize=13, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    waterfall_fig = out_f / "stress_test_pnl_waterfall.png"
    plt.savefig(waterfall_fig, dpi=300)
    plt.close()
    print(f"Saved stress test waterfall plot: {waterfall_fig}")

    # 2. Leg Contribution in Severe Crisis Scenario
    crisis_legs = legs_df[legs_df['scenario_id'] == 'S3_Severe_Crisis'].copy()
    # Add stock leg
    crisis_stock_pnl = -354 * (SPOT_PRICE * 0.8 - SPOT_PRICE) # -354 * -2.466 = +872.96
    stock_row = pd.DataFrame([{
        'scenario_id': 'S3_Severe_Crisis',
        'scenario_name': '3. Severe Crisis',
        'contractSymbol': 'NU_STOCK',
        'kind': 'STOCK',
        'strike': np.nan,
        'quantity': -354,
        'leg_pnl_full': crisis_stock_pnl
    }])
    crisis_all = pd.concat([crisis_legs, stock_row], ignore_index=True)

    plt.figure(figsize=(10, 5))
    colors = ['#d7191c' if p < 0 else '#2ca25f' for p in crisis_all['leg_pnl_full']]
    labels = [f"{r['contractSymbol']} (q={r['quantity']})" for _, r in crisis_all.iterrows()]

    plt.bar(labels, crisis_all['leg_pnl_full'], color=colors, edgecolor='black', alpha=0.85)
    plt.axhline(0, color='black', linewidth=0.8)
    plt.xticks(rotation=20, ha='right', fontsize=9)
    plt.ylabel("Net P&L (USD)", fontsize=11)
    plt.title("Scenario 3: Severe Downside Crisis (-20% Spot, +12pp Vol, Skew Spike) — P&L by Leg", fontsize=12, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()

    leg_fig = out_f / "stress_crisis_leg_breakdown.png"
    plt.savefig(leg_fig, dpi=300)
    plt.close()
    print(f"Saved crisis leg breakdown plot: {leg_fig}")

    return sc_df, legs_df

if __name__ == "__main__":
    run_stress_testing()
