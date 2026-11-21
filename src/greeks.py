"""
Option Greeks Calculator: Analytical (European) and Numerical Finite Differences (American).
Computes Delta, Gamma, Vega, Theta, Vanna, and Volga with explicit financial units.
Guarantees mesh stability by employing a common spatial domain S_max and shared
PDE grid solutions for spatial and cross-derivative evaluations.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
from src.pricing_bs import bs_greeks, bs_price
from src.pricing_american_fd import (
    fd_american_grid,
    evaluate_fd_grid,
    price_american_option
)

def calculate_option_greeks(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    is_american: bool = True,
    dS: float = 0.01,
    dSigma: float = 0.005,
    dTau: float = 1.0 / 365.0,
    M: int = 300,
    N: int = 150,
    interp_method: str = "pchip"
) -> dict[str, Any]:
    """
    Computes option Greeks.
    - If European or (American Call with q=0 and r>=0), uses exact analytical formulas.
    - If American Put, uses high-precision finite difference evaluations on a fixed PDE mesh.
    
    Units:
    - Delta: dV/dS (shares per option contract unit)
    - Gamma: d2V/dS2 (delta change per dollar move in spot)
    - Vega: dV/d(sigma), in dollars per 1 percentage point (0.01) change in vol
    - Theta_daily: dV/dt (dollar time decay per calendar day)
    - Theta_annual: dollar time decay per year (365 * theta_daily)
    - Vanna: d(Delta)/d(sigma) in delta change per 1 percentage point of vol
    - Volga: d(Vega)/d(sigma) in dollars per (1 pp vol)^2
    """
    kind = kind.upper()
    if not is_american or (kind == 'C' and q <= 1e-8 and r >= -1e-8):
        # Exact analytical Merton/Black-Scholes formulas apply
        g = bs_greeks(kind, S, K, tau, r, sigma, q)
        g['method'] = 'analytical_bs'
        return g

    # Common spatial domain to eliminate grid shifting across bumps
    S_max = 4.0 * max(S, K)

    # 1. Base PDE Solve for (S, K, tau, r, sigma, q)
    S_grid_0, V_0, diag_0 = fd_american_grid(
        kind='P', S_ref=S, K=K, tau=tau, r=r, sigma=sigma, q=q,
        M=M, N=N, S_max=S_max
    )

    v_mid = evaluate_fd_grid(S_grid_0, V_0, S, K, kind='P', interp_method=interp_method)
    v_plus = evaluate_fd_grid(S_grid_0, V_0, S + dS, K, kind='P', interp_method=interp_method)
    v_minus = evaluate_fd_grid(S_grid_0, V_0, S - dS, K, kind='P', interp_method=interp_method)

    delta = (v_plus - v_minus) / (2.0 * dS)
    gamma = (v_plus - 2.0 * v_mid + v_minus) / (dS ** 2)

    # 2. Sigma perturbations for Vega, Volga, and Vanna (fixed S_max)
    sig_p = sigma + dSigma
    sig_m = max(sigma - dSigma, 0.01)
    effective_dsig = sig_p - sig_m

    S_grid_sp, V_sp, _ = fd_american_grid(
        kind='P', S_ref=S, K=K, tau=tau, r=r, sigma=sig_p, q=q,
        M=M, N=N, S_max=S_max
    )
    S_grid_sm, V_sm, _ = fd_american_grid(
        kind='P', S_ref=S, K=K, tau=tau, r=r, sigma=sig_m, q=q,
        M=M, N=N, S_max=S_max
    )

    v_sig_p = evaluate_fd_grid(S_grid_sp, V_sp, S, K, kind='P', interp_method=interp_method)
    v_sig_m = evaluate_fd_grid(S_grid_sm, V_sm, S, K, kind='P', interp_method=interp_method)

    vega_1pp = ((v_sig_p - v_sig_m) / effective_dsig) * 0.01
    volga_raw = (v_sig_p - 2.0 * v_mid + v_sig_m) / ((effective_dsig / 2.0) ** 2)
    volga_1pp = volga_raw * 0.0001

    # Vanna: d(Delta)/d(sigma) using same sigma-perturbed solutions
    d_sig_p = (
        evaluate_fd_grid(S_grid_sp, V_sp, S + dS, K, kind='P', interp_method=interp_method)
        - evaluate_fd_grid(S_grid_sp, V_sp, S - dS, K, kind='P', interp_method=interp_method)
    ) / (2.0 * dS)

    d_sig_m = (
        evaluate_fd_grid(S_grid_sm, V_sm, S + dS, K, kind='P', interp_method=interp_method)
        - evaluate_fd_grid(S_grid_sm, V_sm, S - dS, K, kind='P', interp_method=interp_method)
    ) / (2.0 * dS)

    vanna_1pp = ((d_sig_p - d_sig_m) / effective_dsig) * 0.01

    # 3. Tau perturbations for Theta (fixed S_max)
    tau_p = tau + dTau
    tau_m = max(tau - dTau, 1e-4)
    effective_dtau = tau_p - tau_m

    S_grid_tp, V_tp, _ = fd_american_grid(
        kind='P', S_ref=S, K=K, tau=tau_p, r=r, sigma=sigma, q=q,
        M=M, N=N, S_max=S_max
    )
    S_grid_tm, V_tm, _ = fd_american_grid(
        kind='P', S_ref=S, K=K, tau=tau_m, r=r, sigma=sigma, q=q,
        M=M, N=N, S_max=S_max
    )

    v_tau_p = evaluate_fd_grid(S_grid_tp, V_tp, S, K, kind='P', interp_method=interp_method)
    v_tau_m = evaluate_fd_grid(S_grid_tm, V_tm, S, K, kind='P', interp_method=interp_method)

    theta_annual = -(v_tau_p - v_tau_m) / effective_dtau
    theta_daily = theta_annual / 365.0

    return {
        'delta': float(delta),
        'gamma': float(gamma),
        'vega': float(vega_1pp),
        'theta_annual': float(theta_annual),
        'theta_daily': float(theta_daily),
        'vanna': float(vanna_1pp),
        'volga': float(volga_1pp),
        'method': 'numerical_fd_american_fixed_grid'
    }

if __name__ == "__main__":
    S0 = 12.33
    K = 12.0
    tau = 31.0 / 365.0
    r = 0.043
    sigma = 0.452

    g_call = calculate_option_greeks('C', S0, K, tau, r, sigma, is_american=True)
    g_put = calculate_option_greeks('P', S0, K, tau, r, sigma, is_american=True)

    print(f"American Call K={K}:")
    for k, v in g_call.items():
        print(f"  {k}: {v}")

    print(f"\nAmerican Put K={K}:")
    for k, v in g_put.items():
        print(f"  {k}: {v}")
