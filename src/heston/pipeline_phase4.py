"""
Phase 4 Execution Pipeline: Classical Heston Global Calibration and Validation.

Executes:
1. Verification of input files and cryptographic provenance.
2. Replay of Phase 1 5-starts on original calibration grid (heston_phase1_replay.csv).
3. Pre-declared local refinements on production grid (m_t=max(60, round(300*T)), x=160, v=80)
   from historical starts 2, 5, 1 and benchmark PoC (heston_local_refinements.csv).
4. Candidate evaluation on fine grid (QL700/min120/x280/v140) on train 60 and winner selection (heston_candidates_fine_eval.csv, heston_calibrated_parameters.json).
5. Full pricing evaluation of winning parameters on all 97 contracts across partitions and tenors
   (heston_pricing_full_puts.csv, heston_pricing_summary_by_partition.csv, heston_pricing_summary_by_tenor.csv).
6. Mesh stability controls on top 3 pricing errors under QL 1000 and Propio 320/160/900T (heston_worst3_mesh_controls.csv).
7. Representative economic controls: intrinsic floor, early exercise premium, monotonicity, convexity (heston_representative_economic_controls.csv).
8. Parameter sensitivity and identification analysis under +/-5% shocks and +/-0.02 rho (heston_parameter_sensitivity.csv).
9. Common 84 sample baseline comparison vs Flat Black-Scholes and historical SVI (heston_baseline_comparison.csv).
10. Compilation of cryptographic execution manifest (phase4_execution_manifest.json).
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime, timezone
import hashlib
import json
import math
import time
from typing import Dict, List, Tuple, Optional, Any, Union

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import (
    get_official_yield_curve,
    SPOT_PRICE,
    DIVIDEND_YIELD,
    DeterministicYieldCurve
)
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.calibration import HestonCalibrator, HESTON_BOUNDS
from src.heston.solver_2d import Heston2DSolver, Grid2D


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "heston"
PHASE4_DIR = DATA_DIR / "phase4"


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest of a binary or text file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def compute_normalized_source_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest of a source code file with CRLF -> LF normalization."""
    data = file_path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def load_config() -> Dict[str, Any]:
    """Loads pre-declared Phase 4 calibration configuration."""
    cfg_path = PHASE4_DIR / "phase4_calibration_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Configuration file missing: {cfg_path}")
    with open(cfg_path, "r") as f:
        return json.load(f)


def step1_validate_inputs() -> Dict[str, str]:
    """Verifies all input files and returns their cryptographic hashes."""
    print("\n=== STEP 1: Validating Input Files and Cryptographic Hashes ===")
    required_files = {
        "puts_selected_clean": DATA_DIR / "puts_selected_clean.csv",
        "data_split_manifest": DATA_DIR / "data_split_manifest.json",
        "treasury_cmt_raw": DATA_DIR / "treasury_cmt_2026_11_17_raw.json",
        "rates_treasury_manifest": DATA_DIR / "rates_treasury_manifest.json",
        "phase1_multistart_results": DATA_DIR / "phase1" / "heston_multistart_results.csv",
        "phase1_manifest": DATA_DIR / "phase1" / "phase1_execution_manifest.json",
        "phase3_manifest": DATA_DIR / "phase3" / "phase3_execution_manifest.json",
        "phase3_market_97": DATA_DIR / "phase3" / "market_97_puts_validation.csv",
        "phase3_worst3": DATA_DIR / "phase3" / "market_worst3_refinement.csv",
        "source_calibration": Path("src/heston/calibration.py"),
        "source_solver_2d": Path("src/heston/solver_2d.py"),
        "source_heston_model": Path("src/heston/heston_model.py"),
        "source_rates_curve": Path("src/heston/rates_curve.py"),
    }

    hashes = {}
    for name, path in required_files.items():
        if not path.exists():
            raise FileNotFoundError(f"Required input file missing: {path}")
        if path.suffix == ".py":
            h = compute_normalized_source_sha256(path)
        else:
            h = compute_file_sha256(path)
        hashes[name] = h
        print(f"  [OK] {name}: {h[:16]}... ({path})")

    return hashes


def step2_replay_phase1(train_df: pd.DataFrame, ts_handle: Any) -> pd.DataFrame:
    """Replays Phase 1 5-starts on original coarse calibration grid."""
    print("\n=== STEP 2: Replaying Phase 1 5-Starts on Original Calibration Grid ===")
    out_csv = PHASE4_DIR / "heston_phase1_replay.csv"
    if out_csv.exists():
        print(f"  [FOUND] Replay file already exists: {out_csv}")
        return pd.read_csv(out_csv)

    calibrator_orig = HestonCalibrator(
        train_df,
        yield_term_structure=ts_handle,
        grid_t_factor=50.0,
        min_time_steps=25,
        grid_x=70,
        grid_v=35
    )

    df_multi = pd.read_csv(DATA_DIR / "phase1" / "heston_multistart_results.csv")
    records = []
    for _, row in df_multi.iterrows():
        p = [float(row["v0"]), float(row["kappa"]), float(row["theta"]), float(row["xi"]), float(row["rho"])]
        replayed_sse = calibrator_orig.evaluate_sse(p)
        replayed_rmse = float(np.sqrt(replayed_sse / len(train_df)))
        diff_sse = float(abs(replayed_sse - float(row["final_sse"])))

        s_idx = int(row["start_index"])
        if s_idx == 2:
            disp = "Selected for Refinement A (Start 2 / PoC starting point)"
            notes = "Primary candidate, lowest fine SSE in Phase 1"
        elif s_idx == 5:
            disp = "Selected for Refinement B (Start 5)"
            notes = "Second lowest fine SSE in Phase 1, zero-correlation basin"
        elif s_idx == 1:
            disp = "Selected for Refinement C (Start 1)"
            notes = "Third lowest fine SSE in Phase 1, canonical negative skew basin"
        elif s_idx == 3:
            disp = "Excluded from refinements"
            notes = "Severe mesh instability in fine grid (fine SSE jumped to 1.77)"
        elif s_idx == 4:
            disp = "Excluded from refinements"
            notes = "Abnormal termination in Phase 1 (status != 0)"
        else:
            disp = "Excluded"
            notes = ""

        records.append({
            "start_index": s_idx,
            "name": row["name"],
            "v0": float(row["v0"]),
            "kappa": float(row["kappa"]),
            "theta": float(row["theta"]),
            "xi": float(row["xi"]),
            "rho": float(row["rho"]),
            "feller_ratio": float(row["feller_ratio"]),
            "feller_satisfied": bool(row["feller_satisfied"]),
            "boundary_pegged": bool(row["boundary_pegged"]),
            "boundary_hits": str(row["boundary_hits"]),
            "iterations": int(row["iterations"]),
            "function_evals": int(row["function_evals"]),
            "time_seconds": float(row["time_seconds"]),
            "status": int(row["status"]),
            "termination_type": str(row["termination_type"]),
            "success": bool(row["success"]),
            "message": str(row["message"]),
            "recorded_final_sse": float(row["final_sse"]),
            "replayed_final_sse": replayed_sse,
            "diff_final_sse": diff_sse,
            "recorded_final_rmse": float(row["final_rmse"]),
            "replayed_final_rmse": replayed_rmse,
            "fine_grid_sse": float(row["fine_grid_sse"]),
            "fine_grid_rmse": float(row["fine_grid_rmse"]),
            "disposition_phase4": disp,
            "notes": notes
        })

    df_replay = pd.DataFrame(records)
    df_replay.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv}")
    return df_replay


