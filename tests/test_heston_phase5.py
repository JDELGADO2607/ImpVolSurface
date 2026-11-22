"""
Unit and Integration Tests for Phase 5: Heston Implied Volatility Surface.
"""

import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import DeterministicYieldCurve, SPOT_PRICE, DIVIDEND_YIELD
from src.heston.heston_model import HestonParams
from src.pricing_american_fd import fd_american_price
from src.heston.equivalent_iv import (
    fd_american_price_curve,
    invert_american_put_iv,
    price_heston_european_call,
    invert_european_call_iv,
)


@pytest.fixture(scope="module")
def curve():
    return DeterministicYieldCurve(method="bootstrap")


@pytest.fixture(scope="module")
def calibrated_params():
    calib_path = Path("data/heston/phase4/heston_calibrated_parameters.json")
    assert calib_path.exists(), "Phase 4 calibrated parameters file must exist"
    with open(calib_path, "r") as f:
        data = json.load(f)
    return HestonParams(**data["calibrated_parameters"])


def test_1d_engine_scalar_backward_compatibility():
    """Verify that 1D engine with scalar r reproduces exact historical prices bit-for-bit."""
    S0 = 12.33
    K = 14.0
    tau = 60.0 / 365.0
    r_scalar = 0.043
    sigma = 0.45
    p_ref = 1.9558903190116823

    p_test = fd_american_price('P', S0, K, tau, r_scalar, sigma, M=300, N=150)
    assert abs(p_test - p_ref) < 1e-10, f"Scalar price changed: got {p_test}, expected {p_ref}"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib not installed")
def test_1d_control_cases_vs_quantlib(curve):
    """
    Verify the 6 official 1D control cases match QuantLib American engine
    within the numerical discretization budget <= 0.0020 USD.
    """
    ref_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = ref_date

    tenors = curve.tenors
    dates = [ref_date] + [ref_date + ql.Period(int(round(t * 365)), ql.Days) for t in tenors]
    dfs = [1.0] + [curve.get_discount_factor(t) for t in tenors]
    ql_curve = ql.DiscountCurve(dates, dfs, ql.Actual365Fixed())
    ql_curve_handle = ql.YieldTermStructureHandle(ql_curve)
    q_handle = ql.YieldTermStructureHandle(ql.FlatForward(ref_date, 0.0, ql.Actual365Fixed()))
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE))

    cases = [
        (9.0, 31, 0.25),
        (12.33, 31, 0.45),
        (17.0, 31, 0.70),
        (9.0, 430, 0.70),
        (12.33, 94, 0.25),
        (17.0, 430, 0.45)
    ]

    for K, days, sigma in cases:
        tau = days / 365.0
        maturity = ref_date + ql.Period(days, ql.Days)
        payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
        exercise = ql.AmericanExercise(ref_date, maturity)
        option = ql.VanillaOption(payoff, exercise)

        flat_vol = ql.BlackConstantVol(ref_date, ql.NullCalendar(), sigma, ql.Actual365Fixed())
        vol_handle = ql.BlackVolTermStructureHandle(flat_vol)
        bs_process = ql.BlackScholesMertonProcess(spot_handle, q_handle, ql_curve_handle, vol_handle)
        engine = ql.FdBlackScholesVanillaEngine(bs_process, 400, 400)
        option.setPricingEngine(engine)
        ql_price = float(option.NPV())

        fd_price = fd_american_price('P', SPOT_PRICE, K, tau, curve, sigma, M=300, N=150)
        diff = abs(fd_price - ql_price)

        assert diff <= 0.0020, (
            f"Control case K={K}, d={days}, sig={sigma} failed: QL={ql_price:.6f}, FD={fd_price:.6f}, diff={diff:.6f} > 0.0020"
        )


def test_1d_mesh_sensitivity_two_sensitive_cases(curve):
    """
    Verify mesh stability across 3 meshes on the 2 sensitive cases:
    (12.33, 94, 0.25) and (12.33, 31, 0.45).
    """
    sensitive_cases = [(12.33, 94, 0.25), (12.33, 31, 0.45)]
    meshes = [(200, 100), (300, 150), (400, 300)]

    for K, days, sigma in sensitive_cases:
        tau = days / 365.0
        prices = [fd_american_price('P', SPOT_PRICE, K, tau, curve, sigma, M=m, N=n) for m, n in meshes]
        # Mesh changes should be small (< 0.001 USD between standard and fine)
        diff_std_fine = abs(prices[1] - prices[2])
        assert diff_std_fine < 0.0010, f"Mesh jump too large for K={K}, d={days}: {diff_std_fine:.6f}"


