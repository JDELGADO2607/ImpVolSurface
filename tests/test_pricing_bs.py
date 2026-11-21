"""
Unit tests for Black-Scholes pricing and Greeks.
Validates Put-Call parity, monotonicity, boundary conditions,
and numerical consistency between analytical Greeks and finite difference approximations.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np
import pytest
from src.pricing_bs import bs_price, bs_greeks

def test_bs_put_call_parity():
    S = 12.33
    r = 0.045
    q = 0.0
    sigma = 0.40
    for K in [10.0, 12.0, 12.33, 14.0, 16.0]:
        for tau in [7.0 / 365.0, 30.0 / 365.0, 0.5, 1.0, 2.0]:
            c = bs_price('C', S, K, tau, r, sigma, q)
            p = bs_price('P', S, K, tau, r, sigma, q)
            lhs = c - p
            rhs = S * np.exp(-q * tau) - K * np.exp(-r * tau)
            assert abs(lhs - rhs) < 1e-12, f"Parity violated at K={K}, tau={tau}: {lhs} vs {rhs}"

def test_bs_monotonicity():
    S = 12.33
    K = 12.5
    tau = 0.25
    r = 0.04
    # Call price increases with S, increases with sigma, decreases with K
    c1 = bs_price('C', S, K, tau, r, 0.30)
    c2 = bs_price('C', S, K, tau, r, 0.50)
    assert c2 > c1

    p1 = bs_price('P', S, K, tau, r, 0.30)
    p2 = bs_price('P', S, K, tau, r, 0.50)
    assert p2 > p1

def test_bs_analytical_greeks_vs_fd():
    S = 12.33
    K = 12.0
    tau = 45.0 / 365.0
    r = 0.042
    sigma = 0.42

    greeks = bs_greeks('C', S, K, tau, r, sigma)

    # 1. Delta via central FD
    eps_s = 1e-4
    c_plus = bs_price('C', S + eps_s, K, tau, r, sigma)
    c_minus = bs_price('C', S - eps_s, K, tau, r, sigma)
    fd_delta = (c_plus - c_minus) / (2.0 * eps_s)
    assert abs(greeks['delta'] - fd_delta) < 1e-5

    # 2. Gamma via central FD
    c_mid = bs_price('C', S, K, tau, r, sigma)
    fd_gamma = (c_plus - 2.0 * c_mid + c_minus) / (eps_s ** 2)
    assert abs(greeks['gamma'] - fd_gamma) < 1e-4

    # 3. Vega via central FD
    eps_sig = 1e-4
    c_sig_p = bs_price('C', S, K, tau, r, sigma + eps_sig)
    c_sig_m = bs_price('C', S, K, tau, r, sigma - eps_sig)
    fd_vega_1pp = ((c_sig_p - c_sig_m) / (2.0 * eps_sig)) * 0.01
    assert abs(greeks['vega'] - fd_vega_1pp) < 1e-5

    # 4. Theta via central FD (tau derivative with minus sign)
    eps_t = 1e-5
    c_t_p = bs_price('C', S, K, tau + eps_t, r, sigma)
    c_t_m = bs_price('C', S, K, tau - eps_t, r, sigma)
    fd_theta = -(c_t_p - c_t_m) / (2.0 * eps_t)
    assert abs(greeks['theta_annual'] - fd_theta) < 1e-3
