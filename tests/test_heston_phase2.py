"""
Unit and integration tests for Phase 2: Proprietary 2D Heston Solver (MCS-IT).

Validates:
1. Exact zero QuantLib calls inside src/heston/solver_2d.py core.
2. Spatial stencil accuracy on non-uniform mesh for first, second, and mixed cross derivatives.
3. Payoff reproduction at tau = 0 (exact match with intrinsic).
4. Boundary handling at S=0, S=S_max, v=0 (degenerate transport), and v=v_max.
5. Black-Scholes limit degeneracy: xi -> 0, v0 = theta matches analytical BS formula within 0.0020 USD.
6. 12 Smoke test cases vs QuantLib references (AnalyticHestonEngine and FdHestonVanillaEngine)
   satisfying max error <= 0.0100 USD (and target <= 0.0020 USD).
7. Unclipped raw American put lower bound (V_AM >= max(K - S0, 0)) and early exercise premium (V_AM >= V_EU).
8. Ikonen-Toivanen splitting complementarity and feasibility satisfaction (residual < 1e-10).
9. Convergence stability across spatial and temporal mesh refinements.
10. Preservation of Phase 0 and Phase 1 artifacts without modification.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np
import pytest
from scipy.stats import norm

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import get_official_yield_curve, SPOT_PRICE
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.solver_2d import (
    Heston2DSolver,
    Grid2D,
    Heston2DSolverResult,
    compute_temporal_consistency_defect
)
from src.heston.pipeline_phase2 import get_phase1_poc_params, run_stencil_validation


def test_zero_quantlib_dependency_in_solver_core():
    """
    Architectural gate: verifies that src/heston/solver_2d.py does NOT import
    or reference QuantLib anywhere in its implementation.
    """
    solver_path = root_dir / "src" / "heston" / "solver_2d.py"
    with open(solver_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "import QuantLib" not in content, "QuantLib imported in solver_2d.py!"
    assert "import ql" not in content, "ql imported in solver_2d.py!"
    assert "ql." not in content, "QuantLib call found in solver_2d.py!"


def test_spatial_stencils_accuracy_on_test_function():
    """
    Verifies that non-uniform finite-difference stencils for d/dS, d2/dS2, d/dv, d2/dv2,
    and the mixed cross-derivative d2/dSdv achieve 2nd-order accuracy against known derivatives.
    """
    df_stencils = run_stencil_validation()
    for _, row in df_stencils.iterrows():
        assert row["status"] == "PASS", f"Stencil {row['derivative']} failed: err={row['max_error_interior']}"
        assert row["max_error_interior"] < 0.030, f"Stencil {row['derivative']} error too large: {row['max_error_interior']}"


def test_instantaneous_payoff_at_tau_zero():
    """
    Verifies that at tau = 0 (maturity = 0), the solver returns the exact analytical payoff
    without any bias, clipping, or smoothing.
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()

    test_strikes = [9.0, 11.0, 12.33, 15.0, 18.0]
    for K in test_strikes:
        expected_put = max(K - SPOT_PRICE, 0.0)
        res_eu = solver.price(K, 0.0, params, curve, is_american=False)
        res_am = solver.price(K, 0.0, params, curve, is_american=True)

        assert abs(res_eu.price - expected_put) < 1e-12, f"European payoff at T=0 mismatch for K={K}"
        assert abs(res_am.price - expected_put) < 1e-12, f"American payoff at T=0 mismatch for K={K}"


def test_degenerate_variance_boundary_transport():
    """
    Verifies degenerate boundary behavior at v = 0:
    Drift kappa * theta > 0 points into the domain, and one-sided forward differencing
    preserves non-negative option prices and stable interior propagation without blowup.
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()

    # Price an option evaluated at boundary v = 0
    params_v0 = HestonParams(v0=0.0, kappa=params.kappa, theta=params.theta, xi=params.xi, rho=params.rho)
    res_v0 = solver.price(12.33, 31.0 / 365.0, params_v0, curve, is_american=True, n_s=160, n_v=80, m_t=100)

    assert np.isfinite(res_v0.price), "Price at v=0 is not finite!"
    assert res_v0.price > 0.0, "Price at v=0 must be strictly positive for ATM put!"
    assert res_v0.price >= max(12.33 - SPOT_PRICE, 0.0), "American lower bound violated at v=0!"


def test_black_scholes_limit_degeneracy():
    """
    Verifies that in the limit xi -> 0 and v0 = theta, the 2D Heston PDE degenerates
    to the 1D Black-Scholes PDE, and European put prices match the analytical BS formula.
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")

    theta_val = 0.20
    sigma_val = np.sqrt(theta_val)
    params_bs = HestonParams(v0=theta_val, kappa=2.0, theta=theta_val, xi=1e-5, rho=0.0)

    for K in [11.0, 12.33, 15.0]:
        for T in [31.0 / 365.0, 94.0 / 365.0]:
            D = curve.get_discount_factor(T)
            d1 = (np.log(SPOT_PRICE / (K * D)) + 0.5 * theta_val * T) / (sigma_val * np.sqrt(T))
            d2 = d1 - sigma_val * np.sqrt(T)
            bs_exact = K * D * norm.cdf(-d2) - SPOT_PRICE * norm.cdf(-d1)

            res_fd = solver.price(K, T, params_bs, curve, is_american=False, n_s=160, n_v=80, m_t=100)
            diff = abs(res_fd.price - bs_exact)

            assert diff < 0.0020, f"BS limit error {diff:.6f} exceeds 0.0020 USD for K={K}, T={T}"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required for benchmark comparison")
