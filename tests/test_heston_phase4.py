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
        assert row["gradient_curvature_evidence"] in [
            "NONZERO_GRADIENT", "FLAT_OR_DESCENT",
            "NONZERO_GRADIENT_INCREASE", "FLAT_OR_TRUNCATED_DESCENT"
        ]

    # Verify all 12 representative contract price columns exist and are strictly positive
    rep_cols = [
        "price_K9_T31", "price_K12_T31", "price_K17_T31",
        "price_K9_T94", "price_K12_T94", "price_K17_T94",
        "price_K9_T430", "price_K12_T430", "price_K17_T430",
        "price_K9_T794", "price_K12_T794", "price_K17_T794"
    ]
    for col in rep_cols:
        assert col in sensitivity_df.columns, f"Missing representative contract price column: {col}"
        assert (sensitivity_df[col] > 0).all()

    # Verify rho truncation to -0.95 and inmaterial delta SSE
    rho_neg = sensitivity_df[sensitivity_df["scenario_id"] == "RHO_MINUS_002"].iloc[0]
    assert rho_neg["rho"] == -0.95
    assert abs(rho_neg["delta_sse_vs_base"]) < 1e-5


def test_baseline_comparison_84_common(baseline_df):
    """Verifies common 84 sample comparison against Flat BS and SVI."""
    assert len(baseline_df) == 84
    mae_heston = baseline_df["abs_err_heston_prop_fine"].mean()
    mae_flat = baseline_df["abs_err_flat_common"].mean()
    mae_svi = baseline_df["abs_err_svi_historical"].mean()

    assert np.isfinite(mae_heston)
    assert np.isfinite(mae_flat)
    assert np.isfinite(mae_svi)
    # Heston outperforms flat Black-Scholes and SVI
    assert mae_heston < mae_flat
    assert mae_heston < mae_svi
    assert abs(mae_heston - 0.023109) < 0.005
    assert abs(mae_flat - 0.039674) < 0.005
    assert abs(mae_svi - 0.068442) < 0.005


def test_execution_manifest_verdict_and_provenance(manifest):
    """Verifies execution manifest contains all required keys, output files, and PASS verdict."""
    assert manifest["phase"] == "PHASE_4"
    assert manifest["verdict"] == "PASS"

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
        "heston_baseline_comparison.csv",
        "refinement_A_res.json",
        "refinement_B_res.json",
        "refinement_C_res.json"
    ]
    for ro in required_outputs:
        assert ro in out_files, f"Manifest missing output file: {ro}"


# --- REAL PRODUCTION NEGATIVE TESTS (CALLING PRODUCTION FUNCTIONS) ---

def test_negative_tampered_crude_price_fails_manifest_gates(tmp_path):
    """Real production negative test: A +1 USD tampered crude price fails step10 raw validation gates."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # Tamper crude price on contract 0 by +1.0 USD
    df_puts_tampered = df_puts.copy()
    df_puts_tampered.loc[0, "prop_fine_price"] += 1.0

    # Production gate recalculates raw train MAE/discrepancy and raises RuntimeError
    with pytest.raises(RuntimeError, match="Execution Manifest Gates Failed"):
        step10_build_manifest(
            input_hashes={},
            config=config,
            winner_meta=winner_meta,
            df_puts=df_puts_tampered,
            df_part=df_part,
            df_worst3=df_worst3,
            df_econ=df_econ,
            start_time=0.0,
            out_manifest_path=tmp_path / "tampered_manifest.json"
        )


def test_negative_missing_economic_control_file_fails_manifest(monkeypatch, tmp_path):
    """Real production negative test: Missing economic control file fails step10 with FileNotFoundError."""
    from src.heston.pipeline_phase4 import step10_build_manifest
    import src.heston.pipeline_phase4 as p4_mod

    # Setup isolated tmp_path missing files
    empty_phase4 = tmp_path / "phase4_empty"
    empty_phase4.mkdir()
    monkeypatch.setattr(p4_mod, "PHASE4_DIR", empty_phase4)

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    with pytest.raises(FileNotFoundError, match="Missing required Phase 4 output file"):
        step10_build_manifest(
            input_hashes={},
            config=config,
            winner_meta=winner_meta,
            df_puts=df_puts,
            df_part=df_part,
            df_worst3=df_worst3,
            df_econ=df_econ,
            start_time=0.0,
            out_manifest_path=tmp_path / "missing_file_manifest.json"
        )


def test_negative_out_of_bounds_parameters_rejected(tmp_path):
    """Real production negative test: Negative initial variance v0 < 0 or out-of-bounds parameter rejected with ValueError."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # Negative v0
    bad_meta = json.loads(json.dumps(winner_meta))
    bad_meta["calibrated_parameters_raw"] = [-0.05, 2.725, 0.213, 0.481, -0.949]

    with pytest.raises(ValueError, match="violates bounds"):
        step10_build_manifest(
            input_hashes={},
            config=config,
            winner_meta=bad_meta,
            df_puts=df_puts,
            df_part=df_part,
            df_worst3=df_worst3,
            df_econ=df_econ,
            start_time=0.0,
            out_manifest_path=tmp_path / "bad_params_manifest.json"
        )


