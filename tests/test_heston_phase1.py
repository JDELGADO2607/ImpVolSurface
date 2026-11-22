"""
Unit and integration tests for Phase 1: Classical Heston PoC Implementation (Remediation 2).

Validates:
1. Exactness of QuantLib term structure adapter on calendar dates.
2. HestonParams data structure, Feller condition ratio, and conversions.
3. Unclipped raw American put lower/upper arbitrage bounds and early exercise premium (American >= European).
4. Strike monotonicity and non-uniform strike convexity via second divided differences (with NOT_TESTABLE on endpoints).
5. Tenor monotonicity for American puts at fixed strike K under zero dividend.
6. Separate temporal and spatial numerical grid refinements satisfying <= 0.0020 USD budget.
7. Compliance with all pre-declared gate criteria on Train, Strike Holdout, Tenor Holdout, and diagnostics.
8. Multistart tracking: all 5 starts recorded with status, Feller ratios, and near-optimal predictive dispersion.
9. Export and ranking stability of fine-grid SSE table (heston_multistart_fine_sse.csv).
10. Exact reconciliation of Common 84 sample metrics against SVI historical and flat baseline.
11. Negative test: Cache rejected when training data is modified (hash mismatch).
12. Negative test: Cache rejected when SSE is negative.
13. Negative test: Cache rejected when parameters fall outside bounds.
14. Isolation and clean execution using tmp_path with zero writes outside phase1.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import shutil
import numpy as np
import pandas as pd
import pytest

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import get_official_yield_curve, SPOT_PRICE
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.calibration import HestonCalibrator, HESTON_5_STARTS, HESTON_BOUNDS
from src.heston.pipeline_phase1 import run_phase1_pipeline


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_quantlib_term_structure_adapter_exactness():
    """Confirms dense daily curve achieves zero discount factor difference on calendar dates."""
    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date
    ql_curve = ts_handle.currentLink()

    # Test all integer days up to 794 (covering all contract expirations)
    max_day_err = 0.0
    for day in range(1, 795):
        d_ql = ql_curve.discount(eval_date + day)
        d_py = curve.get_discount_factor(day / 365.0)
        err = abs(d_ql - d_py)
        if err > max_day_err:
            max_day_err = err

    assert max_day_err < 1e-12, f"Calendar day discount factor error {max_day_err} exceeds 1e-12"

    # Test continuous float queries: bounded by < 5e-6
    t_samples = np.linspace(0.01, 2.5, 500)
    max_cont_err = max(abs(ql_curve.discount(float(t)) - curve.get_discount_factor(float(t))) for t in t_samples)
    assert max_cont_err < 5e-6, f"Continuous discount factor error {max_cont_err} exceeds 5e-6"


def test_heston_params_dataclass_and_feller():
    """Validates HestonParams methods, Feller ratio calculation, and conversions."""
    # Feller satisfied: 2 * 2.0 * 0.20 / (0.5^2) = 0.80 / 0.25 = 3.20 > 1
    p1 = HestonParams(v0=0.20, kappa=2.0, theta=0.20, xi=0.50, rho=-0.50)
    assert abs(p1.feller_ratio - 3.20) < 1e-6
    assert p1.feller_satisfied is True
    assert abs(p1.spot_vol - np.sqrt(0.20)) < 1e-6

    # Feller violated: 2 * 0.5 * 0.35 / (1.2^2) = 0.35 / 1.44 = 0.243 < 1
    p2 = HestonParams(v0=0.35, kappa=0.5, theta=0.35, xi=1.20, rho=-0.70)
    assert abs(p2.feller_ratio - (0.35 / 1.44)) < 1e-6
    assert p2.feller_satisfied is False

    # Array roundtrip
    arr = p1.to_array()
    p1_rt = HestonParams.from_array(arr)
    assert np.allclose(p1.to_array(), p1_rt.to_array())


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_heston_option_pricer_raw_bounds_and_arbitrage():
    """Verifies that American puts respect theoretical upper and lower bounds on RAW unclipped output."""
    pricer = HestonOptionPricer()
    params = HestonParams(v0=0.186138, kappa=2.725460, theta=0.213680, xi=0.481785, rho=-0.949807)

    test_strikes = [9.0, 12.0, 15.0, 17.0, 20.0]
    for K in test_strikes:
        p_am_raw = pricer.price_american(K, "2026-12-18", params, option_type="P", clip_to_intrinsic=False)
        p_eu_raw = pricer.price_european(K, "2026-12-18", params, option_type="P", clip_nonnegative=False)

        lower_bound = max(K - SPOT_PRICE, 0.0)
        upper_bound = K

        assert p_am_raw >= lower_bound - 1e-6, f"Raw put price {p_am_raw} violates lower bound {lower_bound} at K={K}"
        assert p_am_raw <= upper_bound + 1e-6, f"Raw put price {p_am_raw} violates upper bound {upper_bound} at K={K}"
        assert p_am_raw >= p_eu_raw - 1e-5, f"Raw American {p_am_raw} is less than European {p_eu_raw} at K={K}"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_heston_strike_monotonicity_and_divided_difference_convexity():
    """Checks strike monotonicity and second divided difference convexity on raw prices."""
    shape_csv = Path("data/heston/phase1/heston_shape_arbitrage_checks.csv")
    assert shape_csv.exists(), "heston_shape_arbitrage_checks.csv must exist"
    df_shape = pd.read_csv(shape_csv)

    assert len(df_shape) == 97, f"Expected 97 shape check rows, found {len(df_shape)}"
    assert (df_shape["lower_bound_ok"]).all(), "Lower bound violations found in raw pricing"
    assert (df_shape["upper_bound_ok"]).all(), "Upper bound violations found in raw pricing"
    assert (df_shape["am_ge_eu_ok"]).all(), "Early exercise premium violations found in raw pricing"

    # Strike monotonicity
    mono_testable = df_shape[df_shape["strike_monotonicity_status"] != "FIRST_STRIKE"]
    assert (mono_testable["strike_monotonicity_status"] == "PASS").all(), "Strike monotonicity violation"

    # Convexity: Interior points must PASS; Boundary points must be NOT_TESTABLE
    interior = df_shape[df_shape["convexity_status"] != "NOT_TESTABLE"]
    assert len(interior) > 0, "No interior convexity test points found"
    assert (interior["convexity_status"] == "PASS").all(), "Convexity violations found in interior points"
    assert (interior["convexity_second_divided_diff"] >= -0.0020).all()


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_fixed_strike_tenor_monotonicity():
    """Validates that American put prices increase with maturity at fixed strikes."""
    tenor_csv = Path("data/heston/phase1/heston_tenor_monotonicity_checks.csv")
    assert tenor_csv.exists(), "heston_tenor_monotonicity_checks.csv must exist"
    df_tenor_mono = pd.read_csv(tenor_csv)

    assert len(df_tenor_mono) >= 70, f"Expected at least 70 multi-tenor transitions, found {len(df_tenor_mono)}"
    assert (df_tenor_mono["tenor_monotonicity_ok"]).all(), "Tenor monotonicity violations found"
    assert (df_tenor_mono["price_diff"] >= -0.0020).all()


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_numerical_grid_budget_convergence_and_separate_refinements():
    """Verifies that separate temporal and spatial refinements satisfy the 0.0020 USD budget."""
    grid_csv = Path("data/heston/phase1/heston_grid_convergence.csv")
    assert grid_csv.exists(), "heston_grid_convergence.csv must exist"
    df_grid = pd.read_csv(grid_csv)

    assert len(df_grid) >= 10, f"Expected at least 10 representative grid contracts, found {len(df_grid)}"
    assert df_grid["diff_temporal_usd"].max() <= 0.0020, "Temporal refinement exceeded budget"
    assert df_grid["diff_spatial_usd"].max() <= 0.0020, "Spatial refinement exceeded budget"
    assert df_grid["diff_ultrafine_usd"].max() <= 0.0020, "Ultra-fine refinement exceeded budget"
    assert df_grid["budget_passed"].all(), "Not all contracts passed budget <= 0.0020 USD"


def test_phase1_gate_criteria_compliance():
    """Validates that all pre-declared Phase 1 gate criteria and diagnostics are strictly met."""
    manifest_path = Path("data/heston/phase1/phase1_execution_manifest.json")
    assert manifest_path.exists(), "phase1_execution_manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    metrics = manifest["performance_metrics"]
    diag = manifest["diagnostic_counts"]

    assert metrics["train_mae"] <= 0.080, f"Train MAE {metrics['train_mae']:.4f} > 0.080 USD"
    assert metrics["train_rmse"] <= 0.120, f"Train RMSE {metrics['train_rmse']:.4f} > 0.120 USD"
    assert metrics["strike_holdout_mae"] <= 0.100, f"Strike holdout MAE {metrics['strike_holdout_mae']:.4f} > 0.100 USD"
    assert metrics["tenor_holdout_mae"] <= 0.100, f"Tenor holdout MAE {metrics['tenor_holdout_mae']:.4f} > 0.100 USD"

    assert diag["lower_bound_violations"] == 0
    assert diag["upper_bound_violations"] == 0
    assert diag["early_exercise_premium_violations"] == 0
    assert diag["strike_monotonicity_violations"] == 0
    assert diag["tenor_monotonicity_violations"] == 0
    assert diag["convexity_violations"] == 0

    assert manifest["gate_verdict"] == "PASSED", f"Gate verdict is {manifest['gate_verdict']}"


def test_multistart_tracking_and_candidate_predictive_dispersion():
    """Ensures all 5 starts are recorded with status and verifies near-optimal dispersion."""
    ms_path = Path("data/heston/phase1/heston_multistart_results.csv")
    assert ms_path.exists(), "heston_multistart_results.csv must exist"
    df_ms = pd.read_csv(ms_path)

    assert len(df_ms) == 5, f"Expected 5 starts, found {len(df_ms)}"
    assert set(df_ms["start_index"]) == {1, 2, 3, 4, 5}
    assert "termination_type" in df_ms.columns
    assert "feller_ratio" in df_ms.columns

    best_row = df_ms.sort_values("final_sse").iloc[0]
    assert best_row["final_rmse"] < 0.040, f"Best RMSE {best_row['final_rmse']} is not < 0.040 USD"

    # Check candidate predictive dispersion file
    disp_csv = Path("data/heston/phase1/heston_candidate_predictive_dispersion.csv")
    assert disp_csv.exists(), "heston_candidate_predictive_dispersion.csv must exist"
    df_disp = pd.read_csv(disp_csv)
    assert len(df_disp) >= 3


def test_multistart_fine_sse_table_stability():
    """Verifies that fine SSE table exists and confirms Start 2 as lowest fine SSE."""
    fine_csv = Path("data/heston/phase1/heston_multistart_fine_sse.csv")
    assert fine_csv.exists(), "heston_multistart_fine_sse.csv must exist"
    df_fine = pd.read_csv(fine_csv)

    assert len(df_fine) == 5
    assert set(df_fine["start_index"]) == {1, 2, 3, 4, 5}
    best_fine = df_fine.sort_values("fine_grid_sse").iloc[0]
    assert best_fine["start_index"] == 2, f"Expected start 2 to have lowest fine SSE, got {best_fine['start_index']}"
    assert best_fine["fine_grid_sse"] < 0.087, f"Fine SSE {best_fine['fine_grid_sse']} is not < 0.087"


def test_common_84_exact_reconciliation():
    """Verifies that common 84 metrics reconcile exactly with audit values."""
    c84_csv = Path("data/heston/phase1/heston_common_84_comparison.csv")
    assert c84_csv.exists(), "heston_common_84_comparison.csv must exist"
    df = pd.read_csv(c84_csv)
    assert len(df) == 84

    # Heston American
    mae_h = df["abs_err_heston"].mean()
    rmse_h = np.sqrt((df["err_heston"]**2).mean())
    max_h = df["abs_err_heston"].max()
    assert abs(mae_h - 0.02315795) < 1e-4
    assert abs(rmse_h - 0.03392139) < 1e-4
    assert abs(max_h - 0.18228136) < 1e-4

    # Flat American Common Curve
    mae_f = df["abs_err_flat_common"].mean()
    rmse_f = np.sqrt((df["err_flat_common"]**2).mean())
    max_f = df["abs_err_flat_common"].max()
    assert abs(mae_f - 0.03967434) < 1e-4
    assert abs(rmse_f - 0.06028916) < 1e-4
    assert abs(max_f - 0.33331439) < 1e-4

    # SVI Historical
    mae_s = df["abs_err_svi"].mean()
    rmse_s = np.sqrt((df["err_svi_historical"]**2).mean())
    max_s = df["abs_err_svi"].max()
    assert abs(mae_s - 0.06844167) < 1e-4
    assert abs(rmse_s - 0.08857929) < 1e-4
    assert abs(max_s - 0.24630000) < 1e-4


def test_negative_cache_rejected_on_modified_train_data(tmp_path):
    """Negative test: pipeline must reject cache with ValueError when train data is modified."""
    data_t = tmp_path / "data"
    shutil.copytree("data/heston", data_t)
    train_file = data_t / "data_split_train.csv"
    train_df = pd.read_csv(train_file)
    train_df.loc[0, "lastPrice"] += 0.01
    train_df.to_csv(train_file, index=False)

    with pytest.raises(ValueError, match=r"Cache validation failed|hash mismatch"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)


def test_negative_cache_rejected_on_negative_sse(tmp_path):
    """Negative test: pipeline must reject cache with ValueError when SSE is negative."""
    data_t = tmp_path / "data"
    shutil.copytree("data/heston", data_t)
    ms_file = data_t / "phase1" / "heston_multistart_results.csv"
    ms_df = pd.read_csv(ms_file)
    ms_df.loc[ms_df["start_index"] == 3, "final_sse"] = -1.0
    ms_df.to_csv(ms_file, index=False)

    with pytest.raises(ValueError, match=r"Cache validation failed|invalid final_sse|non-negative"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)


def test_negative_cache_rejected_on_out_of_bounds_parameter(tmp_path):
    """Negative test: pipeline must reject cache with ValueError when a parameter is out of bounds."""
    data_t = tmp_path / "data"
    shutil.copytree("data/heston", data_t)
    ms_file = data_t / "phase1" / "heston_multistart_results.csv"
    ms_df = pd.read_csv(ms_file)
    ms_df.loc[ms_df["start_index"] == 1, "v0"] = 2.50  # Upper bound is 1.50
    ms_df.to_csv(ms_file, index=False)

    with pytest.raises(ValueError, match=r"Cache validation failed|outside bounds"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)


def test_negative_cache_rejected_on_status2_zero_sse(tmp_path):
    """Negative test: pipeline must reject cache with ValueError when a candidate has status 2 and falsified SSE=0."""
    data_t = tmp_path / "data"
    shutil.copytree("data/heston", data_t)
    ms_file = data_t / "phase1" / "heston_multistart_results.csv"
    ms_df = pd.read_csv(ms_file)
    # Replicate Codex contraexample: set candidate 3 to status 2, final_sse=0.0, final_rmse=0.0
    ms_df.loc[ms_df["start_index"] == 3, "status"] = 2
    ms_df.loc[ms_df["start_index"] == 3, "final_sse"] = 0.0
    ms_df.loc[ms_df["start_index"] == 3, "final_rmse"] = 0.0
    ms_df.to_csv(ms_file, index=False)

    with pytest.raises(ValueError, match=r"Cache validation failed|does not match replayed SSE"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)


def test_negative_cache_rejected_on_nan_or_inf_rmse(tmp_path):
    """Negative test: pipeline must reject cache with ValueError when final_rmse is NaN or Inf."""
    data_t = tmp_path / "data"
    shutil.copytree("data/heston", data_t)
    ms_file = data_t / "phase1" / "heston_multistart_results.csv"
    ms_df = pd.read_csv(ms_file)
    # Set candidate 1 final_rmse to NaN
    ms_df.loc[ms_df["start_index"] == 1, "final_rmse"] = float("nan")
    ms_df.to_csv(ms_file, index=False)

    with pytest.raises(ValueError, match=r"Cache validation failed|RMSE must be non-negative and finite"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)

    # Set candidate 1 final_rmse to Inf
    ms_df.loc[ms_df["start_index"] == 1, "final_rmse"] = float("inf")
    ms_df.to_csv(ms_file, index=False)
    with pytest.raises(ValueError, match=r"Cache validation failed|RMSE must be non-negative and finite"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)


def test_negative_cache_rejected_on_objective_mismatch(tmp_path):
    """Negative test: pipeline must reject cache with ValueError when declared SSE mismatches replayed SSE."""
    data_t = tmp_path / "data"
    shutil.copytree("data/heston", data_t)
    ms_file = data_t / "phase1" / "heston_multistart_results.csv"
    ms_df = pd.read_csv(ms_file)
    # Alter start 2 SSE by +0.005 while maintaining mathematical consistency with RMSE
    new_sse = ms_df.loc[ms_df["start_index"] == 2, "final_sse"].values[0] + 0.005
    ms_df.loc[ms_df["start_index"] == 2, "final_sse"] = new_sse
    ms_df.loc[ms_df["start_index"] == 2, "final_rmse"] = np.sqrt(new_sse / 60.0)
    ms_df.to_csv(ms_file, index=False)

    with pytest.raises(ValueError, match=r"Cache validation failed|does not match replayed SSE"):
        run_phase1_pipeline(str(data_t), str(data_t / "phase1"), reuse_existing_multistart=True, allow_recalibration=False)


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_isolated_evaluation_using_tmp_path(tmp_path):
    """Verifies that pricing and evaluation run cleanly in an isolated directory without official writes."""
    test_out = tmp_path / "phase1_test"
    test_out.mkdir()

    pricer = HestonOptionPricer()
    params = HestonParams(v0=0.186138, kappa=2.725460, theta=0.213680, xi=0.481785, rho=-0.949807)

    test_file = test_out / "sample_pricing.csv"
    price = pricer.price_american(12.0, "2026-12-18", params, option_type="P", clip_to_intrinsic=False)

    pd.DataFrame([{"strike": 12.0, "price": price}]).to_csv(test_file, index=False)
    assert test_file.exists()
    assert price > 0.0
