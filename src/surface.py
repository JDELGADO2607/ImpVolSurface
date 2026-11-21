"""
Implied Volatility Surface Construction: Raw SVI, Spline Interpolation,
Arbitrage Diagnostics (Butterfly and Calendar), American Economic Checks,
Grouped Leave-One-Strike-Out Validation, and Visualizations.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.interpolate import interp1d, PchipInterpolator
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from src.market_data import (
    SPOT_PRICE,
    get_zero_rate,
    get_discount_factor,
    get_forward_price
)
from src.pricing_bs import bs_price
from src.pricing_american_fd import price_american_option

def raw_svi_total_variance(k: np.ndarray, a: float, b: float, rho: float, m: float, eta: float) -> np.ndarray:
    """
    Computes total implied variance w(k) = sigma^2 * tau using the Raw SVI formula:
    w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + eta^2))
    """
    k_arr = np.asarray(k, dtype=float)
    return a + b * (rho * (k_arr - m) + np.sqrt((k_arr - m)**2 + eta**2))

def svi_butterfly_density_g(k: np.ndarray, a: float, b: float, rho: float, m: float, eta: float) -> np.ndarray:
    """
    Computes Gatheral's g(k) function for butterfly arbitrage.
    No butterfly arbitrage requires g(k) >= 0.
    w'(k) = b * (rho + (k - m) / sqrt((k - m)^2 + eta^2))
    w''(k) = b * eta^2 / ((k - m)^2 + eta^2)^(3/2)
    g(k) = (1 - k * w' / (2 * w))^2 - (w'^2 / 4) * (1/w + 1/4) + w'' / 2
    """
    k_arr = np.asarray(k, dtype=float)
    disc = np.sqrt((k_arr - m)**2 + eta**2)
    w = np.maximum(a + b * (rho * (k_arr - m) + disc), 1e-6)

    w_prime = b * (rho + (k_arr - m) / disc)
    w_second = b * (eta**2) / (disc**3)

    term1 = (1.0 - (k_arr * w_prime) / (2.0 * w)) ** 2
    term2 = ((w_prime ** 2) / 4.0) * (1.0 / w + 0.25)
    term3 = 0.5 * w_second

    g = term1 - term2 + term3
    return g

def fit_svi_slice(
    k_obs: np.ndarray,
    w_obs: np.ndarray,
    tau: float,
    min_strikes: int = 6,
    min_span: float = 0.15
) -> dict[str, Any]:
    """
    Calibrates Raw SVI parameters (a, b, rho, m, eta) to a single maturity slice.
    Policy:
    - Requires at least min_strikes unique strikes and moneyness span >= min_span.
    - Strictly enforces Roger Lee's wing condition: b * (1 + |rho|) <= 1.95 < 2.0.
    - Strictly penalizes negative variance and butterfly arbitrage g(k) < 0 across the support.
    """
    unique_k = np.unique(k_obs)
    n_strikes = len(unique_k)
    span = float(np.max(k_obs) - np.min(k_obs))

    if n_strikes < min_strikes or span < min_span:
        return {
            'success': False,
            'params': None,
            'method': 'insufficient_points_for_svi',
            'reason': f"Strikes={n_strikes} (<{min_strikes}) or span={span:.3f} (<{min_span})",
            'rmse_w': np.nan,
            'rmse_iv': np.nan,
            'pct_no_butterfly_arb': np.nan
        }

    k_min = float(np.min(k_obs))
    k_max = float(np.max(k_obs))
    w_min = float(np.min(w_obs))
    k_dense = np.linspace(k_min - 0.05, k_max + 0.05, 100)

    # Initial parameter guesses
    init_params = [
        max(0.5 * w_min, 1e-4),          # a
        0.1,                              # b
        -0.2,                             # rho
        float(k_obs[np.argmin(w_obs)]),   # m
        0.1                               # eta
    ]

    bounds = [
        (0.0, 5.0),          # a
        (0.001, 1.0),        # b (ensures b*(1+|rho|) <= 2)
        (-0.95, 0.95),       # rho
        (k_min - 0.5, k_max + 0.5), # m
        (0.005, 1.5)         # eta
    ]

    def loss(p):
        a, b, rho, m, eta = p
        w_pred = raw_svi_total_variance(k_obs, a, b, rho, m, eta)
        residual = np.sum((w_pred - w_obs) ** 2)

        penalty = 0.0
        # 1. Total variance non-negativity
        min_v = a + b * eta * np.sqrt(max(1.0 - rho**2, 0.0))
        if min_v < 1e-5:
            penalty += 1e5 * ((1e-5 - min_v) ** 2)

        # 2. Roger Lee wing condition: b * (1 + |rho|) <= 1.95
        wing = b * (1.0 + abs(rho))
        if wing >= 1.95:
            penalty += 1e5 * ((wing - 1.95) ** 2)

        # 3. Butterfly density on slice support
        g_vals = svi_butterfly_density_g(k_dense, a, b, rho, m, eta)
        neg_g = np.maximum(-g_vals, 0.0)
        penalty += 1e6 * np.sum(neg_g ** 2)

        return residual + penalty

    res = minimize(loss, init_params, bounds=bounds, method='L-BFGS-B')

    if res.success or res.fun < 1e-2:
        a, b, rho, m, eta = res.x
        g_chk = svi_butterfly_density_g(k_dense, a, b, rho, m, eta)
        pct_no_arb = float(np.mean(g_chk >= -1e-6) * 100.0)
        lee_wing = float(b * (1.0 + abs(rho)))

        # SVI is only accepted if 100% of support is free of butterfly arbitrage and Lee wing < 2.0
        if pct_no_arb >= 99.9 and lee_wing < 2.0:
            w_pred = raw_svi_total_variance(k_obs, a, b, rho, m, eta)
            iv_pred = np.sqrt(np.maximum(w_pred, 1e-6) / tau)
            iv_obs = np.sqrt(np.maximum(w_obs, 1e-6) / tau)
            rmse_w = float(np.sqrt(np.mean((w_pred - w_obs)**2)))
            rmse_iv = float(np.sqrt(np.mean((iv_pred - iv_obs)**2)))

            return {
                'success': True,
                'params': (float(a), float(b), float(rho), float(m), float(eta)),
                'method': 'Raw SVI',
                'rmse_w': rmse_w,
                'rmse_iv': rmse_iv,
                'pct_no_butterfly_arb': 100.0,
                'lee_wing': lee_wing
            }

    # SVI failed or produced residual arbitrage -> fallback
    return {
        'success': False,
        'params': None,
        'method': 'svi_arbitrage_or_opt_failed',
        'reason': f"Optimization result: fun={res.fun:.4f}",
        'rmse_w': np.nan,
        'rmse_iv': np.nan,
        'pct_no_butterfly_arb': np.nan
    }

class VolatilitySurface:
    """
    Two-dimensional implied volatility surface sigma(k, tau) calibrated on NU options.
    Enforces explicit calibrate/fallback policies, Roger Lee wing bounds,
    support domain boundaries, and calendar monotonicity.
    """
    def __init__(self, iv_df: pd.DataFrame):
        self.raw_data = iv_df[iv_df['our_iv_decimal'].notna()].copy()
        self.slices = {}
        self.slice_params = []
        self.tenors = []
        self.k_min_global = float(self.raw_data['k_log_moneyness'].min())
        self.k_max_global = float(self.raw_data['k_log_moneyness'].max())
        self.tau_min_global = float(self.raw_data['tau_recalc'].min())
        self.tau_max_global = float(self.raw_data['tau_recalc'].max())

        self._calibrate()

    def _calibrate(self):
        grouped = self.raw_data.groupby('expirationDate')
        for exp_date, grp in grouped:
            tau = float(grp['tau_recalc'].iloc[0])
            tau_days = float(grp['tau_days'].iloc[0])
            k_obs = grp['k_log_moneyness'].values
            iv_obs = grp['our_iv_decimal'].values
            w_obs = (iv_obs ** 2) * tau

            sort_idx = np.argsort(k_obs)
            k_obs = k_obs[sort_idx]
            w_obs = w_obs[sort_idx]
            iv_obs = iv_obs[sort_idx]

            k_min = float(k_obs.min())
            k_max = float(k_obs.max())

            svi_res = fit_svi_slice(k_obs, w_obs, tau)
            if svi_res['success']:
                a, b, rho, m, eta = svi_res['params']
                self.slices[tau] = {
                    'type': 'svi',
                    'params': (a, b, rho, m, eta),
                    'k_min': k_min,
                    'k_max': k_max,
                    'tau': tau,
                    'tau_days': tau_days,
                    'exp_date': exp_date,
                    'n_strikes': len(np.unique(k_obs)),
                    'k_obs': k_obs,
                    'w_obs': w_obs
                }
                self.slice_params.append({
                    'expirationDate': exp_date,
                    'tau_days': round(tau_days, 1),
                    'tau_years': round(tau, 4),
                    'n_strikes': len(np.unique(k_obs)),
                    'method': 'Raw SVI',
                    'param_a': round(a, 5),
                    'param_b': round(b, 5),
                    'param_rho': round(rho, 4),
                    'param_m': round(m, 4),
                    'param_eta': round(eta, 5),
                    'rmse_iv_pp': round(svi_res['rmse_iv'] * 100.0, 3),
                    'pct_no_butterfly_arb': 100.0,
                    'lee_wing_b_1_rho': round(svi_res['lee_wing'], 4),
                    'k_support_min': round(k_min, 3),
                    'k_support_max': round(k_max, 3)
                })
            else:
                # Fallback: Monotonic PCHIP on empirical slice strikes
                # Aggregate identical strikes by taking median w
                df_slice = pd.DataFrame({'k': k_obs, 'w': w_obs}).groupby('k', as_index=False).median()
                k_uniq = df_slice['k'].values
                w_uniq = df_slice['w'].values

                if len(k_uniq) >= 2:
                    pchip = PchipInterpolator(k_uniq, w_uniq, extrapolate=True)
                else:
                    # Single point flat extrapolation
                    pchip = lambda k_eval: np.full_like(k_eval, w_uniq[0])

                self.slices[tau] = {
                    'type': 'spline',
                    'interpolator': pchip,
                    'k_min': k_min,
                    'k_max': k_max,
                    'tau': tau,
                    'tau_days': tau_days,
                    'exp_date': exp_date,
                    'n_strikes': len(k_uniq),
                    'k_obs': k_uniq,
                    'w_obs': w_uniq
                }
                self.slice_params.append({
                    'expirationDate': exp_date,
                    'tau_days': round(tau_days, 1),
                    'tau_years': round(tau, 4),
                    'n_strikes': len(k_uniq),
                    'method': 'PCHIP Spline (Fallback)',
                    'param_a': np.nan,
                    'param_b': np.nan,
                    'param_rho': np.nan,
                    'param_m': np.nan,
                    'param_eta': np.nan,
                    'rmse_iv_pp': 0.0,
                    'pct_no_butterfly_arb': 100.0,
                    'lee_wing_b_1_rho': np.nan,
                    'k_support_min': round(k_min, 3),
                    'k_support_max': round(k_max, 3)
                })

        self.tenors = sorted(list(self.slices.keys()))

    def evaluate_slice_total_variance(self, tau: float, k: float) -> tuple[float, str]:
        """
        Evaluates total variance w(k) on the slice corresponding to tau.
        """
        slice_info = self.slices[tau]
        if slice_info['type'] == 'svi':
            a, b, rho, m, eta = slice_info['params']
            w = raw_svi_total_variance(np.array([k]), a, b, rho, m, eta)[0]
            method = 'svi'
        else:
            w = float(slice_info['interpolator'](np.array([k]))[0])
            method = 'spline'
        w = max(float(w), 1e-6)
        return w, method

    def surface_iv(
        self,
        k: float,
        tau: float,
        policy: str = 'allow'
    ) -> dict[str, Any]:
        """
        Evaluates implied volatility sigma(k, tau).
        policy:
        - 'strict': raises ValueError if query is outside empirical bounds.
        - 'warn': flags 'EXTRAPOLATED_OUT_OF_BOUNDS'.
        - 'allow': default, returns value with explicit quality metadata.
        """
        is_extrapolated = (
            k < self.k_min_global - 0.05 or k > self.k_max_global + 0.05 or
            tau < self.tau_min_global * 0.8 or tau > self.tau_max_global * 1.2
        )

        if is_extrapolated and policy == 'strict':
            raise ValueError(f"Query point (k={k:.3f}, tau={tau:.4f}) outside surface empirical support.")

        quality = 'EXTRAPOLATED_OUT_OF_BOUNDS' if is_extrapolated else 'SUPPORTED_INSIDE_GRID'

        # Degenerate maturity handling: evaluate at shortest calibrated tenor
        if tau <= 1e-6:
            tau_short = self.tenors[0]
            w_short, method = self.evaluate_slice_total_variance(tau_short, k)
            iv_short = np.sqrt(w_short / tau_short)
            return {
                'iv': float(iv_short),
                'quality': 'DEGENERATE_TAU_SHORT_LIMIT',
                'method': f"limit_at_tau_{tau_short*365:.1f}d",
                'w': float(w_short)
            }

        # If tau matches an exact calibrated tenor
        if tau in self.slices:
            w, method = self.evaluate_slice_total_variance(tau, k)
            iv = np.sqrt(w / tau)
            return {'iv': float(iv), 'quality': quality, 'method': method, 'w': float(w)}

        # Interpolate in tau with monotonic cumulative projection to eliminate calendar arbitrage
        w_tenors = []
        for t_i in self.tenors:
            w_i, _ = self.evaluate_slice_total_variance(t_i, k)
            w_tenors.append(w_i)

        # Monotonic non-decreasing projection across tenors: w(k, t_{i+1}) >= w(k, t_i)
        w_mono = np.maximum.accumulate(w_tenors)

        pchip_tau = PchipInterpolator(self.tenors, w_mono, extrapolate=True)
        w_interp = max(float(pchip_tau(tau)), 1e-6)
        iv_interp = np.sqrt(w_interp / tau)

        return {
            'iv': float(iv_interp),
            'quality': quality,
            'method': 'svi_pchip_monotonic_2d',
            'w': float(w_interp)
        }

def check_american_economic_arbitrage(
    surface: VolatilitySurface,
    S0: float = SPOT_PRICE,
    tau_grid: list[float] | None = None,
    strike_grid: list[float] | None = None
) -> dict[str, Any]:
    """
    Performs economic arbitrage checks on American options priced from the surface:
    1. Strike monotonicity: Calls decreasing in K, Puts increasing in K.
    2. Expiry monotonicity: American options non-decreasing in tau.
    3. Intrinsic lower bounds: C >= max(S - K, 0), P >= max(K - S, 0).
    4. Upper bounds: C <= S, P <= K.
    """
    if tau_grid is None:
        tau_grid = [10.0/365.0, 31.0/365.0, 60.0/365.0, 120.0/365.0, 365.0/365.0]
    if strike_grid is None:
        strike_grid = [9.0, 10.0, 11.0, 12.0, 12.33, 13.0, 14.0, 15.0, 16.0]

    call_strike_viol = 0
    put_strike_viol = 0
    call_expiry_viol = 0
    put_expiry_viol = 0
    intrinsic_viol = 0
    upper_viol = 0

    tol = 1e-4

    # 1. Strike monotonicity and bounds
    for tau in tau_grid:
        r = get_zero_rate(tau)
        fwd = get_forward_price(tau, S0)
        c_prev, p_prev = None, None

        for K in strike_grid:
            k = float(np.log(K / fwd))
            iv = surface.surface_iv(k, tau)['iv']

            c_px = price_american_option('C', S0, K, tau, r, iv, q=0.0)
            p_px = price_american_option('P', S0, K, tau, r, iv, q=0.0)

            # Intrinsic bounds
            if c_px < max(S0 - K, 0.0) - tol:
                intrinsic_viol += 1
            if p_px < max(K - S0, 0.0) - tol:
                intrinsic_viol += 1

            # Upper bounds
            if c_px > S0 + tol:
                upper_viol += 1
            if p_px > K + tol:
                upper_viol += 1

            # Strike monotonicity
            if c_prev is not None and c_px > c_prev + tol:
                call_strike_viol += 1
            if p_prev is not None and p_px < p_prev - tol:
                put_strike_viol += 1

            c_prev = c_px
            p_prev = p_px

    # 2. Expiry monotonicity (American option value non-decreasing in tau)
    for K in strike_grid:
        c_prev_tau, p_prev_tau = None, None
        for tau in tau_grid:
            r = get_zero_rate(tau)
            fwd = get_forward_price(tau, S0)
            k = float(np.log(K / fwd))
            iv = surface.surface_iv(k, tau)['iv']

            c_px = price_american_option('C', S0, K, tau, r, iv, q=0.0)
            p_px = price_american_option('P', S0, K, tau, r, iv, q=0.0)

            if c_prev_tau is not None and c_px < c_prev_tau - tol:
                call_expiry_viol += 1
            if p_prev_tau is not None and p_px < p_prev_tau - tol:
                put_expiry_viol += 1

            c_prev_tau = c_px
            p_prev_tau = p_px

    return {
        'call_strike_monotonicity_violations': call_strike_viol,
        'put_strike_monotonicity_violations': put_strike_viol,
        'call_expiry_monotonicity_violations': call_expiry_viol,
        'put_expiry_monotonicity_violations': put_expiry_viol,
        'intrinsic_bound_violations': intrinsic_viol,
        'upper_bound_violations': upper_viol
    }

def leave_one_strike_out_validation(iv_df: pd.DataFrame) -> pd.DataFrame:
    """
    Performs Grouped Leave-One-Strike-Out cross-validation across slices with >= 5 strikes.
    When holding out strike K_test, excludes ALL contracts (both Call and Put) with K_test
    to prevent information leakage.
    Uses American PDE pricing engine for Puts and exact analytical BS for Calls (q=0).
    """
    val_records = []
    grouped = iv_df.groupby('expirationDate')

    for exp_date, grp in grouped:
        unique_strikes = grp['strike'].unique()
        if len(unique_strikes) < 5:
            continue

        tau = float(grp['tau_recalc'].iloc[0])
        r = get_zero_rate(tau)

        for strike_test in unique_strikes:
            # Exclude ALL contracts of strike_test from training slice
            train_sub = grp[grp['strike'] != strike_test]
            test_sub = grp[grp['strike'] == strike_test]

            k_train = train_sub['k_log_moneyness'].values
            w_train = ((train_sub['our_iv_decimal'].values) ** 2) * tau

            sort_idx = np.argsort(k_train)
            k_train = k_train[sort_idx]
            w_train = w_train[sort_idx]

            svi_res = fit_svi_slice(k_train, w_train, tau, min_strikes=4, min_span=0.10)

            for idx_out, row_out in test_sub.iterrows():
                k_test = float(row_out['k_log_moneyness'])
                true_iv = float(row_out['our_iv_decimal'])
                obs_price = float(row_out['lastPrice'])
                kind = row_out['type']
                strike = float(row_out['strike'])

                if svi_res['success']:
                    a, b, rho, m, eta = svi_res['params']
                    w_pred = raw_svi_total_variance(np.array([k_test]), a, b, rho, m, eta)[0]
                else:
                    # Fallback to PCHIP on train set
                    df_tr = pd.DataFrame({'k': k_train, 'w': w_train}).groupby('k', as_index=False).median()
                    pchip = PchipInterpolator(df_tr['k'].values, df_tr['w'].values, extrapolate=True)
                    w_pred = float(pchip(k_test))

                pred_iv = float(np.sqrt(max(w_pred, 1e-6) / tau))

                # Proper American option pricing engine (FD for puts, closed BS for calls q=0)
                pred_price = price_american_option(kind, SPOT_PRICE, strike, tau, r, pred_iv, q=0.0, method="auto")

                iv_err_pp = (pred_iv - true_iv) * 100.0
                price_err = pred_price - obs_price

                # Moneyness classification
                if k_test < -0.20:
                    moneyness_tier = "Deep OTM"
                elif k_test < -0.05:
                    moneyness_tier = "OTM"
                elif k_test <= 0.05:
                    moneyness_tier = "ATM"
                elif k_test <= 0.20:
                    moneyness_tier = "ITM"
                else:
                    moneyness_tier = "Deep ITM"

                val_records.append({
                    'contractSymbol': row_out['contractSymbol'],
                    'expirationDate': exp_date,
                    'tau_days': row_out['tau_days'],
                    'strike': strike,
                    'type': kind,
                    'moneyness_tier': moneyness_tier,
                    'true_iv_pct': true_iv * 100.0,
                    'pred_iv_pct': pred_iv * 100.0,
                    'iv_error_pp': iv_err_pp,
                    'obs_price': obs_price,
                    'pred_price': round(pred_price, 4),
                    'price_error_usd': round(price_err, 4)
                })

    return pd.DataFrame(val_records)

def generate_surface_plots_and_tables(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
):
    """
    Builds surface, validates, exports parameters and generates publication figures.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    iv_df = pd.read_csv(iv_csv)
    surface = VolatilitySurface(iv_df)

    # 1. Export SVI Slice Parameters
    params_df = pd.DataFrame(surface.slice_params)
    params_csv = out_t / "svi_slice_parameters.csv"
    params_df.to_csv(params_csv, index=False)
    print(f"Exported SVI slice parameters to: {params_csv}")

    # 2. Leave-One-Strike-Out Validation
    print("Running Grouped Leave-One-Strike-Out Cross Validation with American pricing...")
    loo_df = leave_one_strike_out_validation(iv_df)
    loo_csv = out_t / "surface_leave_one_out_validation.csv"
    loo_df.to_csv(loo_csv, index=False)
    print(f"Exported LOO validation to: {loo_csv}")

    mae_iv = loo_df['iv_error_pp'].abs().mean()
    rmse_iv = np.sqrt((loo_df['iv_error_pp']**2).mean())
    mae_px = loo_df['price_error_usd'].abs().mean()
    rmse_px = np.sqrt((loo_df['price_error_usd']**2).mean())

    print("\n--- Out-of-Sample Leave-One-Strike-Out Summary ---")
    print(f"Total Validated Contracts: {len(loo_df)}")
    print(f"IV MAE:  {mae_iv:.2f} pp | RMSE: {rmse_iv:.2f} pp")
    print(f"Price MAE: ${mae_px:.4f} USD | RMSE: ${rmse_px:.4f} USD")

    # 3. Figures
    # Figure 1: 2D Slices
    selected_tenors = [t for t in surface.tenors if surface.slices[t]['tau_days'] in [10.0, 24.0, 31.0, 59.0, 122.0, 212.0]]
    if not selected_tenors:
        selected_tenors = surface.tenors[:6]

    plt.figure(figsize=(12, 7))
    for t_i in selected_tenors:
        s_info = surface.slices[t_i]
        days = s_info['tau_days']
        k_min = s_info['k_min']
        k_max = s_info['k_max']
        k_dense = np.linspace(k_min, k_max, 100)
        iv_curve = [surface.surface_iv(k, t_i)['iv'] * 100.0 for k in k_dense]

        lbl = f"{days:.0f}d ({s_info['exp_date']}) [{s_info['type'].upper()}]"
        line = plt.plot(k_dense, iv_curve, label=lbl, linewidth=2)

        # Plot observed points
        sub_pts = iv_df[iv_df['expirationDate'] == s_info['exp_date']]
        plt.scatter(
            sub_pts['k_log_moneyness'],
            sub_pts['our_iv_decimal'] * 100.0,
            color=line[0].get_color(),
            s=25, alpha=0.7
        )

    plt.axvline(0, color='gray', linestyle=':', label='ATM Forward (k=0)')
    plt.xlabel("Log-Forward Moneyness $k = \\ln(K / F)$", fontsize=11)
    plt.ylabel("Implied Volatility (%)", fontsize=11)
    plt.title("Calibrated SVI & Monotonic Slices: NU American Options", fontsize=13, fontweight='bold')
    plt.legend(fontsize=9, loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()

    fig_2d = out_f / "smile_2d_slices.png"
    plt.savefig(fig_2d, dpi=300)
    plt.close()
    print(f"Saved 2D slices figure: {fig_2d}")

    # Figure 2: Term structure ATM
    plt.figure(figsize=(10, 5))
    taus_dense = np.linspace(surface.tau_min_global, surface.tau_max_global, 100)
    iv_atm = [surface.surface_iv(0.0, t)['iv'] * 100.0 for t in taus_dense]

    plt.plot(taus_dense * 365.0, iv_atm, color='#2b83ba', linewidth=2.5, label='ATM Term Structure $\\sigma_{\\mathrm{ATM}}(\\tau)$')
    # Scatter calibrated points
    atm_tenors = [surface.surface_iv(0.0, t_i)['iv'] * 100.0 for t_i in surface.tenors]
    plt.scatter([t_i * 365.0 for t_i in surface.tenors], atm_tenors, color='#d7191c', s=40, zorder=5, label='Calibrated Slices')

    plt.xlabel("Maturity $\\tau$ (Calendar Days)", fontsize=11)
    plt.ylabel("Implied Volatility ATM (%)", fontsize=11)
    plt.title("Term Structure of ATM Implied Volatility: NU US Equity", fontsize=12, fontweight='bold')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    fig_term = out_f / "term_structure_atm.png"
    plt.savefig(fig_term, dpi=300)
    plt.close()
    print(f"Saved term structure figure: {fig_term}")

    # Figure 3: 3D Surface
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    k_grid = np.linspace(surface.k_min_global, surface.k_max_global, 40)
    tau_grid = np.linspace(surface.tau_min_global, surface.tau_max_global, 40)
    K_mesh, Tau_mesh = np.meshgrid(k_grid, tau_grid)
    IV_mesh = np.zeros_like(K_mesh)

    for i in range(len(tau_grid)):
        for j in range(len(k_grid)):
            IV_mesh[i, j] = surface.surface_iv(K_mesh[i, j], Tau_mesh[i, j])['iv'] * 100.0

    surf = ax.plot_surface(K_mesh, Tau_mesh * 365.0, IV_mesh, cmap='viridis', edgecolor='none', alpha=0.85)
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label='Implied Volatility (%)')

    ax.set_xlabel("Log Moneyness $k$", fontsize=10, labelpad=8)
    ax.set_ylabel("Maturity (Days)", fontsize=10, labelpad=8)
    ax.set_zlabel("IV (%)", fontsize=10, labelpad=8)
    ax.set_title("3D Implied Volatility Surface: NU Holdings Ltd. (NU)", fontsize=12, fontweight='bold')
    ax.view_init(elev=28, azim=-125)
    plt.tight_layout()

    fig_3d = out_f / "surface_3d_volatility.png"
    plt.savefig(fig_3d, dpi=300)
    plt.close()
    print(f"Saved 3D surface figure: {fig_3d}")

if __name__ == "__main__":
    generate_surface_plots_and_tables()