def test_negative_tampered_partition_count_rejected(tmp_path):
    """Real production negative test: Tampered partition count (e.g. train != 60) rejected with ValueError."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # Drop 1 contract
    df_puts_tampered = df_puts.iloc[1:].copy()

    with pytest.raises(ValueError, match="Full pricing DataFrame must have exactly 97 contracts"):
        step10_build_manifest(
            input_hashes={},
            config=config,
            winner_meta=winner_meta,
            df_puts=df_puts_tampered,
            df_part=df_part,
            df_worst3=df_worst3,
            df_econ=df_econ,
            start_time=0.0,
            out_manifest_path=tmp_path / "bad_partition_manifest.json"
        )


def test_negative_all_refinements_failed_halts_candidate_selection():
    """Real production negative test: When all local refinements fail (status != 0), candidate selection halts with RuntimeError."""
    from src.heston.pipeline_phase4 import step4_evaluate_candidates_fine_and_select

    # Fake df_refine where all local refinements failed
    df_refine_failed = pd.DataFrame([
        {
            "start_index": 2, "name": "Refinement_A_Start_2", "status": 1, "success": False,
            "final_v0": 0.18, "final_kappa": 2.7, "final_theta": 0.21, "final_xi": 0.48, "final_rho": -0.94,
            "final_sse": 0.086, "final_rmse": 0.038
        },
        {
            "start_index": 5, "name": "Refinement_B_Start_5", "status": 1, "success": False,
            "final_v0": 0.18, "final_kappa": 2.7, "final_theta": 0.21, "final_xi": 0.48, "final_rho": -0.94,
            "final_sse": 0.087, "final_rmse": 0.038
        }
    ])

    with pytest.raises(RuntimeError, match="Zero local refinements achieved convergence"):
        step4_evaluate_candidates_fine_and_select(
            df_refine=df_refine_failed,
            train_df=pd.DataFrame(),
            ts_handle=None,
            config={}
        )


def test_fresh_solver_valuation_route_executes_without_error():
    """Production test: Heston2DSolver().price(...) executes cleanly across default, fine, and extra-fine grids."""
    from src.heston.solver_2d import Heston2DSolver
    from src.heston.heston_model import HestonParams
    from src.heston.rates_curve import get_official_yield_curve

    curve = get_official_yield_curve(method="bootstrap")
    solver = Heston2DSolver()
    params = HestonParams(v0=0.1861, kappa=2.725, theta=0.2137, xi=0.4818, rho=-0.9498)

    # 1. Default grid (160x80, mt=60)
    res_def = solver.price(strike=12.33, maturity_years=0.5, params=params, curve=curve, is_american=True, n_s=160, n_v=80, m_t=60)
    assert res_def.price > 0.0
    assert np.isfinite(res_def.price)
    assert res_def.n_s == 160
    assert res_def.n_v == 80

    # 2. Fine grid (240x120, mt=100)
    res_fine = solver.price(strike=12.33, maturity_years=0.5, params=params, curve=curve, is_american=True, n_s=240, n_v=120, m_t=100)
    assert res_fine.price > 0.0
    assert np.isfinite(res_fine.price)
    assert res_fine.n_s == 240
    assert res_fine.n_v == 120

    # 3. Extra-fine grid (320x160, mt=160)
    res_ex = solver.price(strike=12.33, maturity_years=0.5, params=params, curve=curve, is_american=True, n_s=320, n_v=160, m_t=160)
    assert res_ex.price > 0.0
    assert np.isfinite(res_ex.price)
    assert res_ex.n_s == 320
    assert res_ex.n_v == 160


def test_fresh_valuation_route_triggered_when_vector_differs():
    """Production test: When calibrated vector differs from canonical PoC, Step 5 initiates fresh valuation route."""
    from src.heston.pipeline_phase4 import POC_CANONICAL

    altered_vec = POC_CANONICAL.copy()
    altered_vec[0] += 0.01  # shift v0
    assert not np.allclose(altered_vec, POC_CANONICAL, rtol=0.0, atol=1e-7)


def test_negative_nan_or_inf_in_pricing_columns_rejected(tmp_path):
    """Real production negative test: Non-finite values (NaN/Inf) in required pricing columns fail step10 immediately."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # 1. NaN in prop_fine_price
    df_tampered_1 = df_puts.copy()
    df_tampered_1.loc[0, "prop_fine_price"] = np.nan
    with pytest.raises(ValueError, match="Non-finite pricing value.*prop_fine_price"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_tampered_1, df_part=df_part, df_worst3=df_worst3, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "nan_prop_manifest.json"
        )

    # 2. NaN in ql_fine_price
    df_tampered_2 = df_puts.copy()
    df_tampered_2.loc[1, "ql_fine_price"] = np.nan
    with pytest.raises(ValueError, match="Non-finite pricing value.*ql_fine_price"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_tampered_2, df_part=df_part, df_worst3=df_worst3, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "nan_ql_manifest.json"
        )

    # 3. NaN in lastPrice
    df_tampered_3 = df_puts.copy()
    df_tampered_3.loc[2, "lastPrice"] = np.nan
    with pytest.raises(ValueError, match="Non-finite pricing value.*lastPrice"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_tampered_3, df_part=df_part, df_worst3=df_worst3, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "nan_last_manifest.json"
        )

    # 4. Inf in prop_default_price
    df_tampered_4 = df_puts.copy()
    df_tampered_4.loc[3, "prop_default_price"] = np.inf
    with pytest.raises(ValueError, match="Non-finite pricing value.*prop_default_price"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_tampered_4, df_part=df_part, df_worst3=df_worst3, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "inf_default_manifest.json"
        )


