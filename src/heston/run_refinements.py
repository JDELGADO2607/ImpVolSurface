"""
Optimization Runner and Replay Validator for Phase 4 Local Refinements.
Supports:
1. Replay / Verification Mode: verifies existing refinement JSONs and replays SSEs against market data.
2. Fresh Optimization Mode: runs L-BFGS-B from declared starts on the production grid (Nx=160, Nv=80, m_t=max(60, round(300*T))).
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.heston.rates_curve import get_official_yield_curve
from src.heston.calibration import HestonCalibrator, HESTON_BOUNDS


STARTS_CONFIG = {
    "A": {
        "index": 2,
        "name": "Refinement_A_Start_2",
        "description": "Local refinement from historical Start 2 (PoC starting vector)",
        "params": [0.186138, 2.725460, 0.213680, 0.481785, -0.949807],
        "filename": "refinement_A_res.json"
    },
    "B": {
        "index": 5,
        "name": "Refinement_B_Start_5",
        "description": "Local refinement from historical Start 5",
        "params": [0.185765, 1.776739, 0.220899, 0.407838, -0.887226],
        "filename": "refinement_B_res.json"
    },
    "C": {
        "index": 1,
        "name": "Refinement_C_Start_1",
        "description": "Local refinement from historical Start 1",
        "params": [0.186800, 1.991740, 0.225116, 0.617904, -0.646363],
        "filename": "refinement_C_res.json"
    }
}


def get_production_calibrator() -> HestonCalibrator:
    """Instantiates HestonCalibrator on the official train dataset and production grid."""
    split_meta = json.load(open(root_dir / "data" / "heston" / "data_split_manifest.json"))
    df_all = pd.read_csv(root_dir / "data" / "heston" / "puts_selected_clean.csv")
    train_df = df_all[df_all["contractSymbol"].isin(split_meta["train_symbols"])].copy()

    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure(dense_daily=True)

    return HestonCalibrator(
        train_df,
        yield_term_structure=ts_handle,
        grid_t_factor=300.0,
        min_time_steps=60,
        grid_x=160,
        grid_v=80
    )


def run_single_optimization(
    start_key: str,
    out_dir: Path,
    maxiter: int = 35
) -> Dict[str, Any]:
    """Runs fresh L-BFGS-B local refinement from a designated start key ('A', 'B', or 'C')."""
    start_def = STARTS_CONFIG[start_key]
    out_file = out_dir / start_def["filename"]
    calibrator = get_production_calibrator()

    print(f"\n[OPTIMIZATION] Starting {start_def['name']} (Start {start_def['index']})")
    print(f"  Init params: {start_def['params']}")
    print(f"  Grid: Nx=160, Nv=80, m_t=max(60, round(300*T))")
    print(f"  Bounds: {HESTON_BOUNDS}")

    def callback(xk):
        print(f"  [{start_def['name']}] Iter completed: {xk.tolist()}", flush=True)

    t0 = time.time()
    res = calibrator.run_single_start(
        start_def={
            "index": start_def["index"],
            "name": start_def["name"],
            "description": start_def["description"],
            "params": start_def["params"]
        },
        maxiter=maxiter,
        eps=1e-3,
        options={"ftol": 1e-7, "gtol": 1e-5},
        callback=callback
    )
    res["wall_clock_seconds"] = round(time.time() - t0, 2)

    with open(out_file, "w") as fp:
        json.dump(res, fp, indent=2)

    print(f"  [SAVED] {out_file} (Status: {res['status']}, SSE: {res['final_sse']:.6f})")
    return res


def replay_and_verify_refinements(out_dir: Path) -> List[Dict[str, Any]]:
    """
    Validates presence of existing refinement JSONs and verifies machine-precision
    reproducibility of their initial and final SSE on the production grid.
    """
    calibrator = get_production_calibrator()
    results = []

    print("\n=== REPLAY & VERIFICATION OF HISTORICAL LOCAL REFINEMENTS ===")
    for key, s_def in STARTS_CONFIG.items():
        fpath = out_dir / s_def["filename"]
        if not fpath.exists():
            raise FileNotFoundError(
                f"Refinement JSON missing: {fpath}. "
                f"Run with '--optimize {key}' to execute fresh optimization."
            )

        with open(fpath, "r") as fp:
            data = json.load(fp)

        # Verify initial SSE replay
        init_vec = np.array(data["init_params_raw"], dtype=float)
        replayed_init_sse = calibrator.evaluate_sse(init_vec)
        diff_init = abs(replayed_init_sse - data["init_sse"])

        # Verify final SSE replay
        final_vec = np.array(data["final_params_raw"], dtype=float)
        replayed_final_sse = calibrator.evaluate_sse(final_vec)
        diff_final = abs(replayed_final_sse - data["final_sse"])

        print(f"  [{data['name']}]")
        print(f"    Recorded Init SSE:   {data['init_sse']:.8f} | Replayed: {replayed_init_sse:.8f} | Diff: {diff_init:.2e}")
        print(f"    Recorded Final SSE:  {data['final_sse']:.8f} | Replayed: {replayed_final_sse:.8f} | Diff: {diff_final:.2e}")
        print(f"    Status: {data['status']} ({data['termination_type']}) | Feller: {data['feller_ratio']:.4f}")

        assert diff_init < 1e-7, f"Init SSE replay mismatch for {data['name']}: {diff_init}"
        assert diff_final < 1e-7, f"Final SSE replay mismatch for {data['name']}: {diff_final}"

        results.append(data)

    print("=== ALL HISTORICAL REFINEMENTS VERIFIED AND REPLAYED AT MACHINE PRECISION ===\n")
    return results


def main():
    parser = argparse.ArgumentParser(description="Phase 4 Refinement Runner and Validator")
    parser.add_argument("--optimize", choices=["A", "B", "C", "all"], help="Execute fresh optimization for given start(s)")
    parser.add_argument("--replay-only", action="store_true", help="Only verify and replay existing refinement files")
    parser.add_argument("--maxiter", type=int, default=35, help="Maximum L-BFGS-B iterations")
    parser.add_argument("--out-dir", type=str, default="data/heston/phase4", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.optimize:
        targets = ["A", "B", "C"] if args.optimize == "all" else [args.optimize]
        for t in targets:
            run_single_optimization(t, out_dir=out_dir, maxiter=args.maxiter)
    else:
        replay_and_verify_refinements(out_dir)


if __name__ == "__main__":
    main()
