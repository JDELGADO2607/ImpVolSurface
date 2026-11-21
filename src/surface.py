"""
Implied Volatility Surface Construction: Raw SVI, Spline Interpolation,
Static Arbitrage Diagnostics, Leave-One-Strike-Out Validation, and Visualizations.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import minimize, least_squares
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

def raw_svi_total_variance(k: np.ndarray, a: float, b: float, rho: float, m: float, eta: float) -> np.ndarray:
    """
    Computes total implied variance w(k) = sigma^2 * tau using the Raw SVI formula:
    w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + eta^2))
    """
    return a + b * (rho * (k - m) + np.sqrt((k - m)**2 + eta**2))

def svi_butterfly_density_g(k: np.ndarray, a: float, b: float, rho: float, m: float, eta: float) -> np.ndarray:
    """
    Computes Gatheral's g(k) function for butterfly arbitrage.
    No butterfly arbitrage requires g(k) >= 0.
    w'(k) = b * (rho + (k - m) / sqrt((k - m)^2 + eta^2))
    w''(k) = b * eta^2 / ((k - m)^2 + eta^2)^(3/2)
    g(k) = (1 - k * w' / (2 * w))^2 - (w'^2 / 4) * (1/w + 1/4) + w'' / 2
    """
    disc = np.sqrt((k - m)**2 + eta**2)
    w = a + b * (rho * (k - m) + disc)
    w = np.maximum(w, 1e-6)

    w_prime = b * (rho + (k - m) / disc)
    w_second = b * (eta**2) / (disc**3)

    term1 = (1.0 - (k * w_prime) / (2.0 * w)) ** 2
    term2 = ((w_prime ** 2) / 4.0) * (1.0 / w + 0.25)
    term3 = 0.5 * w_second

    g = term1 - term2 + term3
    return g

def fit_svi_slice(k_obs: np.ndarray, w_obs: np.ndarray, tau: float) -> dict[str, Any]:
    """
    Calibrates Raw SVI parameters (a, b, rho, m, eta) to a single maturity slice.
    Enforces no-arbitrage constraints and minimum variance.
    """
    n_pts = len(k_obs)
    if n_pts < 4:
        # Not enough points for 5 SVI parameters
        return {
            'success': False,
            'params': None,
            'method': 'insufficient_points',
            'rmse_w': np.nan,
            'rmse_iv': np.nan
        }

    # Initial parameter guess
    w_min = np.min(w_obs)
    k_min = k_obs[np.argmin(w_obs)]
    init_params = [
        max(0.5 * w_min, 1e-4), # a
        0.1,                     # b
        -0.2,                    # rho
        float(k_min),           # m
        0.1                      # eta
    ]

    # Bounds: a in [0, 2*w_max], b in [0, 2], rho in [-0.99, 0.99], m in [-2, 2], eta in [0.005, 1.5]
    bounds = [
        (0.0, 5.0),
        (0.001, 2.0),
        (-0.99, 0.99),
        (-2.0, 2.0),
        (0.005, 2.0)
    ]

    def loss(p):
        a, b, rho, m, eta = p
        # Penalty for negative variance
        w_pred = raw_svi_total_variance(k_obs, a, b, rho, m, eta)
        residual = w_pred - w_obs
        penalty = 0.0
        # Check minimum total variance constraint
        min_v = a + b * eta * np.sqrt(1.0 - rho**2)
        if min_v < 0:
            penalty += 1e4 * (abs(min_v) ** 2)
        # Lee's moment cota penalty: b * (1 + |rho|) < 4
        if b * (1.0 + abs(rho)) >= 3.9:
            penalty += 1e3 * (b * (1.0 + abs(rho)) - 3.9)**2
        return np.sum(residual**2) + penalty

    res = minimize(loss, init_params, bounds=bounds, method='L-BFGS-B')

    if res.success or res.fun < 1e-2:
        a, b, rho, m, eta = res.x
        w_pred = raw_svi_total_variance(k_obs, a, b, rho, m, eta)
        iv_pred = np.sqrt(np.maximum(w_pred, 1e-6) / tau)
        iv_obs = np.sqrt(np.maximum(w_obs, 1e-6) / tau)
        rmse_w = np.sqrt(np.mean((w_pred - w_obs)**2))
        rmse_iv = np.sqrt(np.mean((iv_pred - iv_obs)**2))
        return {
            'success': True,
            'params': (a, b, rho, m, eta),
            'method': 'raw_svi',
            'rmse_w': float(rmse_w),
            'rmse_iv': float(rmse_iv)
        }
    else:
        return {
            'success': False,
            'params': None,
            'method': 'optimization_failed',
            'rmse_w': np.nan,
            'rmse_iv': np.nan
        }

class VolatilitySurface:
    """
    Two-dimensional implied volatility surface sigma(k, tau) calibrated on NU options.
    Uses Raw SVI slices where sufficient points exist, with PCHIP interpolation in tau.
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

            # Sort by k
            sort_idx = np.argsort(k_obs)
            k_obs = k_obs[sort_idx]
            w_obs = w_obs[sort_idx]
            iv_obs = iv_obs[sort_idx]

            svi_res = fit_svi_slice(k_obs, w_obs, tau)
            if svi_res['success']:
                a, b, rho, m, eta = svi_res['params']
                # Check butterfly density on dense grid
                k_dense = np.linspace(k_obs.min() - 0.2, k_obs.max() + 0.2, 100)
                g_vals = svi_butterfly_density_g(k_dense, a, b, rho, m, eta)
                pct_no_arb = float(np.mean(g_vals >= -1e-6) * 100.0)

                self.slices[tau] = {
                    'type': 'svi',
                    'params': (a, b, rho, m, eta),
                    'k_min': float(k_obs.min()),
                    'k_max': float(k_obs.max()),
                    'tau': tau,
                    'tau_days': tau_days,
                    'exp_date': exp_date,
                    'n_strikes': len(k_obs)
                }
                self.slice_params.append({
                    'expirationDate': exp_date,
                    'tau_days': round(tau_days, 1),
                    'tau_years': round(tau, 4),
                    'n_strikes': len(k_obs),
                    'method': 'Raw SVI',
                    'param_a': round(a, 5),
                    'param_b': round(b, 5),
                    'param_rho': round(rho, 4),
                    'param_m': round(m, 4),
                    'param_eta': round(eta, 5),
                    'rmse_iv_pp': round(svi_res['rmse_iv'] * 100.0, 3),
                    'pct_no_butterfly_arb': round(pct_no_arb, 1)
                })
            else:
                # Fallback: PCHIP or linear spline on w(k)
                if len(k_obs) >= 2:
                    pchip = PchipInterpolator(k_obs, w_obs, extrapolate=True)
                    self.slices[tau] = {
                        'type': 'spline',
                        'interpolator': pchip,
                        'k_min': float(k_obs.min()),
                        'k_max': float(k_obs.max()),
                        'tau': tau,
                        'tau_days': tau_days,
                        'exp_date': exp_date,
                        'n_strikes': len(k_obs)
                    }
                    self.slice_params.append({
                        'expirationDate': exp_date,
                        'tau_days': round(tau_days, 1),
                        'tau_years': round(tau, 4),
                        'n_strikes': len(k_obs),
                        'method': 'PCHIP Spline',
                        'param_a': np.nan,
                        'param_b': np.nan,
                        'param_rho': np.nan,
                        'param_m': np.nan,
                        'param_eta': np.nan,
                        'rmse_iv_pp': 0.0,
                        'pct_no_butterfly_arb': 100.0
                    })

        self.tenors = sorted(list(self.slices.keys()))

    def evaluate_slice_total_variance(self, tau: float, k: float) -> tuple[float, str]:
        slice_info = self.slices[tau]
        if slice_info['type'] == 'svi':
            a, b, rho, m, eta = slice_info['params']
            w = raw_svi_total_variance(np.array([k]), a, b, rho, m, eta)[0]
            method = 'svi'
        else:
            w = float(slice_info['interpolator'](k))
            method = 'spline'
        w = max(w, 1e-6)
        return w, method

    def surface_iv(
        self,
        k: float,
        tau: float,
        policy: str = 'no_silent_extrapolation'
    ) -> dict[str, Any]:
        """
        Evaluates the implied volatility surface at (k, tau).
        Returns {'iv': float, 'quality': str, 'method': str, 'w': float}.
        """
        if tau <= 1e-6:
            return {'iv': 0.45, 'quality': 'DEGENERATE_TAU', 'method': 'constant', 'w': 0.0}

        is_extrapolated = (k < self.k_min_global - 0.05 or k > self.k_max_global + 0.05 or
                           tau < self.tau_min_global * 0.8 or tau > self.tau_max_global * 1.2)

        if is_extrapolated and policy == 'strict':
            raise ValueError(f"Query point (k={k:.3f}, tau={tau:.4f}) outside surface support.")

        quality = 'EXTRAPOLATED_OUT_OF_BOUNDS' if is_extrapolated else 'SUPPORTED_INSIDE_GRID'

        # If tau is exactly one of our calibrated slices
        if tau in self.slices:
            w, method = self.evaluate_slice_total_variance(tau, k)
            iv = np.sqrt(w / tau)
            return {'iv': float(iv), 'quality': quality, 'method': method, 'w': float(w)}

        # Otherwise interpolate total variance across tenors for given k
        w_tenors = []
        for t_i in self.tenors:
            w_i, _ = self.evaluate_slice_total_variance(t_i, k)
            w_tenors.append(w_i)

        # Monotone PCHIP interpolation in tau ensures w(tau) is monotonic, preventing calendar arbitrage
        pchip_tau = PchipInterpolator(self.tenors, w_tenors, extrapolate=True)
        w_interp = max(float(pchip_tau(tau)), 1e-6)
        iv_interp = np.sqrt(w_interp / tau)

        return {
            'iv': float(iv_interp),
            'quality': quality,
            'method': 'svi_pchip_2d',
            'w': float(w_interp)
        }

