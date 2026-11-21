"""
Data cleaning, OCC symbol parsing, maturity recalculation, no-arbitrage bounds,
Vega conditioning, and multi-tier auditing for NU options.
Preserves original inputs, audits all 575 rows, and outputs clean datasets.
"""

import sys
from pathlib import Path

# Ensure root workspace is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import re
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from scipy.stats import norm

from src.market_data import (
    SPOT_PRICE,
    VALUATION_DATETIME,
    NY_TZ,
    get_zero_rate,
    get_discount_factor,
    get_forward_price
)

OCC_REGEX = re.compile(r"^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")

def parse_occ_symbol(symbol: str):
    """
    Parses standard OCC option symbol into components.
    Example: 'NU261120C00001000' -> ('NU', 2026, 11, 20, 'C', 1.0)
    """
    m = OCC_REGEX.match(symbol)
    if not m:
        raise ValueError(f"Invalid OCC option symbol format: {symbol}")
    underlying = m.group(1)
    year = 2000 + int(m.group(2))
    month = int(m.group(3))
    day = int(m.group(4))
    opt_type = m.group(5)
    strike = int(m.group(6)) / 1000.0
    return underlying, year, month, day, opt_type, strike

def calculate_exact_tau(exp_date: datetime, val_datetime: datetime = VALUATION_DATETIME) -> float:
    """
    Computes exact maturity in Act/365F years from valuation datetime to expiration at 16:00 EST.
    """
    exp_dt = datetime(exp_date.year, exp_date.month, exp_date.day, 16, 0, 0, tzinfo=NY_TZ)
    delta_seconds = (exp_dt - val_datetime).total_seconds()
    tau = delta_seconds / (365.0 * 86400.0)
    return float(tau)

def calculate_vega_bs(S0: float, K: float, tau: float, r: float, sigma: float = 0.45) -> float:
    """
    Computes Black-Scholes Vega in dollars per 1 percentage point of volatility (0.01 of sigma).
    """
    if tau <= 1e-8 or S0 <= 0 or K <= 0 or sigma <= 1e-8:
        return 0.0
    d1 = (np.log(S0 / K) + (r + 0.5 * sigma**2) * tau) / (sigma * np.sqrt(tau))
    vega_unit = S0 * np.sqrt(tau) * norm.pdf(d1) * 0.01
    return float(vega_unit)