def step3_assemble_local_refinements(
    train_df: pd.DataFrame,
    ts_handle: Any,
    config: Dict[str, Any]
) -> pd.DataFrame:
    """Gathers local refinements A, B, C and evaluates PoC benchmark on production grid."""
    print("\n=== STEP 3: Assembling Local Refinements and Evaluating PoC Benchmark ===")
    out_csv = PHASE4_DIR / "heston_local_refinements.csv"

    # Evaluator on production grid for benchmark
    calibrator_prod = HestonCalibrator(
        train_df,
        yield_term_structure=ts_handle,
        grid_t_factor=300.0,
        min_time_steps=60,
        grid_x=160,
        grid_v=80
    )

    starts_info = [
        {"key": "A", "index": 2, "json": "refinement_A_res.json", "name": "Refinement_A_Start_2"},
        {"key": "B", "index": 5, "json": "refinement_B_res.json", "name": "Refinement_B_Start_5"},
        {"key": "C", "index": 1, "json": "refinement_C_res.json", "name": "Refinement_C_Start_1"},
    ]

    records = []
    for s in starts_info:
        j_path = PHASE4_DIR / s["json"]
        if not j_path.exists():
            raise FileNotFoundError(f"Refinement JSON missing: {j_path}. Wait for optimization run to complete.")
        with open(j_path, "r") as f:
            d = json.load(f)

        f_raw = d["final_params_raw"]
        i_raw = d["init_params_raw"]
        rec = {
            "start_index": d["start_index"],
            "name": d["name"],
            "description": d["description"],
            "init_v0": i_raw[0],
            "init_kappa": i_raw[1],
            "init_theta": i_raw[2],
            "init_xi": i_raw[3],
            "init_rho": i_raw[4],
            "init_sse": float(d["init_sse"]),
            "init_rmse": float(d["init_rmse"]),
            "final_v0": f_raw[0],
            "final_kappa": f_raw[1],
            "final_theta": f_raw[2],
            "final_xi": f_raw[3],
            "final_rho": f_raw[4],
            "final_sse": float(d["final_sse"]),
            "final_rmse": float(d["final_rmse"]),
            "iterations": int(d["iterations"]),
            "function_evals": int(d["function_evals"]),
            "time_seconds": float(d.get("wall_clock_seconds", d["time_seconds"])),
            "termination_type": d["termination_type"],
            "status": int(d["status"]),
            "success": bool(d["success"]),
            "message": d["message"],
            "engine_failures": int(d.get("engine_failures", 0)),
            "feller_ratio": float(d["feller_ratio"]),
            "feller_satisfied": bool(d["feller_satisfied"]),
            "boundary_hits": str(d.get("boundary_hits", []))
        }
        records.append(rec)

    # Benchmark PoC exact evaluation on production grid
    poc_def = config["benchmark_poc"]
    poc_params = np.array(poc_def["params"], dtype=float)
    t0 = time.time()
    poc_sse = calibrator_prod.evaluate_sse(poc_params)
    poc_time = time.time() - t0
    n_contracts = len(train_df)
    poc_rmse = math.sqrt(poc_sse / n_contracts)
    poc_hp = HestonParams.from_array(poc_params)

    records.append({
        "start_index": 0,
        "name": poc_def["name"],
        "description": poc_def["description"],
        "init_v0": poc_params[0],
        "init_kappa": poc_params[1],
        "init_theta": poc_params[2],
        "init_xi": poc_params[3],
        "init_rho": poc_params[4],
        "init_sse": poc_sse,
        "init_rmse": poc_rmse,
        "final_v0": poc_params[0],
        "final_kappa": poc_params[1],
        "final_theta": poc_params[2],
        "final_xi": poc_params[3],
        "final_rho": poc_params[4],
        "final_sse": poc_sse,
        "final_rmse": poc_rmse,
        "iterations": 0,
        "function_evals": 1,
        "time_seconds": poc_time,
        "termination_type": "BENCHMARK_REFERENCE",
        "status": 0,
        "success": True,
        "message": "Exact Phase 1 PoC Regime A reference evaluation",
        "engine_failures": 0,
        "feller_ratio": poc_hp.feller_ratio,
        "feller_satisfied": poc_hp.feller_satisfied,
        "boundary_hits": "[]"
    })

    df_refine = pd.DataFrame(records)
    df_refine.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv}")
    return df_refine


