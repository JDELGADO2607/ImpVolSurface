"""
Option selection and forensic data audit for Heston calibration on NU US Equity.

Audits all 575 contracts (303 calls, 272 puts) from data/raw/Opciones_Completo.xlsx.
Enforces:
- S0 = 12.33 USD (NYSE 2026-11-17 16:00 NY close)
- q = 0.00 (NU does not pay dividends)
- ACT/365F exact duration with timezone awareness (accounting for EST/EDT)
- American no-arbitrage bounds for puts: max(K - S0, 0) <= P <= K
- Identification of trade date staleness and midday execution asynchrony
- Granular liquidity, penny tick, and microstructure flags
- Support analysis across all 16 tenors without forcing legacy minimums
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional
import re
import numpy as np
import pandas as pd
from scipy.stats import norm

from src.heston.rates_curve import (
    VALUATION_DATETIME,
    NY_TZ,
    SPOT_PRICE,
    DIVIDEND_YIELD,
    get_official_yield_curve,
    DeterministicYieldCurve
)

OCC_REGEX = re.compile(r"^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")


def parse_occ_symbol(symbol: str) -> Tuple[str, int, int, int, str, float]:
    """
    Parses standard OCC option symbol into components.
    Example: 'NU261120P00012000' -> ('NU', 2026, 11, 20, 'P', 12.0)
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
    Computes exact maturity in ACT/365F continuous years using timezone-aware UTC duration.
    Expiration occurs at 16:00:00 America/New_York on expiration date.
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


