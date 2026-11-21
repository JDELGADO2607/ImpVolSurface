"""
Implied Volatility (IV) Inversion Engine using Brent's Root-Finding Algorithm.
Inverts American Calls (via exact BS) and American Puts (via Crank-Nicolson FD + Penalty).
Contrasts computed IVs with external Bloomberg references without circular calibration.
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
        # Bracket sign condition violated
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
        err = final_px - target_price
        return {
            'sigma': float(sol),
            'status': 'CONVERGED',
            'model_price': float(final_px),
            'price_error': float(err),
            'iterations': iteration_count[0],
            'notes': f"Converged in {r_res.iterations} Brent steps"
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
    out_comparison: str = "outputs/tables/iv_comparison_bloomberg.csv"
) -> pd.DataFrame:
    """
    Inverts IV for all clean contracts and contrasts with Bloomberg fields.
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
            'model_price': res['model_price'],
            'price_error': res['price_error'],
            'brent_evals': res['iterations'],
            'bbg_iv_mid': bbg_mid,
            'bbg_iv_last': bbg_last,
            'diff_vs_bbg_mid_pp': diff_mid,
            'diff_vs_bbg_last_pp': diff_last,
            'tier': row['tier']
        })

    iv_df = pd.DataFrame(results)
    iv_df.to_csv(out_csv, index=False)
    print(f"Exported IV dataset to: {out_csv}")

    # Stratified comparison against Bloomberg
    valid_mid = iv_df.dropna(subset=['diff_vs_bbg_mid_pp']).copy()

    # Buckets of maturity: <15d, 15-90d, 90-365d, >365d
    def get_tau_bucket(days):
        if days < 15:
            return '< 15d (Short / Asynchronous)'
        elif days <= 90:
            return '15-90d (Liquid Term)'
        elif days <= 365:
            return '90-365d (Medium Term)'
        else:
            return '> 365d (LEAPS)'

    valid_mid['tau_bucket'] = valid_mid['tau_days'].apply(get_tau_bucket)

    comp_summary = []
    for bucket, grp in valid_mid.groupby('tau_bucket'):
        diffs = grp['diff_vs_bbg_mid_pp']
        comp_summary.append({
            'maturity_bucket': bucket,
            'contracts_evaluated': len(grp),
            'mean_bias_pp': round(diffs.mean(), 2),
            'mae_pp': round(diffs.abs().mean(), 2),
            'rmse_pp': round(np.sqrt((diffs**2).mean()), 2),
            'min_diff_pp': round(diffs.min(), 2),
            'max_diff_pp': round(diffs.max(), 2)
        })

    comp_df = pd.DataFrame(comp_summary).sort_values('maturity_bucket').reset_index(drop=True)
    comp_df.to_csv(out_comparison, index=False)
    print(f"Exported Bloomberg comparison to: {out_comparison}")
    print("\n--- Stratified Contrast with Bloomberg IV Mid ---")
    print(comp_df.to_string())

    return iv_df

if __name__ == "__main__":
    invert_clean_dataset()