def clean_and_audit_options(
    raw_path: str = "data/raw/Opciones_Completo.xlsx",
    tables_dir: str = "outputs/tables"
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads raw Excel, audits all 575 contracts, validates no-arbitrage bounds,
    computes exact tau and conditioning, and exports audit tables.
    """
    raw_p = Path(raw_path)
    out_dir = Path(tables_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    xls = pd.ExcelFile(raw_p)
    df1 = pd.read_excel(xls, sheet_name="Hoja1")
    df2 = pd.read_excel(xls, sheet_name="Hoja2")

    # Normalize Bloomberg tickers for exact 1-to-1 merge
    df1['ticker_bbg_norm'] = df1['bloombergOptionTicker'].astype(str).str.replace(',', '.', regex=False)
    df2['ticker_bbg_norm'] = df2['Bloomberg Option Ticker'].astype(str).str.replace(',', '.', regex=False)

    merged = pd.merge(
        df1,
        df2[['ticker_bbg_norm', 'IV Mid', 'IV Best Price', 'IV Last Trade']],
        on='ticker_bbg_norm',
        how='left',
        suffixes=('', '_hoja2')
    )

    records = []
    for idx, row in merged.iterrows():
        contract = row['contractSymbol']
        und, exp_y, exp_m, exp_d, o_type, occ_strike = parse_occ_symbol(contract)

        # Cross checks
        exp_dt_raw = pd.to_datetime(row['expirationDate'])
        assert exp_dt_raw.year == exp_y and exp_dt_raw.month == exp_m and exp_dt_raw.day == exp_d, \
            f"Expiration mismatch in {contract}: {exp_dt_raw} vs {exp_y}-{exp_m}-{exp_d}"
        assert row['type'] == o_type, f"Type mismatch in {contract}"
        assert abs(row['strike'] - occ_strike) < 1e-5, f"Strike mismatch in {contract}"

        # Recalculate exact tau
        tau = calculate_exact_tau(exp_dt_raw, VALUATION_DATETIME)
        r = get_zero_rate(tau)
        dfactor = get_discount_factor(tau)
        fwd = get_forward_price(tau, SPOT_PRICE)
        k_moneyness = float(np.log(occ_strike / fwd))

        # Trade date audit
        ltd = pd.to_datetime(row['lastTradeDate'])
        # Convert to NY time
        ltd_ny = ltd.tz_convert(NY_TZ) if ltd.tzinfo is not None else ltd.tz_localize("UTC").tz_convert(NY_TZ)
        is_val_date_trade = (ltd_ny.date() == VALUATION_DATETIME.date())
        days_stale = (VALUATION_DATETIME.date() - ltd_ny.date()).days

        p_obs = float(row['lastPrice'])

        # Economic bounds (American q=0)
        if o_type == 'C':
            lower_bound = max(SPOT_PRICE - occ_strike * dfactor, 0.0)
            upper_bound = SPOT_PRICE
            intrinsic_val = max(SPOT_PRICE - occ_strike, 0.0)
        else: # Put
            lower_bound = max(occ_strike - SPOT_PRICE, 0.0)
            upper_bound = occ_strike
            intrinsic_val = lower_bound

        time_val = p_obs - lower_bound

        # Vega & conditioning
        vega_ref = calculate_vega_bs(SPOT_PRICE, occ_strike, tau, r, sigma=0.45)
        kappa = 0.01 / max(vega_ref, 1e-6) # pp of vol per 1 cent of price

        # Reason flags
        reasons = []
        bounds_ok = (lower_bound < p_obs < upper_bound)
        if not bounds_ok:
            reasons.append("VIOLATES_BOUNDS")
        if time_val < 0.01:
            reasons.append("TIME_VALUE_BELOW_1_CENT")
        if p_obs < 0.05:
            reasons.append("PRICE_BELOW_5_CENTS")
        if not is_val_date_trade:
            reasons.append(f"STALE_TRADE_{days_stale}D")
        if kappa > 3.0:
            reasons.append(f"ILLIQUID_KAPPA_{kappa:.1f}")

        # Tier assignment
        if bounds_ok and time_val >= 0.01 and is_val_date_trade and p_obs >= 0.05 and kappa <= 3.0:
            tier = 1
        elif bounds_ok and time_val >= 0.01 and is_val_date_trade and (p_obs >= 0.02) and (kappa <= 5.0):
            tier = 2
        elif bounds_ok and not is_val_date_trade:
            tier = 3
        else:
            tier = 4

        records.append({
            'contractSymbol': contract,
            'bloombergOptionTicker': row['ticker_bbg_norm'],
            'type': o_type,
            'strike': occ_strike,
            'expirationDate': exp_dt_raw.strftime('%Y-%m-%d'),
            'lastTradeDate_UTC': str(row['lastTradeDate']),
            'lastTradeDate_NY': ltd_ny.strftime('%Y-%m-%d %H:%M:%S'),
            'is_trade_17nov': is_val_date_trade,
            'days_stale': days_stale,
            'lastPrice': p_obs,
            'bid': float(row['bid']),
            'ask': float(row['ask']),
            'volume': row['volume'],
            'openInterest': int(row['openInterest']),
            'yearsToExpiry_excel': float(row['yearsToExpiry']),
            'tau_recalc': tau,
            'tau_days': tau * 365.0,
            'rate_r': r,
            'discount_factor': dfactor,
            'forward_price': fwd,
            'k_log_moneyness': k_moneyness,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'intrinsic_value': intrinsic_val,
            'time_value': time_val,
            'vega_ref_bs45': vega_ref,
            'kappa_conditioning': kappa,
            'tier': tier,
            'rejection_reasons': ";".join(reasons) if reasons else "NONE",
            'bbg_iv_mid': row['ivMid'],
            'bbg_iv_last': row['ivLast Trade'],
            'bbg_iv_best': row['ivBestPrice'],
            'yahoo_iv': float(row['impliedVolatility'])
        })

    audit_df = pd.DataFrame(records)

    # Clean subset: Tier 1 + Tier 2
    clean_df = audit_df[audit_df['tier'].isin([1, 2])].copy().reset_index(drop=True)

    # Summary by tenor
    summary_records = []
    for exp_str, grp in audit_df.groupby('expirationDate'):
        n_total = len(grp)
        n_t1 = (grp['tier'] == 1).sum()
        n_t2 = (grp['tier'] == 2).sum()
        n_t3 = (grp['tier'] == 3).sum()
        n_t4 = (grp['tier'] == 4).sum()
        n_clean = n_t1 + n_t2
        tau_mean = grp['tau_days'].mean()
        summary_records.append({
            'expirationDate': exp_str,
            'tau_days': round(tau_mean, 1),
            'total_contracts': n_total,
            'tier_1_core': n_t1,
            'tier_2_sensitivity': n_t2,
            'clean_total': n_clean,
            'tier_3_stale': n_t3,
            'tier_4_corrupt_or_bounds': n_t4,
            'retention_pct': round(n_clean / n_total * 100, 1),
            'calls_clean': len(grp[(grp['tier'].isin([1, 2])) & (grp['type'] == 'C')]),
            'puts_clean': len(grp[(grp['tier'].isin([1, 2])) & (grp['type'] == 'P')])
        })
    summary_df = pd.DataFrame(summary_records).sort_values('tau_days').reset_index(drop=True)

    # Export CSVs
    audit_path = out_dir / "options_audit.csv"
    clean_path = out_dir / "options_clean.csv"
    summary_path = out_dir / "audit_summary_by_tenor.csv"

    audit_df.to_csv(audit_path, index=False)
    clean_df.to_csv(clean_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    print(f"Audit table exported: {audit_path} ({len(audit_df)} rows)")
    print(f"Clean table exported: {clean_path} ({len(clean_df)} rows)")
    print(f"Summary by tenor exported: {summary_path} ({len(summary_df)} tenors)")
    print("\n--- Overall Tier Breakdown ---")
    print(audit_df['tier'].value_counts().sort_index())
    print("\n--- Tenor Summary Preview ---")
    print(summary_df[['expirationDate', 'tau_days', 'total_contracts', 'clean_total', 'retention_pct', 'calls_clean', 'puts_clean']])

    return audit_df, clean_df, summary_df

if __name__ == "__main__":
    clean_and_audit_options()
