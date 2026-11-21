"""
Hypothetical Options Portfolio Construction, Delta-Hedging, and Risk Profiling for NU.
Selects a compact, realistic 5-leg structure from clean contracts,
computes net Greeks, and adds an equity hedge position for delta-neutrality.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd

from src.market_data import SPOT_PRICE, CONTRACT_MULTIPLIER, get_zero_rate
from src.greeks import calculate_option_greeks
from src.pricing_american_fd import price_american_option
from src.surface import VolatilitySurface

# Defined portfolio structure: 5 legs using verified clean contracts
PORTFOLIO_LEGS = [
    {'contractSymbol': 'NU261218C00012000', 'qty': 5,  'label': 'Leg 1: Long Call 31d Near-ATM (12.0)'},
    {'contractSymbol': 'NU261218C00014000', 'qty': -5, 'label': 'Leg 2: Short Call 31d OTM (14.0)'},
    {'contractSymbol': 'NU261218P00012000', 'qty': 3,  'label': 'Leg 3: Long Put 31d Near-ATM (12.0)'},
    {'contractSymbol': 'NU270115C00013000', 'qty': 4,  'label': 'Leg 4: Long Call 59d Near-ATM (13.0)'},
    {'contractSymbol': 'NU270115P00011000', 'qty': -4, 'label': 'Leg 5: Short Put 59d OTM (11.0)'},
]

def build_hypothetical_portfolio(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables"
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Constructs the portfolio, prices each leg under surface and market price,
    computes Greeks, and calculates the delta-hedging share position.
    """
    out_t = Path(tables_dir)
    out_t.mkdir(parents=True, exist_ok=True)

    df_iv = pd.read_csv(iv_csv).set_index('contractSymbol')
    surface = VolatilitySurface(pd.read_csv(iv_csv))

    records = []
    total_options_delta = 0.0
    total_gamma = 0.0
    total_vega = 0.0
    total_theta_daily = 0.0
    total_vanna = 0.0
    total_volga = 0.0
    total_options_value_market = 0.0
    total_options_value_model = 0.0

    for leg in PORTFOLIO_LEGS:
        sym = leg['contractSymbol']
        qty = leg['qty']
        label = leg['label']

        if sym not in df_iv.index:
            raise KeyError(f"Contract {sym} not found in clean IV dataset.")

        row = df_iv.loc[sym]
        kind = row['type']
        K = float(row['strike'])
        tau = float(row['tau_recalc'])
        tau_days = float(row['tau_days'])
        k = float(row['k_log_moneyness'])
        p_obs = float(row['lastPrice'])
        r = get_zero_rate(tau)

        # Surface IV
        sig_surf = surface.surface_iv(k, tau)['iv']
        p_model = price_american_option(kind, SPOT_PRICE, K, tau, r, sig_surf, q=0.0, method="auto")

        # Greeks per option
        g = calculate_option_greeks(kind, SPOT_PRICE, K, tau, r, sig_surf, q=0.0, is_american=True)

        # Aggregate for this position (qty * multiplier)
        contract_scale = qty * CONTRACT_MULTIPLIER
        val_mkt = contract_scale * p_obs
        val_mod = contract_scale * p_model

        pos_delta = contract_scale * g['delta']
        pos_gamma = contract_scale * g['gamma']
        pos_vega = contract_scale * g['vega']
        pos_theta = contract_scale * g['theta_daily']
        pos_vanna = contract_scale * g['vanna']
        pos_volga = contract_scale * g['volga']

        total_options_delta += pos_delta
        total_gamma += pos_gamma
        total_vega += pos_vega
        total_theta_daily += pos_theta
        total_vanna += pos_vanna
        total_volga += pos_volga
        total_options_value_market += val_mkt
        total_options_value_model += val_mod

        records.append({
            'label': label,
            'contractSymbol': sym,
            'type': kind,
            'strike': K,
            'expirationDate': row['expirationDate'],
            'tau_days': round(tau_days, 1),
            'quantity': qty,
            'multiplier': CONTRACT_MULTIPLIER,
            'obs_price': p_obs,
            'surface_price': round(p_model, 4),
            'market_value_usd': round(val_mkt, 2),
            'surface_value_usd': round(val_mod, 2),
            'delta_per_unit': round(g['delta'], 4),
            'gamma_per_unit': round(g['gamma'], 4),
            'vega_1pp_per_unit': round(g['vega'], 4),
            'theta_daily_per_unit': round(g['theta_daily'], 4),
            'position_delta': round(pos_delta, 2),
            'position_gamma': round(pos_gamma, 2),
            'position_vega_1pp': round(pos_vega, 2),
            'position_theta_daily': round(pos_theta, 2)
        })

    # Delta Hedge with underlying shares
    hedge_shares = -int(np.round(total_options_delta))
    hedge_val = hedge_shares * SPOT_PRICE
    net_portfolio_delta = total_options_delta + hedge_shares

    # Add Stock row
    records.append({
        'label': 'Hedge: NU Equity Shares',
        'contractSymbol': 'NU_STOCK',
        'type': 'STOCK',
        'strike': np.nan,
        'expirationDate': 'N/A',
        'tau_days': np.nan,
        'quantity': hedge_shares,
        'multiplier': 1,
        'obs_price': SPOT_PRICE,
        'surface_price': SPOT_PRICE,
        'market_value_usd': round(hedge_val, 2),
        'surface_value_usd': round(hedge_val, 2),
        'delta_per_unit': 1.0,
        'gamma_per_unit': 0.0,
        'vega_1pp_per_unit': 0.0,
        'theta_daily_per_unit': 0.0,
        'position_delta': round(hedge_shares, 2),
        'position_gamma': 0.0,
        'position_vega_1pp': 0.0,
        'position_theta_daily': 0.0
    })

    port_df = pd.DataFrame(records)
    out_csv = out_t / "hypothetical_portfolio.csv"
    port_df.to_csv(out_csv, index=False)
    print(f"Exported hypothetical portfolio to: {out_csv}")

    total_port_value_mkt = total_options_value_market + hedge_val
    total_port_value_mod = total_options_value_model + hedge_val

    portfolio_summary = {
        'total_options_value_mkt': total_options_value_market,
        'total_options_value_mod': total_options_value_model,
        'hedge_shares': hedge_shares,
        'hedge_value': hedge_val,
        'total_portfolio_value_mkt': total_port_value_mkt,
        'total_portfolio_value_mod': total_port_value_mod,
        'net_delta': net_portfolio_delta,
        'net_gamma': total_gamma,
        'net_vega_1pp': total_vega,
        'net_theta_daily': total_theta_daily,
        'net_vanna': total_vanna,
        'net_volga': total_volga
    }

    print("\n--- Initial Portfolio Risk Profile (Delta-Hedged) ---")
    print(f"Total Options Value (Market): ${total_options_value_market:.2f} | Surface: ${total_options_value_model:.2f}")
    print(f"Stock Hedge: {hedge_shares} shares of NU @ ${SPOT_PRICE:.2f} = ${hedge_val:.2f}")
    print(f"Net Portfolio Value: ${total_port_value_mkt:.2f}")
    print(f"Net Delta: {net_portfolio_delta:.2f} (Options: {total_options_delta:.2f}, Stock: {hedge_shares})")
    print(f"Net Gamma: {total_gamma:.2f} shares/$")
    print(f"Net Vega:  ${total_vega:.2f} per 1 pp of volatility")
    print(f"Net Theta: ${total_theta_daily:.2f} per calendar day")

    return port_df, portfolio_summary

if __name__ == "__main__":
    build_hypothetical_portfolio()