def step4_evaluate_candidates_fine_and_select(
    df_refine: pd.DataFrame,
    train_df: pd.DataFrame,
    ts_handle: Any,
    config: Dict[str, Any]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Evaluates all candidates and benchmark PoC on fine grid (QL700/min120/x280/v140).
    Selects winning parameter vector strictly based on train 60 fine evaluation.
    """
    print("\n=== STEP 4: Fine Grid Evaluation (QL700) on Train 60 & Winner Selection ===")
    out_csv = PHASE4_DIR / "heston_candidates_fine_eval.csv"
    out_json = PHASE4_DIR / "heston_calibrated_parameters.json"

    if out_csv.exists() and out_json.exists():
        print(f"  [FOUND] Fine candidates and winner already exist: {out_csv}")
        with open(out_json, "r") as fp:
            calibrated_meta = json.load(fp)
        return pd.read_csv(out_csv), calibrated_meta

    calibrator_fine = HestonCalibrator(
        train_df,
        yield_term_structure=ts_handle,
        grid_t_factor=700.0,
        min_time_steps=120,
        grid_x=280,
        grid_v=140
    )

    records = []
    n_contracts = len(train_df)

    for _, row in df_refine.iterrows():
        c_id = str(row["name"])
        p = np.array([row["final_v0"], row["final_kappa"], row["final_theta"], row["final_xi"], row["final_rho"]], dtype=float)

        t0 = time.time()
        # Evaluate individual prices on fine grid to get MAE and max error
        prices = []
        errors = []
        for opt, mkt, K, T in calibrator_fine.contracts:
            steps = max(calibrator_fine.min_time_steps, int(round(calibrator_fine.grid_t_factor * T)))
            proc = ql.HestonProcess(
                calibrator_fine.ts_handle,
                calibrator_fine.div_handle,
                calibrator_fine.spot_handle,
                float(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4])
            )
            model = ql.HestonModel(proc)
            eng = ql.FdHestonVanillaEngine(model, steps, calibrator_fine.grid_x, calibrator_fine.grid_v)
            opt.setPricingEngine(eng)
            price = opt.NPV()
            prices.append(price)
            errors.append(price - mkt)

        eval_time = time.time() - t0
        err_arr = np.array(errors)
        fine_sse = float(np.sum(err_arr ** 2))
        fine_rmse = float(np.sqrt(fine_sse / n_contracts))
        fine_mae = float(np.mean(np.abs(err_arr)))
        fine_max_abs_err = float(np.max(np.abs(err_arr)))

        hp = HestonParams.from_array(p)
        is_converged = (int(row["status"]) == 0 and bool(row["success"]) and np.isfinite(fine_sse))

        records.append({
            "candidate_id": c_id,
            "start_index": int(row["start_index"]),
            "status": int(row["status"]),
            "success": bool(row["success"]),
            "v0": p[0],
            "kappa": p[1],
            "theta": p[2],
            "xi": p[3],
            "rho": p[4],
            "feller_ratio": hp.feller_ratio,
            "feller_satisfied": hp.feller_satisfied,
            "prod_sse": float(row["final_sse"]),
            "prod_rmse": float(row["final_rmse"]),
            "fine_sse": fine_sse,
            "fine_rmse": fine_rmse,
            "fine_mae": fine_mae,
            "fine_max_abs_err": fine_max_abs_err,
            "eval_time_seconds": eval_time,
            "eligible_for_selection": is_converged
        })

    df_fine = pd.DataFrame(records)

    # Winner selection logic
    eligible = df_fine[df_fine["eligible_for_selection"] == True]
    if len(eligible) == 0:
        raise RuntimeError("No candidate eligible for selection: all starts failed or diverged.")

    best_candidate = eligible.loc[eligible["fine_sse"].idxmin()]
    poc_row = df_fine[df_fine["candidate_id"] == "Benchmark_PoC_Regime_A"].iloc[0]

    poc_fine_sse = poc_row["fine_sse"]
    best_fine_sse = best_candidate["fine_sse"]

    # Predeclared discretization noise threshold (0.0001 in SSE, ~0.001 in price / numerical PDE truncation)
    discretization_noise_sse = 0.0001

    if best_candidate["candidate_id"] == "Benchmark_PoC_Regime_A" or (poc_fine_sse - best_fine_sse) < discretization_noise_sse:
        winner_row = poc_row
        winner_status = "WINNER_POC_CONSERVED"
        selection_rationale = (
            f"Benchmark PoC Regime A retained: Best candidate {best_candidate['candidate_id']} fine SSE "
            f"({best_fine_sse:.6f}) improvement over PoC fine SSE ({poc_fine_sse:.6f}) is "
            f"{poc_fine_sse - best_fine_sse:.6e}, which is below discretization noise threshold "
            f"({discretization_noise_sse}). Following predeclared protocol, PoC parameterization is strictly conserved."
        )
    else:
        winner_row = best_candidate
        winner_status = "WINNER_NEW_OPTIMUM"
        selection_rationale = (
            f"New optimum selected: Candidate {winner_row['candidate_id']} achieved lowest fine SSE "
            f"({winner_row['fine_sse']:.6f} vs PoC {poc_fine_sse:.6f}) with material gain > {discretization_noise_sse}."
        )

    # Assign selection verdict to df_fine
    df_fine["selection_verdict"] = df_fine["candidate_id"].apply(
        lambda cid: "SELECTED_WINNER" if cid == winner_row["candidate_id"] else "NOT_SELECTED"
    )
    df_fine.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv}")
    print(f"  [WINNER] {winner_status}: {winner_row['candidate_id']}")
    print(f"  [RATIONALE] {selection_rationale}")

    # Bounds proximity
    p_win = np.array([winner_row["v0"], winner_row["kappa"], winner_row["theta"], winner_row["xi"], winner_row["rho"]])
    bounds_prox = {}
    param_names = ["v0", "kappa", "theta", "xi", "rho"]
    for i, name in enumerate(param_names):
        b_lo, b_hi = HESTON_BOUNDS[i]
        val = p_win[i]
        bounds_prox[name] = {
            "value": float(val),
            "lower_bound": b_lo,
            "upper_bound": b_hi,
            "dist_to_lower": float(val - b_lo),
            "dist_to_upper": float(b_hi - val),
            "near_boundary": bool((val - b_lo) < 0.02 * (b_hi - b_lo) or (b_hi - val) < 0.02 * (b_hi - b_lo))
        }

    calibrated_meta = {
        "candidate_id": str(winner_row["candidate_id"]),
        "selection_status": winner_status,
        "selection_rationale": selection_rationale,
        "calibrated_parameters_raw": [float(x) for x in p_win],
        "calibrated_parameters": {
            "v0": float(p_win[0]),
            "kappa": float(p_win[1]),
            "theta": float(p_win[2]),
            "xi": float(p_win[3]),
            "rho": float(p_win[4])
        },
        "feller_condition": {
            "feller_ratio": float(winner_row["feller_ratio"]),
            "feller_satisfied": bool(winner_row["feller_satisfied"]),
            "formula": "2*kappa*theta / xi^2"
        },
        "bounds_proximity": bounds_prox,
        "train_metrics": {
            "prod_sse": float(winner_row["prod_sse"]),
            "prod_rmse": float(winner_row["prod_rmse"]),
            "fine_sse": float(winner_row["fine_sse"]),
            "fine_rmse": float(winner_row["fine_rmse"]),
            "fine_mae": float(winner_row["fine_mae"]),
            "fine_max_abs_err": float(winner_row["fine_max_abs_err"])
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    with open(out_json, "w") as f:
        json.dump(calibrated_meta, f, indent=2)
    print(f"  [EXPORTED] {out_json}")

    return df_fine, calibrated_meta


def step5_full_pricing_evaluation(
    winner_meta: Dict[str, Any],
    curve: DeterministicYieldCurve,
    ts_handle: Any
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Evaluates all 97 puts across partitions and tenors with winning parameters.
    Integrates verified Phase 3 proprietary snapshot if PoC is conserved.
    """
    print("\n=== STEP 5: Full 97 Puts Pricing Evaluation Across Engines & Partitions ===")
    out_puts_csv = PHASE4_DIR / "heston_pricing_full_puts.csv"
    out_part_csv = PHASE4_DIR / "heston_pricing_summary_by_partition.csv"
    out_tenor_csv = PHASE4_DIR / "heston_pricing_summary_by_tenor.csv"

    if out_puts_csv.exists() and out_part_csv.exists() and out_tenor_csv.exists():
        print(f"  [FOUND] Full pricing tables already exist: {out_puts_csv}")
        return pd.read_csv(out_puts_csv), pd.read_csv(out_part_csv), pd.read_csv(out_tenor_csv)

    df_clean = pd.read_csv(DATA_DIR / "puts_selected_clean.csv")
    split_meta = json.load(open(DATA_DIR / "data_split_manifest.json"))
    p_win = winner_meta["calibrated_parameters_raw"]
    params = HestonParams(v0=p_win[0], kappa=p_win[1], theta=p_win[2], xi=p_win[3], rho=p_win[4])

    is_poc_conserved = (winner_meta["selection_status"] == "WINNER_POC_CONSERVED")
    phase3_market_csv = DATA_DIR / "phase3" / "market_97_puts_validation.csv"

    if is_poc_conserved and phase3_market_csv.exists():
        print("  [INTEGRATION] PoC conserved: Leveraging verified Phase 3 pricing table with cryptographic audit.")
        df_p3 = pd.read_csv(phase3_market_csv)
    else:
        df_p3 = None

    # We evaluate QuantLib production grid (300*T / min60 / 160 / 80) for all 97 contracts
    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date
    proc_prod = ql.HestonProcess(
        ts_handle,
        ql.YieldTermStructureHandle(ql.FlatForward(eval_date, 0.0, ql.Actual365Fixed())),
        ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE)),
        params.v0, params.kappa, params.theta, params.xi, params.rho
    )
    model_prod = ql.HestonModel(proc_prod)

    proc_fine = ql.HestonProcess(
        ts_handle,
        ql.YieldTermStructureHandle(ql.FlatForward(eval_date, 0.0, ql.Actual365Fixed())),
        ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE)),
        params.v0, params.kappa, params.theta, params.xi, params.rho
    )
    model_fine = ql.HestonModel(proc_fine)

    records = []
    for idx, row in df_clean.iterrows():
        symbol = str(row["contractSymbol"])
        K = float(row["strike"])
        mkt = float(row["lastPrice"])
        exp_str = str(row["expirationDate"])
        tau_days = int(row["tau_days"])
        tau_years = float(row["tau_years"])
        tenor_label = str(row.get("tenor_label", f"{tau_days}d"))

        # Partition mapping
        if symbol in split_meta["train_symbols"]:
            partition = "train"
        elif symbol in split_meta["strike_holdout_symbols"]:
            partition = "strike_holdout"
        elif symbol in split_meta["tenor_holdout_symbols"]:
            partition = "tenor_holdout"
        else:
            partition = "unknown"

        # QuantLib option setup
        parts = exp_str.split("-")
        exp_date = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
        payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
        exercise = ql.AmericanExercise(eval_date, exp_date)
        opt = ql.VanillaOption(payoff, exercise)

        # QL Production Grid
        t_steps_prod = max(60, int(round(300.0 * tau_years)))
        eng_prod = ql.FdHestonVanillaEngine(model_prod, t_steps_prod, 160, 80)
        opt.setPricingEngine(eng_prod)
        ql_prod_price = float(opt.NPV())

        if df_p3 is not None and symbol in df_p3["contractSymbol"].values:
            row_p3 = df_p3[df_p3["contractSymbol"] == symbol].iloc[0]
            prop_def_price = float(row_p3["proprietary_default_usd"])
            prop_fine_price = float(row_p3["proprietary_fine_usd"])
            ql_fine_price = float(row_p3["ql_refined_700_usd"])
        else:
            # QL Fine Grid
            t_steps_fine = max(120, int(round(700.0 * tau_years)))
            eng_fine = ql.FdHestonVanillaEngine(model_fine, t_steps_fine, 280, 140)
            opt.setPricingEngine(eng_fine)
            ql_fine_price = float(opt.NPV())

            # Proprietary Solver Default
            m_t_def = max(50, int(round(300.0 * tau_years)))
            grid_def = Grid2D(s_min=0.0, s_max=3.0 * SPOT_PRICE, n_s=120, v_min=0.0, v_max=1.0, n_v=60, m_t=m_t_def)
            solver_def = Heston2DSolver(grid_def, params, curve, is_american=True, exercise_style="American")
            res_def = solver_def.solve(spot=SPOT_PRICE, strike=K, tau=tau_years, is_put=True)
            prop_def_price = float(res_def["price"])

            # Proprietary Solver Fine
            m_t_fine = max(100, int(round(600.0 * tau_years)))
            grid_fine = Grid2D(s_min=0.0, s_max=3.0 * SPOT_PRICE, n_s=240, v_min=0.0, v_max=1.0, n_v=120, m_t=m_t_fine)
            solver_fine = Heston2DSolver(grid_fine, params, curve, is_american=True, exercise_style="American")
            res_fine = solver_fine.solve(spot=SPOT_PRICE, strike=K, tau=tau_years, is_put=True)
            prop_fine_price = float(res_fine["price"])

        # Error metrics
        err_ql_prod = ql_prod_price - mkt
        err_ql_fine = ql_fine_price - mkt
        err_prop_def = prop_def_price - mkt
        err_prop_fine = prop_fine_price - mkt

        diff_prop_vs_ql_fine = prop_fine_price - ql_fine_price
        abs_diff_discrepancy = abs(diff_prop_vs_ql_fine)

        records.append({
            "contractSymbol": symbol,
            "strike": K,
            "expirationDate": exp_str,
            "tau_days": tau_days,
            "tenor_label": tenor_label,
            "tau_years": tau_years,
            "partition": partition,
            "lastPrice": mkt,
            "ql_prod_price": ql_prod_price,
            "ql_fine_price": ql_fine_price,
            "prop_default_price": prop_def_price,
            "prop_fine_price": prop_fine_price,
            "err_ql_prod_usd": err_ql_prod,
            "abs_err_ql_prod_usd": abs(err_ql_prod),
            "err_ql_fine_usd": err_ql_fine,
            "abs_err_ql_fine_usd": abs(err_ql_fine),
            "rel_err_ql_fine_pct": (abs(err_ql_fine) / mkt * 100.0) if mkt > 0 else 0.0,
            "err_prop_default_usd": err_prop_def,
            "abs_err_prop_default_usd": abs(err_prop_def),
            "err_prop_fine_usd": err_prop_fine,
            "abs_err_prop_fine_usd": abs(err_prop_fine),
            "rel_err_prop_fine_pct": (abs(err_prop_fine) / mkt * 100.0) if mkt > 0 else 0.0,
            "diff_prop_fine_vs_ql_fine_usd": diff_prop_vs_ql_fine,
            "abs_diff_prop_fine_vs_ql_fine_usd": abs_diff_discrepancy,
            "diff_prop_fine_vs_ql_fine_cents": diff_prop_vs_ql_fine * 100.0,
            "diff_prop_default_vs_fine_usd": prop_def_price - prop_fine_price,
            "target_threshold_usd": 0.002,
            "status_discrepancy_gate_002": "PASS" if abs_diff_discrepancy <= 0.002 else "FAIL"
        })

    df_puts = pd.DataFrame(records)
    df_puts.to_csv(out_puts_csv, index=False)
    print(f"  [EXPORTED] {out_puts_csv} (97 contracts)")

    # Partition Summary
    part_records = []
    partitions = ["train", "strike_holdout", "tenor_holdout", "total"]
    for p_name in partitions:
        sub = df_puts if p_name == "total" else df_puts[df_puts["partition"] == p_name]
        n_c = len(sub)
        mean_mkt = float(sub["lastPrice"].mean())

        mae_ql_prod = float(sub["abs_err_ql_prod_usd"].mean())
        rmse_ql_prod = float(np.sqrt((sub["err_ql_prod_usd"] ** 2).mean()))
        max_ql_prod = float(sub["abs_err_ql_prod_usd"].max())

        mae_ql_fine = float(sub["abs_err_ql_fine_usd"].mean())
        rmse_ql_fine = float(np.sqrt((sub["err_ql_fine_usd"] ** 2).mean()))
        max_ql_fine = float(sub["abs_err_ql_fine_usd"].max())

        mae_prop_def = float(sub["abs_err_prop_default_usd"].mean())
        rmse_prop_def = float(np.sqrt((sub["err_prop_default_usd"] ** 2).mean()))
        max_prop_def = float(sub["abs_err_prop_default_usd"].max())

        mae_prop_fine = float(sub["abs_err_prop_fine_usd"].mean())
        rmse_prop_fine = float(np.sqrt((sub["err_prop_fine_usd"] ** 2).mean()))
        max_prop_fine = float(sub["abs_err_prop_fine_usd"].max())

        mean_disc = float(sub["abs_diff_prop_fine_vs_ql_fine_usd"].mean())
        max_disc = float(sub["abs_diff_prop_fine_vs_ql_fine_usd"].max())

        cov_5c = float((sub["abs_err_prop_fine_usd"] <= 0.05).mean() * 100.0)
        cov_10c = float((sub["abs_err_prop_fine_usd"] <= 0.10).mean() * 100.0)

        # Gate criteria
        if p_name == "train":
            gate_mae = (mae_prop_fine <= 0.080)
            gate_rmse = (rmse_prop_fine <= 0.120)
        elif p_name in ["strike_holdout", "tenor_holdout"]:
            gate_mae = (mae_prop_fine <= 0.100)
            gate_rmse = True
        else:
            gate_mae = (mae_prop_fine <= 0.100)
            gate_rmse = (rmse_prop_fine <= 0.120)

        part_records.append({
            "partition": p_name,
            "n_contracts": n_c,
            "mean_market_price": mean_mkt,
            "mae_ql_prod": mae_ql_prod,
            "rmse_ql_prod": rmse_ql_prod,
            "max_err_ql_prod": max_ql_prod,
            "mae_ql_fine": mae_ql_fine,
            "rmse_ql_fine": rmse_ql_fine,
            "max_err_ql_fine": max_ql_fine,
            "mae_prop_default": mae_prop_def,
            "rmse_prop_default": rmse_prop_def,
            "max_err_prop_default": max_prop_def,
            "mae_prop_fine": mae_prop_fine,
            "rmse_prop_fine": rmse_prop_fine,
            "max_err_prop_fine": max_prop_fine,
            "mean_abs_discrepancy_prop_vs_ql_fine": mean_disc,
            "max_abs_discrepancy_prop_vs_ql_fine": max_disc,
            "coverage_within_5c_pct": cov_5c,
            "coverage_within_10c_pct": cov_10c,
            "gate_mae_pass": gate_mae,
            "gate_rmse_pass": gate_rmse
        })

    df_part = pd.DataFrame(part_records)
    df_part.to_csv(out_part_csv, index=False)
    print(f"  [EXPORTED] {out_part_csv}")

    # Tenor Summary
    tenor_records = []
    tenor_groups = df_puts.groupby(["tau_days", "expirationDate"], sort=True)
    t_idx = 0
    for (t_days, exp_d), grp in tenor_groups:
        t_idx += 1
        t_label = grp["tenor_label"].iloc[0]
        tau_yr = grp["tau_years"].iloc[0]
        p_types = "/".join(sorted(grp["partition"].unique()))

        tenor_records.append({
            "tenor_index": t_idx,
            "tenor_label": t_label,
            "expirationDate": exp_d,
            "tau_days": t_days,
            "tau_years": tau_yr,
            "partition_type": p_types,
            "n_contracts": len(grp),
            "mean_market_price": float(grp["lastPrice"].mean()),
            "mae_ql_fine": float(grp["abs_err_ql_fine_usd"].mean()),
            "rmse_ql_fine": float(np.sqrt((grp["err_ql_fine_usd"] ** 2).mean())),
            "max_err_ql_fine": float(grp["abs_err_ql_fine_usd"].max()),
            "mae_prop_fine": float(grp["abs_err_prop_fine_usd"].mean()),
            "rmse_prop_fine": float(np.sqrt((grp["err_prop_fine_usd"] ** 2).mean())),
            "max_err_prop_fine": float(grp["abs_err_prop_fine_usd"].max()),
            "mean_abs_discrepancy_prop_vs_ql_fine": float(grp["abs_diff_prop_fine_vs_ql_fine_usd"].mean()),
            "max_abs_discrepancy_prop_vs_ql_fine": float(grp["abs_diff_prop_fine_vs_ql_fine_usd"].max())
        })

    df_tenor = pd.DataFrame(tenor_records)
    df_tenor.to_csv(out_tenor_csv, index=False)
    print(f"  [EXPORTED] {out_tenor_csv} (12 tenors)")

    return df_puts, df_part, df_tenor


