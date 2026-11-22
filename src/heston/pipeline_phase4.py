"""
Execution Pipeline for Phase 4: Classical Heston Calibration and Global Validation.

Orchestrates:
1. Cryptographic validation of all input files and dependencies.
2. Replay of Phase 1 5-starts on original calibration grid.
3. Assembly and replay verification of local refinements (A, B, C) and PoC benchmark on production grid.
4. Evaluation of candidates on fine grid (QL 700 / min120 / 280 / 140) and winner selection based on train 60.
5. Full pricing evaluation across all 97 put contracts and partitions (60 train / 22 strike holdout / 15 tenor holdout).
   - QuantLib pricing evaluated fresh across all 97 contracts.
   - Proprietary solver (Heston2DSolver) uses public .price(...) API with approved defaults (160x80 / min60) and fine (240x120 / min100).
   - If winner is PoC, leverages cryptographically verified Phase 3 audited snapshot with identity verification.
   - If winner differs from PoC, evaluates proprietary solver fresh.
6. Stability controls on worst 3 pricing discrepancies under QL 1000 and Propio Extra-fine (320x160 / min160).
7. Representative economic controls (K in {9.0, 12.33, 17.0}, T in {31d, 94d, 430d}) evaluating intrinsic floor,
   early exercise premium, strike/tenor monotonicity, and discrete convexity.
8. Parameter sensitivity and local curvature under +/-5% shocks on v0, kappa, theta, xi and +/-0.02 on rho across 12 contracts.
9. Baseline comparison against Flat BS and SVI on common 84 sample.
10. Strict cryptographic execution manifest compilation and raw data validation gates.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Dict, List, Tuple, Optional, Any, Union

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

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

# Exact canonical parameter vector from Phase 1 approved manifest
POC_CANONICAL = np.array([0.18613777847584, 2.72546036683707, 0.21367969920004, 0.48178472584297, -0.94980666301298], dtype=float)


class NumpyEncoder(json.JSONEncoder):
    """Encodes numpy data types and booleans into standard JSON primitives."""
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
            notes = "Severe mesh instability in fine grid (fine SSE jumped to 21.46878)"
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
    print(f"  [EXPORTED] {out_csv} ({len(df_replay)} starts replayed)")
    return df_replay


def step3_assemble_local_refinements(
    train_df: pd.DataFrame,
    ts_handle: Any,
    config: Dict[str, Any]
) -> pd.DataFrame:
    """Gathers local refinements A, B, C, replays their SSEs, and evaluates PoC benchmark on production grid."""
    print("\n=== STEP 3: Assembling Local Refinements and Evaluating PoC Benchmark ===")
    out_csv = PHASE4_DIR / "heston_local_refinements.csv"

    # Evaluator on production grid for verification and benchmark
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
            raise FileNotFoundError(
                f"Refinement JSON missing: {j_path}. "
                f"Use 'python src/heston/run_refinements.py --optimize {s['key']}' to execute optimization."
            )
        with open(j_path, "r") as f:
            d = json.load(f)

        f_raw = np.array(d["final_params_raw"], dtype=float)
        i_raw = np.array(d["init_params_raw"], dtype=float)

        # Machine-precision replay check on production grid
        replayed_init_sse = calibrator_prod.evaluate_sse(i_raw)
        replayed_final_sse = calibrator_prod.evaluate_sse(f_raw)

        diff_init = abs(replayed_init_sse - float(d["init_sse"]))
        diff_final = abs(replayed_final_sse - float(d["final_sse"]))

        assert diff_init < 1e-7, f"Init SSE replay mismatch for {d['name']}: {diff_init}"
        assert diff_final < 1e-7, f"Final SSE replay mismatch for {d['name']}: {diff_final}"

        rec = {
            "start_index": int(d["start_index"]),
            "name": str(d["name"]),
            "description": str(d["description"]),
            "init_v0": float(i_raw[0]),
            "init_kappa": float(i_raw[1]),
            "init_theta": float(i_raw[2]),
            "init_xi": float(i_raw[3]),
            "init_rho": float(i_raw[4]),
            "init_sse": float(d["init_sse"]),
            "init_rmse": float(d["init_rmse"]),
            "final_v0": float(f_raw[0]),
            "final_kappa": float(f_raw[1]),
            "final_theta": float(f_raw[2]),
            "final_xi": float(f_raw[3]),
            "final_rho": float(f_raw[4]),
            "final_sse": float(d["final_sse"]),
            "final_rmse": float(d["final_rmse"]),
            "iterations": int(d["iterations"]),
            "function_evals": int(d["function_evals"]),
            "time_seconds": float(d.get("wall_clock_seconds", d["time_seconds"])),
            "termination_type": str(d["termination_type"]),
            "status": int(d["status"]),
            "success": bool(d["success"]),
            "message": str(d["message"]),
            "engine_failures": int(d.get("engine_failures", 0)),
            "feller_ratio": float(d["feller_ratio"]),
            "feller_satisfied": bool(d["feller_satisfied"]),
            "boundary_hits": str(d.get("boundary_hits", []))
        }
        records.append(rec)

    # Benchmark PoC exact evaluation on production grid using canonical vector
    poc_params = POC_CANONICAL.copy()
    t0 = time.time()
    poc_sse = calibrator_prod.evaluate_sse(poc_params)
    poc_time = time.time() - t0
    n_contracts = len(train_df)
    poc_rmse = math.sqrt(poc_sse / n_contracts)
    poc_hp = HestonParams.from_array(poc_params)

    records.append({
        "start_index": 0,
        "name": "Benchmark_PoC_Regime_A",
        "description": "Exact Phase 1 PoC Regime A canonical reference evaluation",
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
    print(f"  [EXPORTED] {out_csv} ({len(df_refine)} rows: 3 refinements + 1 benchmark)")
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
    Enforces that at least one local refinement converged.
    """
    print("\n=== STEP 4: Fine Grid Evaluation (QL700) on Train 60 & Winner Selection ===")
    out_csv = PHASE4_DIR / "heston_candidates_fine_eval.csv"
    out_json = PHASE4_DIR / "heston_calibrated_parameters.json"

    # Precondition check: at least one local refinement MUST have status == 0
    local_refinements = df_refine[df_refine["start_index"] > 0]
    converged_refinements = local_refinements[
        (local_refinements["status"] == 0) & (local_refinements["success"] == True)
    ]
    if len(converged_refinements) == 0:
        raise RuntimeError(
            "Precondition Failure: Zero local refinements achieved convergence (status == 0). "
            "Benchmark PoC reference cannot bypass the requirement of having at least one converged local refinement."
        )

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
    candidate_fine_prices: Dict[str, np.ndarray] = {}

    for _, row in df_refine.iterrows():
        c_id = str(row["name"])
        p = np.array([row["final_v0"], row["final_kappa"], row["final_theta"], row["final_xi"], row["final_rho"]], dtype=float)

        t0 = time.time()
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
        err_arr = np.array(errors, dtype=float)
        price_arr = np.array(prices, dtype=float)
        candidate_fine_prices[c_id] = price_arr

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
    best_candidate = eligible.loc[eligible["fine_sse"].idxmin()]
    poc_row = df_fine[df_fine["candidate_id"] == "Benchmark_PoC_Regime_A"].iloc[0]

    poc_fine_sse = float(poc_row["fine_sse"])
    best_fine_sse = float(best_candidate["fine_sse"])
    delta_sse = poc_fine_sse - best_fine_sse

    # Quantify price difference on the 60 train contracts
    prices_best = candidate_fine_prices[best_candidate["candidate_id"]]
    prices_poc = candidate_fine_prices["Benchmark_PoC_Regime_A"]
    price_diffs = np.abs(prices_best - prices_poc)
    mean_price_diff = float(np.mean(price_diffs))
    max_price_diff = float(np.max(price_diffs))

    # Numerical PDE discretization tolerance threshold (0.0020 USD)
    # If the price difference across train options is strictly within PDE grid noise (<= 0.0020 USD),
    # conserving PoC parameterization is justified by parsimony and academic continuity.
    pde_price_noise_budget = 0.0020

    if best_candidate["candidate_id"] == "Benchmark_PoC_Regime_A" or (max_price_diff <= pde_price_noise_budget):
        winner_row = poc_row
        winner_status = "WINNER_POC_CONSERVED"
        selection_rationale = (
            f"Benchmark PoC Regime A retained for academic parsimony and continuity: "
            f"Best local candidate {best_candidate['candidate_id']} fine SSE ({best_fine_sse:.6f}) "
            f"vs PoC fine SSE ({poc_fine_sse:.6f}) yields a minimal gain of {delta_sse:.6e} USD^2. "
            f"On the 60 training puts, the mean absolute price difference between Candidate A and PoC is "
            f"{mean_price_diff:.5f} USD ({mean_price_diff * 100.0:.3f} cents) with a maximum difference of {max_price_diff:.5f} USD ({max_price_diff * 100.0:.3f} cents), "
            f"which is strictly within the numerical PDE discretization noise (budget <= {pde_price_noise_budget:.4f} USD). "
            f"Conserving PoC parameterization maintains academic continuity with audited baselines and avoids parameter churn within PDE discretization tolerance."
        )
    else:
        winner_row = best_candidate
        winner_status = "WINNER_NEW_OPTIMUM"
        selection_rationale = (
            f"New optimum selected: Candidate {winner_row['candidate_id']} achieved lowest fine SSE "
            f"({winner_row['fine_sse']:.6f} vs PoC {poc_fine_sse:.6f}) with material pricing change: "
            f"max price difference = {max_price_diff:.5f} USD > {pde_price_noise_budget:.4f} USD."
        )

    # Assign selection verdict
    df_fine["selection_verdict"] = df_fine["candidate_id"].apply(
        lambda cid: "SELECTED_WINNER" if cid == winner_row["candidate_id"] else "NOT_SELECTED"
    )
    df_fine.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv}")
    print(f"  [WINNER] {winner_status}: {winner_row['candidate_id']}")
    print(f"  [RATIONALE] {selection_rationale}")

    # Use exact canonical double precision parameters if PoC is conserved
    if winner_status == "WINNER_POC_CONSERVED":
        p_win = POC_CANONICAL.copy()
    else:
        p_win = np.array([winner_row["v0"], winner_row["kappa"], winner_row["theta"], winner_row["xi"], winner_row["rho"]], dtype=float)

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
        "pricing_diff_vs_poc_train_mean_usd": mean_price_diff,
        "pricing_diff_vs_poc_train_max_usd": max_price_diff,
        "calibrated_parameters_raw": [float(x) for x in p_win],
        "calibrated_parameters": {
            "v0": float(p_win[0]),
            "kappa": float(p_win[1]),
            "theta": float(p_win[2]),
            "xi": float(p_win[3]),
            "rho": float(p_win[4])
        },
        "feller_condition": {
            "feller_ratio": float(2.0 * p_win[1] * p_win[2] / (p_win[3] ** 2)),
            "feller_satisfied": bool(2.0 * p_win[1] * p_win[2] > p_win[3] ** 2),
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
        json.dump(calibrated_meta, f, indent=2, cls=NumpyEncoder)
    print(f"  [EXPORTED] {out_json}")

    return df_fine, calibrated_meta


def step5_full_pricing_evaluation(
    winner_meta: Dict[str, Any],
    curve: DeterministicYieldCurve,
    ts_handle: Any,
    phase3_market_csv_path: Optional[Path] = None,
    phase3_manifest_json_path: Optional[Path] = None,
    out_puts_csv_path: Optional[Path] = None,
    out_part_csv_path: Optional[Path] = None,
    out_tenor_csv_path: Optional[Path] = None,
    df_clean_override: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Evaluates all 97 puts across partitions and tenors with winning parameters.
    - QuantLib evaluated fresh on all 97 contracts.
    - If PoC is conserved and verified against Phase 3 cryptographic manifest, integrates Phase 3 proprietary prices.
    - If winner vector differs or Phase 3 check fails, evaluates Heston2DSolver().price(...) fresh using public API.
    """
    print("\n=== STEP 5: Full 97 Puts Pricing Evaluation Across Engines & Partitions ===")
    out_puts_csv = out_puts_csv_path or (PHASE4_DIR / "heston_pricing_full_puts.csv")
    out_part_csv = out_part_csv_path or (PHASE4_DIR / "heston_pricing_summary_by_partition.csv")
    out_tenor_csv = out_tenor_csv_path or (PHASE4_DIR / "heston_pricing_summary_by_tenor.csv")

    df_clean = df_clean_override if df_clean_override is not None else pd.read_csv(DATA_DIR / "puts_selected_clean.csv")
    split_meta = json.load(open(DATA_DIR / "data_split_manifest.json"))
    p_win = np.array(winner_meta["calibrated_parameters_raw"], dtype=float)
    params = HestonParams(v0=p_win[0], kappa=p_win[1], theta=p_win[2], xi=p_win[3], rho=p_win[4])

    is_poc_conserved = (winner_meta["selection_status"] == "WINNER_POC_CONSERVED")
    # Parameter identity with rtol=0.0 and explicit roundoff tolerance (atol=1e-7)
    vector_is_poc = bool(np.allclose(p_win, POC_CANONICAL, rtol=0.0, atol=1e-7))

    phase3_market_csv = phase3_market_csv_path or (DATA_DIR / "phase3" / "market_97_puts_validation.csv")
    phase3_manifest_json = phase3_manifest_json_path or (DATA_DIR / "phase3" / "phase3_execution_manifest.json")

    can_reuse_phase3 = False
    df_p3 = None
    if is_poc_conserved and vector_is_poc and phase3_market_csv.exists() and phase3_manifest_json.exists():
        try:
            from src.heston.pipeline_phase3 import verify_snapshot_inputs_and_params, verify_snapshot_table_file
            inputs_ok, msg_in = verify_snapshot_inputs_and_params()
            table_ok, msg_tab = verify_snapshot_table_file("market_97_puts_validation.csv", phase3_market_csv)
            if inputs_ok and table_ok:
                df_candidate_p3 = pd.read_csv(phase3_market_csv)
                required_p3_cols = ["contractSymbol", "proprietary_default_usd", "proprietary_fine_usd"]
                p3_cols_ok = all(c in df_candidate_p3.columns for c in required_p3_cols)
                if (
                    p3_cols_ok and
                    len(df_candidate_p3) == 97 and
                    np.isfinite(df_candidate_p3["proprietary_default_usd"]).all() and
                    np.isfinite(df_candidate_p3["proprietary_fine_usd"]).all()
                ):
                    df_p3 = df_candidate_p3
                    can_reuse_phase3 = True
                    print(f"  [INTEGRATION] PoC canonical vector and Phase 3 snapshot cryptographically verified ({msg_tab}).")
                else:
                    print("  [INTEGRATION WARNING] Phase 3 snapshot schema invalid or non-finite values detected. Falling back to fresh valuation.")
            else:
                print(f"  [INTEGRATION WARNING] Phase 3 snapshot verification failed ({msg_tab}; {msg_in}). Falling back to fresh valuation.")
        except Exception as e:
            print(f"  [INTEGRATION WARNING] Error verifying Phase 3 snapshot: {e}. Falling back to fresh valuation.")
    else:
        print("  [FRESH VALUATION] Winner vector differs or fresh computation required: Invoking Heston2DSolver().price(...)")

    # QuantLib engine setup
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
    solver_prop = Heston2DSolver() if not can_reuse_phase3 else None

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

        # QL Production Grid (Nx=160, Nv=80, m_t=max(60, round(300*T)))
        t_steps_prod = max(60, int(round(300.0 * tau_years)))
        eng_prod = ql.FdHestonVanillaEngine(model_prod, t_steps_prod, 160, 80)
        opt.setPricingEngine(eng_prod)
        ql_prod_price = float(opt.NPV())

        # QL Fine Grid (Nx=280, Nv=140, m_t=max(120, round(700*T)))
        t_steps_fine = max(120, int(round(700.0 * tau_years)))
        eng_fine = ql.FdHestonVanillaEngine(model_fine, t_steps_fine, 280, 140)
        opt.setPricingEngine(eng_fine)
        ql_fine_price = float(opt.NPV())

        if can_reuse_phase3 and df_p3 is not None and symbol in df_p3["contractSymbol"].values:
            row_p3 = df_p3[df_p3["contractSymbol"] == symbol].iloc[0]
            prop_def_price = float(row_p3["proprietary_default_usd"])
            prop_fine_price = float(row_p3["proprietary_fine_usd"])
            prov = "PHASE3_VERIFIED_AUDITED"
        else:
            # Correct public solver API: Heston2DSolver().price(...)
            m_t_def = max(60, int(round(300.0 * tau_years)))
            res_def = solver_prop.price(
                strike=K, maturity_years=tau_years, params=params, curve=curve,
                is_american=True, n_s=160, n_v=80, m_t=m_t_def
            )
            prop_def_price = float(res_def.price)

            m_t_fine = max(100, int(round(600.0 * tau_years)))
            res_fine = solver_prop.price(
                strike=K, maturity_years=tau_years, params=params, curve=curve,
                is_american=True, n_s=240, n_v=120, m_t=m_t_fine
            )
            prop_fine_price = float(res_fine.price)
            prov = "FRESH_SOLVER_2D_VALUATION"

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
            "status_discrepancy_gate_002": "PASS" if abs_diff_discrepancy <= 0.002 else "FAIL",
            "valuation_provenance": prov
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
            "gate_mae_pass": bool(gate_mae),
            "gate_rmse_pass": bool(gate_rmse)
        })

    df_part = pd.DataFrame(part_records)
    df_part.to_csv(out_part_csv, index=False)
    print(f"  [EXPORTED] {out_part_csv}")

    # Tenor Summary (12 distinct tenors in the clean dataset)
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
    """Verifies mesh stability on the top 3 pricing discrepancy contracts under QL 1000 and Prop Extra-fine (320x160)."""
    print("\n=== STEP 6: Worst 3 Pricing Discrepancy Mesh Controls ===")
    out_csv = PHASE4_DIR / "heston_worst3_mesh_controls.csv"

    # Identify top 3 discrepancy contracts
    top3 = df_puts.sort_values(by="abs_diff_prop_fine_vs_ql_fine_usd", ascending=False).head(3).copy()

    p_win = np.array(winner_meta["calibrated_parameters_raw"], dtype=float)
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

    solver_prop = Heston2DSolver()
    records = []

    for _, r in top3.iterrows():
        sym = str(r["contractSymbol"])
        K = float(r["strike"])
        tau_yr = float(r["tau_years"])
        parts = str(r["expirationDate"]).split("-")
        exp_date = ql.Date(int(parts[2]), int(parts[1]), int(parts[0]))
        payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
        exercise = ql.AmericanExercise(eval_date, exp_date)
        opt = ql.VanillaOption(payoff, exercise)

        # QL 1000 ultra-fine: steps=max(160, round(1000*T)), Nx=360, Nv=180
        m_t_1000 = max(160, int(round(1000.0 * tau_yr)))
        eng_1000 = ql.FdHestonVanillaEngine(model_1000, m_t_1000, 360, 180)
        opt.setPricingEngine(eng_1000)
        ql_1000_price = float(opt.NPV())

        # Propio Extra-fine: Ns=320, Nv=160, m_t=max(160, round(900*T))
        m_t_ex = max(160, int(round(900.0 * tau_yr)))
        res_ex = solver_prop.price(
            strike=K, maturity_years=tau_yr, params=params, curve=curve,
            is_american=True, n_s=320, n_v=160, m_t=m_t_ex
        )
        prop_ex_price = float(res_ex.price)

        diff_ql = float(r["ql_fine_price"]) - ql_1000_price
        diff_prop = float(r["prop_fine_price"]) - prop_ex_price

        records.append({
            "contractSymbol": sym,
            "strike": K,
            "tau_days": int(r["tau_days"]),
            "tenor_label": str(r["tenor_label"]),
            "partition": str(r["partition"]),
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
            "gate_ql_stability_pass": bool(abs(diff_ql) <= 0.0005),
            "gate_prop_stability_pass": bool(abs(diff_prop) <= 0.002)
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

    p_win = np.array(winner_meta["calibrated_parameters_raw"], dtype=float)
    params = HestonParams(v0=p_win[0], kappa=p_win[1], theta=p_win[2], xi=p_win[3], rho=p_win[4])

    strikes = [9.0, 12.33, 17.0]
    maturities = [
        {"label": "31d", "tau_days": 31, "tau_years": 31.0 / 365.0},
        {"label": "94d", "tau_days": 94, "tau_years": 94.0 / 365.0},
        {"label": "430d", "tau_days": 430, "tau_years": 430.0 / 365.0},
    ]

    records = []
    prices_am_grid = {}
    solver = Heston2DSolver()

    for mat in maturities:
        t_label = mat["label"]
        tau_yr = mat["tau_years"]
        t_days = mat["tau_days"]
        r_rate = curve.get_zero_rate(tau_yr)
        prices_am_grid[t_label] = {}

        m_t = max(100, int(round(600.0 * tau_yr)))

        for K in strikes:
            res_am = solver.price(strike=K, maturity_years=tau_yr, params=params, curve=curve, is_american=True, n_s=240, n_v=120, m_t=m_t)
            res_eu = solver.price(strike=K, maturity_years=tau_yr, params=params, curve=curve, is_american=False, n_s=240, n_v=120, m_t=m_t)

            p_am = float(res_am.price)
            p_eu = float(res_eu.price)
            intrinsic = max(0.0, K - SPOT_PRICE)
            eep = p_am - p_eu

            prices_am_grid[t_label][K] = p_am

            violates_intrinsic = bool(p_am < intrinsic - 1e-4)
            violates_eep = bool(p_am < p_eu - 1e-4)

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
                "monotonicity_strike_pass": True,
                "monotonicity_maturity_pass": True,
                "convexity_strike_pass": True
            })

    df_econ = pd.DataFrame(records)

    # Monotonicity in Strike: P(K1) <= P(K2) <= P(K3)
    for mat in maturities:
        t_label = mat["label"]
        p9 = prices_am_grid[t_label][9.0]
        p12 = prices_am_grid[t_label][12.33]
        p17 = prices_am_grid[t_label][17.0]
        strike_mono = bool((p9 <= p12 + 1e-4) and (p12 <= p17 + 1e-4))
        df_econ.loc[df_econ["tenor_label"] == t_label, "monotonicity_strike_pass"] = strike_mono

    # Monotonicity in Maturity: P(31d) <= P(94d) <= P(430d)
    for K in strikes:
        p_31 = prices_am_grid["31d"][K]
        p_94 = prices_am_grid["94d"][K]
        p_430 = prices_am_grid["430d"][K]
        mat_mono = bool((p_31 <= p_94 + 1e-4) and (p_94 <= p_430 + 1e-4))
        df_econ.loc[df_econ["strike"] == K, "monotonicity_maturity_pass"] = mat_mono

    # Discrete Convexity
    for mat in maturities:
        t_label = mat["label"]
        p1 = prices_am_grid[t_label][9.0]
        p2 = prices_am_grid[t_label][12.33]
        p3 = prices_am_grid[t_label][17.0]
        h1 = 12.33 - 9.0
        h2 = 17.0 - 12.33
        slope1 = (p2 - p1) / h1
        slope2 = (p3 - p2) / h2
        convex = bool(slope2 >= slope1 - 1e-4)
        df_econ.loc[df_econ["tenor_label"] == t_label, "convexity_strike_pass"] = convex

    df_econ.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv} (9 economic controls)")
    return df_econ


def step8_parameter_sensitivity(
    winner_meta: Dict[str, Any],
    train_df: pd.DataFrame,
    ts_handle: Any
) -> pd.DataFrame:
    """
    Evaluates parameter sensitivity under +/-5% shocks on v0, kappa, theta, xi and +/-0.02 on rho.
    Prices 12 representative contracts covering K in {9.0, 12.33, 17.0} and T in {31d, 94d, 430d, 794d}.
    """
    print("\n=== STEP 8: Parameter Sensitivity and Local Curvature Analysis (12 Contracts) ===")
    out_csv = PHASE4_DIR / "heston_parameter_sensitivity.csv"

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

    # 12 representative contracts (3 strikes x 4 maturities)
    rep_contracts = [
        # T = 31d
        {"id": "K9_T31", "strike": 9.0, "tau_years": 31.0 / 365.0, "exp_date": ql.Date(18, 12, 2026)},
        {"id": "K12_T31", "strike": 12.33, "tau_years": 31.0 / 365.0, "exp_date": ql.Date(18, 12, 2026)},
        {"id": "K17_T31", "strike": 17.0, "tau_years": 31.0 / 365.0, "exp_date": ql.Date(18, 12, 2026)},
        # T = 94d
        {"id": "K9_T94", "strike": 9.0, "tau_years": 94.0 / 365.0, "exp_date": ql.Date(19, 2, 2027)},
        {"id": "K12_T94", "strike": 12.33, "tau_years": 94.0 / 365.0, "exp_date": ql.Date(19, 2, 2027)},
        {"id": "K17_T94", "strike": 17.0, "tau_years": 94.0 / 365.0, "exp_date": ql.Date(19, 2, 2027)},
        # T = 430d
        {"id": "K9_T430", "strike": 9.0, "tau_years": 430.0 / 365.0, "exp_date": ql.Date(21, 1, 2028)},
        {"id": "K12_T430", "strike": 12.33, "tau_years": 430.0 / 365.0, "exp_date": ql.Date(21, 1, 2028)},
        {"id": "K17_T430", "strike": 17.0, "tau_years": 430.0 / 365.0, "exp_date": ql.Date(21, 1, 2028)},
        # T = 794d
        {"id": "K9_T794", "strike": 9.0, "tau_years": 794.0 / 365.0, "exp_date": ql.Date(19, 1, 2029)},
        {"id": "K12_T794", "strike": 12.33, "tau_years": 794.0 / 365.0, "exp_date": ql.Date(19, 1, 2029)},
        {"id": "K17_T794", "strike": 17.0, "tau_years": 794.0 / 365.0, "exp_date": ql.Date(19, 1, 2029)},
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

    # Scenarios respecting parameter boundaries
    scenarios = [
        {"id": "BASE", "desc": "Unshocked calibrated vector", "param": "none", "nominal_shock": 0.0, "vec": p_win.copy()},
        {"id": "V0_PLUS_5PCT", "desc": "v0 + 5%", "param": "v0", "nominal_shock": +0.05, "vec": np.array([base_v0 * 1.05, base_kappa, base_theta, base_xi, base_rho])},
        {"id": "V0_MINUS_5PCT", "desc": "v0 - 5%", "param": "v0", "nominal_shock": -0.05, "vec": np.array([base_v0 * 0.95, base_kappa, base_theta, base_xi, base_rho])},
        {"id": "KAPPA_PLUS_5PCT", "desc": "kappa + 5%", "param": "kappa", "nominal_shock": +0.05, "vec": np.array([base_v0, base_kappa * 1.05, base_theta, base_xi, base_rho])},
        {"id": "KAPPA_MINUS_5PCT", "desc": "kappa - 5%", "param": "kappa", "nominal_shock": -0.05, "vec": np.array([base_v0, base_kappa * 0.95, base_theta, base_xi, base_rho])},
        {"id": "THETA_PLUS_5PCT", "desc": "theta + 5%", "param": "theta", "nominal_shock": +0.05, "vec": np.array([base_v0, base_kappa, base_theta * 1.05, base_xi, base_rho])},
        {"id": "THETA_MINUS_5PCT", "desc": "theta - 5%", "param": "theta", "nominal_shock": -0.05, "vec": np.array([base_v0, base_kappa, base_theta * 0.95, base_xi, base_rho])},
        {"id": "XI_PLUS_5PCT", "desc": "xi + 5%", "param": "xi", "nominal_shock": +0.05, "vec": np.array([base_v0, base_kappa, base_theta, base_xi * 1.05, base_rho])},
        {"id": "XI_MINUS_5PCT", "desc": "xi - 5%", "param": "xi", "nominal_shock": -0.05, "vec": np.array([base_v0, base_kappa, base_theta, base_xi * 0.95, base_rho])},
        {"id": "RHO_PLUS_002", "desc": "rho + 0.02", "param": "rho", "nominal_shock": +0.02, "vec": np.array([base_v0, base_kappa, base_theta, base_xi, min(0.95, base_rho + 0.02)])},
        {"id": "RHO_MINUS_002", "desc": "rho - 0.02 (truncated to lower bound -0.95)", "param": "rho", "nominal_shock": -0.02, "vec": np.array([base_v0, base_kappa, base_theta, base_xi, max(-0.95, base_rho - 0.02)])},
    ]

    records = []
    for sc in scenarios:
        vec = sc["vec"]
        hp = HestonParams.from_array(vec)

        # Calculate effective shock accounting for boundary truncation
        if sc["param"] == "rho":
            effective_shock = float(vec[4] - base_rho)
        elif sc["param"] != "none":
            idx_p = {"v0": 0, "kappa": 1, "theta": 2, "xi": 3}[sc["param"]]
            effective_shock = float((vec[idx_p] - p_win[idx_p]) / p_win[idx_p])
        else:
            effective_shock = 0.0

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

        if sc["id"] == "BASE":
            curv_evidence = "BASE_MINIMUM"
        elif delta_sse > 0:
            curv_evidence = "NONZERO_GRADIENT_INCREASE"
        else:
            curv_evidence = "FLAT_OR_TRUNCATED_DESCENT"

        rec = {
            "scenario_id": sc["id"],
            "shock_description": sc["desc"],
            "param_shocked": sc["param"],
            "nominal_shock_val": sc["nominal_shock"],
            "effective_shock_val": effective_shock,
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
            "gradient_curvature_evidence": curv_evidence
        }
        # Add all 12 representative prices
        for c in rep_contracts:
            rec[f"price_{c['id']}"] = sc_prices[c["id"]]

        records.append(rec)

    df_sens = pd.DataFrame(records)
    df_sens.to_csv(out_csv, index=False)
    print(f"  [EXPORTED] {out_csv} (11 sensitivity scenarios x 12 contracts)")
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

    # Print exact metrics
    mae_prop = float(df_base["abs_err_heston_prop_fine"].mean())
    rmse_prop = float(np.sqrt((df_base["abs_err_heston_prop_fine"] ** 2).mean()))
    mae_ql = float(df_base["abs_err_heston_ql_fine"].mean())
    rmse_ql = float(np.sqrt((df_base["abs_err_heston_ql_fine"] ** 2).mean()))
    mae_flat = float(df_base["abs_err_flat_common"].mean())
    rmse_flat = float(np.sqrt((df_base["abs_err_flat_common"] ** 2).mean()))
    mae_svi = float(df_base["abs_err_svi_historical"].mean())
    rmse_svi = float(np.sqrt((df_base["abs_err_svi_historical"] ** 2).mean()))

    print(f"  [BASELINE RECONCILIATION ON 84 PUTS]")
    print(f"    Heston Prop Fine:  MAE = {mae_prop:.6f} USD | RMSE = {rmse_prop:.6f} USD")
    print(f"    Heston QL Fine:    MAE = {mae_ql:.6f} USD | RMSE = {rmse_ql:.6f} USD")
    print(f"    Flat Common Curve: MAE = {mae_flat:.6f} USD | RMSE = {rmse_flat:.6f} USD")
    print(f"    SVI Historical R3: MAE = {mae_svi:.6f} USD | RMSE = {rmse_svi:.6f} USD")
    print(f"    MAE Reduction Heston Prop vs Flat Common: {((mae_flat - mae_prop) / mae_flat * 100.0):.2f}%")

    return df_base


def step10_build_manifest(
    input_hashes: Dict[str, str],
    config: Dict[str, Any],
    winner_meta: Dict[str, Any],
    df_puts: pd.DataFrame,
    df_part: pd.DataFrame,
    df_worst3: pd.DataFrame,
    df_econ: pd.DataFrame,
    start_time: float,
    out_manifest_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Compiles complete Phase 4 execution manifest and executes strict raw-data validation gates.
    Fails immediately if any required output is missing, partitions mismatch, or prices are invalid.
    """
    print("\n=== STEP 10: Building Cryptographic Execution Manifest & Strict Raw Validation ===")
    out_manifest = out_manifest_path or (PHASE4_DIR / "phase4_execution_manifest.json")
    runtime = time.time() - start_time

    # Output file hashes: strictly verify all 12 output files exist and are non-empty
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
        "heston_baseline_comparison.csv",
        "refinement_A_res.json",
        "refinement_B_res.json",
        "refinement_C_res.json"
    ]

    out_hashes = {}
    for fname in out_files:
        fpath = PHASE4_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Missing required Phase 4 output file: {fname}")
        if fpath.stat().st_size == 0:
            raise ValueError(f"Required Phase 4 output file is empty: {fname}")
        out_hashes[fname] = compute_file_sha256(fpath)

    # Raw Data Validation on df_puts
    clean_puts = pd.read_csv(DATA_DIR / "puts_selected_clean.csv")
    split_meta = json.load(open(DATA_DIR / "data_split_manifest.json"))

    if len(df_puts) != 97 or len(clean_puts) != 97:
        raise ValueError(
            f"Full pricing DataFrame and clean puts must both have exactly 97 contracts, found {len(df_puts)} and {len(clean_puts)}"
        )
    if clean_puts["contractSymbol"].duplicated().any() or df_puts["contractSymbol"].duplicated().any():
        raise ValueError("Duplicate contractSymbol detected in pricing or clean puts dataset")
    if set(df_puts["contractSymbol"]) != set(clean_puts["contractSymbol"]):
        raise ValueError("Contract symbols in df_puts do not match official puts_selected_clean.csv")

    # Strict schema and finiteness validation before any reductions
    required_pricing_cols = [
        "contractSymbol", "strike", "tau_years", "partition", "lastPrice",
        "ql_prod_price", "ql_fine_price", "prop_default_price", "prop_fine_price"
    ]
    for col in required_pricing_cols:
        if col not in df_puts.columns:
            raise ValueError(f"Missing required pricing column in df_puts: '{col}'")
        if df_puts[col].isna().any():
            bad_mask = df_puts[col].isna()
            bad_contracts = df_puts.loc[bad_mask, "contractSymbol"].tolist()
            raise ValueError(
                f"Non-finite pricing value (NaN/Inf) detected in column '{col}' for contract(s): {bad_contracts}"
            )

    numeric_pricing_cols = [
        "strike", "tau_years", "lastPrice", "ql_prod_price", "ql_fine_price",
        "prop_default_price", "prop_fine_price"
    ]
    for col in numeric_pricing_cols:
        series_num = pd.to_numeric(df_puts[col], errors="coerce")
        if not np.isfinite(series_num).all():
            bad_mask = ~np.isfinite(series_num)
            bad_contracts = df_puts.loc[bad_mask, "contractSymbol"].tolist()
            raise ValueError(
                f"Non-finite pricing value (NaN/Inf) detected in column '{col}' for contract(s): {bad_contracts}"
            )

    # Reconcile pricing table against canonical market inputs 1-to-1 at serialization tolerance (1e-6)
    merged_clean = pd.merge(
        df_puts,
        clean_puts[["contractSymbol", "strike", "lastPrice", "tau_years", "tau_days", "expirationDate"]],
        on="contractSymbol",
        suffixes=("", "_canon"),
        validate="one_to_one"
    )
    for idx, row in merged_clean.iterrows():
        sym = row["contractSymbol"]
        diff_p = abs(float(row["lastPrice"]) - float(row["lastPrice_canon"]))
        if diff_p > 1e-6:
            raise ValueError(
                f"Canonical market price mismatch for contract '{sym}': exported lastPrice {row['lastPrice']} differs from canonical market data {row['lastPrice_canon']} (diff={diff_p:.6e} USD)"
            )
        diff_k = abs(float(row["strike"]) - float(row["strike_canon"]))
        if diff_k > 1e-6:
            raise ValueError(
                f"Canonical strike mismatch for contract '{sym}': exported strike {row['strike']} differs from canonical {row['strike_canon']} (diff={diff_k:.6e})"
            )
        diff_tau = abs(float(row["tau_years"]) - float(row["tau_years_canon"]))
        if diff_tau > 1e-6:
            raise ValueError(
                f"Canonical tau_years mismatch for contract '{sym}': exported tau_years {row['tau_years']} differs from canonical {row['tau_years_canon']} (diff={diff_tau:.6e})"
            )
        if "tau_days" in row and "tau_days_canon" in row:
            if int(row["tau_days"]) != int(row["tau_days_canon"]):
                raise ValueError(
                    f"Canonical tau_days mismatch for contract '{sym}': exported tau_days {row['tau_days']} != canonical {row['tau_days_canon']}"
                )
        if "expirationDate" in row and "expirationDate_canon" in row:
            if str(row["expirationDate"]).strip() != str(row["expirationDate_canon"]).strip():
                raise ValueError(
                    f"Canonical expirationDate mismatch for contract '{sym}': exported expirationDate '{row['expirationDate']}' != canonical '{row['expirationDate_canon']}'"
                )

    train_syms = set(split_meta["train_symbols"])
    sh_syms = set(split_meta["strike_holdout_symbols"])
    th_syms = set(split_meta["tenor_holdout_symbols"])

    # Reconcile partition label of every contract against canonical split
    for idx, row in df_puts.iterrows():
        sym = row["contractSymbol"]
        expected_part = (
            "train" if sym in train_syms
            else ("strike_holdout" if sym in sh_syms
            else ("tenor_holdout" if sym in th_syms
            else "unknown"))
        )
        if row["partition"] != expected_part:
            raise ValueError(
                f"Partition label mismatch for contract '{sym}': declared '{row['partition']}', expected '{expected_part}'"
            )

    df_train = df_puts[df_puts["contractSymbol"].isin(train_syms)]
    df_sh = df_puts[df_puts["contractSymbol"].isin(sh_syms)]
    df_th = df_puts[df_puts["contractSymbol"].isin(th_syms)]

    if len(df_train) != 60:
        raise ValueError(f"Train partition must have exactly 60 contracts, found {len(df_train)}")
    if len(df_sh) != 22:
        raise ValueError(f"Strike holdout must have exactly 22 contracts, found {len(df_sh)}")
    if len(df_th) != 15:
        raise ValueError(f"Tenor holdout must have exactly 15 contracts, found {len(df_th)}")

    # Reconcile partition summary df_part counts against df_puts
    for _, pr in df_part.iterrows():
        p_name = pr["partition"]
        expected_count = 97 if p_name == "total" else len(df_puts[df_puts["partition"] == p_name])
        if int(pr["n_contracts"]) != expected_count:
            raise ValueError(
                f"Contradictory partition summary: partition '{p_name}' claims {pr['n_contracts']} contracts, expected {expected_count}"
            )

    # Recalculate metrics directly from verified finite raw contract prices
    raw_train_mae = float(np.mean(np.abs(df_train["prop_fine_price"] - df_train["lastPrice"])))
    raw_train_rmse = float(np.sqrt(np.mean((df_train["prop_fine_price"] - df_train["lastPrice"]) ** 2)))
    raw_sh_mae = float(np.mean(np.abs(df_sh["prop_fine_price"] - df_sh["lastPrice"])))
    raw_th_mae = float(np.mean(np.abs(df_th["prop_fine_price"] - df_th["lastPrice"])))
    raw_max_disc = float(np.max(np.abs(df_puts["prop_fine_price"] - df_puts["ql_fine_price"])))

    # Raw Parameter Validation
    p_win = np.array(winner_meta["calibrated_parameters_raw"], dtype=float)
    if len(p_win) != 5:
        raise ValueError("Calibrated parameters vector must have length 5")
    for i, (b_lo, b_hi) in enumerate(HESTON_BOUNDS):
        if not (b_lo <= p_win[i] <= b_hi):
            raise ValueError(f"Calibrated parameter {i} violates bounds [{b_lo}, {b_hi}]: {p_win[i]}")

    # Validate that at least one local refinement converged
    df_refine_check = pd.read_csv(PHASE4_DIR / "heston_local_refinements.csv")
    local_converged = df_refine_check[
        (df_refine_check["start_index"] > 0) &
        (df_refine_check["status"] == 0) &
        (df_refine_check["success"] == True)
    ]
    if len(local_converged) == 0:
        raise RuntimeError("Validation Failure: Zero local refinements converged.")

    # Mesh stability raw price difference gate on df_worst3
    if len(df_worst3) != 3:
        raise ValueError(f"Worst 3 controls must have exactly 3 contracts, found {len(df_worst3)}")

    worst3_required_cols = [
        "contractSymbol", "ql_refined_700_usd", "ql_ultrafine_1000_usd",
        "abs_diff_ql_refinement_usd", "prop_fine_usd", "prop_extrafine_320_usd",
        "abs_diff_prop_refinement_usd", "gate_ql_stability_pass", "gate_prop_stability_pass"
    ]
    for col in worst3_required_cols:
        if col not in df_worst3.columns:
            raise ValueError(f"Missing required column in df_worst3: '{col}'")
        if col not in ["contractSymbol", "gate_ql_stability_pass", "gate_prop_stability_pass"]:
            s_num = pd.to_numeric(df_worst3[col], errors="coerce")
            if not np.isfinite(s_num).all():
                raise ValueError(f"Non-finite value detected in df_worst3 column '{col}'")

    max_raw_diff_ql = 0.0
    max_raw_diff_prop = 0.0
    for _, r in df_worst3.iterrows():
        raw_diff_ql = abs(float(r["ql_refined_700_usd"]) - float(r["ql_ultrafine_1000_usd"]))
        raw_diff_prop = abs(float(r["prop_fine_usd"]) - float(r["prop_extrafine_320_usd"]))
        max_raw_diff_ql = max(max_raw_diff_ql, raw_diff_ql)
        max_raw_diff_prop = max(max_raw_diff_prop, raw_diff_prop)

        if raw_diff_ql > 0.0005:
            raise ValueError(
                f"Mesh stability failure: Contract {r['contractSymbol']} QL discrepancy {raw_diff_ql:.6f} > 0.0005 USD"
            )
        if raw_diff_prop > 0.0020:
            raise ValueError(
                f"Mesh stability failure: Contract {r['contractSymbol']} Prop discrepancy {raw_diff_prop:.6f} > 0.0020 USD"
            )

        # Coherence check between raw differences and declared diff columns
        if abs(raw_diff_ql - float(r["abs_diff_ql_refinement_usd"])) > 1e-7:
            raise ValueError(f"Incoherent QL mesh refinement diff declared for {r['contractSymbol']}")
        if abs(raw_diff_prop - float(r["abs_diff_prop_refinement_usd"])) > 1e-7:
            raise ValueError(f"Incoherent Prop mesh refinement diff declared for {r['contractSymbol']}")
        if not bool(r["gate_ql_stability_pass"]):
            raise ValueError(f"Incoherent gate_ql_stability_pass flag for {r['contractSymbol']}")
        if not bool(r["gate_prop_stability_pass"]):
            raise ValueError(f"Incoherent gate_prop_stability_pass flag for {r['contractSymbol']}")

    # Validate raw economic controls from real evidence
    if len(df_econ) != 9:
        raise ValueError(f"Economic controls DataFrame must have exactly 9 contracts, found {len(df_econ)}")

    econ_required_cols = [
        "contract_id", "strike", "tau_days", "tau_years", "spot", "price_american", "price_european"
    ]
    for col in econ_required_cols:
        if col not in df_econ.columns:
            raise ValueError(f"Missing required economic control column in df_econ: '{col}'")
        if df_econ[col].isna().any():
            raise ValueError(f"Missing/NaN value detected in df_econ column '{col}'")

    # Strict numeric finiteness check on all economic variables
    econ_numeric_cols = ["strike", "tau_days", "tau_years", "spot", "price_american", "price_european"]
    if "early_exercise_premium" in df_econ.columns:
        econ_numeric_cols.append("early_exercise_premium")
    if "intrinsic_floor" in df_econ.columns:
        econ_numeric_cols.append("intrinsic_floor")
    for col in econ_numeric_cols:
        s_num = pd.to_numeric(df_econ[col], errors="coerce")
        if not np.isfinite(s_num).all():
            bad_contracts = df_econ.loc[~np.isfinite(s_num), "contract_id"].tolist()
            raise ValueError(
                f"Non-finite value (NaN/Inf) detected in df_econ column '{col}' for contract(s): {bad_contracts}"
            )

    # Check 9 unique expected tuples of strikes {9.0, 12.33, 17.0} and days {31, 94, 430}
    expected_tuples = {
        (9.0, 31), (12.33, 31), (17.0, 31),
        (9.0, 94), (12.33, 94), (17.0, 94),
        (9.0, 430), (12.33, 430), (17.0, 430)
    }
    actual_tuples = set(zip(df_econ["strike"].round(2), df_econ["tau_days"].astype(int)))
    if actual_tuples != expected_tuples or len(df_econ["contract_id"].unique()) != 9:
        raise ValueError(
            f"Economic controls grid mismatch or duplicates: expected 9 unique (K, T_days) tuples, found {len(actual_tuples)} unique"
        )

    if not np.allclose(df_econ["spot"], SPOT_PRICE, atol=1e-6):
        raise ValueError(f"Economic controls spot price mismatch: expected {SPOT_PRICE}")

    # Derive intrinsic, EEP, and test rigorous financial bounds
    econ_grid = {}
    for _, er in df_econ.iterrows():
        c_id = er["contract_id"]
        K = float(er["strike"])
        t_days = int(er["tau_days"])
        p_am = float(er["price_american"])
        p_eu = float(er["price_european"])

        derived_intrinsic = max(0.0, K - SPOT_PRICE)
        derived_eep = p_am - p_eu

        # Bounds: 0 <= derived_intrinsic <= p_am <= K and p_eu <= p_am
        if p_eu < -1e-4:
            raise ValueError(f"Economic Failure on {c_id}: European price {p_eu:.6f} < 0.0")
        if p_am < derived_intrinsic - 1e-4:
            raise ValueError(
                f"Economic Failure on {c_id}: American put price {p_am:.6f} below intrinsic floor {derived_intrinsic:.6f}"
            )
        if p_am < p_eu - 1e-4:
            raise ValueError(
                f"Economic Failure on {c_id}: American put price {p_am:.6f} below European price {p_eu:.6f} (negative EEP)"
            )
        if p_am > K + 1e-4:
            raise ValueError(
                f"Economic Failure on {c_id}: American put price {p_am:.6f} exceeds strike upper bound {K:.6f}"
            )
        if p_eu > K + 1e-4:
            raise ValueError(
                f"Economic Failure on {c_id}: European put price {p_eu:.6f} exceeds strike upper bound {K:.6f}"
            )

        # Coherence with declared columns
        if "intrinsic_floor" in er:
            if abs(float(er["intrinsic_floor"]) - derived_intrinsic) > 1e-4:
                raise ValueError(f"Incoherent intrinsic_floor declared for {c_id}")
        if "early_exercise_premium" in er:
            if abs(float(er["early_exercise_premium"]) - derived_eep) > 1e-4:
                raise ValueError(f"Incoherent early_exercise_premium declared for {c_id}")

        if t_days not in econ_grid:
            econ_grid[t_days] = {}
        econ_grid[t_days][K] = p_am

    # Recalculate strike monotonicity from raw prices: P(9) <= P(12.33) <= P(17)
    for t_days in [31, 94, 430]:
        p9 = econ_grid[t_days][9.0]
        p12 = econ_grid[t_days][12.33]
        p17 = econ_grid[t_days][17.0]
        if not (p9 <= p12 + 1e-4 and p12 <= p17 + 1e-4):
            raise ValueError(
                f"Economic Validation Failure: Strike monotonicity violated for tenor {t_days}d: P(9)={p9:.6f}, P(12.33)={p12:.6f}, P(17)={p17:.6f}"
            )

    # Recalculate maturity monotonicity from raw prices: P(31d) <= P(94d) <= P(430d)
    for K in [9.0, 12.33, 17.0]:
        p31 = econ_grid[31][K]
        p94 = econ_grid[94][K]
        p430 = econ_grid[430][K]
        if not (p31 <= p94 + 1e-4 and p94 <= p430 + 1e-4):
            raise ValueError(
                f"Economic Validation Failure: Maturity monotonicity violated for strike {K}: P(31d)={p31:.6f}, P(94d)={p94:.6f}, P(430d)={p430:.6f}"
            )

    # Recalculate discrete strike convexity from raw prices
    for t_days in [31, 94, 430]:
        p1 = econ_grid[t_days][9.0]
        p2 = econ_grid[t_days][12.33]
        p3 = econ_grid[t_days][17.0]
        h1 = 12.33 - 9.0
        h2 = 17.0 - 12.33
        slope1 = (p2 - p1) / h1
        slope2 = (p3 - p2) / h2
        if slope2 < slope1 - 1e-4:
            raise ValueError(
                f"Economic Validation Failure: Strike convexity violated for tenor {t_days}d: slope1={slope1:.6f}, slope2={slope2:.6f}"
            )

    # Coherence with declared boolean flags
    for flag_col in ["monotonicity_strike_pass", "monotonicity_maturity_pass", "convexity_strike_pass"]:
        if flag_col in df_econ.columns:
            if not bool(df_econ[flag_col].all()):
                raise ValueError(f"Economic Validation Failure: Declared flag {flag_col} contains False")

    # Gate dictionary derived from verified raw values
    gates = {
        "gate_coverage_97_puts": bool(len(df_puts) == 97 and len(df_train) == 60 and len(df_sh) == 22 and len(df_th) == 15),
        "gate_train_mae_le_008": bool(raw_train_mae <= 0.080),
        "gate_train_rmse_le_012": bool(raw_train_rmse <= 0.120),
        "gate_strike_holdout_mae_le_010": bool(raw_sh_mae <= 0.100),
        "gate_tenor_holdout_mae_le_010": bool(raw_th_mae <= 0.100),
        "gate_solver_discrepancy_le_002": bool(raw_max_disc <= 0.0020),
        "gate_mesh_stability_worst3_ql_le_0005": bool(max_raw_diff_ql <= 0.0005 and df_worst3["gate_ql_stability_pass"].all()),
        "gate_mesh_stability_worst3_prop_le_002": bool(max_raw_diff_prop <= 0.0020 and df_worst3["gate_prop_stability_pass"].all()),
        "gate_economic_properties_pass": True,
        "gate_local_refinement_converged": True,
        "gate_parameters_within_bounds": True
    }
    all_passed = bool(all(gates.values()))

    manifest = {
        "phase": "PHASE_4",
        "title": "Classical Heston Q Calibration and Global Validation",
        "base_commit": "12664a8ca88fd9c3f365fe449391af9deeb5f19d",
        "last_approved_global_commit": "09d9beb060a4a80d9dc4ae7035407cbc8e81e061",
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime_wall_seconds": float(runtime),
        "runtime_breakdown": {
            "validation_wall_seconds": float(runtime),
            "refinements_cumulative_optimization_seconds": 12474.12,
            "notes": "Refinements executed via L-BFGS-B (Refinement A: 2938.49s, B: 3929.56s, C: 5606.07s). Manifest runtime measures verification, replay and validation gates."
        },
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
        "recalculated_raw_metrics": {
            "train_mae": raw_train_mae,
            "train_rmse": raw_train_rmse,
            "strike_holdout_mae": raw_sh_mae,
            "tenor_holdout_mae": raw_th_mae,
            "max_solver_discrepancy": raw_max_disc
        },
        "validation_gates": gates,
        "verdict": "PASS" if all_passed else "FAIL",
        "output_files": out_hashes
    }

    with open(out_manifest, "w") as f:
        json.dump(manifest, f, indent=2, cls=NumpyEncoder)
    print(f"  [EXPORTED] {out_manifest}")
    print(f"  [GATE VERDICT] {'PASS' if all_passed else 'FAIL'}")

    if not all_passed:
        raise RuntimeError("Execution Manifest Gates Failed.")

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

    # Step 10: Execution manifest & strict raw validation
    manifest = step10_build_manifest(input_hashes, config, winner_meta, df_puts, df_part, df_worst3, df_econ, t_start)

    print("\n================================================================================")
    print("PHASE 4 PIPELINE COMPLETED SUCCESSFULLY")
    print("================================================================================")
    return manifest


if __name__ == "__main__":
    run_pipeline()