def audit_and_select_options(
    raw_path: str = "data/raw/Opciones_Completo.xlsx",
    curve: Optional[DeterministicYieldCurve] = None,
    output_dir: Optional[str] = "data/heston"
) -> Dict[str, pd.DataFrame]:
    """
    Performs full forensic audit of raw options dataset.
    Exports:
    1. puts_all: all 272 puts with full classification, metrics, and audit reasons.
    2. puts_selected: clean puts suitable for Heston calibration.
    3. puts_common_r3: puts matching the historical 84 puts from R3 for exact common-sample baseline.
    4. support_summary: tenor-by-tenor support metrics (counts, strikes, moneyness, liquidity).
    5. calls_all: all 303 calls audited for out-of-sample external contrast.
    """
    raw_p = Path(raw_path)
    if not raw_p.exists():
        raise FileNotFoundError(f"Raw Excel file not found at: {raw_p}")

    if curve is None:
        curve = get_official_yield_curve(method="bootstrap")

    xls = pd.ExcelFile(raw_p)
    df1 = pd.read_excel(xls, sheet_name="Hoja1")
    df2 = pd.read_excel(xls, sheet_name="Hoja2")

    # Normalize Bloomberg tickers for exact 1-to-1 merge
    df1['ticker_bbg_norm'] = df1['bloombergOptionTicker'].astype(str).str.replace(',', '.', regex=False)
    df2['ticker_bbg_norm'] = df2['Bloomberg Option Ticker'].astype(str).str.replace(',', '.', regex=False)

    assert not df1['ticker_bbg_norm'].duplicated().any(), "Duplicate Bloomberg tickers in Hoja1"
    assert not df2['ticker_bbg_norm'].duplicated().any(), "Duplicate Bloomberg tickers in Hoja2"

    merged = pd.merge(
        df1,
        df2[['ticker_bbg_norm', 'IV Mid', 'IV Best Price', 'IV Last Trade']],
        on='ticker_bbg_norm',
        how='left',
        validate='1:1'
    )

    # Check if historical R3 clean puts are available for tagging
    r3_clean_symbols = set()
    hist_clean_p = Path("outputs/tables/options_clean.csv")
    if hist_clean_p.exists():
        df_hist = pd.read_csv(hist_clean_p)
        r3_clean_symbols = set(df_hist[df_hist["type"] == "P"]["contractSymbol"])

    records = []
    for idx, row in merged.iterrows():
        contract = row['contractSymbol']
        und, exp_y, exp_m, exp_d, o_type, occ_strike = parse_occ_symbol(contract)

        exp_dt_raw = pd.to_datetime(row['expirationDate'])
        assert exp_dt_raw.year == exp_y and exp_dt_raw.month == exp_m and exp_dt_raw.day == exp_d, \
            f"Expiration mismatch in {contract}: {exp_dt_raw} vs {exp_y}-{exp_m}-{exp_d}"
        assert row['type'] == o_type, f"Type mismatch in {contract}"
        assert abs(row['strike'] - occ_strike) < 1e-5, f"Strike mismatch in {contract}"

        tau = calculate_exact_tau(exp_dt_raw, VALUATION_DATETIME)
        r = curve.get_zero_rate(tau)
        dfactor = curve.get_discount_factor(tau)
        fwd = curve.get_forward_price(tau, SPOT_PRICE)
        k_moneyness = float(np.log(occ_strike / fwd))

        # Trade date parsing
        ltd = pd.to_datetime(row['lastTradeDate'])
        ltd_ny = ltd.tz_convert(NY_TZ) if ltd.tzinfo is not None else ltd.tz_localize("UTC").tz_convert(NY_TZ)
        is_val_date_trade = (ltd_ny.date() == VALUATION_DATETIME.date())
        days_stale = (VALUATION_DATETIME.date() - ltd_ny.date()).days
        trade_time_str = ltd_ny.strftime("%H:%M:%S")

        vol_val = row['volume']
        vol_clean = float(vol_val) if pd.notna(vol_val) else 0.0
        oi_val = row['openInterest']
        oi_clean = int(oi_val) if pd.notna(oi_val) else 0

        p_obs = float(row['lastPrice'])

        # Economic bounds
        if o_type == 'P':
            intrinsic_val = max(occ_strike - SPOT_PRICE, 0.0)
            lower_bound = intrinsic_val # American put lower bound
            upper_bound = occ_strike     # American put upper bound
            time_val = p_obs - lower_bound
        else: # Call
            intrinsic_val = max(SPOT_PRICE - occ_strike, 0.0)
            lower_bound = max(SPOT_PRICE - occ_strike * dfactor, 0.0)
            upper_bound = SPOT_PRICE
            time_val = p_obs - max(SPOT_PRICE - occ_strike, 0.0)

        vega_ref = calculate_vega_bs(SPOT_PRICE, occ_strike, tau, r, sigma=0.45)
        kappa = 0.01 / max(vega_ref, 1e-6)

        reasons = []
        bounds_ok = True

        if not is_val_date_trade:
            reasons.append(f"STALE_TRADE_{days_stale}D")

        if p_obs <= 0.0:
            reasons.append("ZERO_OR_NEGATIVE_PRICE")
            bounds_ok = False

        if p_obs < lower_bound - 1e-4:
            diff_cents = (lower_bound - p_obs) * 100.0
            reasons.append(f"VIOLATES_AMERICAN_LOWER_BOUND_{diff_cents:.1f}c")
            bounds_ok = False

        if p_obs > upper_bound + 1e-4:
            reasons.append("VIOLATES_AMERICAN_UPPER_BOUND")
            bounds_ok = False

        penny_quote = (p_obs <= 0.01)
        if penny_quote:
            reasons.append("MIN_TICK_PENNY_PRICE")

        negligible_time_val = (time_val < 0.01) and bounds_ok
        if negligible_time_val:
            reasons.append("NEGLIGIBLE_TIME_VALUE")

        # Classification status
        if not is_val_date_trade:
            status = "REJECTED_STALE_TRADE"
        elif not bounds_ok:
            status = "REJECTED_BOUNDS_VIOLATION"
        elif penny_quote or (time_val < 0.01):
            status = "CANDIDATE_MICROSTRUCTURE_SENSITIVE"
        elif p_obs >= 0.02 and time_val >= 0.01:
            status = "SELECTED_CLEAN"
        else:
            status = "REJECTED_ILLIQUID"

        records.append({
            'contractSymbol': contract,
            'bloombergOptionTicker': row['ticker_bbg_norm'],
            'type': o_type,
            'strike': occ_strike,
            'expirationDate': exp_dt_raw.strftime('%Y-%m-%d'),
            'lastTradeDate_NY': ltd_ny.strftime('%Y-%m-%d %H:%M:%S'),
            'trade_time_ny': trade_time_str,
            'is_trade_17nov': is_val_date_trade,
            'days_stale': days_stale,
            'lastPrice': p_obs,
            'volume': vol_clean,
            'openInterest': oi_clean,
            'tau_days': round(tau * 365.0, 1),
            'tau_years': tau,
            'rate_r': r,
            'discount_factor': dfactor,
            'forward_price': fwd,
            'k_log_moneyness': k_moneyness,
            'intrinsic_value': intrinsic_val,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'time_value': time_val,
            'vega_ref_bs45': vega_ref,
            'kappa_conditioning': kappa,
            'bounds_ok': bounds_ok,
            'status': status,
            'rejection_reasons': ";".join(reasons) if reasons else "NONE",
            'in_r3_common_84': contract in r3_clean_symbols,
            'bbg_iv_mid': row['IV Mid'],
            'bbg_iv_last': row['IV Last Trade'],
        })

    all_df = pd.DataFrame(records)

    # Separate puts and calls
    puts_all = all_df[all_df["type"] == "P"].copy().reset_index(drop=True)
    calls_all = all_df[all_df["type"] == "C"].copy().reset_index(drop=True)

    # Clean selected puts
    puts_clean = puts_all[puts_all["status"] == "SELECTED_CLEAN"].copy().reset_index(drop=True)

    # Common R3 puts (84 puts)
    puts_common_r3 = puts_all[puts_all["in_r3_common_84"]].copy().reset_index(drop=True)

    # Support by tenor for puts
    support_records = []
    for exp_str, grp in puts_all.groupby('expirationDate'):
        tau_d = grp['tau_days'].iloc[0]
        n_raw = len(grp)
        n_17nov = grp['is_trade_17nov'].sum()
        n_viol = (grp['status'] == 'REJECTED_BOUNDS_VIOLATION').sum()
        n_stale = (grp['status'] == 'REJECTED_STALE_TRADE').sum()
        n_micro = (grp['status'] == 'CANDIDATE_MICROSTRUCTURE_SENSITIVE').sum()
        n_clean = (grp['status'] == 'SELECTED_CLEAN').sum()
        n_r3 = grp['in_r3_common_84'].sum()

        clean_grp = grp[grp['status'] == 'SELECTED_CLEAN']
        if len(clean_grp) > 0:
            k_min = clean_grp['strike'].min()
            k_max = clean_grp['strike'].max()
            m_min = clean_grp['k_log_moneyness'].min()
            m_max = clean_grp['k_log_moneyness'].max()
            vol_sum = clean_grp['volume'].sum()
            oi_sum = clean_grp['openInterest'].sum()
        else:
            k_min, k_max = np.nan, np.nan
            m_min, m_max = np.nan, np.nan
            vol_sum, oi_sum = 0.0, 0

        if n_clean >= 5:
            slice_status = "ROBUST"
        elif n_clean >= 3:
            slice_status = "ADEQUATE"
        elif n_clean >= 1:
            slice_status = "SPARSE"
        else:
            slice_status = "EMPTY"

        support_records.append({
            'expirationDate': exp_str,
            'tau_days': tau_d,
            'n_raw_puts': n_raw,
            'n_traded_17nov': n_17nov,
            'n_rejected_stale': n_stale,
            'n_rejected_bounds': n_viol,
            'n_microstructure_sensitive': n_micro,
            'n_selected_clean': n_clean,
            'n_common_r3': n_r3,
            'slice_status': slice_status,
            'min_clean_strike': k_min,
            'max_clean_strike': k_max,
            'min_clean_moneyness': round(m_min, 4) if pd.notna(m_min) else np.nan,
            'max_clean_moneyness': round(m_max, 4) if pd.notna(m_max) else np.nan,
            'total_clean_volume': vol_sum,
            'total_clean_oi': oi_sum
        })

    support_df = pd.DataFrame(support_records)

    # Save to output_dir if specified
    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        puts_all.to_csv(out_p / "puts_selection_all.csv", index=False)
        puts_clean.to_csv(out_p / "puts_selected_clean.csv", index=False)
        puts_common_r3.to_csv(out_p / "puts_common_r3_benchmark.csv", index=False)
        support_df.to_csv(out_p / "puts_support_by_tenor.csv", index=False)
        calls_all.to_csv(out_p / "calls_external_contrast_all.csv", index=False)

    return {
        "puts_all": puts_all,
        "puts_clean": puts_clean,
        "puts_common_r3": puts_common_r3,
        "support_summary": support_df,
        "calls_all": calls_all
    }
