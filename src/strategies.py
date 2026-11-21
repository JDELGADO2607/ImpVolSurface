"""
Hypothetical Trading Strategies on NU Implied Volatility Surface (Punto 53):
1. Strategy 1: Conditional Volatility Premium (Delta-Neutral Straddle on RV Forecast vs ATM IV).
2. Strategy 2: Term Structure Calendar Spread exploiting Forward Implied Volatility.
Includes explicit transaction cost tiers and academic risk disclosures.
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

from src.market_data import SPOT_PRICE, CONTRACT_MULTIPLIER, get_zero_rate
from src.pricing_bs import bs_price, bs_greeks
from src.pricing_american_fd import price_american_option
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

def analyze_strategy_1_straddle(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    forecast_vol_pct: float = 72.97,
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> pd.DataFrame:
    """
    Evaluates Strategy 1: Long ATM Straddle on 31-day expiration (2026-12-18, Strike 12.00).
    Signal: Forecast Vol (72.97%) > ATM IV (44.02%) -> z = +0.505 > 0.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)

    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')
    call_sym = 'NU261218C00012000'
    put_sym = 'NU261218P00012000'

    c_obs = float(df_iv.loc[call_sym, 'lastPrice']) # 0.86
    p_obs = float(df_iv.loc[put_sym, 'lastPrice']) # 0.47
    K = 12.0
    tau = float(df_iv.loc[call_sym, 'tau_recalc'])
    r = get_zero_rate(tau)
    atm_iv = float(df_iv.loc[call_sym, 'our_iv_pct'])

    # Greeks for delta hedge
    g_c = bs_greeks('C', SPOT_PRICE, K, tau, r, atm_iv / 100.0)
    g_p = bs_greeks('P', SPOT_PRICE, K, tau, r, atm_iv / 100.0)
    net_delta_unit = g_c['delta'] + g_p['delta']
    hedge_shares = -int(np.round(net_delta_unit * CONTRACT_MULTIPLIER))

    # Scenario spot shocks at maturity (tau = 0)
    spot_shocks_pct = np.array([-0.25, -0.15, -0.075, 0.0, 0.075, 0.15, 0.25])
    S_T_vals = SPOT_PRICE * (1.0 + spot_shocks_pct)

    records = []
    for cost_name, costs in COST_TIERS.items():
        # Cost of establishing 1 straddle (1 Call + 1 Put) + stock hedge
        # Spread friction: 2 options * half_spread * 100
        spread_friction = 2.0 * costs['half_spread_opt'] * CONTRACT_MULTIPLIER
        comm_friction = 2.0 * costs['commission_per_contract']
        stock_friction = abs(hedge_shares) * SPOT_PRICE * (costs['stock_spread_bps'] / 10000.0)
        total_entry_friction = spread_friction + comm_friction + stock_friction

        premium_paid = (c_obs + p_obs) * CONTRACT_MULTIPLIER
        stock_outlay = hedge_shares * SPOT_PRICE

        for s_pct, S_T in zip(spot_shocks_pct, S_T_vals):
            # Terminal payoffs
            call_payoff = max(S_T - K, 0.0) * CONTRACT_MULTIPLIER
            put_payoff = max(K - S_T, 0.0) * CONTRACT_MULTIPLIER
            options_payoff = call_payoff + put_payoff
            stock_pnl = hedge_shares * (S_T - SPOT_PRICE)

            gross_pnl = (options_payoff - premium_paid) + stock_pnl
            net_pnl = gross_pnl - total_entry_friction

            records.append({
                'Cost_Regime': cost_name,
                'Spot_Shock': f"{s_pct*100:+.1f}%",
                'Terminal_Spot': round(S_T, 2),
                'Options_Payoff': round(options_payoff, 2),
                'Stock_Hedge_PnL': round(stock_pnl, 2),
                'Gross_PnL': round(gross_pnl, 2),
                'Friction_Cost': round(total_entry_friction, 2),
                'Net_PnL': round(net_pnl, 2),
                'Return_on_Premium_pct': round((net_pnl / premium_paid) * 100, 2)
            })

    strat1_df = pd.DataFrame(records)
    out_csv = out_t / "strategy1_straddle_scenarios.csv"
    strat1_df.to_csv(out_csv, index=False)
    print(f"Exported Strategy 1 scenarios: {out_csv}")

    # Plot Strategy 1 Payoff Curves
    plt.figure(figsize=(10, 6))
    dense_spots = np.linspace(8.0, 16.0, 100)
    for cost_name in COST_TIERS.keys():
        sub_c = COST_TIERS[cost_name]
        fric = (2.0 * sub_c['half_spread_opt'] * CONTRACT_MULTIPLIER
                + 2.0 * sub_c['commission_per_contract']
                + abs(hedge_shares) * SPOT_PRICE * (sub_c['stock_spread_bps'] / 10000.0))
        net_pnls = []
        for st in dense_spots:
            c_po = max(st - K, 0.0) * CONTRACT_MULTIPLIER
            p_po = max(K - st, 0.0) * CONTRACT_MULTIPLIER
            stk_pnl = hedge_shares * (st - SPOT_PRICE)
            pnl = (c_po + p_po - (c_obs + p_obs) * CONTRACT_MULTIPLIER) + stk_pnl - fric
            net_pnls.append(pnl)
        plt.plot(dense_spots, net_pnls, linewidth=2.0, label=f"Net P&L ({cost_name} Frictions)")

    plt.axhline(0, color='black', linestyle='--', linewidth=0.8)
    plt.axvline(SPOT_PRICE, color='gray', linestyle=':', label=f'Initial Spot S0=${SPOT_PRICE:.2f}')
    plt.title(f"Strategy 1: Delta-Neutral ATM Straddle (K={K:.1f}) Terminal Payoff vs Spot Move", fontsize=12, fontweight='bold')
    plt.xlabel("Terminal Spot Price at Expiration (USD)")
    plt.ylabel("Net Profit / Loss (USD)")
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    fig_path = out_f / "strategy1_payoff_scenarios.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved Strategy 1 plot: {fig_path}")

    return strat1_df

