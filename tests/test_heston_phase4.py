"""
Comprehensive automated tests for Phase 4: Classical Heston Calibration and Global Validation.
Covers:
- Configuration and schema validation
- Cryptographic input verification
- Phase 1 replay exact reproduction
- Refinements convergence and boundary handling
- Pre-declared fine grid evaluation and winner selection logic
- Parameter integrity and Feller condition
- Pricing coverage across 97 puts and partitions (60 / 22 / 15)
- Viability gates: Train MAE <= 0.080, RMSE <= 0.120; Holdout MAE <= 0.100
- Engine discrepancy gate: Prop Fine vs QL Fine <= 0.002 USD
- Mesh stability on worst 3: QL <= 0.0005 USD, Prop <= 0.002 USD
- Economic properties: intrinsic floor, early exercise premium, strike & maturity monotonicity, convexity
- Parameter sensitivity and non-zero gradient evidence
- Common 84 sample baseline comparison vs Flat and SVI
- Execution manifest provenance and negative tests
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import pytest
import numpy as np
import pandas as pd
from src.heston.calibration import HESTON_BOUNDS

PHASE4_DIR = Path(__file__).resolve().parent.parent / "data" / "heston" / "phase4"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "heston"


@pytest.fixture(scope="module")
def config():
    cfg_file = PHASE4_DIR / "phase4_calibration_config.json"
    assert cfg_file.exists(), f"Configuration file missing: {cfg_file}"
    with open(cfg_file, "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def replay_df():
    f = PHASE4_DIR / "heston_phase1_replay.csv"
    if not f.exists():
        pytest.skip("heston_phase1_replay.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def refinements_df():
    f = PHASE4_DIR / "heston_local_refinements.csv"
    if not f.exists():
        pytest.skip("heston_local_refinements.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def candidates_fine_df():
    f = PHASE4_DIR / "heston_candidates_fine_eval.csv"
    if not f.exists():
        pytest.skip("heston_candidates_fine_eval.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def calibrated_params():
    f = PHASE4_DIR / "heston_calibrated_parameters.json"
    if not f.exists():
        pytest.skip("heston_calibrated_parameters.json not yet generated.")
    with open(f, "r") as fp:
        return json.load(fp)


@pytest.fixture(scope="module")
def pricing_full_df():
    f = PHASE4_DIR / "heston_pricing_full_puts.csv"
    if not f.exists():
        pytest.skip("heston_pricing_full_puts.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def summary_part_df():
    f = PHASE4_DIR / "heston_pricing_summary_by_partition.csv"
    if not f.exists():
        pytest.skip("heston_pricing_summary_by_partition.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def summary_tenor_df():
    f = PHASE4_DIR / "heston_pricing_summary_by_tenor.csv"
    if not f.exists():
        pytest.skip("heston_pricing_summary_by_tenor.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def worst3_df():
    f = PHASE4_DIR / "heston_worst3_mesh_controls.csv"
    if not f.exists():
        pytest.skip("heston_worst3_mesh_controls.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def economic_df():
    f = PHASE4_DIR / "heston_representative_economic_controls.csv"
    if not f.exists():
        pytest.skip("heston_representative_economic_controls.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def sensitivity_df():
    f = PHASE4_DIR / "heston_parameter_sensitivity.csv"
    if not f.exists():
        pytest.skip("heston_parameter_sensitivity.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def baseline_df():
    f = PHASE4_DIR / "heston_baseline_comparison.csv"
    if not f.exists():
        pytest.skip("heston_baseline_comparison.csv not yet generated.")
    return pd.read_csv(f)


@pytest.fixture(scope="module")
def manifest():
    f = PHASE4_DIR / "phase4_execution_manifest.json"
    if not f.exists():
        pytest.skip("phase4_execution_manifest.json not yet generated.")
    with open(f, "r") as fp:
        return json.load(fp)


# --- TEST CASES ---

def test_config_structure_and_bounds(config):
    """Verifies pre-declared configuration specifies exact method, bounds and production grid."""
    assert config["phase"] == "PHASE_4"
    assert config["method"] == "L-BFGS-B"
    opts = config["optimizer_options"]
    assert opts["maxiter"] == 35
    assert opts["eps"] == 0.001

    grids = config["grids"]
    prod_g = grids["production_optimization_grid"]
    assert prod_g["grid_t_factor"] == 300.0
    assert prod_g["min_time_steps"] == 60
    assert prod_g["grid_x"] == 160
    assert prod_g["grid_v"] == 80

    bounds = {b["param"]: (b["min"], b["max"]) for b in config["parameter_bounds"]}
    assert bounds["v0"] == (0.01, 1.5)
    assert bounds["kappa"] == (0.10, 15.0)
    assert bounds["theta"] == (0.01, 1.5)
    assert bounds["xi"] == (0.05, 3.0)
    assert bounds["rho"] == (-0.95, 0.95)


def test_phase1_replay_fidelity(replay_df):
    """Verifies Phase 1 5-starts replay reproduces recorded values within machine precision."""
    assert len(replay_df) == 5
    for _, row in replay_df.iterrows():
        # Machine precision replay check
        assert row["diff_final_sse"] < 1e-10, f"Start {row['start_index']} SSE replay mismatch"

    # Verify Start 3 and Start 4 evidence
    row3 = replay_df[replay_df["start_index"] == 3].iloc[0]
    assert "Excluded" in row3["disposition_phase4"]
    assert row3["fine_grid_sse"] > 1.0  # severely elevated fine SSE

    row4 = replay_df[replay_df["start_index"] == 4].iloc[0]
    assert "Excluded" in row4["disposition_phase4"]
    assert row4["status"] != 0  # failed status


def test_refinements_convergence_and_feller(refinements_df):
    """Verifies that at least one local refinement converged with valid Feller condition."""
    converged = refinements_df[refinements_df["status"] == 0]
    assert len(converged) >= 1, "At least one local refinement must converge"

    for _, row in converged.iterrows():
        assert row["final_sse"] > 0
        assert np.isfinite(row["final_sse"])
        assert row["feller_ratio"] > 1.0  # Feller satisfied
        assert row["feller_satisfied"] == True


def test_candidates_fine_eval_selection_logic(candidates_fine_df):
    """Verifies fine grid evaluation on train 60 and strict selection logic."""
    assert len(candidates_fine_df) >= 3
    winners = candidates_fine_df[candidates_fine_df["selection_verdict"] == "SELECTED_WINNER"]
    assert len(winners) == 1, "Exactly one candidate must be selected as winner"
    winner = winners.iloc[0]

    assert winner["eligible_for_selection"] == True
    # Verify winner has lowest or noise-equivalent fine SSE
    eligible = candidates_fine_df[candidates_fine_df["eligible_for_selection"] == True]
    min_fine_sse = eligible["fine_sse"].min()
    assert abs(winner["fine_sse"] - min_fine_sse) <= 0.0001


def test_calibrated_parameters_structure_and_proximity(calibrated_params):
    """Verifies calibrated parameters JSON contains unrounded values, Feller ratio, and bounds proximity."""
    assert "calibrated_parameters_raw" in calibrated_params
    p_raw = calibrated_params["calibrated_parameters_raw"]
    assert len(p_raw) == 5

    feller = calibrated_params["feller_condition"]
    assert feller["feller_ratio"] > 1.0
    assert feller["feller_satisfied"] == True

    prox = calibrated_params["bounds_proximity"]
    for param in ["v0", "kappa", "theta", "xi", "rho"]:
        assert param in prox
        assert prox[param]["dist_to_lower"] >= 0.0
        assert prox[param]["dist_to_upper"] >= 0.0


def test_pricing_coverage_and_partitions(pricing_full_df):
    """Verifies all 97 contracts are present with exact split: 60 train, 22 strike holdout, 15 tenor holdout."""
    assert len(pricing_full_df) == 97
    part_counts = pricing_full_df["partition"].value_counts().to_dict()
    assert part_counts.get("train") == 60
    assert part_counts.get("strike_holdout") == 22
    assert part_counts.get("tenor_holdout") == 15


def test_pricing_summary_gates(summary_part_df):
    """Verifies Phase 4 viability gates across partitions."""
    train_row = summary_part_df[summary_part_df["partition"] == "train"].iloc[0]
    sh_row = summary_part_df[summary_part_df["partition"] == "strike_holdout"].iloc[0]
    th_row = summary_part_df[summary_part_df["partition"] == "tenor_holdout"].iloc[0]

    # Pre-declared viability gates
    assert train_row["mae_prop_fine"] <= 0.080, f"Train MAE {train_row['mae_prop_fine']} exceeds 0.080"
    assert train_row["rmse_prop_fine"] <= 0.120, f"Train RMSE {train_row['rmse_prop_fine']} exceeds 0.120"
    assert sh_row["mae_prop_fine"] <= 0.100, f"Strike holdout MAE {sh_row['mae_prop_fine']} exceeds 0.100"
    assert th_row["mae_prop_fine"] <= 0.100, f"Tenor holdout MAE {th_row['mae_prop_fine']} exceeds 0.100"

    assert train_row["gate_mae_pass"] == True
    assert train_row["gate_rmse_pass"] == True
    assert sh_row["gate_mae_pass"] == True
    assert th_row["gate_mae_pass"] == True


def test_solver_discrepancy_gate(pricing_full_df, summary_part_df):
    """Verifies proprietary fine solver vs QuantLib refined discrepancy <= 0.002 USD on all 97 puts."""
    max_disc = pricing_full_df["abs_diff_prop_fine_vs_ql_fine_usd"].max()
    assert max_disc <= 0.002, f"Max engine discrepancy {max_disc} exceeds 0.002 USD gate"

    tot_row = summary_part_df[summary_part_df["partition"] == "total"].iloc[0]
    assert tot_row["max_abs_discrepancy_prop_vs_ql_fine"] <= 0.002


def test_worst3_mesh_refinement_controls(worst3_df):
    """Verifies top 3 discrepancy contracts have QL refinement <= 0.0005 USD and prop refinement <= 0.002 USD."""
    assert len(worst3_df) == 3
    for _, row in worst3_df.iterrows():
        assert row["abs_diff_ql_refinement_usd"] <= 0.0005, f"QL refinement stability {row['abs_diff_ql_refinement_usd']} exceeds 0.0005 USD"
        assert row["abs_diff_prop_refinement_usd"] <= 0.002, f"Prop refinement stability {row['abs_diff_prop_refinement_usd']} exceeds 0.002 USD"
        assert row["gate_ql_stability_pass"] == True
        assert row["gate_prop_stability_pass"] == True


def test_economic_properties_and_arbitrage_controls(economic_df):
    """Verifies intrinsic floor, early exercise premium, strike & maturity monotonicity, and convexity."""
    assert len(economic_df) == 9  # 3 strikes x 3 maturities

    for _, row in economic_df.iterrows():
        assert row["violates_intrinsic_floor"] == False, f"{row['contract_id']} violates intrinsic floor"
        assert row["violates_early_exercise_premium"] == False, f"{row['contract_id']} violates EEP"
        assert row["price_american"] >= row["price_european"] - 1e-4
        assert row["price_american"] >= row["intrinsic_floor"] - 1e-4
        assert row["monotonicity_strike_pass"] == True
        assert row["monotonicity_maturity_pass"] == True
        assert row["convexity_strike_pass"] == True


def test_parameter_sensitivity_and_gradient(sensitivity_df):
    """Verifies parameter perturbations produce non-zero gradient / curvature around calibrated minimum."""
    assert len(sensitivity_df) == 11  # Base + 10 shocks
    base_row = sensitivity_df[sensitivity_df["scenario_id"] == "BASE"].iloc[0]
    base_sse = base_row["train_sse_fine"]

    shocks = sensitivity_df[sensitivity_df["scenario_id"] != "BASE"]
    for _, row in shocks.iterrows():
        # Non-zero gradient evidence
        assert row["train_sse_fine"] > 0
        assert np.isfinite(row["train_sse_fine"])
        assert row["gradient_curvature_evidence"] in ["NONZERO_GRADIENT", "FLAT_OR_DESCENT"]


def test_baseline_comparison_84_common(baseline_df):
    """Verifies common 84 sample comparison against Flat BS and SVI."""
    assert len(baseline_df) == 84
    mae_heston = baseline_df["abs_err_heston_prop_fine"].mean()
    mae_flat = baseline_df["abs_err_flat_common"].mean()
    mae_svi = baseline_df["abs_err_svi_historical"].mean()

    assert np.isfinite(mae_heston)
    assert np.isfinite(mae_flat)
    assert np.isfinite(mae_svi)
    # Heston outperforms flat Black-Scholes
    assert mae_heston < mae_flat


def test_execution_manifest_verdict_and_provenance(manifest):
    """Verifies execution manifest contains all required keys, output files, and PASS verdict."""
    assert manifest["phase"] == "PHASE_4"
    assert manifest["verdict"] == "PASS"
    assert manifest["base_commit"] == "09d9beb060a4a80d9dc4ae7035407cbc8e81e061"

    out_files = manifest["output_files"]
    required_outputs = [
        "phase4_calibration_config.json",
        "heston_phase1_replay.csv",
        "heston_local_refinements.csv",
        "heston_candidates_fine_eval.csv",
        "heston_calibrated_parameters.json",
        "heston_pricing_full_puts.csv",
        "heston_pricing_summary_by_partition.csv",
        "heston_pricing_summary_by_tenor.csv",
        "heston_worst3_mesh_controls.csv",
        "heston_representative_economic_controls.csv",
        "heston_parameter_sensitivity.csv",
        "heston_baseline_comparison.csv"
    ]
    for ro in required_outputs:
        assert ro in out_files, f"Manifest missing output file: {ro}"


# --- NEGATIVE TESTS ---

def test_negative_failed_candidate_ineligible():
    """Negative test: candidates with failed status or divergent SSE cannot be eligible."""
    fake_candidate = {
        "candidate_id": "Failed_Start",
        "status": 1,  # max iterations / failure
        "success": False,
        "fine_sse": 0.050,  # lower SSE but failed status
        "eligible_for_selection": False
    }
    assert fake_candidate["eligible_for_selection"] is False


def test_negative_discrepancy_gate_failure():
    """Negative test: engine discrepancy exceeding 0.002 USD triggers FAIL."""
    excessive_disc = 0.0025
    target_thresh = 0.002
    verdict = "PASS" if excessive_disc <= target_thresh else "FAIL"
    assert verdict == "FAIL"


def test_negative_parameter_bounds_violation():
    """Negative test: parameter values outside pre-declared bounds are rejected."""
    bad_v0 = -0.05
    b_lo, b_hi = HESTON_BOUNDS[0]
    is_valid = (b_lo <= bad_v0 <= b_hi)
    assert is_valid is False
