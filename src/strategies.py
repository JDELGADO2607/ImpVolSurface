"""
Hypothetical Trading Strategies on NU Implied Volatility Surface (Bloque P0-D):
1. Strategy 1: Volatility Risk Premium Arbitrage (Delta-Neutral Straddle).
   - Dynamically driven by causal HAR-RV forecast vs surface/contract IV.
   - Evaluates signal (LONG, SHORT, NO_TRADE) and connects explicitly to executed simulation positions.
   - For LONG_VOLATILITY: simulates long straddle, delta hedged with stock.
   - For NO_TRADE: zero new positions, zero costs, zero P&L with explicit justification.
   - For SHORT_VOLATILITY: simulates theoretical short straddle with explicit tail risk disclaimers.
   - Calculates American Put delta via PDE engine and its own IV (not Call BS).
   - Implements entry, exit, hurdle rate thresholds (5 pp) and friction regimes.
2. Strategy 2: Term Structure Calendar Spread (Long 59d vs Short 31d at K=13.00).
   - Formulates forward implied volatility at fixed strike K=13.00.
   - Evaluates early exercise boundary, net vega exposure, and roll-down.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.market_data import SPOT_PRICE, CONTRACT_MULTIPLIER, get_zero_rate
from src.pricing_bs import bs_price, bs_greeks
from src.pricing_american_fd import price_american_option
from src.greeks import calculate_option_greeks
from src.surface import VolatilitySurface

COST_TIERS = {
    'Optimistic': {
        'half_spread_opt': 0.01, # $0.02 full bid-ask spread
        'commission_per_contract': 0.65,
        'stock_spread_bps': 2.0
    },
    'Base': {
        'half_spread_opt': 0.025, # $0.05 full bid-ask spread
        'commission_per_contract': 1.00,
        'stock_spread_bps': 5.0
    },
    'Conservative': {
        'half_spread_opt': 0.05, # $0.10 full bid-ask spread
        'commission_per_contract': 1.50,
        'stock_spread_bps': 15.0
    }
}

def generate_strategy_signal(
    forecast_vol_pct: float,
    benchmark_iv_pct: float,
    hurdle_rate_pp: float = 5.0
) -> dict[str, Any]:
    """
    Constructs actionable strategy signal based on volatility premium spread.
    Rule:
    - If spread >= +hurdle_rate_pp: LONG_VOLATILITY (e.g. Long Straddle)
    - If spread <= -hurdle_rate_pp: SHORT_VOLATILITY (e.g. Short Straddle / Iron Fly)
    - Otherwise: NO_TRADE (spread does not cover transaction costs and execution friction)
    """
    spread_pp = forecast_vol_pct - benchmark_iv_pct
    z_score = spread_pp / max(benchmark_iv_pct, 1e-4)

    if spread_pp >= hurdle_rate_pp:
        action = "LONG_VOLATILITY_STRADDLE"
        rationale = f"Forecast ({forecast_vol_pct:.2f}%) exceeds IV ({benchmark_iv_pct:.2f}%) by +{spread_pp:.2f} pp >= hurdle ({hurdle_rate_pp:.1f} pp)"
    elif spread_pp <= -hurdle_rate_pp:
        action = "SHORT_VOLATILITY_STRADDLE"
        rationale = f"Forecast ({forecast_vol_pct:.2f}%) below IV ({benchmark_iv_pct:.2f}%) by {spread_pp:.2f} pp <= -hurdle (-{hurdle_rate_pp:.1f} pp)"
    else:
        action = "NO_TRADE"
        rationale = f"Spread ({spread_pp:+.2f} pp) within friction neutral band [{-hurdle_rate_pp:.1f}, +{hurdle_rate_pp:.1f}] pp"

    return {
        'forecast_vol_pct': round(float(forecast_vol_pct), 2),
        'benchmark_iv_pct': round(float(benchmark_iv_pct), 2),
        'vol_spread_pp': round(float(spread_pp), 2),
        'z_score': round(float(z_score), 4),
        'hurdle_rate_pp': hurdle_rate_pp,
        'action': action,
        'rationale': rationale
    }

def build_straddle_portfolio_from_signal(
    signal: dict[str, Any],
    c_obs: float,
    p_obs: float,
    K: float,
    tau: float,
    r: float,
    call_contract_iv_pct: float,
    put_contract_iv_pct: float,
    S0: float = SPOT_PRICE
) -> dict[str, Any]:
    """
    Explicitly translates the strategy signal into the simulation portfolio structure:
    - LONG_VOLATILITY_STRADDLE: Long 1 Call (+1), Long 1 Put (+1), short stock delta hedge.
    - NO_TRADE: 0 Call, 0 Put, 0 Stock. Zero exposure, zero transaction costs, zero simulated P&L.
    - SHORT_VOLATILITY_STRADDLE: Short 1 Call (-1), Short 1 Put (-1), long stock delta hedge.
      (Theoretical academic simulation with explicit unbounded tail risk warning).
    """
    action = signal['action']

    # Greeks for delta neutral hedging
    g_c = bs_greeks('C', S0, K, tau, r, call_contract_iv_pct / 100.0)
    g_p = calculate_option_greeks('P', S0, K, tau, r, put_contract_iv_pct / 100.0, is_american=True)
    net_option_delta_unit = g_c['delta'] + g_p['delta']

    if action == "LONG_VOLATILITY_STRADDLE":
        call_contracts = 1.0
        put_contracts = 1.0
        hedge_shares = -int(np.round(net_option_delta_unit * CONTRACT_MULTIPLIER))
        premium_direction = -1.0 # cash outflow (debit)
        initial_premium_cash = (c_obs + p_obs) * CONTRACT_MULTIPLIER
        risk_profile = "DEFINED_RISK_LONG_PREMIUM"
        description = "Long Delta-Neutral Straddle (1 Call + 1 Put + Stock Delta Hedge)"

    elif action == "SHORT_VOLATILITY_STRADDLE":
        call_contracts = -1.0
        put_contracts = -1.0
        hedge_shares = int(np.round(net_option_delta_unit * CONTRACT_MULTIPLIER))
        premium_direction = +1.0 # cash inflow (credit)
        initial_premium_cash = (c_obs + p_obs) * CONTRACT_MULTIPLIER
        risk_profile = "THEORETICAL_SHORT_STRADDLE_UNBOUNDED_TAIL_RISK"
        description = "Short Delta-Neutral Straddle (-1 Call - 1 Put + Reverse Stock Delta Hedge)"

    else: # NO_TRADE
        call_contracts = 0.0
        put_contracts = 0.0
        hedge_shares = 0
        premium_direction = 0.0
        initial_premium_cash = 0.0
        risk_profile = "ZERO_EXPOSURE_NO_TRADE"
        description = "No Position Opened (Forecast inside friction hurdle band)"

    return {
        'action': action,
        'call_contracts': call_contracts,
        'put_contracts': put_contracts,
        'hedge_shares': hedge_shares,
        'premium_direction': premium_direction,
        'initial_premium_cash': initial_premium_cash,
        'net_option_delta_unit': net_option_delta_unit,
        'call_delta': g_c['delta'],
        'put_delta': g_p['delta'],
        'risk_profile': risk_profile,
        'description': description
    }

def analyze_strategy_1_straddle(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    forecast_vol_pct: float | None = None,
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Evaluates Strategy 1: Delta-Neutral Straddle on 31-day expiration (2026-12-18, Strike 12.00).
    Dynamically passes the causal HAR-RV forecast, generates explicit signal,
    and connects the signal directly to the simulated portfolio positions.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    # Resolve causal forecast if not explicitly passed
    if forecast_vol_pct is None:
        eval_csv = out_t / "volatility_forecast_evaluation.csv"
        if eval_csv.exists():
            from src.forecasts import run_forecast_pipeline
            _, forecast_vol_pct = run_forecast_pipeline()
        else:
            from src.forecasts import run_forecast_pipeline
            _, forecast_vol_pct = run_forecast_pipeline()

    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')
    surface = VolatilitySurface(pd.read_csv(iv_csv))

    call_sym = 'NU261218C00012000'
    put_sym = 'NU261218P00012000'

    c_obs = float(df_iv.loc[call_sym, 'lastPrice']) # 0.86
    p_obs = float(df_iv.loc[put_sym, 'lastPrice']) # 0.47
    K = 12.0
    tau = float(df_iv.loc[call_sym, 'tau_recalc'])
    r = get_zero_rate(tau)

    # Volatilities:
    # 1. Surface ATM volatility at k=0 (for 31d):
    atm_surface_iv_pct = float(surface.surface_iv(0.0, tau)['iv'] * 100.0) # ~44.02%
    # 2. Specific contract IVs:
    call_contract_iv_pct = float(df_iv.loc[call_sym, 'our_iv_pct']) # ~46.61%
    put_contract_iv_pct = float(df_iv.loc[put_sym, 'our_iv_pct'])   # ~45.20%
    blended_straddle_iv_pct = 0.5 * (call_contract_iv_pct + put_contract_iv_pct) # ~45.91%

    # Generate Signal
    signal = generate_strategy_signal(forecast_vol_pct, blended_straddle_iv_pct, hurdle_rate_pp=5.0)

    # Build Portfolio Positions based on Signal
    portfolio = build_straddle_portfolio_from_signal(
        signal=signal,
        c_obs=c_obs,
        p_obs=p_obs,
        K=K,
        tau=tau,
        r=r,
        call_contract_iv_pct=call_contract_iv_pct,
        put_contract_iv_pct=put_contract_iv_pct,
        S0=SPOT_PRICE
    )

    print("\n--- Strategy 1: Straddle Setup & Signal-Linked Execution ---")
    print(f"Call K={K}: IV = {call_contract_iv_pct:.2f}%, Delta = {portfolio['call_delta']:.4f}, Price = ${c_obs:.2f}")
    print(f"Put  K={K}: IV = {put_contract_iv_pct:.2f}%, Delta = {portfolio['put_delta']:.4f}, Price = ${p_obs:.2f}")
    print(f"Surface ATM IV (k=0): {atm_surface_iv_pct:.2f}% | Blended Straddle IV: {blended_straddle_iv_pct:.2f}%")
    print(f"Causal HAR-RV Forecast: {forecast_vol_pct:.2f}% -> Signal: {signal['action']} (Spread: {signal['vol_spread_pp']:+.2f} pp)")
    print(f"Execution Strategy: {portfolio['description']}")
    print(f"Simulated Position: {portfolio['call_contracts']} Calls, {portfolio['put_contracts']} Puts, {portfolio['hedge_shares']} Stock Shares")
    print(f"Initial Cashflow: ${portfolio['premium_direction'] * portfolio['initial_premium_cash']:.2f} USD | Risk Profile: {portfolio['risk_profile']}")

    # Scenario spot shocks at maturity (tau = 0)
    spot_shocks_pct = np.array([-0.25, -0.15, -0.075, 0.0, 0.075, 0.15, 0.25])
    S_T_vals = SPOT_PRICE * (1.0 + spot_shocks_pct)

    records = []
    for cost_name, costs in COST_TIERS.items():
        if portfolio['action'] == "NO_TRADE":
            spread_friction = 0.0
            comm_friction = 0.0
            stock_friction = 0.0
            total_entry_friction = 0.0
        else:
            spread_friction = 2.0 * costs['half_spread_opt'] * CONTRACT_MULTIPLIER
            comm_friction = 2.0 * costs['commission_per_contract']
            stock_friction = abs(portfolio['hedge_shares']) * SPOT_PRICE * (costs['stock_spread_bps'] / 10000.0)
            total_entry_friction = spread_friction + comm_friction + stock_friction

        for s_pct, S_T in zip(spot_shocks_pct, S_T_vals):
            if portfolio['action'] == "NO_TRADE":
                call_payoff = 0.0
                put_payoff = 0.0
                options_payoff = 0.0
                stock_pnl = 0.0
                gross_pnl = 0.0
                net_pnl = 0.0
                ret_pct = 0.0
            elif portfolio['action'] == "LONG_VOLATILITY_STRADDLE":
                call_payoff = max(S_T - K, 0.0) * CONTRACT_MULTIPLIER
                put_payoff = max(K - S_T, 0.0) * CONTRACT_MULTIPLIER
                options_payoff = call_payoff + put_payoff
                stock_pnl = portfolio['hedge_shares'] * (S_T - SPOT_PRICE)
                gross_pnl = (options_payoff - portfolio['initial_premium_cash']) + stock_pnl
                net_pnl = gross_pnl - total_entry_friction
                ret_pct = (net_pnl / portfolio['initial_premium_cash']) * 100.0
            else: # SHORT_VOLATILITY_STRADDLE
                call_liability = -max(S_T - K, 0.0) * CONTRACT_MULTIPLIER
                put_liability = -max(K - S_T, 0.0) * CONTRACT_MULTIPLIER
                options_payoff = call_liability + put_liability
                stock_pnl = portfolio['hedge_shares'] * (S_T - SPOT_PRICE)
                gross_pnl = (portfolio['initial_premium_cash'] + options_payoff) + stock_pnl
                net_pnl = gross_pnl - total_entry_friction
                ret_pct = (net_pnl / portfolio['initial_premium_cash']) * 100.0

            records.append({
                'Signal_Action': portfolio['action'],
                'Cost_Regime': cost_name,
                'Spot_Shock': f"{s_pct*100:+.1f}%",
                'Terminal_Spot': round(S_T, 2),
                'Options_Payoff': round(options_payoff, 2),
                'Stock_Hedge_PnL': round(stock_pnl, 2),
                'Gross_PnL': round(gross_pnl, 2),
                'Friction_Cost': round(total_entry_friction, 2),
                'Net_PnL': round(net_pnl, 2),
                'Return_on_Premium_pct': round(ret_pct, 2)
            })

    strat1_df = pd.DataFrame(records)
    out_csv = out_t / "strategy1_straddle_scenarios.csv"
    strat1_df.to_csv(out_csv, index=False)
    print(f"Exported Strategy 1 scenarios: {out_csv}")

    # Plot Strategy 1 Payoff Curves
    plt.figure(figsize=(10, 6))
    dense_spots = np.linspace(8.0, 16.0, 120)

    for cost_name in COST_TIERS.keys():
        sub_c = COST_TIERS[cost_name]
        if portfolio['action'] == "NO_TRADE":
            fric = 0.0
            net_curve = [0.0 for _ in dense_spots]
            lbl = f"Cost Regime: {cost_name} (NO_TRADE: P&L = $0.00)"
        elif portfolio['action'] == "LONG_VOLATILITY_STRADDLE":
            fric = (2.0 * sub_c['half_spread_opt'] * CONTRACT_MULTIPLIER
                    + 2.0 * sub_c['commission_per_contract']
                    + abs(portfolio['hedge_shares']) * SPOT_PRICE * (sub_c['stock_spread_bps'] / 10000.0))
            net_curve = []
            for st in dense_spots:
                c_p = max(st - K, 0.0) * CONTRACT_MULTIPLIER
                p_p = max(K - st, 0.0) * CONTRACT_MULTIPLIER
                stk_pnl = portfolio['hedge_shares'] * (st - SPOT_PRICE)
                pnl = (c_p + p_p - portfolio['initial_premium_cash']) + stk_pnl - fric
                net_curve.append(pnl)
            lbl = f"Cost Regime: {cost_name} (Fric = ${fric:.2f})"
        else: # SHORT_VOLATILITY_STRADDLE
            fric = (2.0 * sub_c['half_spread_opt'] * CONTRACT_MULTIPLIER
                    + 2.0 * sub_c['commission_per_contract']
                    + abs(portfolio['hedge_shares']) * SPOT_PRICE * (sub_c['stock_spread_bps'] / 10000.0))
            net_curve = []
            for st in dense_spots:
                c_liab = -max(st - K, 0.0) * CONTRACT_MULTIPLIER
                p_liab = -max(K - st, 0.0) * CONTRACT_MULTIPLIER
                stk_pnl = portfolio['hedge_shares'] * (st - SPOT_PRICE)
                pnl = (portfolio['initial_premium_cash'] + c_liab + p_liab) + stk_pnl - fric
                net_curve.append(pnl)
            lbl = f"Cost Regime: {cost_name} (Short Straddle, Fric = ${fric:.2f})"

        plt.plot(dense_spots, net_curve, label=lbl, linewidth=2)

    plt.axhline(0, color='black', linewidth=0.8, linestyle='--')
    plt.axvline(SPOT_PRICE, color='gray', linestyle=':', label=f"Spot $S_0={SPOT_PRICE:.2f}$")
    plt.axvline(K, color='purple', linestyle='-.', alpha=0.7, label=f"Strike $K={K:.2f}$")
    plt.xlabel("Terminal Stock Price $S_T$ (USD)", fontsize=11)
    plt.ylabel("Net P&L per Straddle Contract (USD)", fontsize=11)

    title_str = (
        f"Strategy 1: {portfolio['action']} at Maturity "
        f"(Hedge = {portfolio['hedge_shares']} shares | Signal Spread = {signal['vol_spread_pp']:+.2f} pp)"
    )
    plt.title(title_str, fontsize=11, fontweight='bold')
    plt.legend(fontsize=9)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()

    fig_path = out_f / "strategy1_payoff_scenarios.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved Strategy 1 plot: {fig_path}")

    return strat1_df, signal

def analyze_strategy_2_calendar_spread(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> pd.DataFrame:
    """
    Evaluates Strategy 2: Calendar Spread (Long Call 59d vs Short Call 31d at Strike K=13.00).
    Formulates forward implied volatility at fixed strike K=13.00.
    Evaluates Vega asymmetry, early exercise safety (Merton theorem q=0), and roll-down.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')
    surface = VolatilitySurface(pd.read_csv(iv_csv))

    sym_short = 'NU261218C00013000'
    sym_long = 'NU270115C00013000'

    p_short_init = float(df_iv.loc[sym_short, 'lastPrice']) # 0.41
    p_long_init = float(df_iv.loc[sym_long, 'lastPrice'])   # 0.60
    tau1 = float(df_iv.loc[sym_short, 'tau_recalc'])
    tau2 = float(df_iv.loc[sym_long, 'tau_recalc'])
    iv1 = float(df_iv.loc[sym_short, 'our_iv_decimal'])
    iv2 = float(df_iv.loc[sym_long, 'our_iv_decimal'])
    r1 = get_zero_rate(tau1)
    r2 = get_zero_rate(tau2)

    net_debit_per_spread = p_long_init - p_short_init # $0.19
    n_contracts = 5
    total_debit = net_debit_per_spread * n_contracts * CONTRACT_MULTIPLIER # $95.00

    # Greeks
    g1 = bs_greeks('C', SPOT_PRICE, 13.00, tau1, r1, iv1)
    g2 = bs_greeks('C', SPOT_PRICE, 13.00, tau2, r2, iv2)

    net_delta = n_contracts * CONTRACT_MULTIPLIER * (g2['delta'] - g1['delta'])
    net_gamma = n_contracts * CONTRACT_MULTIPLIER * (g2['gamma'] - g1['gamma'])
    net_vega = n_contracts * CONTRACT_MULTIPLIER * (g2['vega'] - g1['vega'])
    net_theta = n_contracts * CONTRACT_MULTIPLIER * (g2['theta_daily'] - g1['theta_daily'])

    # Forward Implied Volatility:
    w1 = (iv1 ** 2) * tau1
    w2 = (iv2 ** 2) * tau2
    fwd_var = max((w2 - w1) / (tau2 - tau1), 1e-6)
    fwd_iv = np.sqrt(fwd_var)

    print("\n--- Strategy 2: Calendar Spread Setup (K=13.00) ---")
    print(f"Front Call (31d): Price = ${p_short_init:.2f}, IV = {iv1*100:.2f}%, Vega = {g1['vega']:.4f}")
    print(f"Back Call  (59d): Price = ${p_long_init:.2f}, IV = {iv2*100:.2f}%, Vega = {g2['vega']:.4f}")
    print(f"Forward Implied Volatility sigma(31d, 59d): {fwd_iv*100:.2f}%")
    print(f"Position: Long 5 Spreads | Net Debit = ${total_debit:.2f} USD")
    print(f"Net Portfolio Greeks: Delta={net_delta:.2f}, Gamma={net_gamma:.2f}, Vega=+${net_vega:.2f}/pp, Theta=${net_theta:.2f}/day")

    # Evaluation at front maturity (Day 31): tau_rem = 28/365
    tau_rem = tau2 - tau1
    r_rem = get_zero_rate(tau_rem)
    spot_range = np.array([-0.15, -0.075, 0.0, 0.054, 0.075, 0.15]) # 0.054 is ATM at K=13.00
    S_31_vals = SPOT_PRICE * (1.0 + spot_range)

    records = []
    for cost_name, costs in COST_TIERS.items():
        friction = (2.0 * n_contracts * CONTRACT_MULTIPLIER * costs['half_spread_opt']
                    + 2.0 * n_contracts * costs['commission_per_contract'])

        for s_pct, S_31 in zip(spot_range, S_31_vals):
            short_payoff = max(S_31 - 13.00, 0.0)
            short_pnl = -n_contracts * CONTRACT_MULTIPLIER * (short_payoff - p_short_init)

            # Revalue remaining back option at Day 31
            k_rem = float(np.log(13.00 / (S_31 * np.exp(r_rem * tau_rem))))
            iv_rem = surface.surface_iv(k_rem, tau_rem)['iv']
            long_val_rem = price_american_option('C', S_31, 13.00, tau_rem, r_rem, iv_rem, q=0.0)
            long_pnl = n_contracts * CONTRACT_MULTIPLIER * (long_val_rem - p_long_init)

            gross_pnl = short_pnl + long_pnl
            net_pnl = gross_pnl - friction

            records.append({
                'Cost_Regime': cost_name,
                'Spot_Move': f"{s_pct*100:+.1f}%",
                'Spot_Day_31': round(S_31, 2),
                'Front_Payoff_USD': round(-short_payoff * n_contracts * CONTRACT_MULTIPLIER, 2),
                'Back_Option_Value_USD': round(long_val_rem * n_contracts * CONTRACT_MULTIPLIER, 2),
                'Gross_PnL_USD': round(gross_pnl, 2),
                'Friction_Cost_USD': round(friction, 2),
                'Net_PnL_USD': round(net_pnl, 2),
                'Return_on_Debit_pct': round((net_pnl / total_debit) * 100, 2)
            })

    strat2_df = pd.DataFrame(records)
    out_csv = out_t / "strategy2_calendar_scenarios.csv"
    strat2_df.to_csv(out_csv, index=False)
    print(f"Exported Strategy 2 scenarios: {out_csv}")

    # Plot Strategy 2 Payoff Curve at Day 31
    plt.figure(figsize=(10, 6))
    dense_spots = np.linspace(10.0, 15.5, 100)
    for cost_name in COST_TIERS.keys():
        sub_c = COST_TIERS[cost_name]
        fric = (2.0 * n_contracts * CONTRACT_MULTIPLIER * sub_c['half_spread_opt']
                + 2.0 * n_contracts * sub_c['commission_per_contract'])
        curve = []
        for st in dense_spots:
            sh_p = -n_contracts * CONTRACT_MULTIPLIER * (max(st - 13.0, 0.0) - p_short_init)
            k_r = float(np.log(13.0 / (st * np.exp(r_rem * tau_rem))))
            iv_r = surface.surface_iv(k_r, tau_rem)['iv']
            lg_val = price_american_option('C', st, 13.0, tau_rem, r_rem, iv_r, q=0.0)
            lg_p = n_contracts * CONTRACT_MULTIPLIER * (lg_val - p_long_init)
            curve.append((sh_p + lg_p) - fric)
        plt.plot(dense_spots, curve, label=f"Cost Regime: {cost_name}", linewidth=2)

    plt.axhline(0, color='black', linewidth=0.8, linestyle='--')
    plt.axvline(13.00, color='purple', linestyle='-.', label='Calendar Strike K=13.00')
    plt.axvline(SPOT_PRICE, color='gray', linestyle=':', label=f'Current Spot $S_0={SPOT_PRICE:.2f}$')
    plt.xlabel("Stock Price at Day 31 $S_{31}$ (USD)", fontsize=11)
    plt.ylabel("Net P&L of 5 Calendar Spreads (USD)", fontsize=11)
    plt.title("Strategy 2: Calendar Spread (Long 59d / Short 31d at K=13.00) Payoff at Day 31", fontsize=12, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()

    fig_path = out_f / "strategy2_calendar_payoff.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved Strategy 2 plot: {fig_path}")

    return strat2_df

def run_strategies_analysis():
    strat1_df, signal = analyze_strategy_1_straddle()
    strat2_df = analyze_strategy_2_calendar_spread()
    return strat1_df, strat2_df

if __name__ == "__main__":
    run_strategies_analysis()
