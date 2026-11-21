"""
Unit tests for American Option Pricing (Crank-Nicolson FD + Penalty vs CRR Binomial Tree).
Validates American early exercise premium, Call European/American identity with q=0,
and convergence between FD PDE and CRR.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
from src.pricing_bs import bs_price
from src.pricing_crr import crr_price
from src.pricing_american_fd import fd_american_price, price_american_option

def test_american_put_early_exercise_premium():
    S0 = 12.33
    K = 15.0 # Deep ITM put
    tau = 90.0 / 365.0
    r = 0.045
    sigma = 0.40

    p_eu = bs_price('P', S0, K, tau, r, sigma)
    p_am = fd_american_price('P', S0, K, tau, r, sigma, M=300, N=150)

    # American put must be strictly greater than European put
    assert p_am > p_eu
    # Must respect intrinsic value
    assert p_am >= (K - S0)
    # Early exercise premium is positive
    early_exercise_premium = p_am - p_eu
    assert early_exercise_premium > 0.01

def test_american_call_matches_european_with_zero_dividends():
    S0 = 12.33
    r = 0.045
    q = 0.0
    sigma = 0.45
    for K in [10.0, 12.33, 14.0]:
        for tau in [30.0 / 365.0, 120.0 / 365.0]:
            c_eu = bs_price('C', S0, K, tau, r, sigma, q=q)
            c_am_fd = fd_american_price('C', S0, K, tau, r, sigma, q=q, M=300, N=150)
            assert abs(c_am_fd - c_eu) < 0.0015, f"Call mismatch at K={K}, tau={tau}: FD={c_am_fd}, BS={c_eu}"

def test_fd_vs_crr_benchmark():
    S0 = 12.33
    r = 0.043
    sigma = 0.45
    test_cases = [
        # (K, tau_days, kind)
        (11.0, 30.0, 'P'),
        (12.33, 30.0, 'P'),
        (14.0, 30.0, 'P'),
        (12.0, 90.0, 'P'),
        (13.0, 180.0, 'P'),
    ]

    for K, days, kind in test_cases:
        tau = days / 365.0
        p_fd = fd_american_price(kind, S0, K, tau, r, sigma, M=300, N=150)
        p_crr = crr_price(kind, S0, K, tau, r, sigma, exercise_type='american', N=800)
        diff = abs(p_fd - p_crr)
        assert diff < 0.0025, f"Discrepancy at K={K}, tau={days}d: FD={p_fd:.4f}, CRR={p_crr:.4f}, diff={diff:.4f}"

def test_fd_grid_convergence():
    S0 = 12.33
    K = 13.0
    tau = 60.0 / 365.0
    r = 0.043
    sigma = 0.45

    p_coarse = fd_american_price('P', S0, K, tau, r, sigma, M=150, N=75)
    p_medium = fd_american_price('P', S0, K, tau, r, sigma, M=300, N=150)
    p_fine = fd_american_price('P', S0, K, tau, r, sigma, M=600, N=300)

    diff_coarse_med = abs(p_coarse - p_medium)
    diff_med_fine = abs(p_medium - p_fine)

    # In uniform grids, node placement relative to strike introduces small O(dS) interpolation jitter
    # Price difference between medium and fine is well under 1/10th of a cent ($0.001)
    assert diff_med_fine < 0.001
    assert diff_coarse_med < 0.001
