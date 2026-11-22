"""
Unit and Integration Tests for Phase 6: Financial Integration, Portfolio Risk, and Stress Testing.
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

from src.heston.rates_curve import DeterministicYieldCurve, SPOT_PRICE
from src.heston.heston_model import HestonParams
from src.heston.financial_integration import (
    run_four_model_comparison,
    evaluate_portfolio_and_greeks,
    run_portfolio_stress_testing,
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


def test_four_model_comparison_structure_and_completeness():
    """Verify that models_comparison_detailed.csv contains all 239 contracts with 4 models."""
    csv_path = Path("data/heston/phase6/models_comparison_detailed.csv")
    assert csv_path.exists(), f"File {csv_path} must exist after pipeline run"
    df = pd.read_csv(csv_path)

    assert len(df) == 239, f"Expected 239 contracts, got {len(df)}"
    assert (df["type"] == "PUT").sum() == 97, "Expected 97 puts"
    assert (df["type"] == "CALL").sum() == 142, "Expected 142 calls"

    required_cols = [
        "contractSymbol", "type", "strike", "tau_days", "partition", "market_last_price",
        "m1_eu_const_bs", "m2_am_const_1d", "m3_eu_heston", "m4_am_heston",
        "err_m4_usd", "abs_err_m4_usd", "eep_heston_usd"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column {col}"
        assert not df[col].isna().any(), f"Column {col} has NaN values"


def test_early_exercise_premium_consistency():
    """Verify that American option prices are >= European prices (EEP >= -1e-4) and call EEP == 0."""
    csv_path = Path("data/heston/phase6/models_comparison_detailed.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    puts = df[df["type"] == "PUT"]
    calls = df[df["type"] == "CALL"]

    # For puts: American Heston price must be >= European Heston price (EEP >= -1e-4)
    assert (puts["eep_heston_usd"] >= -1e-4).all(), (
        f"Some puts violate EEP non-negativity: {puts[puts['eep_heston_usd'] < -1e-4][['contractSymbol', 'eep_heston_usd']]}"
    )

    # For calls under q=0, r>=0: EEP must be exactly 0
    assert (calls["eep_heston_usd"].abs() < 1e-10).all(), "Calls must have exactly zero EEP"


def test_portfolio_valuation_and_delta_hedging():
    """Verify 5-leg portfolio valuation, Delta-neutral hedge position, and residual delta."""
    csv_path = Path("data/heston/phase6/portfolio_greeks_and_valuation.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 6, f"Expected 6 rows (5 options + 1 stock), got {len(df)}"

    stock_row = df[df["type"] == "STOCK"].iloc[0]
    opt_rows = df[df["type"] != "STOCK"]

    assert len(opt_rows) == 5, "Expected 5 option legs"
    assert stock_row["quantity"] < 0, "Stock hedge should be short shares"

    total_delta = df["position_delta"].sum()
    assert abs(total_delta) < 1.0, f"Net portfolio delta should be near-neutral: {total_delta}"


def test_finite_difference_step_stability():
    """Verify that finite difference Greek step sensitivity check passes within tolerance."""
    csv_path = Path("data/heston/phase6/portfolio_convergence_checks.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 2, "Expected 2 test legs"
    assert df["stable_step_discrepancy"].all(), "Step stability check failed"
    assert (df["diff_delta"] < 0.005).all(), "Delta difference between h and h/2 exceeds 0.005"
    assert (df["diff_gamma"] < 0.005).all(), "Gamma difference between h and h/2 exceeds 0.005"


def test_stress_testing_scenarios():
    """Verify the 6 stress scenarios, including exact null shock and non-linear Taylor divergence."""
    csv_path = Path("data/heston/phase6/portfolio_stress_scenarios.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    assert len(df) == 6, f"Expected 6 scenarios, got {len(df)}"

    # S0 null shock must yield exactly zero P&L
    s0 = df[df["scenario_id"] == "S0_Base_Null"].iloc[0]
    assert abs(s0["total_portfolio_pnl_reval_usd"]) < 1e-10, "Null scenario PnL must be 0"
    assert abs(s0["taylor_divergence_usd"]) < 1e-10, "Null scenario Taylor divergence must be 0"

    # S1 and S2 (small shocks) must have small Taylor divergence
    s1 = df[df["scenario_id"] == "S1_Spot_Down_5"].iloc[0]
    s2 = df[df["scenario_id"] == "S2_Spot_Up_5"].iloc[0]
    assert abs(s1["taylor_divergence_usd"]) < 10.0, "S1 Taylor divergence too high for small shock"
    assert abs(s2["taylor_divergence_usd"]) < 10.0, "S2 Taylor divergence too high for small shock"

    # S4 (severe crisis -20%) must exhibit non-linear divergence from Taylor
    s4 = df[df["scenario_id"] == "S4_Severe_Crisis"].iloc[0]
    assert s4["abs_taylor_divergence_usd"] > 15.0, "Severe crisis should demonstrate non-linear curvature"


def test_phase6_manifest_and_figures():
    """Verify that manifest and publication figures exist and are non-empty."""
    manifest_path = Path("data/heston/phase6/phase6_execution_manifest.json")
    assert manifest_path.exists()

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    assert manifest["phase"] == "PHASE_6"

    fig_dir = Path("figures/phase6")
    required_figures = [
        "models_comparison_errors_by_partition.png",
        "early_exercise_premium_profile.png",
        "portfolio_stress_pnl_profile.png",
        "stress_taylor_vs_revaluation.png"
    ]
    for fig_name in required_figures:
        fig_path = fig_dir / fig_name
        assert fig_path.exists(), f"Figure {fig_name} missing"
        assert fig_path.stat().st_size > 1000, f"Figure {fig_name} is empty"