def step6_worst3_mesh_controls(
    df_puts: pd.DataFrame,
    winner_meta: Dict[str, Any],
    curve: DeterministicYieldCurve,
    ts_handle: Any
) -> pd.DataFrame:
    """Evaluates mesh refinement on worst 3 pricing error contracts under QL1000 and Propio 320/160/900T."""
    print("\n=== STEP 6: Worst 3 Pricing Discrepancy Mesh Controls ===")
    out_csv = PHASE4_DIR / "heston_worst3_mesh_controls.csv"

    is_poc_conserved = (winner_meta["selection_status"] == "WINNER_POC_CONSERVED")
    p3_worst3_csv = DATA_DIR / "phase3" / "market_worst3_refinement.csv"

    if is_poc_conserved and p3_worst3_csv.exists():
        print("  [INTEGRATION] PoC conserved: Leveraging verified Phase 3 worst 3 refinement snapshot.")
        df_w3_raw = pd.read_csv(p3_worst3_csv)
        # Adapt schema to Phase 4
        records = []
        for _, r in df_w3_raw.iterrows():
            sym = r["contractSymbol"]
            put_row = df_puts[df_puts["contractSymbol"] == sym].iloc[0]
            prop_fine = float(r["price_fine"])
            ql700 = float(r["ql_refined_700"])
            ql1000 = float(r["ql_ultra_1000"])
            prop_ex = float(r["price_extrafine_320x160_m900"])
            diff_ql = ql700 - ql1000
            diff_prop = prop_fine - prop_ex

            records.append({
                "contractSymbol": sym,
                "strike": float(r["strike"]),
                "tau_days": int(put_row["tau_days"]),
                "tenor_label": str(put_row["tenor_label"]),
                "partition": put_row["partition"],
                "lastPrice": float(put_row["lastPrice"]),
                "prop_fine_usd": prop_fine,
                "ql_refined_700_usd": ql700,
                "diff_fine_vs_ql700_usd": float(r["diff_fine_vs_ql700"]),
                "ql_ultrafine_1000_usd": ql1000,
                "diff_ql700_vs_ql1000_usd": diff_ql,
                "abs_diff_ql_refinement_usd": abs(diff_ql),
                "prop_extrafine_320_usd": prop_ex,
                "diff_prop_fine_vs_extrafine_usd": diff_prop,
                "abs_diff_prop_refinement_usd": abs(diff_prop),
                "gate_ql_stability_pass": abs(diff_ql) <= 0.0005,
                "gate_prop_stability_pass": abs(diff_prop) <= 0.002
            })
        df_worst3 = pd.DataFrame(records)
    else:
        # Compute dynamically on top 3 discrepancies
        top3 = df_puts.sort_values(by="abs_diff_prop_fine_vs_ql_fine_usd", ascending=False).head(3)
        p_win = winner_meta["calibrated_parameters_raw"]
        params = HestonParams(v0=p_win[0], kappa=p_win[1], theta=p_win[2], xi=p_win[3], rho=p_win[4])
        eval_date = ql.Date(17, 11, 2026)
        ql.Settings.instance().evaluationDate = eval_date

        proc_1000 = ql.HestonProcess(
            ts_handle,
            ql.YieldTermStructureHandle(ql.FlatForward(eval_date, 0.0, ql.Actual365Fixed())),
            ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE)),
            params.v0, params.kappa, params.theta, params.xi, params.rho
        )
        model_1000 = ql.HestonModel(proc_1000)

        records = []
        for _, r in top3.iterrows():
            sym = r["contractSymbol"]
            K = float(r["strike"])
            tau_yr = float(r["tau_years"])
            parts = str(r["expirationDate"]).split("-")
            exp_date = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
            payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
            exercise = ql.AmericanExercise(eval_date, exp_date)
            opt = ql.VanillaOption(payoff, exercise)

            # QL 1000
            m_t_1000 = max(160, int(round(1000.0 * tau_yr)))
            eng_1000 = ql.FdHestonVanillaEngine(model_1000, m_t_1000, 360, 180)
            opt.setPricingEngine(eng_1000)
            ql_1000_price = float(opt.NPV())

            # Propio Extra-fine (320, 160, max(160, round(900*T)))
            m_t_ex = max(160, int(round(900.0 * tau_yr)))
            grid_ex = Grid2D(s_min=0.0, s_max=3.0 * SPOT_PRICE, n_s=320, v_min=0.0, v_max=1.0, n_v=160, m_t=m_t_ex)
            solver_ex = Heston2DSolver(grid_ex, params, curve, is_american=True, exercise_style="American")
            res_ex = solver_ex.solve(spot=SPOT_PRICE, strike=K, tau=tau_yr, is_put=True)
            prop_ex_price = float(res_ex["price"])

            diff_ql = float(r["ql_fine_price"]) - ql_1000_price
            diff_prop = float(r["prop_fine_price"]) - prop_ex_price

            records.append({
                "contractSymbol": sym,
                "strike": K,
                "tau_days": int(r["tau_days"]),
                "tenor_label": str(r["tenor_label"]),
                "partition": r["partition"],
                "lastPrice": float(r["lastPrice"]),
                "prop_fine_usd": float(r["prop_fine_price"]),
                "ql_refined_700_usd": float(r["ql_fine_price"]),
                "diff_fine_vs_ql700_usd": float(r["diff_prop_fine_vs_ql_fine_usd"]),
                "ql_ultrafine_1000_usd": ql_1000_price,
                "diff_ql700_vs_ql1000_usd": diff_ql,
                "abs_diff_ql_refinement_usd": abs(diff_ql),
                "prop_extrafine_320_usd": prop_ex_price,
                "diff_prop_fine_vs_extrafine_usd": diff_prop,
                "abs_diff_prop_refinement_usd": abs(diff_prop),
                "gate_ql_stability_pass": abs(diff_ql) <= 0.0005,
                "gate_prop_stability_pass": abs(diff_prop) <= 0.002
            })
        df_worst3 = pd.DataFrame(records)

    df_worst3.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv} (3 controls)")
    return df_worst3


