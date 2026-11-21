"""
Fixed-Chain Stress Testing Engine (Punto 52):
Maintains fixed contract symbols and strikes, updates residual maturity tau and moneyness k,
models multi-factor surface deformations (Level, Skew, Curvature, Term Slope),
executes full American PDE revaluation, and contrasts against Taylor Greek expansions.
Separates initial mark-to-model differences from pure stress P&L and validates null shock.
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
    'S0_Null_Shock': {
        'name': '0. Baseline Null Shock (Diagnostic)',
        'dt_days': 0.0,
        'dS_pct': 0.0,
        'dVol_level_pp': 0.0,
        'skew_tilt_pp': 0.0,
        'term_tilt_pp': 0.0,
        'curvature_tilt_pp': 0.0,
        'description': 'Zero shock diagnostic scenario (dS=0, dt=0, dVol=0) verifying zero stress P&L.'
    },
    'S1_RollDown_10d': {
        'name': '1. Pure Roll-Down (Time Decay)',
        'dt_days': 10.0,
        'dS_pct': 0.0,
        'dVol_level_pp': 0.0,
        'skew_tilt_pp': 0.0,
        'term_tilt_pp': 0.0,
        'curvature_tilt_pp': 0.0,
        'description': '10 days forward time decay with unchanged spot and invariant surface.'
    },
    'S2_Parallel_Drop': {
        'name': '2. Parallel Drop & Vol Spike',
        'dt_days': 5.0,
        'dS_pct': -0.10,
        'dVol_level_pp': 10.0,
        'skew_tilt_pp': 0.0,
        'term_tilt_pp': 0.0,
        'curvature_tilt_pp': 0.0,
        'description': 'Spot -10%, parallel surface jump +10 pp after 5 days.'
    },
    'S3_Severe_Crisis': {
        'name': '3. Severe Crisis & Skew Steepening',
        'dt_days': 5.0,
        'dS_pct': -0.20,
        'dVol_level_pp': 12.0,
        'skew_tilt_pp': 8.0,
        'term_tilt_pp': 10.0,
        'curvature_tilt_pp': 4.0,
        'description': 'Spot -20%, level +12 pp, put skew +8 pp, short-term tilt +10 pp, wing curvature +4 pp.'
    },
    'S4_Bullish_Rally': {
        'name': '4. Bullish Rally & Vol Crush',
        'dt_days': 3.0,
        'dS_pct': 0.15,
        'dVol_level_pp': -8.0,
        'skew_tilt_pp': -2.0,
        'term_tilt_pp': -5.0,
        'curvature_tilt_pp': -1.0,
        'description': 'Spot +15%, level crush -8 pp, short-tenor crush -5 pp after 3 days.'
    },
    'S5_Short_Tenor_Inversion': {
        'name': '5. Short-Tenor Inversion Shock',
        'dt_days': 2.0,
        'dS_pct': -0.05,
        'dVol_level_pp': 2.0,
        'skew_tilt_pp': 4.0,
        'term_tilt_pp': 15.0,
        'curvature_tilt_pp': 2.0,
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
    curvature_tilt_pp: float = 0.0,
    convention: str = "sticky_moneyness",
    k0: float = 0.0
) -> float:
    """
    Deforms implied volatility according to multi-factor shocks:
    Level, Skew, Term Slope, and Curvature (wing convexity).
    Enforces minimum volatility floor of 10.0% (0.10).
    """
    if convention == "sticky_strike":
        base_iv = base_surface.surface_iv(k0, max(tau1, 1e-4))['iv']
    else:
        base_iv = base_surface.surface_iv(k1, max(tau1, 1e-4))['iv']

    # 1. Level shock
    shock_pp = dVol_level_pp

    # 2. Skew tilt: increases volatility for out-of-the-money puts (k1 < 0)
    if k1 < 0.0:
        shock_pp += skew_tilt_pp * min(abs(k1) / 0.20, 2.0)
    else:
        shock_pp += 0.5 * skew_tilt_pp * (k1 / 0.20)

    # 3. Term structure tilt: shock decays exponentially with maturity tau
    term_factor = np.exp(-tau1 / 0.30)
    shock_pp += term_tilt_pp * term_factor

    # 4. Curvature tilt: quadratic wing elevation centered at ATM (k1 = 0)
    if curvature_tilt_pp != 0.0:
        shock_pp += curvature_tilt_pp * ((k1 / 0.20) ** 2)

    stressed_iv = base_iv + (shock_pp / 100.0)
    return float(max(stressed_iv, 0.10))

def run_stress_testing(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes fixed-chain stress testing across all scenarios with exact
    separation of mark-to-model differences and pure stress P&L.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    # Load portfolio and baseline
    port_df, port_summary = build_hypothetical_portfolio(iv_csv, tables_dir)
    surface = VolatilitySurface(pd.read_csv(iv_csv))
    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')

    hedge_shares = int(port_summary['hedge_shares'])
    m2m_options_initial = float(port_summary['total_options_value_mod'] - port_summary['total_options_value_mkt'])

    # Economic Margin Capital Requirement estimation:
    # Option premium paid + short margin (20% underlying spot) + 50% short stock margin
    stock_margin = abs(hedge_shares) * SPOT_PRICE * 0.50
    short_opt_margin = (5 * 100 * (0.16 + 0.20 * SPOT_PRICE)) + (4 * 100 * (0.31 + 0.20 * SPOT_PRICE))
    long_opt_outlay = (5 * 100 * 0.86) + (3 * 100 * 0.47) + (4 * 100 * 0.60)
    economic_margin_capital = float(long_opt_outlay + short_opt_margin + stock_margin)

    scenario_matrix_records = []
    leg_detail_records = []

    print("\n=======================================================")
    print("RUNNING FIXED-CHAIN STRESS TESTING (POINT 52 — REPAIRED)")
    print("=======================================================")

    for sc_id, sc_data in SCENARIOS.items():
        sc_name = sc_data['name']
        dt_days = sc_data['dt_days']
        dt_years = dt_days / 365.0
        dS_pct = sc_data['dS_pct']
        S1 = SPOT_PRICE * (1.0 + dS_pct)
        delta_S = S1 - SPOT_PRICE
        stock_pnl = hedge_shares * delta_S

        for convention in ['sticky_moneyness', 'sticky_strike']:
            total_options_pnl_mod = 0.0
            total_options_pnl_mkt = 0.0
            total_options_pnl_taylor = 0.0

            for leg in PORTFOLIO_LEGS:
                sym = leg['contractSymbol']
                qty = leg['qty']
                row = df_iv.loc[sym]
                kind = row['type']
                K = float(row['strike'])
                tau0 = float(row['tau_recalc'])
                tau1 = max(tau0 - dt_years, 0.0)
                r0 = get_zero_rate(tau0)
                r1 = get_zero_rate(tau1) if tau1 > 0 else get_zero_rate(0.01)
                fwd0 = get_forward_price(tau0, SPOT_PRICE)
                fwd1 = get_forward_price(tau1, S1) if tau1 > 0 else S1
                k0 = float(row['k_log_moneyness'])
                k1 = float(np.log(K / fwd1)) if tau1 > 0 else 0.0
                p_mkt_init = float(row['lastPrice'])

                # Base model price at t0
                base_iv = surface.surface_iv(k0, tau0)['iv']
                p0_mod = price_american_option(kind, SPOT_PRICE, K, tau0, r0, base_iv, q=0.0, method="auto")

                # Greeks at t0 on the model base
                g = calculate_option_greeks(kind, SPOT_PRICE, K, tau0, r0, base_iv, q=0.0, is_american=True)

                # Stressed volatility and model price at t1
                if tau1 > 1e-4:
                    stressed_iv = apply_surface_shock(
                        surface, k1, tau1,
                        sc_data['dVol_level_pp'],
                        sc_data['skew_tilt_pp'],
                        sc_data['term_tilt_pp'],
                        curvature_tilt_pp=sc_data.get('curvature_tilt_pp', 0.0),
                        convention=convention,
                        k0=k0
                    )
                    p1_mod = price_american_option(kind, S1, K, tau1, r1, stressed_iv, q=0.0, method="auto")
                else:
                    # Expired option: intrinsic payoff
                    stressed_iv = 0.0
                    p1_mod = max(S1 - K, 0.0) if kind == 'C' else max(K - S1, 0.0)

                contract_scale = qty * CONTRACT_MULTIPLIER

                # P&L components
                leg_pnl_stress_mod = contract_scale * (p1_mod - p0_mod)
                leg_mark_to_model = contract_scale * (p0_mod - p_mkt_init)
                leg_pnl_mkt_base = contract_scale * (p1_mod - p_mkt_init)

                # Taylor expansion on model Greeks
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

                total_options_pnl_mod += leg_pnl_stress_mod
                total_options_pnl_mkt += leg_pnl_mkt_base
                total_options_pnl_taylor += leg_pnl_taylor

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
                        'p0_mkt': p_mkt_init,
                        'p0_mod': round(p0_mod, 4),
                        'p1_mod': round(p1_mod, 4),
                        'leg_mark_to_model': round(leg_mark_to_model, 2),
                        'leg_pnl_stress_mod': round(leg_pnl_stress_mod, 2),
                        'leg_pnl_mkt_base': round(leg_pnl_mkt_base, 2),
                        'leg_pnl_taylor': round(leg_pnl_taylor, 2),
                        'discrepancy': round(leg_pnl_stress_mod - leg_pnl_taylor, 2)
                    })

            total_port_pnl_stress_mod = total_options_pnl_mod + stock_pnl
            total_port_pnl_mkt_base = total_options_pnl_mkt + stock_pnl
            total_port_pnl_taylor = total_options_pnl_taylor + stock_pnl
            discrepancy = total_port_pnl_stress_mod - total_port_pnl_taylor

            scenario_matrix_records.append({
                'scenario_id': sc_id,
                'scenario_name': sc_name,
                'convention': convention,
                'dt_days': dt_days,
                'S1': round(S1, 2),
                'dS_pct': f"{dS_pct*100:+.1f}%",
                'hedge_shares': hedge_shares,
                'stock_hedge_pnl': round(stock_pnl, 2),
                'options_pnl_stress_mod': round(total_options_pnl_mod, 2),
                'total_port_pnl_stress_mod': round(total_port_pnl_stress_mod, 2),
                'options_pnl_taylor': round(total_options_pnl_taylor, 2),
                'total_port_pnl_taylor': round(total_port_pnl_taylor, 2),
                'taylor_discrepancy': round(discrepancy, 2),
                'mark_to_model_diff_initial': round(m2m_options_initial, 2),
                'total_port_pnl_mkt_base': round(total_port_pnl_mkt_base, 2),
                'economic_margin_capital': round(economic_margin_capital, 2),
                'return_on_margin_pct': round((total_port_pnl_stress_mod / economic_margin_capital) * 100, 2)
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
    print(sticky_m[['scenario_name', 'S1', 'dS_pct', 'stock_hedge_pnl', 'options_pnl_stress_mod', 'total_port_pnl_stress_mod', 'total_port_pnl_taylor', 'taylor_discrepancy', 'total_port_pnl_mkt_base']].to_string())

    # Visualizations
    # 1. P&L Waterfall / Bar Plot across Scenarios
    plt.figure(figsize=(12, 6))
    x = np.arange(len(sticky_m))
    width = 0.35

    plt.bar(x - width/2, sticky_m['total_port_pnl_stress_mod'], width=width, label='Full American Revaluation (PDE Model P&L)', color='#2b83ba')
    plt.bar(x + width/2, sticky_m['total_port_pnl_taylor'], width=width, label='Greek Taylor Approximation', color='#fdae61')

    plt.axhline(0, color='black', linewidth=0.8, linestyle='--')
    plt.xticks(x, [s.split('. ')[1] for s in sticky_m['scenario_name']], rotation=15, ha='right', fontsize=9)
    plt.ylabel("Portfolio Net Stress P&L (USD)", fontsize=11)
    plt.title("Fixed-Chain Stress Testing: Full American Revaluation vs Taylor Greek Approximation", fontsize=12, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    waterfall_fig = out_f / "stress_test_pnl_waterfall.png"
    plt.savefig(waterfall_fig, dpi=300)
    plt.close()
    print(f"Saved stress test waterfall plot: {waterfall_fig}")

    # 2. Leg Contribution in Severe Crisis Scenario (Using dynamic hedge shares from portfolio)
    crisis_legs = legs_df[legs_df['scenario_id'] == 'S3_Severe_Crisis'].copy()
    crisis_delta_S = SPOT_PRICE * (-0.20)
    crisis_stock_pnl = hedge_shares * crisis_delta_S

    stock_row = pd.DataFrame([{
        'scenario_id': 'S3_Severe_Crisis',
        'scenario_name': '3. Severe Crisis & Skew Steepening',
        'contractSymbol': 'NU_STOCK',
        'kind': 'STOCK',
        'strike': np.nan,
        'quantity': hedge_shares,
        'leg_pnl_stress_mod': round(crisis_stock_pnl, 2)
    }])
    crisis_all = pd.concat([crisis_legs, stock_row], ignore_index=True)

    plt.figure(figsize=(10, 5))
    colors = ['#d7191c' if p < 0 else '#2ca25f' for p in crisis_all['leg_pnl_stress_mod']]
    labels = [f"{r['contractSymbol']} (q={r['quantity']})" for _, r in crisis_all.iterrows()]

    plt.bar(labels, crisis_all['leg_pnl_stress_mod'], color=colors, edgecolor='black', alpha=0.85)
    plt.axhline(0, color='black', linewidth=0.8)
    plt.xticks(rotation=20, ha='right', fontsize=9)
    plt.ylabel("Net Stress P&L (USD)", fontsize=11)
    plt.title(f"Scenario 3: Severe Downside Crisis (-20% Spot, +12pp Vol, Skew Spike) — P&L by Leg ({hedge_shares} shares)", fontsize=11, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()

    leg_fig = out_f / "stress_crisis_leg_breakdown.png"
    plt.savefig(leg_fig, dpi=300)
    plt.close()
    print(f"Saved crisis leg breakdown plot: {leg_fig}")

    return sc_df, legs_df

if __name__ == "__main__":
    run_stress_testing()
