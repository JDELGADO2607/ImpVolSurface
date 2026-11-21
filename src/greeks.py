"""
Option Greeks Calculator: Analytical (European) and Numerical Finite Differences (American).
Computes Delta, Gamma, Vega, Theta, Vanna, and Volga with explicit financial units.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
from src.pricing_bs import bs_greeks, bs_price
from src.pricing_american_fd import price_american_option

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
    dTau: float = 1.0 / 365.0
) -> dict[str, Any]:
    """
    Computes option Greeks.
    - If European or (American Call with q=0 and r>=0), uses exact analytical formulas.
    - If American Put, uses high-precision central finite difference perturbations of the American PDE.
    
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
        # Exact analytical formulas apply
        g = bs_greeks(kind, S, K, tau, r, sigma, q)
        g['method'] = 'analytical_bs'
        return g

    # Numerical American PDE Greeks
    # 1. Delta & Gamma via central perturbations in S
    v_plus = price_american_option('P', S + dS, K, tau, r, sigma, q, method="fd")
    v_mid = price_american_option('P', S, K, tau, r, sigma, q, method="fd")
    v_minus = price_american_option('P', S - dS, K, tau, r, sigma, q, method="fd")

    delta = (v_plus - v_minus) / (2.0 * dS)
    gamma = (v_plus - 2.0 * v_mid + v_minus) / (dS ** 2)

    # 2. Vega via central perturbations in sigma
    sig_p = sigma + dSigma
    sig_m = max(sigma - dSigma, 0.01)
    effective_dsig = sig_p - sig_m
    v_sig_p = price_american_option('P', S, K, tau, r, sig_p, q, method="fd")
    v_sig_m = price_american_option('P', S, K, tau, r, sig_m, q, method="fd")
    vega_1pp = ((v_sig_p - v_sig_m) / effective_dsig) * 0.01

    # 3. Theta via central perturbation in tau
    tau_p = tau + dTau
    tau_m = max(tau - dTau, 1e-4)
    effective_dtau = tau_p - tau_m
    v_tau_p = price_american_option('P', S, K, tau_p, r, sigma, q, method="fd")
    v_tau_m = price_american_option('P', S, K, tau_m, r, sigma, q, method="fd")
    theta_annual = -(v_tau_p - v_tau_m) / effective_dtau
    theta_daily = theta_annual / 365.0

    # 4. Cross Greeks (Vanna & Volga)
    # Vanna: Delta perturbation with respect to sigma
    v_plus_sig_p = price_american_option('P', S + dS, K, tau, r, sig_p, q, method="fd")
    v_minus_sig_p = price_american_option('P', S - dS, K, tau, r, sig_p, q, method="fd")
    delta_sig_p = (v_plus_sig_p - v_minus_sig_p) / (2.0 * dS)

    v_plus_sig_m = price_american_option('P', S + dS, K, tau, r, sig_m, q, method="fd")
    v_minus_sig_m = price_american_option('P', S - dS, K, tau, r, sig_m, q, method="fd")
    delta_sig_m = (v_plus_sig_m - v_minus_sig_m) / (2.0 * dS)

    vanna_1pp = ((delta_sig_p - delta_sig_m) / effective_dsig) * 0.01

    # Volga: curvature with respect to sigma
    volga_raw = (v_sig_p - 2.0 * v_mid + v_sig_m) / ((effective_dsig / 2.0) ** 2)
    volga_1pp = volga_raw * 0.01 * 0.01

    return {
        'delta': float(delta),
        'gamma': float(gamma),
        'vega': float(vega_1pp),
        'theta_annual': float(theta_annual),
        'theta_daily': float(theta_daily),
        'vanna': float(vanna_1pp),
        'volga': float(volga_1pp),
        'method': 'numerical_fd_american'
    }

if __name__ == "__main__":
    S0 = 12.33
    K = 13.0
    tau = 45.0 / 365.0
    r = 0.043
    sigma = 0.45

    g_call = calculate_option_greeks('C', S0, K, tau, r, sigma, is_american=True)
    g_put = calculate_option_greeks('P', S0, K, tau, r, sigma, is_american=True)

    print(f"American Call K={K}:")
    for k, v in g_call.items():
        print(f"  {k}: {v}")

    print(f"\nAmerican Put K={K}:")
    for k, v in g_put.items():
        print(f"  {k}: {v}")