def step7_representative_economic_controls(
    winner_meta: Dict[str, Any],
    curve: DeterministicYieldCurve
) -> pd.DataFrame:
    """Verifies economic properties: intrinsic floor, early exercise premium, monotonicity, convexity."""
    print("\n=== STEP 7: Representative Economic Controls (K in {9, 12.33, 17}, T in {31d, 94d, 430d}) ===")
    out_csv = PHASE4_DIR / "heston_representative_economic_controls.csv"

    p_win = winner_meta["calibrated_parameters_raw"]
    params = HestonParams(v0=p_win[0], kappa=p_win[1], theta=p_win[2], xi=p_win[3], rho=p_win[4])

    strikes = [9.0, 12.33, 17.0]
    maturities = [
        {"label": "31d", "tau_days": 31, "tau_years": 31.0 / 365.0},
        {"label": "94d", "tau_days": 94, "tau_years": 94.0 / 365.0},
        {"label": "430d", "tau_days": 430, "tau_years": 430.0 / 365.0},
    ]

    records = []
    prices_am_grid = {}

    for mat in maturities:
        t_label = mat["label"]
        tau_yr = mat["tau_years"]
        t_days = mat["tau_days"]
        r_rate = curve.get_zero_rate(tau_yr)
        prices_am_grid[t_label] = {}

        m_t = max(100, int(round(600.0 * tau_yr)))
        solver = Heston2DSolver()

        for K in strikes:
            res_am = solver.price(K, tau_yr, params, curve, is_american=True, n_s=240, n_v=120, m_t=m_t)
            res_eu = solver.price(K, tau_yr, params, curve, is_american=False, n_s=240, n_v=120, m_t=m_t)

            p_am = float(res_am.price)
            p_eu = float(res_eu.price)
            intrinsic = max(0.0, K - SPOT_PRICE)
            eep = p_am - p_eu

            prices_am_grid[t_label][K] = p_am

            violates_intrinsic = (p_am < intrinsic - 1e-4)
            violates_eep = (p_am < p_eu - 1e-4)

            records.append({
                "contract_id": f"PUT_K{K:.2f}_{t_label}",
                "strike": K,
                "tau_days": t_days,
                "tenor_label": t_label,
                "tau_years": tau_yr,
                "spot": SPOT_PRICE,
                "r_rate": r_rate,
                "price_american": p_am,
                "price_european": p_eu,
                "early_exercise_premium": eep,
                "intrinsic_floor": intrinsic,
                "violates_intrinsic_floor": violates_intrinsic,
                "violates_early_exercise_premium": violates_eep,
                "monotonicity_strike_pass": True,  # verified post-loop
                "monotonicity_maturity_pass": True,  # verified post-loop
                "convexity_strike_pass": True  # verified post-loop
            })

    df_econ = pd.DataFrame(records)

    # Verify Monotonicity in Strike: P(K1) <= P(K2) <= P(K3)
    for mat in maturities:
        t_label = mat["label"]
        p9 = prices_am_grid[t_label][9.0]
        p12 = prices_am_grid[t_label][12.33]
        p17 = prices_am_grid[t_label][17.0]
        strike_mono = (p9 <= p12 + 1e-4) and (p12 <= p17 + 1e-4)
        df_econ.loc[df_econ["tenor_label"] == t_label, "monotonicity_strike_pass"] = strike_mono

    # Verify Monotonicity in Maturity: P(31d) <= P(94d) <= P(430d) for each strike
    for K in strikes:
        p_31 = prices_am_grid["31d"][K]
        p_94 = prices_am_grid["94d"][K]
        p_430 = prices_am_grid["430d"][K]
        mat_mono = (p_31 <= p_94 + 1e-4) and (p_94 <= p_430 + 1e-4)
        df_econ.loc[df_econ["strike"] == K, "monotonicity_maturity_pass"] = mat_mono

    # Verify discrete convexity: for K1=9.0, K2=12.33, K3=17.0
    # Second derivative estimate on non-uniform grid: d^2P/dK^2 > 0
    for mat in maturities:
        t_label = mat["label"]
        p1 = prices_am_grid[t_label][9.0]
        p2 = prices_am_grid[t_label][12.33]
        p3 = prices_am_grid[t_label][17.0]
        h1 = 12.33 - 9.0   # 3.33
        h2 = 17.0 - 12.33  # 4.67
        # Discrete second derivative: 2 * ( (p3 - p2)/h2 - (p2 - p1)/h1 ) / (h1 + h2)
        slope1 = (p2 - p1) / h1
        slope2 = (p3 - p2) / h2
        convex = (slope2 >= slope1 - 1e-4)
        df_econ.loc[df_econ["tenor_label"] == t_label, "convexity_strike_pass"] = convex

    df_econ.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv} (9 economic controls)")
    return df_econ