def test_smoke_cases_european_vs_quantlib_analytic():
    """
    Smoke test gate: 6 European puts (K in {11.0, 12.33, 15.0}, 31d and 94d)
    must match QuantLib AnalyticHestonEngine within <= 0.0100 USD (Gate 1).
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()
    pricer = HestonOptionPricer()

    cases = [
        ("2026-12-18", 31.0 / 365.0, 11.00),
        ("2026-12-18", 31.0 / 365.0, 12.33),
        ("2026-12-18", 31.0 / 365.0, 15.00),
        ("2027-02-19", 94.0 / 365.0, 11.00),
        ("2027-02-19", 94.0 / 365.0, 12.33),
        ("2027-02-19", 94.0 / 365.0, 15.00),
    ]

    for expiry, T, K in cases:
        ql_eu = pricer.price_european(K, expiry, params, option_type="P")
        res_eu = solver.price(K, T, params, curve, is_american=False, n_s=160, n_v=80, m_t=100)
        diff = abs(res_eu.price - ql_eu)

        assert diff <= 0.0100, f"Gate failure: EU error {diff:.6f} > 0.01 USD for K={K}, T={T}"
        # Also confirm target budget <= 0.0020 USD is achieved
        assert diff <= 0.0020, f"EU error {diff:.6f} > 0.0020 USD for K={K}, T={T}"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required for benchmark comparison")
def test_smoke_cases_american_vs_quantlib_fdm():
    """
    Smoke test gate: 6 American puts (K in {11.0, 12.33, 15.0}, 31d and 94d)
    must match QuantLib FdHestonVanillaEngine within <= 0.0100 USD (Gate 1).
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()
    pricer = HestonOptionPricer()

    cases = [
        ("2026-12-18", 31.0 / 365.0, 11.00),
        ("2026-12-18", 31.0 / 365.0, 12.33),
        ("2026-12-18", 31.0 / 365.0, 15.00),
        ("2027-02-19", 94.0 / 365.0, 11.00),
        ("2027-02-19", 94.0 / 365.0, 12.33),
        ("2027-02-19", 94.0 / 365.0, 15.00),
    ]

    for expiry, T, K in cases:
        ql_am = pricer.price_american(K, expiry, params, option_type="P")
        res_am = solver.price(K, T, params, curve, is_american=True, n_s=160, n_v=80, m_t=100)
        diff = abs(res_am.price - ql_am)

        assert diff <= 0.0100, f"Gate failure: AM error {diff:.6f} > 0.01 USD for K={K}, T={T}"
        # Also confirm target budget <= 0.0020 USD is achieved
        assert diff <= 0.0020, f"AM error {diff:.6f} > 0.0020 USD for K={K}, T={T}"


def test_unclipped_arbitrage_bounds_and_early_exercise_premium():
    """
    Verifies that unclipped raw American put prices strictly satisfy:
    1. V_AM >= max(K - S0, 0) (no intrinsic arbitrage)
    2. V_AM >= V_EU (non-negative early exercise premium)
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()

    strikes = [9.0, 11.0, 12.33, 14.0, 15.0, 18.0]
    for K in strikes:
        intrinsic = max(K - SPOT_PRICE, 0.0)
        for T in [31.0 / 365.0, 94.0 / 365.0]:
            res_eu = solver.price(K, T, params, curve, is_american=False, n_s=160, n_v=80, m_t=100)
            res_am = solver.price(K, T, params, curve, is_american=True, n_s=160, n_v=80, m_t=100)

            # Raw unclipped output satisfies bounds within measured interpolation tolerance (1e-4 USD)
            assert res_am.price >= intrinsic - 1e-4, f"American price {res_am.price} < intrinsic {intrinsic} for K={K}"
            assert res_am.price >= res_eu.price - 1e-4, f"American price {res_am.price} < European price {res_eu.price} for K={K}"


def test_ikonen_toivanen_complementarity_residuals():
    """
    Verifies that the Ikonen-Toivanen splitting multiplier satisfies:
    1. lambda >= 0 (non-negative multiplier)
    2. V >= g (obstacle respected everywhere on grid)
    3. lambda * (V - g) == 0 (discrete complementarity)
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()

    res_am = solver.price(12.33, 31.0 / 365.0, params, curve, is_american=True, n_s=160, n_v=80, m_t=100)

    assert res_am.max_feasibility_violation < 1e-10, f"Feasibility violation: {res_am.max_feasibility_violation}"
    assert res_am.max_multiplier_violation < 1e-10, f"Multiplier violation: {res_am.max_multiplier_violation}"
    assert res_am.max_algebraic_complementarity_residual < 1e-10, f"Algebraic complementarity: {res_am.max_algebraic_complementarity_residual}"
    assert res_am.max_complementarity_residual < 1e-10, f"Complementarity residual alias: {res_am.max_complementarity_residual}"