def analyze_strategy_2_calendar_spread(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> pd.DataFrame:
    """
    Evaluates Strategy 2: Calendar Spread (Long Call 59d vs Short Call 31d at Strike K=13.00).
    Exploits term structure forward variance and roll-down.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)

    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')
    surface = VolatilitySurface(pd.read_csv(iv_csv))

    # Short front-month call: 2026-12-18 (31d, K=13.0)
    sym_short = 'NU261218C00013000'
    # Long back-month call: 2027-01-15 (59d, K=13.0)
    sym_long = 'NU270115C00013000'

    p_short_init = float(df_iv.loc[sym_short, 'lastPrice']) # 0.41
    p_long_init = float(df_iv.loc[sym_long, 'lastPrice'])   # 0.60
    tau1 = float(df_iv.loc[sym_short, 'tau_recalc'])
    tau2 = float(df_iv.loc[sym_long, 'tau_recalc'])
    iv1 = float(df_iv.loc[sym_short, 'our_iv_decimal'])
    iv2 = float(df_iv.loc[sym_long, 'our_iv_decimal'])

    # Forward volatility calculation
    w1 = (iv1 ** 2) * tau1
    w2 = (iv2 ** 2) * tau2
    fwd_var = (w2 - w1) / (tau2 - tau1)
    fwd_vol_pct = np.sqrt(max(fwd_var, 0.0)) * 100.0

    print(f"\nCalendar Spread Parameters (K=13.00):")
    print(f"  Front Month (31d): IV = {iv1*100:.2f}%, Price = ${p_short_init:.2f}")
    print(f"  Back Month (59d):  IV = {iv2*100:.2f}%, Price = ${p_long_init:.2f}")
    print(f"  Implied Forward Volatility (day 31 to 59): {fwd_vol_pct:.2f}%")

    n_contracts = 5
    net_debit_unit = p_long_init - p_short_init # 0.60 - 0.41 = 0.19
    total_debit = n_contracts * CONTRACT_MULTIPLIER * net_debit_unit # $95.00

    # At front month expiration (t = 31 days):
    # Remaining maturity of back month: tau_rem = tau2 - tau1 = 28 days = 28 / 365
    tau_rem = max(tau2 - tau1, 0.0)
    r_rem = get_zero_rate(tau_rem)

    spot_scenarios = [10.50, 11.50, 12.33, 13.00, 13.50, 14.50]
    records = []

    for cost_name, costs in COST_TIERS.items():
        friction = (2.0 * n_contracts * CONTRACT_MULTIPLIER * costs['half_spread_opt']
                    + 2.0 * n_contracts * costs['commission_per_contract'])

        for st in spot_scenarios:
            # Front month payoff
            short_payoff = max(st - 13.0, 0.0)
            short_pnl = -n_contracts * CONTRACT_MULTIPLIER * (short_payoff - p_short_init)

            # Back month value at day 31: revalued with remaining maturity tau_rem
            k_rem = np.log(13.0 / (st * np.exp(r_rem * tau_rem)))
            iv_rem = surface.surface_iv(k_rem, tau_rem)['iv']
            long_val_rem = bs_price('C', st, 13.0, tau_rem, r_rem, iv_rem)
            long_pnl = n_contracts * CONTRACT_MULTIPLIER * (long_val_rem - p_long_init)

            net_pnl = (short_pnl + long_pnl) - friction

            records.append({
                'Cost_Regime': cost_name,
                'Spot_at_Day_31': st,
                'Front_Payoff_USD': round(-short_payoff * n_contracts * CONTRACT_MULTIPLIER, 2),
                'Back_Option_Value_USD': round(long_val_rem * n_contracts * CONTRACT_MULTIPLIER, 2),
                'Gross_PnL_USD': round(short_pnl + long_pnl, 2),
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
    dense_st = np.linspace(9.5, 15.5, 80)
    for cost_name in COST_TIERS.keys():
        fric = (2.0 * n_contracts * CONTRACT_MULTIPLIER * COST_TIERS[cost_name]['half_spread_opt']
                + 2.0 * n_contracts * COST_TIERS[cost_name]['commission_per_contract'])
        pnls = []
        for st in dense_st:
            sp = max(st - 13.0, 0.0)
            k_rem = np.log(13.0 / (st * np.exp(r_rem * tau_rem)))
            iv_rem = surface.surface_iv(k_rem, tau_rem)['iv']
            lv = bs_price('C', st, 13.0, tau_rem, r_rem, iv_rem)
            pnl = n_contracts * CONTRACT_MULTIPLIER * ((lv - p_long_init) - (sp - p_short_init)) - fric
            pnls.append(pnl)
        plt.plot(dense_st, pnls, linewidth=2.0, label=f"Net P&L at Day 31 ({cost_name} Frictions)")

    plt.axhline(0, color='black', linestyle='--', linewidth=0.8)
    plt.axvline(13.0, color='purple', linestyle=':', label='Strike K=13.00 (Max Value Vertex)')
    plt.axvline(SPOT_PRICE, color='gray', linestyle='--', label=f'Initial Spot S0=${SPOT_PRICE:.2f}')
    plt.title("Strategy 2: Long Calendar Spread (Call K=13.00, 59d vs 31d) P&L Profile", fontsize=12, fontweight='bold')
    plt.xlabel("Spot Price at Day 31 Expiration (USD)")
    plt.ylabel("Net P&L (USD)")
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    fig_path = out_f / "strategy2_calendar_payoff.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved Strategy 2 plot: {fig_path}")

    return strat2_df

def run_strategies_analysis():
    print("\n=======================================================")
    print("RUNNING HYPOTHETICAL TRADING STRATEGIES (POINT 53)")
    print("=======================================================")
    s1_df = analyze_strategy_1_straddle()
    s2_df = analyze_strategy_2_calendar_spread()
    print("\nStrategy evaluation successfully completed!")

if __name__ == "__main__":
    run_strategies_analysis()