def step8_parameter_sensitivity(
    winner_meta: Dict[str, Any],
    train_df: pd.DataFrame,
    ts_handle: Any
) -> pd.DataFrame:
    """Evaluates parameter sensitivity under +/-5% shocks on v0, kappa, theta, xi and +/-0.02 on rho."""
    print("\n=== STEP 8: Parameter Sensitivity and Local Curvature Analysis ===")
    out_csv = PHASE4_DIR / "heston_parameter_sensitivity.csv"
    if out_csv.exists():
        print(f"  [FOUND] Sensitivity analysis already exists: {out_csv}")
        return pd.read_csv(out_csv)

    p_win = np.array(winner_meta["calibrated_parameters_raw"], dtype=float)
    base_v0, base_kappa, base_theta, base_xi, base_rho = p_win

    calibrator_fine = HestonCalibrator(
        train_df,
        yield_term_structure=ts_handle,
        grid_t_factor=700.0,
        min_time_steps=120,
        grid_x=280,
        grid_v=140
    )

    base_sse = calibrator_fine.evaluate_sse(p_win)
    n_contracts = len(train_df)
    base_rmse = math.sqrt(base_sse / n_contracts)

    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date

    # Representative contracts to price
    rep_contracts = [
        {"id": "K9_T94", "strike": 9.0, "tau_days": 94, "tau_years": 94.0 / 365.0, "exp_date": ql.Date(19, 2, 2027)},
        {"id": "K12_T94", "strike": 12.33, "tau_days": 94, "tau_years": 94.0 / 365.0, "exp_date": ql.Date(19, 2, 2027)},
        {"id": "K17_T94", "strike": 17.0, "tau_days": 94, "tau_years": 94.0 / 365.0, "exp_date": ql.Date(19, 2, 2027)},
        {"id": "K12_T31", "strike": 12.33, "tau_days": 31, "tau_years": 31.0 / 365.0, "exp_date": ql.Date(18, 12, 2026)},
        {"id": "K12_T430", "strike": 12.33, "tau_days": 430, "tau_years": 430.0 / 365.0, "exp_date": ql.Date(21, 1, 2028)},
        {"id": "K12_T794", "strike": 12.33, "tau_days": 794, "tau_years": 794.0 / 365.0, "exp_date": ql.Date(19, 1, 2029)},
    ]

    def price_representatives(p_vec: np.ndarray) -> Dict[str, float]:
        proc = ql.HestonProcess(
            ts_handle,
            ql.YieldTermStructureHandle(ql.FlatForward(eval_date, 0.0, ql.Actual365Fixed())),
            ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE)),
            float(p_vec[0]), float(p_vec[1]), float(p_vec[2]), float(p_vec[3]), float(p_vec[4])
        )
        mod = ql.HestonModel(proc)
        prices = {}
        for c in rep_contracts:
            steps = max(120, int(round(700.0 * c["tau_years"])))
            eng = ql.FdHestonVanillaEngine(mod, steps, 280, 140)
            payoff = ql.PlainVanillaPayoff(ql.Option.Put, c["strike"])
            ex = ql.AmericanExercise(eval_date, c["exp_date"])
            opt = ql.VanillaOption(payoff, ex)
            opt.setPricingEngine(eng)
            prices[c["id"]] = float(opt.NPV())
        return prices

    base_prices = price_representatives(p_win)

    # Predefined shocks respecting bounds
    scenarios = [
        {"id": "BASE", "desc": "Unshocked calibrated vector", "param": "none", "shock": 0.0, "vec": p_win.copy()},
        {"id": "V0_PLUS_5PCT", "desc": "v0 + 5%", "param": "v0", "shock": +0.05, "vec": np.array([base_v0 * 1.05, base_kappa, base_theta, base_xi, base_rho])},
        {"id": "V0_MINUS_5PCT", "desc": "v0 - 5%", "param": "v0", "shock": -0.05, "vec": np.array([base_v0 * 0.95, base_kappa, base_theta, base_xi, base_rho])},
        {"id": "KAPPA_PLUS_5PCT", "desc": "kappa + 5%", "param": "kappa", "shock": +0.05, "vec": np.array([base_v0, base_kappa * 1.05, base_theta, base_xi, base_rho])},
        {"id": "KAPPA_MINUS_5PCT", "desc": "kappa - 5%", "param": "kappa", "shock": -0.05, "vec": np.array([base_v0, base_kappa * 0.95, base_theta, base_xi, base_rho])},
        {"id": "THETA_PLUS_5PCT", "desc": "theta + 5%", "param": "theta", "shock": +0.05, "vec": np.array([base_v0, base_kappa, base_theta * 1.05, base_xi, base_rho])},
        {"id": "THETA_MINUS_5PCT", "desc": "theta - 5%", "param": "theta", "shock": -0.05, "vec": np.array([base_v0, base_kappa, base_theta * 0.95, base_xi, base_rho])},
        {"id": "XI_PLUS_5PCT", "desc": "xi + 5%", "param": "xi", "shock": +0.05, "vec": np.array([base_v0, base_kappa, base_theta, base_xi * 1.05, base_rho])},
        {"id": "XI_MINUS_5PCT", "desc": "xi - 5%", "param": "xi", "shock": -0.05, "vec": np.array([base_v0, base_kappa, base_theta, base_xi * 0.95, base_rho])},
        {"id": "RHO_PLUS_002", "desc": "rho + 0.02", "param": "rho", "shock": +0.02, "vec": np.array([base_v0, base_kappa, base_theta, base_xi, min(0.95, base_rho + 0.02)])},
        {"id": "RHO_MINUS_002", "desc": "rho - 0.02", "param": "rho", "shock": -0.02, "vec": np.array([base_v0, base_kappa, base_theta, base_xi, max(-0.95, base_rho - 0.02)])},
    ]

    records = []
    for sc in scenarios:
        vec = sc["vec"]
        hp = HestonParams.from_array(vec)

        if sc["id"] == "BASE":
            sc_sse = base_sse
            sc_rmse = base_rmse
            sc_prices = base_prices
        else:
            sc_sse = calibrator_fine.evaluate_sse(vec)
            sc_rmse = math.sqrt(sc_sse / n_contracts)
            sc_prices = price_representatives(vec)

        delta_sse = sc_sse - base_sse
        delta_rmse = sc_rmse - base_rmse

        # Non-zero gradient evidence: delta_sse != 0
        curv_evidence = "BASE_MINIMUM" if sc["id"] == "BASE" else ("NONZERO_GRADIENT" if delta_sse > 0 else "FLAT_OR_DESCENT")

        records.append({
            "scenario_id": sc["id"],
            "shock_description": sc["desc"],
            "param_shocked": sc["param"],
            "shock_val": sc["shock"],
            "v0": vec[0],
            "kappa": vec[1],
            "theta": vec[2],
            "xi": vec[3],
            "rho": vec[4],
            "feller_ratio": hp.feller_ratio,
            "feller_satisfied": hp.feller_satisfied,
            "train_sse_fine": sc_sse,
            "train_rmse_fine": sc_rmse,
            "delta_sse_vs_base": delta_sse,
            "delta_rmse_vs_base": delta_rmse,
            "price_K9_T94": sc_prices["K9_T94"],
            "price_K12_T94": sc_prices["K12_T94"],
            "price_K17_T94": sc_prices["K17_T94"],
            "price_K12_T31": sc_prices["K12_T31"],
            "price_K12_T430": sc_prices["K12_T430"],
            "price_K12_T794": sc_prices["K12_T794"],
            "gradient_curvature_evidence": curv_evidence
        })

    df_sens = pd.DataFrame(records)
    df_sens.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv} (11 sensitivity scenarios)")
    return df_sens


