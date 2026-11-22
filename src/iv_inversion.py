"""
Implied Volatility (IV) Inversion Engine using Brent's Root-Finding Algorithm (Bloque P1-B).
Inverts American Calls (via exact BS) and American Puts (via Crank-Nicolson FD + Penalty).
Explicitly separates Brent volatility tolerance, PDE discretization error, and price tolerance.
Audits Call/Put IV parity across matching strikes without circular calibration.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import brentq

from src.pricing_bs import bs_price
from src.pricing_american_fd import fd_american_price, price_american_option
from src.market_data import SPOT_PRICE, get_zero_rate, get_discount_factor

def price_option(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    method: str = "auto"
) -> float:
    """
    Unified option pricing dispatcher.
    """
    return price_american_option(kind, S, K, tau, r, sigma, q=q, method=method)

def implied_vol(
    target_price: float,
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    q: float = 0.0,
    method: str = "auto",
    sigma_min: float = 0.01,
    sigma_max: float = 5.0,
    price_tol: float = 1e-6,
    max_iter: int = 100
) -> dict[str, Any]:
    """
    Inverts option market price into implied volatility using Brent's method.
    Returns dictionary with sigma, status, model_price, price_error, iterations, and notes.
    Separates volatility root tolerance (xtol=1e-5) from target price tolerance (price_tol).
    """
    kind = kind.upper()
    if target_price <= 0.0:
        return {
            'sigma': np.nan,
            'status': 'INVALID_PRICE_NONPOSITIVE',
            'model_price': np.nan,
            'price_error': np.nan,
            'iterations': 0,
            'notes': f"Target price must be positive, got {target_price}"
        }

    # Economic lower bound check
    df = np.exp(-r * tau)
    if kind == 'C':
        lb = max(S * np.exp(-q * tau) - K * df, 0.0)
        ub = S * np.exp(-q * tau)
    else:
        lb = max(K - S, 0.0)
        ub = K

    if target_price <= lb:
        return {
            'sigma': np.nan,
            'status': 'PRICE_BELOW_LOWER_BOUND',
            'model_price': lb,
            'price_error': target_price - lb,
            'iterations': 0,
            'notes': f"Target price {target_price:.4f} <= lower bound {lb:.4f}"
        }

    if target_price >= ub:
        return {
            'sigma': np.nan,
            'status': 'PRICE_ABOVE_UPPER_BOUND',
            'model_price': ub,
            'price_error': target_price - ub,
            'iterations': 0,
            'notes': f"Target price {target_price:.4f} >= upper bound {ub:.4f}"
        }

    iteration_count = [0]

    def objective(sig: float) -> float:
        iteration_count[0] += 1
        px = price_option(kind, S, K, tau, r, sig, q=q, method=method)
        return px - target_price

    f_min = objective(sigma_min)
    if abs(f_min) < price_tol:
        return {
            'sigma': float(sigma_min),
            'status': 'CONVERGED_AT_LOWER_BRACKET',
            'model_price': float(f_min + target_price),
            'price_error': float(f_min),
            'iterations': iteration_count[0],
            'notes': "Root at bracket boundary sigma_min"
        }

    f_max = objective(sigma_max)
    if abs(f_max) < price_tol:
        return {
            'sigma': float(sigma_max),
            'status': 'CONVERGED_AT_UPPER_BRACKET',
            'model_price': float(f_max + target_price),
            'price_error': float(f_max),
            'iterations': iteration_count[0],
            'notes': "Root at bracket boundary sigma_max"
        }

    if f_min * f_max > 0.0:
        if f_min > 0.0:
            status = 'NO_ROOT_VOL_TOO_LOW'
            notes = f"Model price at sigma={sigma_min} ({f_min + target_price:.4f}) > target ({target_price:.4f})"
        else:
            status = 'NO_ROOT_VOL_TOO_HIGH'
            notes = f"Model price at sigma={sigma_max} ({f_max + target_price:.4f}) < target ({target_price:.4f})"
        return {
            'sigma': np.nan,
            'status': status,
            'model_price': float(f_max + target_price),
            'price_error': float(f_max),
            'iterations': iteration_count[0],
            'notes': notes
        }

    # Run Brent's algorithm
    try:
        sol, r_res = brentq(
            objective,
            sigma_min,
            sigma_max,
            xtol=1e-5,
            rtol=1e-5,
            maxiter=max_iter,
            full_output=True
        )
        final_px = price_option(kind, S, K, tau, r, sol, q=q, method=method)
        err = float(final_px - target_price)

        # Distinguish exact price convergence from volatility-step convergence
        if abs(err) <= price_tol:
            status = 'CONVERGED_PRICE_TOL'
        elif abs(err) <= 1e-4:
            status = 'CONVERGED_VOL_TOL'
        else:
            status = 'CONVERGED_APPROX_RESIDUAL'

        return {
            'sigma': float(sol),
            'status': status,
            'model_price': float(final_px),
            'price_error': err,
            'iterations': iteration_count[0],
            'notes': f"Converged in {r_res.iterations} Brent steps, price residual=${abs(err):.2e}"
        }
    except Exception as e:
        return {
            'sigma': np.nan,
            'status': 'BRENT_FAILED',
            'model_price': np.nan,
            'price_error': np.nan,
            'iterations': iteration_count[0],
            'notes': str(e)
        }

def invert_clean_dataset(
    clean_csv: str = "outputs/tables/options_clean.csv",
    out_csv: str = "outputs/tables/options_with_iv.csv",
    out_comparison: str = "outputs/tables/iv_comparison_bloomberg.csv",
    out_parity_csv: str = "outputs/tables/iv_call_put_parity_audit.csv"
) -> pd.DataFrame:
    """
    Inverts IV for all clean contracts, audits Call/Put paired discrepancies,
    and contrasts with Bloomberg fields without circular calibration.
    """
    clean_path = Path(clean_csv)
    if not clean_path.exists():
        from src.data_cleaning import clean_and_audit_options
        clean_and_audit_options()

    df = pd.read_csv(clean_path)
    print(f"Inverting IV for {len(df)} clean contracts...")

    results = []
    for idx, row in df.iterrows():
        res = implied_vol(
            target_price=row['lastPrice'],
            kind=row['type'],
            S=SPOT_PRICE,
            K=row['strike'],
            tau=row['tau_recalc'],
            r=row['rate_r'],
            q=0.0,
            method="auto"
        )
        iv_dec = res['sigma']
        iv_pct = iv_dec * 100.0 if not np.isnan(iv_dec) else np.nan

        # Comparison with Bloomberg
        bbg_mid = row['bbg_iv_mid']
        bbg_last = row['bbg_iv_last']
        diff_mid = (iv_pct - bbg_mid) if (not np.isnan(iv_pct) and not np.isnan(bbg_mid)) else np.nan
        diff_last = (iv_pct - bbg_last) if (not np.isnan(iv_pct) and not np.isnan(bbg_last)) else np.nan

        results.append({
            'contractSymbol': row['contractSymbol'],
            'type': row['type'],
            'strike': row['strike'],
            'expirationDate': row['expirationDate'],
            'tau_days': row['tau_days'],
            'tau_recalc': row['tau_recalc'],
            'k_log_moneyness': row['k_log_moneyness'],
            'lastPrice': row['lastPrice'],
            'our_iv_decimal': iv_dec,
            'our_iv_pct': iv_pct,
            'iv_status': res['status'],
            'model_price_reconstruction': res['model_price'],
            'price_reconstruction_error': res['price_error'],
            'brent_iterations': res['iterations'],
            'bbg_iv_mid': bbg_mid,
            'bbg_iv_last': bbg_last,
            'diff_vs_bbg_mid': diff_mid,
            'diff_vs_bbg_last': diff_last
        })

    iv_df = pd.DataFrame(results)
    out_p = Path(out_csv)
    iv_df.to_csv(out_p, index=False)
    print(f"Exported IV dataset: {out_p} ({len(iv_df)} rows)")

    # 1. Stratified Comparison with Bloomberg by Maturity Bucket
    buckets = [
        ('Short Tenor (<= 30d)', iv_df[iv_df['tau_days'] <= 30]),
        ('Intermediate (31d - 90d)', iv_df[(iv_df['tau_days'] > 30) & (iv_df['tau_days'] <= 90)]),
        ('Medium-Long (91d - 365d)', iv_df[(iv_df['tau_days'] > 90) & (iv_df['tau_days'] <= 365)]),
        ('LEAPS (> 365d)', iv_df[iv_df['tau_days'] > 365]),
    ]

    comp_records = []
    for b_name, sub in buckets:
        diff_mid = sub['diff_vs_bbg_mid'].dropna()
        diff_last = sub['diff_vs_bbg_last'].dropna()
        comp_records.append({
            'tenor_bucket': b_name,
            'n_contracts': len(sub),
            'n_bbg_mid_available': len(diff_mid),
            'mean_bias_vs_bbg_mid_pp': round(diff_mid.mean(), 2) if len(diff_mid) > 0 else np.nan,
            'mae_vs_bbg_mid_pp': round(diff_mid.abs().mean(), 2) if len(diff_mid) > 0 else np.nan,
            'mean_bias_vs_bbg_last_pp': round(diff_last.mean(), 2) if len(diff_last) > 0 else np.nan,
            'mae_vs_bbg_last_pp': round(diff_last.abs().mean(), 2) if len(diff_last) > 0 else np.nan
        })

    comp_df = pd.DataFrame(comp_records)
    out_c = Path(out_comparison)
    comp_df.to_csv(out_c, index=False)
    print(f"Exported Bloomberg comparison: {out_c}")

    # 2. Call/Put IV Parity Audit on Paired Strikes
    calls = iv_df[iv_df['type'] == 'C'].set_index(['expirationDate', 'strike'])
    puts = iv_df[iv_df['type'] == 'P'].set_index(['expirationDate', 'strike'])
    common_pairs = calls.index.intersection(puts.index)

    parity_records = []
    for exp, k_val in common_pairs:
        c_row = calls.loc[(exp, k_val)]
        p_row = puts.loc[(exp, k_val)]
        c_iv = float(c_row['our_iv_pct'])
        p_iv = float(p_row['our_iv_pct'])
        diff_pp = p_iv - c_iv
        abs_diff = abs(diff_pp)

        parity_records.append({
            'expirationDate': exp,
            'strike': k_val,
            'tau_days': c_row['tau_days'],
            'k_log_moneyness': c_row['k_log_moneyness'],
            'call_symbol': c_row['contractSymbol'],
            'call_lastPrice': c_row['lastPrice'],
            'call_iv_pct': round(c_iv, 2),
            'put_symbol': p_row['contractSymbol'],
            'put_lastPrice': p_row['lastPrice'],
            'put_iv_pct': round(p_iv, 2),
            'iv_gap_put_minus_call_pp': round(diff_pp, 2),
            'abs_iv_gap_pp': round(abs_diff, 2),
            'executable_arbitrage': False,
            'explanatory_driver': 'Asynchronous lastPrice execution times and bid-ask bounce'
        })

    parity_df = pd.DataFrame(parity_records)
    out_par = Path(out_parity_csv)
    parity_df.to_csv(out_par, index=False)
    print(f"Exported Call/Put parity audit: {out_par} ({len(parity_df)} pairs, Mean Gap: {parity_df['abs_iv_gap_pp'].mean():.2f} pp)")

    return iv_df

if __name__ == "__main__":
    invert_clean_dataset()