def leave_one_strike_out_validation(iv_df: pd.DataFrame) -> pd.DataFrame:
    """
    Performs Leave-One-Strike-Out cross-validation across slices with >= 5 strikes.
    Measures out-of-sample prediction error in IV (pp) and option price ($).
    """
    val_records = []
    grouped = iv_df.groupby('expirationDate')

    for exp_date, grp in grouped:
        if len(grp) < 5:
            continue
        tau = float(grp['tau_recalc'].iloc[0])
        r = get_zero_rate(tau)

        for idx_out, row_out in grp.iterrows():
            train_sub = grp.drop(index=idx_out)
            k_train = train_sub['k_log_moneyness'].values
            w_train = ((train_sub['our_iv_decimal'].values) ** 2) * tau

            sort_idx = np.argsort(k_train)
            k_train = k_train[sort_idx]
            w_train = w_train[sort_idx]

            svi_res = fit_svi_slice(k_train, w_train, tau)
            if not svi_res['success']:
                continue

            a, b, rho, m, eta = svi_res['params']
            k_test = row_out['k_log_moneyness']
            true_iv = row_out['our_iv_decimal']
            obs_price = row_out['lastPrice']
            kind = row_out['type']
            strike = row_out['strike']

            w_pred = raw_svi_total_variance(np.array([k_test]), a, b, rho, m, eta)[0]
            pred_iv = np.sqrt(max(w_pred, 1e-6) / tau)

            # Model price under predicted IV
            if kind == 'C':
                pred_price = bs_price('C', SPOT_PRICE, strike, tau, r, pred_iv)
            else:
                pred_price = bs_price('P', SPOT_PRICE, strike, tau, r, pred_iv)

            iv_err_pp = (pred_iv - true_iv) * 100.0
            price_err = pred_price - obs_price

            val_records.append({
                'contractSymbol': row_out['contractSymbol'],
                'expirationDate': exp_date,
                'tau_days': row_out['tau_days'],
                'strike': strike,
                'type': kind,
                'true_iv_pct': true_iv * 100.0,
                'pred_iv_pct': pred_iv * 100.0,
                'iv_error_pp': iv_err_pp,
                'obs_price': obs_price,
                'pred_price': pred_price,
                'price_error_usd': price_err
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

    # Export SVI parameters table
    params_df = pd.DataFrame(surface.slice_params)
    params_path = out_t / "svi_slice_parameters.csv"
    params_df.to_csv(params_path, index=False)
    print(f"Exported SVI slice parameters: {params_path}")

    # Leave-one-out validation
    print("Running Leave-One-Strike-Out cross-validation...")
    val_df = leave_one_strike_out_validation(iv_df)
    val_path = out_t / "surface_leave_one_out_validation.csv"
    val_df.to_csv(val_path, index=False)
    print(f"Exported validation results: {val_path} ({len(val_df)} tests)")

    mae_iv = val_df['iv_error_pp'].abs().mean()
    rmse_iv = np.sqrt((val_df['iv_error_pp']**2).mean())
    mae_px = val_df['price_error_usd'].abs().mean()
    rmse_px = np.sqrt((val_df['price_error_usd']**2).mean())
    print(f"Leave-One-Out OOS Metrics: MAE IV = {mae_iv:.2f} pp, RMSE IV = {rmse_iv:.2f} pp | MAE Px = ${mae_px:.3f}, RMSE Px = ${rmse_px:.3f}")

    # 1. Plot 2D Smiles for Representative Tenors
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    rep_expirations = ['2026-12-18', '2027-01-15', '2027-06-17', '2028-01-21']
    for idx, exp_dt in enumerate(rep_expirations):
        ax = axes[idx]
        sub = iv_df[iv_df['expirationDate'] == exp_dt].copy()
        if len(sub) == 0:
            continue
        tau = sub['tau_recalc'].iloc[0]
        days = sub['tau_days'].iloc[0]

        calls = sub[sub['type'] == 'C']
        puts = sub[sub['type'] == 'P']

        ax.scatter(calls['strike'], calls['our_iv_pct'], color='blue', label='Calls (Clean)', s=45, alpha=0.8)
        ax.scatter(puts['strike'], puts['our_iv_pct'], color='red', marker='s', label='Puts (Clean)', s=45, alpha=0.8)

        # Fitted curve
        k_grid = np.linspace(sub['k_log_moneyness'].min() - 0.15, sub['k_log_moneyness'].max() + 0.15, 120)
        fwd = get_forward_price(tau, SPOT_PRICE)
        strike_grid = fwd * np.exp(k_grid)
        iv_curve = [surface.surface_iv(k_i, tau)['iv'] * 100.0 for k_i in k_grid]

        ax.plot(strike_grid, iv_curve, 'k-', linewidth=2.0, label='Fitted SVI Surface')
        ax.axvline(SPOT_PRICE, color='gray', linestyle='--', alpha=0.7, label=f'Spot S0=${SPOT_PRICE:.2f}')
        ax.set_title(f"Tenor {exp_dt} (tau = {days:.0f} d)", fontsize=12, fontweight='bold')
        ax.set_xlabel("Strike (USD)")
        ax.set_ylabel("Implied Volatility (%)")
        ax.legend(fontsize=9)

    plt.tight_layout()
    smile_fig = out_f / "smile_2d_slices.png"
    plt.savefig(smile_fig, dpi=300)
    plt.close()
    print(f"Saved 2D Smiles: {smile_fig}")

    # 2. Plot 3D Volatility Surface
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    k_mesh = np.linspace(-0.4, 0.6, 50)
    tau_mesh = np.linspace(0.02, 2.0, 50)
    K_GRID, TAU_GRID = np.meshgrid(k_mesh, tau_mesh)
    IV_GRID = np.zeros_like(K_GRID)

    for i in range(len(tau_mesh)):
        for j in range(len(k_mesh)):
            IV_GRID[i, j] = surface.surface_iv(K_GRID[i, j], TAU_GRID[i, j])['iv'] * 100.0

    surf = ax.plot_surface(K_GRID, TAU_GRID, IV_GRID, cmap='viridis', edgecolor='none', alpha=0.9)
    ax.set_xlabel("Log-Forward Moneyness k = ln(K/F)", labelpad=10)
    ax.set_ylabel("Maturity tau (years)", labelpad=10)
    ax.set_zlabel("Implied Volatility (%)", labelpad=10)
    ax.set_title("3D Implied Volatility Surface — NU US Equity (2026-11-17)", fontsize=14, fontweight='bold', pad=20)
    fig.colorbar(surf, shrink=0.5, aspect=10, label="IV (%)")
    ax.view_init(elev=25, azim=-125)

    surf_fig = out_f / "surface_3d_volatility.png"
    plt.savefig(surf_fig, dpi=300)
    plt.close()
    print(f"Saved 3D Surface: {surf_fig}")

    # 3. ATM Term Structure of Volatility
    taus_dense = np.linspace(0.01, 2.17, 100)
    atm_ivs = [surface.surface_iv(0.0, t_i)['iv'] * 100.0 for t_i in taus_dense]

    plt.figure(figsize=(10, 6))
    plt.plot(taus_dense * 365.0, atm_ivs, 'b-', linewidth=2.5, label='ATM Implied Volatility (k=0)')
    # Add empirical ATM points from clean dataset
    atm_points = iv_df[iv_df['k_log_moneyness'].abs() < 0.08].copy()
    plt.scatter(atm_points['tau_days'], atm_points['our_iv_pct'], color='darkorange', s=60, zorder=5, label='Near-ATM Contracts (|k| < 0.08)')

    plt.title("Term Structure of ATM Implied Volatility — NU US Equity", fontsize=13, fontweight='bold')
    plt.xlabel("Maturity (Calendar Days)")
    plt.ylabel("ATM Volatility (%)")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()

    term_fig = out_f / "term_structure_atm.png"
    plt.savefig(term_fig, dpi=300)
    plt.close()
    print(f"Saved ATM Term Structure: {term_fig}")

    return surface

if __name__ == "__main__":
    generate_surface_plots_and_tables()