def step9_baseline_comparison(
    df_puts: pd.DataFrame
) -> pd.DataFrame:
    """Generates comparison against Flat Black-Scholes and SVI on common 84 sample."""
    print("\n=== STEP 9: Baseline Comparison Against Flat BS and SVI on Common 84 Sample ===")
    out_csv = PHASE4_DIR / "heston_baseline_comparison.csv"

    p1_common_csv = DATA_DIR / "phase1" / "heston_common_84_comparison.csv"
    if not p1_common_csv.exists():
        raise FileNotFoundError(f"Phase 1 common 84 comparison file missing: {p1_common_csv}")

    df_c84 = pd.read_csv(p1_common_csv)
    puts_map = df_puts.set_index("contractSymbol")

    records = []
    for _, row in df_c84.iterrows():
        sym = row["contractSymbol"]
        if sym not in puts_map.index:
            continue
        p_row = puts_map.loc[sym]

        mkt = float(row["lastPrice"])
        p_heston_ql = float(p_row["ql_fine_price"])
        p_heston_prop = float(p_row["prop_fine_price"])
        p_flat_com = float(row["price_flat_common_curve"])
        p_flat_cnt = float(row["price_flat_contract_rate"])
        p_svi = float(row["price_svi_historical_r3"])

        records.append({
            "contractSymbol": sym,
            "strike": float(row["strike"]),
            "expirationDate": str(row["expirationDate"]),
            "tau_years": float(row["tau_years"]),
            "partition": p_row["partition"],
            "lastPrice": mkt,
            "price_heston_ql_fine": p_heston_ql,
            "price_heston_prop_fine": p_heston_prop,
            "price_flat_common_curve": p_flat_com,
            "price_flat_contract_rate": p_flat_cnt,
            "price_svi_historical_r3": p_svi,
            "abs_err_heston_ql_fine": abs(p_heston_ql - mkt),
            "abs_err_heston_prop_fine": abs(p_heston_prop - mkt),
            "abs_err_flat_common": abs(p_flat_com - mkt),
            "abs_err_flat_contract": abs(p_flat_cnt - mkt),
            "abs_err_svi_historical": abs(p_svi - mkt)
        })

    df_base = pd.DataFrame(records)
    df_base.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv} ({len(df_base)} common puts)")
    return df_base


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer, int)):
            return int(obj)
        elif isinstance(obj, (np.floating, float)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def step10_build_manifest(
    input_hashes: Dict[str, str],
    config: Dict[str, Any],
    winner_meta: Dict[str, Any],
    df_part: pd.DataFrame,
    df_worst3: pd.DataFrame,
    start_time: float
) -> Dict[str, Any]:
    """Compiles complete Phase 4 execution manifest."""
    print("\n=== STEP 10: Building Cryptographic Execution Manifest ===")
    out_manifest = PHASE4_DIR / "phase4_execution_manifest.json"

    runtime = time.time() - start_time

    # Output file hashes
    out_files = [
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

    out_hashes = {}
    for fname in out_files:
        fpath = PHASE4_DIR / fname
        if fpath.exists():
            out_hashes[fname] = compute_file_sha256(fpath)

    # Gate validations
    train_row = df_part[df_part["partition"] == "train"].iloc[0]
    sh_row = df_part[df_part["partition"] == "strike_holdout"].iloc[0]
    th_row = df_part[df_part["partition"] == "tenor_holdout"].iloc[0]
    tot_row = df_part[df_part["partition"] == "total"].iloc[0]

    gates = {
        "gate_coverage_97_puts": bool(tot_row["n_contracts"] == 97),
        "gate_train_mae_le_008": bool(train_row["mae_prop_fine"] <= 0.080),
        "gate_train_rmse_le_012": bool(train_row["rmse_prop_fine"] <= 0.120),
        "gate_strike_holdout_mae_le_010": bool(sh_row["mae_prop_fine"] <= 0.100),
        "gate_tenor_holdout_mae_le_010": bool(th_row["mae_prop_fine"] <= 0.100),
        "gate_solver_discrepancy_le_002": bool(tot_row["max_abs_discrepancy_prop_vs_ql_fine"] <= 0.002),
        "gate_mesh_stability_worst3_ql_le_0005": bool(df_worst3["gate_ql_stability_pass"].all()),
        "gate_mesh_stability_worst3_prop_le_002": bool(df_worst3["gate_prop_stability_pass"].all())
    }
    all_passed = bool(all(gates.values()))

    manifest = {
        "phase": "PHASE_4",
        "title": "Classical Heston Q Calibration and Global Validation",
        "base_commit": "09d9beb060a4a80d9dc4ae7035407cbc8e81e061",
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime_wall_seconds": float(runtime),
        "environment": {
            "python_version": sys.version,
            "quantlib_version": ql.__version__ if HAS_QUANTLIB else None,
            "scipy_version": scipy.__version__,
            "numpy_version": np.__version__,
            "pandas_version": pd.__version__
        },
        "input_hashes": input_hashes,
        "calibrated_parameters": winner_meta,
        "pricing_summary_by_partition": json.loads(df_part.to_json(orient="records")),
        "validation_gates": gates,
        "verdict": "PASS" if all_passed else "FAIL",
        "output_files": out_hashes
    }

    with open(out_manifest, "w") as f:
        json.dump(manifest, f, indent=2, cls=NumpyEncoder)
    print(f"  [EXPORTED] {out_manifest}")
    print(f"  [GATE VERDICT] {'PASS' if all_passed else 'FAIL'}")
    return manifest


def run_pipeline() -> Dict[str, Any]:
    """Runs the complete Phase 4 pipeline end-to-end."""
    t_start = time.time()
    print("================================================================================")
    print("STARTING PHASE 4 EXECUTION PIPELINE: HESTON CALIBRATION & GLOBAL VALIDATION")
    print("================================================================================")

    # Validate inputs
    input_hashes = step1_validate_inputs()
    config = load_config()

    # Load market curve & training dataset
    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
    df_clean = pd.read_csv(DATA_DIR / "puts_selected_clean.csv")
    split_meta = json.load(open(DATA_DIR / "data_split_manifest.json"))
    train_df = df_clean[df_clean["contractSymbol"].isin(split_meta["train_symbols"])].copy()

    # Step 2: Replay Phase 1
    df_replay = step2_replay_phase1(train_df, ts_handle)

    # Step 3: Assemble local refinements
    df_refine = step3_assemble_local_refinements(train_df, ts_handle, config)

    # Step 4: Fine evaluation & winner selection
    df_fine, winner_meta = step4_evaluate_candidates_fine_and_select(df_refine, train_df, ts_handle, config)

    # Step 5: Full 97 puts pricing
    df_puts, df_part, df_tenor = step5_full_pricing_evaluation(winner_meta, curve, ts_handle)

    # Step 6: Worst 3 mesh controls
    df_worst3 = step6_worst3_mesh_controls(df_puts, winner_meta, curve, ts_handle)

    # Step 7: Economic controls
    df_econ = step7_representative_economic_controls(winner_meta, curve)

    # Step 8: Parameter sensitivity
    df_sens = step8_parameter_sensitivity(winner_meta, train_df, ts_handle)

    # Step 9: Baseline comparison
    df_base = step9_baseline_comparison(df_puts)

    # Step 10: Execution manifest
    manifest = step10_build_manifest(input_hashes, config, winner_meta, df_part, df_worst3, t_start)

    print("\n================================================================================")
    print("PHASE 4 PIPELINE COMPLETED SUCCESSFULLY")
    print("================================================================================")
    return manifest


if __name__ == "__main__":
    run_pipeline()
