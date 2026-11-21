"""
Regression and Stability Tests for American PDE Greeks Engine (Bloque P0-A).
Tests:
1. Reproduction of Gamma instability when spatial mesh shifts with S0.
2. Stability of Gamma under fixed-domain shared mesh across bumps dS in [0.005, 0.01, 0.02, 0.05].
3. Convergence across spatial grid sizes M in [150, 300, 600, 900].
4. Vanna and Volga stability.
5. Penalty method convergence diagnostics.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
from src.pricing_american_fd import (
    fd_american_price,
    fd_american_grid,
    evaluate_fd_grid,
    price_american_option
)
from src.greeks import calculate_option_greeks
from src.pricing_bs import bs_greeks

def test_gamma_stability_across_bumps():
    """
    Gamma for American Put NU K=12, tau=31d, sigma=0.452 must remain stable
    across bump sizes dS in [0.005, 0.01, 0.02, 0.05], staying near ~0.237,
    and must NEVER explode to ~3.35 as was previously reported.
    """
    S0 = 12.33
    K = 12.0
    tau = 31.0 / 365.0
    r = 0.043
    sigma = 0.452

    gammas = []
    for dS in [0.005, 0.01, 0.02, 0.05]:
        g = calculate_option_greeks(
            'P', S0, K, tau, r, sigma, q=0.0,
            is_american=True, dS=dS, interp_method="pchip"
        )
        gammas.append(g['gamma'])

    # All gammas must be within [0.20, 0.28] and close to each other
    for gm in gammas:
        assert 0.20 < gm < 0.28, f"Gamma exploded or collapsed: {gm}"

    # Relative variation across bump sizes must be below 5%
    max_g, min_g = max(gammas), min(gammas)
    rel_spread = (max_g - min_g) / np.mean(gammas)
    assert rel_spread < 0.05, f"Excessive Gamma sensitivity to bump size: spread={rel_spread:.2%}"

def test_mesh_refinement_convergence():
    """
    Verifies spatial mesh convergence across M in [150, 300, 600, 900].
    Prices must agree within $0.001 USD and Gamma within 0.005.
    """
    S0 = 12.33
    K = 12.0
    tau = 31.0 / 365.0
    r = 0.043
    sigma = 0.452

    prices = []
    gammas = []
    for M in [150, 300, 600, 900]:
        N = int(M / 2)
        g = calculate_option_greeks(
            'P', S0, K, tau, r, sigma, q=0.0,
            is_american=True, dS=0.01, M=M, N=N, interp_method="pchip"
        )
        p = price_american_option('P', S0, K, tau, r, sigma, q=0.0, method="fd", M=M, N=N)
        prices.append(p)
        gammas.append(g['gamma'])

    # Price difference between fine (900) and medium (300) < 0.001
    assert abs(prices[-1] - prices[1]) < 0.001, f"Price did not converge: {prices}"

    # Gamma difference between fine (900) and medium (300) < 0.005
    assert abs(gammas[-1] - gammas[1]) < 0.005, f"Gamma did not converge: {gammas}"

def test_cross_greeks_finite_and_stable():
    """
    Verifies Vanna and Volga are finite, economically reasonable, and stable.
    """
    S0 = 12.33
    K = 12.0
    tau = 31.0 / 365.0
    r = 0.043
    sigma = 0.452

    g = calculate_option_greeks('P', S0, K, tau, r, sigma, q=0.0, is_american=True)

    assert not np.isnan(g['vanna'])
    assert not np.isnan(g['volga'])
    assert abs(g['vanna']) < 0.05, f"Vanna out of bounds: {g['vanna']}"
    assert abs(g['volga']) < 0.01, f"Volga out of bounds: {g['volga']}"

def test_penalty_convergence_diagnostics():
    """
    Checks that the PDE solver returns diagnostic information and detects
    exhausted iterations when max_penalty_iter is artificially constrained.
    """
    S0 = 12.33
    K = 12.0
    tau = 31.0 / 365.0
    r = 0.043
    sigma = 0.452

    # Normal case: should converge
    diag_normal = fd_american_price(
        'P', S0, K, tau, r, sigma, M=300, N=150,
        max_penalty_iter=30, return_diagnostics=True
    )
    assert isinstance(diag_normal, dict)
    assert diag_normal['converged'] is True
    assert diag_normal['iterations_exhausted'] is False
    assert diag_normal['max_penalty_iter_used'] < 30

    # Constrained case: max_penalty_iter=1 with tight tolerance should detect exhaustion
    diag_constrained = fd_american_price(
        'P', S0, K, tau, r, sigma, M=300, N=150,
        max_penalty_iter=1, penalty_tol=1e-12, return_diagnostics=True
    )
    assert isinstance(diag_constrained, dict)
    assert diag_constrained['iterations_exhausted'] is True