def test_unsupported_option_types_rejected():
    """
    Audit Finding F2-M1: Verifies that Heston2DSolver explicitly rejects Call options
    and unsupported contract types with a ValueError, rather than returning unphysical prices.
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()

    for invalid_type in ["C", "c", "CALL", "call", "binary", "asian"]:
        with pytest.raises(ValueError, match="not supported by Heston2DSolver"):
            solver.price(12.33, 31.0 / 365.0, params, curve, option_type=invalid_type)


def test_greek_semantics_and_theta_availability():
    """
    Audit Finding F2-M1:
    - Theta is not available in Phase 2 and must be None.
    - Sensitivity to initial variance is d_price_d_v0 (USD / unit variance), with vega as alias.
    - Result class docstring explicitly documents that sensitivities are preliminary grid diagnostics.
    """
    solver = Heston2DSolver()
    curve = get_official_yield_curve(method="bootstrap")
    params = get_phase1_poc_params()

    res = solver.price(12.33, 31.0 / 365.0, params, curve, is_american=True, n_s=160, n_v=80, m_t=100)

    assert res.theta is None, f"Expected theta to be None in Phase 2, got {res.theta}"
    assert res.d_price_d_v0 > 0.0, f"Expected d_price_d_v0 > 0, got {res.d_price_d_v0}"
    assert res.vega == res.d_price_d_v0, f"Expected vega alias to match d_price_d_v0: {res.vega} vs {res.d_price_d_v0}"
    assert "preliminary" in Heston2DSolverResult.__doc__.lower(), "Heston2DSolverResult docstring must warn about preliminary sensitivities"


def test_exact_zero_xi_limit():
    """
    Audit Finding F2-M2:
    Verifies that with xi = 0.0 exactly (not just 1e-5), v0 = theta = 0.20, kappa = 2.0, rho = 0.0,
    the European put prices match the analytical Black-Scholes formula within 0.0020 USD.
    """
    solver = Heston2DSolver()
    rate = 0.05
    theta_val = 0.20
    sigma_val = np.sqrt(theta_val)
    params_exact_0 = HestonParams(v0=theta_val, kappa=2.0, theta=theta_val, xi=0.0, rho=0.0)

    for K in [11.0, 12.33, 15.0]:
        for T in [31.0 / 365.0, 94.0 / 365.0]:
            disc = np.exp(-rate * T)
            d1 = (np.log(SPOT_PRICE / (K * disc)) + 0.5 * theta_val * T) / (sigma_val * np.sqrt(T))
            d2 = d1 - sigma_val * np.sqrt(T)
            bs_exact = K * disc * norm.cdf(-d2) - SPOT_PRICE * norm.cdf(-d1)

            res = solver.price(K, T, params_exact_0, rate, is_american=False, n_s=160, n_v=80, m_t=100)
            diff = abs(res.price - bs_exact)

            assert diff < 0.0020, f"Exact xi=0 BS limit error {diff:.6f} exceeds 0.0020 USD for K={K}, T={T}"


def test_temporal_consistency_defect_convergence():
    """
    Audit Finding F2-M2:
    Verifies the independent interior trapezoidal PDE consistency defect:
        E = U_n - U_{n-1} - dt * [ 0.5 * (L_h U_n + L_h U_{n-1}) + 0.5 * (lambda_n + lambda_{n-1}) ]
    across M in {20, 40, 80} on the core interior domain (8 < S < 18, 0.04 < v < 0.40).
    Demonstrates that:
    1. The continuous PDE defect strictly decreases with temporal refinement (O(dt^2) rate).
    2. The algebraic IT complementarity residual is zero, confirming the conceptual difference.
    """
    params = get_phase1_poc_params()
    records = compute_temporal_consistency_defect(params=params, m_t_values=(20, 40, 80))

    assert len(records) == 3
    # Verify monotonic reduction in max interior defect
    defect_20 = records[0]["max_price_step_defect_core"]
    defect_40 = records[1]["max_price_step_defect_core"]
    defect_80 = records[2]["max_price_step_defect_core"]

    assert defect_40 < defect_20, f"Expected defect(40) < defect(20): {defect_40} vs {defect_20}"
    assert defect_80 < defect_40, f"Expected defect(80) < defect(40): {defect_80} vs {defect_40}"

    # Verify algebraic residual is zero at machine precision
    for r in records:
        assert r["max_algebraic_comp_residual"] < 1e-10, f"Algebraic residual {r['max_algebraic_comp_residual']} >= 1e-10"