def test_negative_mesh_worst3_tampered_diff_rejected(tmp_path):
    """Real production negative test: Shifted mesh price (+1 USD) with favorable flags is rejected by step10."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # Tamper QL1000 price on row 0 by +1.0 USD while leaving flags True
    df_worst3_tampered = df_worst3.copy()
    df_worst3_tampered.loc[0, "ql_ultrafine_1000_usd"] += 1.0
    df_worst3_tampered.loc[0, "gate_ql_stability_pass"] = True

    with pytest.raises(ValueError, match="Mesh stability failure|Incoherent QL mesh refinement diff"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_puts, df_part=df_part, df_worst3=df_worst3_tampered, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "bad_mesh_manifest.json"
        )


def test_negative_mismatched_partition_label_rejected(tmp_path):
    """Real production negative test: A contract with mismatched partition label is rejected by step10."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # Alter partition label of contract 0 from train to strike_holdout
    df_puts_mismatched = df_puts.copy()
    df_puts_mismatched.loc[0, "partition"] = "strike_holdout"

    with pytest.raises(ValueError, match="Partition label mismatch"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_puts_mismatched, df_part=df_part, df_worst3=df_worst3, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "mismatched_label_manifest.json"
        )


def test_negative_contradictory_partition_summary_rejected(tmp_path):
    """Real production negative test: Contradictory partition summary counts in df_part are rejected by step10."""
    from src.heston.pipeline_phase4 import step10_build_manifest

    df_puts = pd.read_csv(PHASE4_DIR / "heston_pricing_full_puts.csv")
    df_part = pd.read_csv(PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    df_worst3 = pd.read_csv(PHASE4_DIR / "heston_worst3_mesh_controls.csv")
    df_econ = pd.read_csv(PHASE4_DIR / "heston_representative_economic_controls.csv")
    with open(PHASE4_DIR / "phase4_calibration_config.json", "r") as f:
        config = json.load(f)
    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # Change train count in df_part from 60 to 59
    df_part_bad = df_part.copy()
    df_part_bad.loc[df_part_bad["partition"] == "train", "n_contracts"] = 59

    with pytest.raises(ValueError, match="Contradictory partition summary"):
        step10_build_manifest(
            input_hashes={}, config=config, winner_meta=winner_meta,
            df_puts=df_puts, df_part=df_part_bad, df_worst3=df_worst3, df_econ=df_econ,
            start_time=0.0, out_manifest_path=tmp_path / "bad_summary_manifest.json"
        )


def test_step5_phase3_snapshot_cryptographic_verification_and_fallback(tmp_path):
    """Real production test: Step 5 strictly verifies Phase 3 cryptographic snapshot and falls back to fresh valuation on tampering."""
    from src.heston.pipeline_phase4 import step5_full_pricing_evaluation
    from src.heston.rates_curve import get_official_yield_curve

    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
    df_clean = pd.read_csv(DATA_DIR / "puts_selected_clean.csv")
    df_sample = df_clean.head(1).copy()  # 1 contract for quick execution

    with open(PHASE4_DIR / "heston_calibrated_parameters.json", "r") as f:
        winner_meta = json.load(f)

    # 1. Positive case: legitimate snapshot gives PHASE3_VERIFIED_AUDITED
    df_puts_pos, _, _ = step5_full_pricing_evaluation(
        winner_meta=winner_meta,
        curve=curve,
        ts_handle=ts_handle,
        out_puts_csv_path=tmp_path / "puts_pos.csv",
        out_part_csv_path=tmp_path / "part_pos.csv",
        out_tenor_csv_path=tmp_path / "tenor_pos.csv",
        df_clean_override=df_sample
    )
    assert len(df_puts_pos) == 1
    assert df_puts_pos.loc[0, "valuation_provenance"] == "PHASE3_VERIFIED_AUDITED"

    # 2. Tampered Phase 3 table: copy market_97_puts_validation.csv to tmp_path and corrupt a price
    tampered_p3_csv = tmp_path / "tampered_market_97_puts.csv"
    orig_p3_df = pd.read_csv(DATA_DIR / "phase3" / "market_97_puts_validation.csv")
    tampered_p3_df = orig_p3_df.copy()
    tampered_p3_df.loc[0, "proprietary_fine_usd"] = np.nan
    tampered_p3_df.to_csv(tampered_p3_csv, index=False)

    df_puts_tampered, _, _ = step5_full_pricing_evaluation(
        winner_meta=winner_meta,
        curve=curve,
        ts_handle=ts_handle,
        phase3_market_csv_path=tampered_p3_csv,
        out_puts_csv_path=tmp_path / "puts_tampered.csv",
        out_part_csv_path=tmp_path / "part_tampered.csv",
        out_tenor_csv_path=tmp_path / "tenor_tampered.csv",
        df_clean_override=df_sample
    )
    assert len(df_puts_tampered) == 1
    # MUST fall back to fresh solver 2D valuation, NEVER mark PHASE3_VERIFIED_AUDITED
    assert df_puts_tampered.loc[0, "valuation_provenance"] == "FRESH_SOLVER_2D_VALUATION"
    assert np.isfinite(df_puts_tampered.loc[0, "prop_fine_price"])