def test_american_put_iv_inversion_roundtrip(curve):
    """
    Roundtrip recovery test: generate price at known sigma_true, then invert.
    Verifies sigma recovery within xtol and residual within price tolerance.
    """
    S0 = SPOT_PRICE
    K = 12.0
    tau = 94.0 / 365.0
    sigma_true = 0.42

    target_px = fd_american_price('P', S0, K, tau, curve, sigma_true, M=300, N=150)
    inv = invert_american_put_iv(target_px, S0, K, tau, curve, price_tol=1e-5, M=300, N=150)

    assert inv['status'] == 'CONVERGED', f"Inversion failed: {inv['status']}"
    assert abs(inv['iv'] - sigma_true) < 1e-3, f"Recovered IV {inv['iv']} far from {sigma_true}"
    assert abs(inv['residual_usd']) < 1e-4, f"Price residual {inv['residual_usd']} exceeds tolerance"


def test_american_put_unidentifiable_near_intrinsic(curve):
    """
    Verify that an option priced at or below intrinsic returns explicit status
    without crashing or returning an artificial boundary.
    """
    S0 = SPOT_PRICE
    K = 18.0
    tau = 3.0 / 365.0
    intrinsic = K - S0

    # Test exact intrinsic
    inv = invert_american_put_iv(intrinsic, S0, K, tau, curve)
    assert inv['status'] == 'PRICE_BELOW_INTRINSIC'
    assert np.isnan(inv['iv'])

    # Test sub-intrinsic
    inv_sub = invert_american_put_iv(intrinsic - 0.10, S0, K, tau, curve)
    assert inv_sub['status'] == 'PRICE_BELOW_INTRINSIC'
    assert np.isnan(inv_sub['iv'])

    # Test above upper bound
    inv_ub = invert_american_put_iv(K + 0.50, S0, K, tau, curve)
    assert inv_ub['status'] == 'PRICE_ABOVE_UPPER_BOUND'
    assert np.isnan(inv_ub['iv'])


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib not installed")
def test_european_call_pricing_and_bs_inversion_roundtrip(curve, calibrated_params):
    """
    Verify European Call pricing with Heston model and analytical BS inversion.
    Residual must be <= 1e-8 USD.
    """
    S0 = SPOT_PRICE
    K = 12.33
    days = 31
    tau_years = days / 365.0

    call_px = price_heston_european_call(S0, K, days, calibrated_params, curve)
    assert call_px > 0.0, "Call price must be positive"

    inv = invert_european_call_iv(call_px, S0, K, tau_years, curve, price_tol=1e-8)
    assert inv['status'] == 'CONVERGED', f"Call inversion failed: {inv['status']}"
    assert abs(inv['residual_usd']) <= 1e-8, f"Call residual {inv['residual_usd']} exceeds 1e-8 USD"
    assert 0.10 <= inv['iv'] <= 1.50, f"Call IV out of plausible range: {inv['iv']}"


def test_pipeline_outputs_and_manifest():
    """
    Verifies that all Phase 5 artifacts exist and satisfy contractual row counts.
    """
    p5_dir = Path("data/heston/phase5")
    manifest_path = p5_dir / "phase5_execution_manifest.json"
    assert manifest_path.exists(), "Manifest must exist"

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    assert manifest["phase"] == "PHASE_5"

    # Check 97 puts table
    puts_csv = p5_dir / "heston_iv_surface_97_puts.csv"
    assert puts_csv.exists()
    df_puts = pd.read_csv(puts_csv)
    assert len(df_puts) == 97, f"Expected 97 puts, got {len(df_puts)}"
    assert "iv_heston_equivalent" in df_puts.columns
    assert "status_heston_inversion" in df_puts.columns

    # Check 142 calls table
    calls_csv = p5_dir / "heston_iv_surface_142_calls.csv"
    assert calls_csv.exists()
    df_calls = pd.read_csv(calls_csv)
    assert len(df_calls) == 142, f"Expected 142 calls, got {len(df_calls)}"
    assert "iv_heston_bs" in df_calls.columns
    assert "status_heston_call" in df_calls.columns

    # Check 35-point grids
    grid_puts = p5_dir / "heston_descriptive_grid_35_puts.csv"
    grid_calls = p5_dir / "heston_descriptive_grid_35_calls.csv"
    assert grid_puts.exists() and len(pd.read_csv(grid_puts)) == 35
    assert grid_calls.exists() and len(pd.read_csv(grid_calls)) == 35

    # Check 1D controls
    controls_csv = p5_dir / "control_cases_1d_quantlib.csv"
    assert controls_csv.exists()
    df_ctrl = pd.read_csv(controls_csv)
    assert len(df_ctrl) == 6
    assert df_ctrl["passed_gate"].all()

    # Check figures
    fig_dir = Path("figures/phase5")
    assert (fig_dir / "heston_iv_surface_puts_3d.png").exists()
    assert (fig_dir / "heston_iv_surface_calls_3d.png").exists()
    assert (fig_dir / "heston_iv_smile_slices.png").exists()
    assert (fig_dir / "heston_iv_grid_35_points.png").exists()
