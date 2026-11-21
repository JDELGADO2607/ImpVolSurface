"""
Phase 1 End-to-End Execution Pipeline: Classical Heston Proof-of-Concept (PoC).

Enforces:
- Clean workspace isolation in data/heston/phase1/
- Zero writes to historical or official directories
- Strict data provenance with separation of historical transcription timestamp (16:20 NY) and execution timestamp
- Cryptographic cache validation (hashes, schema, bounds, non-negative SSE, and objective replay)
- Optimization solely on training split (60 American puts) across 5 pre-declared starts
- Out-of-sample evaluation on strike holdout (22 puts) and tenor holdout (15 puts)
- External contrast on 142 call options
- Common 84 puts comparison against constant flat baseline (under common curve) and historical SVI
- Unified production grid (tFactor=300, min 60, x=160, v=80)
- Separate temporal and spatial grid refinements confirming <= 0.0020 USD budget
- Unclipped raw pricing for all boundary and arbitrage checks
- Non-uniform strike convexity via divided differences and fixed-strike tenor monotonicity
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
    QUANTLIB_VERSION = ql.__version__
except ImportError:
    HAS_QUANTLIB = False
    QUANTLIB_VERSION = None

import scipy
SCIPY_VERSION = scipy.__version__

from src.heston.rates_curve import DeterministicYieldCurve, get_official_yield_curve, SPOT_PRICE, DIVIDEND_YIELD
from src.heston.baseline_pricing import price_american_put_quantlib
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.calibration import HestonCalibrator, HESTON_5_STARTS, HESTON_BOUNDS


def sha256_file(filepath: Path) -> str:
    """Computes SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_and_load_multistart_cache(
    out_path: Path,
    current_file_hashes: Dict[str, str],
    train_df: pd.DataFrame,
    ts_handle: Any,
    eval_date: Any
) -> Tuple[HestonParams, pd.DataFrame, Dict[str, Any]]:
    """
    Cryptographically validates cached multistart calibration results.
    Guarantees:
    1. Input files match manifest hashes exactly (invalidates if train_df or rates changed).
    2. Cached multistart table satisfies schema, row count, and parameter bounds.
    3. Final SSE is non-negative, finite, and consistent with RMSE.
    4. Replays objective evaluation on current training set within numerical tolerance.
    5. Computes fine-grid SSE (tFactor=200, x=200, v=100) and exports heston_multistart_fine_sse.csv.
    """
    manifest_file = out_path / "phase1_execution_manifest.json"
    ms_csv_file = out_path / "heston_multistart_results.csv"

    if not manifest_file.exists():
        raise ValueError(f"Cache validation failed: manifest not found at {manifest_file}")
    if not ms_csv_file.exists():
        raise ValueError(f"Cache validation failed: multistart results not found at {ms_csv_file}")

    # 1. Verify input file hashes
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    cached_hashes = manifest_data.get("input_hashes", {})
    for fname, curr_hash in current_file_hashes.items():
        if fname not in cached_hashes:
            raise ValueError(f"Cache validation failed: file '{fname}' missing from cached manifest hashes.")
        if cached_hashes[fname] != curr_hash:
            raise ValueError(
                f"Cache validation failed: cryptographic hash mismatch for '{fname}'. "
                f"Manifest has '{cached_hashes[fname]}', but current input has '{curr_hash}'. "
                f"Cache invalidated."
            )

    # 2. Load and validate multistart table schema & values
    df_ms = pd.read_csv(ms_csv_file)
    required_cols = {"start_index", "name", "final_sse", "final_rmse", "v0", "kappa", "theta", "xi", "rho", "feller_ratio", "status"}
    missing = required_cols - set(df_ms.columns)
    if missing:
        raise ValueError(f"Cache validation failed: multistart table missing columns: {missing}")

    if len(df_ms) != 5:
        raise ValueError(f"Cache validation failed: expected 5 starts, found {len(df_ms)}")
    if set(df_ms["start_index"]) != {1, 2, 3, 4, 5}:
        raise ValueError(f"Cache validation failed: start indices {set(df_ms['start_index'])} do not match {{1, 2, 3, 4, 5}}")

    # Validate bounds, non-negativity of SSE, and RMSE consistency
    n_train = len(train_df)
    for row in df_ms.itertuples():
        if row.final_sse < 0.0 or not np.isfinite(row.final_sse):
            raise ValueError(
                f"Cache validation failed: start {row.start_index} has invalid final_sse = {row.final_sse}. "
                f"SSE must be non-negative and finite."
            )
        exp_rmse = np.sqrt(row.final_sse / n_train)
        if abs(row.final_rmse - exp_rmse) > 1e-3:
            raise ValueError(
                f"Cache validation failed: start {row.start_index} final_rmse {row.final_rmse} "
                f"inconsistent with final_sse {row.final_sse} (expected {exp_rmse:.6f})."
            )

        # Bounds check
        bounds_map = {
            "v0": (row.v0, HESTON_BOUNDS[0]),
            "kappa": (row.kappa, HESTON_BOUNDS[1]),
            "theta": (row.theta, HESTON_BOUNDS[2]),
            "xi": (row.xi, HESTON_BOUNDS[3]),
            "rho": (row.rho, HESTON_BOUNDS[4]),
        }
        for pname, (pval, (blow, bhigh)) in bounds_map.items():
            if pval < blow - 1e-4 or pval > bhigh + 1e-4 or not np.isfinite(pval):
                raise ValueError(
                    f"Cache validation failed: start {row.start_index} parameter '{pname}'={pval} "
                    f"outside bounds [{blow}, {bhigh}]."
                )

    # 3. Objective Replay Verification on current train set
    cal = HestonCalibrator(train_df=train_df, yield_term_structure=ts_handle, eval_date=eval_date,
                           grid_t_factor=50.0, grid_x=70, grid_v=35)
    for row in df_ms.itertuples():
        # Verify objective replay for candidate runs (status 0 and reasonable SSE)
        if row.status == 0 and row.final_sse < 1.0:
            arr = np.array([row.v0, row.kappa, row.theta, row.xi, row.rho])
            replayed_sse = cal.evaluate_sse(arr)
            if abs(replayed_sse - row.final_sse) > 1e-3:
                raise ValueError(
                    f"Cache validation failed: start {row.start_index} cached SSE {row.final_sse:.6f} "
                    f"does not match replayed SSE {replayed_sse:.6f} on current training dataset."
                )

    # 4. Compute Fine-Grid SSE (tFactor=200, x=200, v=100) and export table
    cal_fine = HestonCalibrator(train_df=train_df, yield_term_structure=ts_handle, eval_date=eval_date,
                                grid_t_factor=200.0, grid_x=200, grid_v=100)
    fine_records = []
    fine_sse_list = []
    fine_rmse_list = []
    for row in df_ms.itertuples():
        arr = np.array([row.v0, row.kappa, row.theta, row.xi, row.rho])
        f_sse = cal_fine.evaluate_sse(arr)
        f_rmse = np.sqrt(f_sse / n_train)
        fine_sse_list.append(f_sse)
        fine_rmse_list.append(f_rmse)
        fine_records.append({
            "start_index": row.start_index,
            "name": row.name,
            "calib_grid_sse": row.final_sse,
            "calib_grid_rmse": row.final_rmse,
            "fine_grid_sse": f_sse,
            "fine_grid_rmse": f_rmse,
            "v0": row.v0,
            "kappa": row.kappa,
            "theta": row.theta,
            "xi": row.xi,
            "rho": row.rho,
            "feller_ratio": row.feller_ratio,
            "status": row.status
        })

    df_fine_sse = pd.DataFrame(fine_records)
    df_fine_sse.to_csv(out_path / "heston_multistart_fine_sse.csv", index=False)

    df_ms["fine_grid_sse"] = fine_sse_list
    df_ms["fine_grid_rmse"] = fine_rmse_list
    df_ms.to_csv(ms_csv_file, index=False)

    # Select best candidate by validated lowest final_sse
    best_row = df_ms.sort_values("final_sse").iloc[0]
    best_params = HestonParams(
        v0=float(best_row["v0"]),
        kappa=float(best_row["kappa"]),
        theta=float(best_row["theta"]),
        xi=float(best_row["xi"]),
        rho=float(best_row["rho"])
    )

    converged = df_ms[(df_ms["status"] == 0) & (df_ms["final_rmse"] < 0.050)]
    dispersion = {
        "v0_mean": float(converged["v0"].mean()),
        "v0_std": float(converged["v0"].std()),
        "theta_mean": float(converged["theta"].mean()),
        "theta_std": float(converged["theta"].std()),
        "kappa_mean": float(converged["kappa"].mean()),
        "kappa_std": float(converged["kappa"].std()),
        "xi_mean": float(converged["xi"].mean()),
        "xi_std": float(converged["xi"].std()),
        "rho_mean": float(converged["rho"].mean()),
        "rho_std": float(converged["rho"].std()),
        "best_start_name": str(best_row["name"]),
        "best_start_index": int(best_row["start_index"]),
        "best_train_sse": float(best_row["final_sse"]),
        "best_train_rmse": float(best_row["final_rmse"]),
    }

    return best_params, df_ms, dispersion


def run_phase1_pipeline(
    data_dir: str = "data/heston",
    output_dir: str = "data/heston/phase1",
    reuse_existing_multistart: bool = True,
    allow_recalibration: bool = False
) -> Dict[str, Any]:
    """
    Executes complete Phase 1 PoC evaluation, grid verification, shape checks, and reporting.
    """
    start_time_utc = datetime.now(timezone.utc).isoformat()
    t_start_wall = time.time()

    data_path = Path(data_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"=== Starting Heston Phase 1 Pipeline (Remediation 2) ===")
    print(f"Historical transcription timestamp: 2026-11-21T16:20:00-05:00")
    print(f"Execution timestamp: {start_time_utc}")
    print(f"QuantLib version: {QUANTLIB_VERSION}, SciPy version: {SCIPY_VERSION}")

    # 1. Insumos verification and hashing
    raw_treasury_file = data_path / "treasury_cmt_2026_11_17_raw.json"
    train_file = data_path / "data_split_train.csv"
    strike_holdout_file = data_path / "data_split_strike_holdout.csv"
    tenor_holdout_file = data_path / "data_split_tenor_holdout.csv"
    puts_full_file = data_path / "puts_selected_clean.csv"
    calls_contrast_file = data_path / "data_split_calls_contrast.csv"
    baseline_file = data_path / "baseline_comparison_detailed.csv"

    required_files = [
        raw_treasury_file, train_file, strike_holdout_file,
        tenor_holdout_file, puts_full_file, calls_contrast_file, baseline_file
    ]
    for rf in required_files:
        if not rf.exists():
            raise FileNotFoundError(f"Required Phase 1 input missing: {rf}")

    file_hashes = {rf.name: sha256_file(rf) for rf in required_files}
    print(f"Verified {len(file_hashes)} input files and cryptographic hashes.")

    # 2. Rate curve & QuantLib unified term structure
    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date

    # 3. Load datasets
    train_df = pd.read_csv(train_file)
    strike_df = pd.read_csv(strike_holdout_file)
    tenor_df = pd.read_csv(tenor_holdout_file)
    puts_full_df = pd.read_csv(puts_full_file)
    calls_df = pd.read_csv(calls_contrast_file)
    baseline_df = pd.read_csv(baseline_file)

    print(f"Data splits: Train={len(train_df)}, StrikeHoldout={len(strike_df)}, TenorHoldout={len(tenor_df)}, FullPuts={len(puts_full_df)}, CallsContrast={len(calls_df)}")

    # 4. Multi-start calibration / Cryptographic Cache Verification
    ms_csv_path = out_path / "heston_multistart_results.csv"
    if reuse_existing_multistart:
        print("\n--- Validating and Verifying Multistart Cache Cryptographically ---")
        try:
            best_params, df_multistarts, dispersion = validate_and_load_multistart_cache(
                out_path=out_path,
                current_file_hashes=file_hashes,
                train_df=train_df,
                ts_handle=ts_handle,
                eval_date=eval_date
            )
            print("Cache validation succeeded: input hashes, schema, parameter bounds, and objective replay verified.")
        except Exception as e:
            if not allow_recalibration:
                raise ValueError(f"Cache validation failed and recalibration not permitted: {e}")
            print(f"Cache validation failed ({e}); initiating full 5-start re-calibration...")
            calibrator = HestonCalibrator(train_df=train_df, yield_term_structure=ts_handle, eval_date=eval_date)
            best_params, df_multistarts, dispersion = calibrator.run_all_multistarts(starts=HESTON_5_STARTS, maxiter=35)
            df_multistarts.to_csv(ms_csv_path, index=False)
    else:
        print("\n--- Running Fresh 5 Dispersed Starts Optimization on Train Split (60 Puts) ---")
        calibrator = HestonCalibrator(train_df=train_df, yield_term_structure=ts_handle, eval_date=eval_date)
        best_params, df_multistarts, dispersion = calibrator.run_all_multistarts(starts=HESTON_5_STARTS, maxiter=35)
        df_multistarts.to_csv(ms_csv_path, index=False)

    print(f"Selected Best Candidate: {dispersion['best_start_name']} (Index {dispersion['best_start_index']})")
    print(f"Best Parameters: {best_params.to_dict()}")

    # 5. Instantiating option pricer with best parameters
    pricer = HestonOptionPricer(yield_term_structure=ts_handle, eval_date=eval_date)

    # 6. Contract-level evaluation helper using UNIFIED PRODUCTION GRID and RAW PRICING
    def evaluate_contract_set(df_subset: pd.DataFrame, set_name: str) -> pd.DataFrame:
        records = []
        for _, row in df_subset.iterrows():
            K = float(row["strike"])
            mkt = float(row["lastPrice"])
            exp_str = str(row["expirationDate"])
            tau_days = float(row["tau_days"])
            tau_years = float(row["tau_years"])

            # Raw unclipped pricing
            t0_eval = time.time()
            p_am_raw = pricer.price_american(K, exp_str, best_params, option_type="P", clip_to_intrinsic=False)
            eval_time_ms = (time.time() - t0_eval) * 1000.0

            p_eu_raw = pricer.price_european(K, exp_str, best_params, option_type="P", clip_nonnegative=False)

            intrinsic = max(K - SPOT_PRICE, 0.0)
            early_prem = p_am_raw - p_eu_raw
            err = p_am_raw - mkt
            abs_err = abs(err)
            rel_err_pct = (abs_err / mkt) * 100.0 if mkt > 1e-4 else 0.0

            records.append({
                "contractSymbol": row.get("contractSymbol", ""),
                "strike": K,
                "expirationDate": exp_str,
                "tau_days": tau_days,
                "tau_years": tau_years,
                "lastPrice": mkt,
                "heston_price_am": p_am_raw,
                "heston_price_eu": p_eu_raw,
                "intrinsic_value": intrinsic,
                "lower_bound_gap": p_am_raw - intrinsic,
                "upper_bound_gap": K - p_am_raw,
                "early_exercise_premium": early_prem,
                "error_usd": err,
                "abs_error_usd": abs_err,
                "rel_error_pct": rel_err_pct,
                "eval_time_ms": eval_time_ms,
                "dataset_split": set_name
            })
        return pd.DataFrame(records)

    print("\n--- Evaluating Best Model across Partitions (Unified Production Grid 300x160x80) ---")
    df_train_eval = evaluate_contract_set(train_df, "train")
    df_strike_eval = evaluate_contract_set(strike_df, "strike_holdout")
    df_tenor_eval = evaluate_contract_set(tenor_df, "tenor_holdout")
    df_full_eval = pd.concat([df_train_eval, df_strike_eval, df_tenor_eval], ignore_index=True)

    df_train_eval.to_csv(out_path / "heston_pricing_train.csv", index=False)
    df_strike_eval.to_csv(out_path / "heston_pricing_strike_holdout.csv", index=False)
    df_tenor_eval.to_csv(out_path / "heston_pricing_tenor_holdout.csv", index=False)
    df_full_eval.to_csv(out_path / "heston_pricing_full_puts.csv", index=False)

    # 7. Aggregation by tenor
    tenor_groups = []
    for exp_date, grp in df_full_eval.groupby("expirationDate"):
        tenor_groups.append({
            "expirationDate": exp_date,
            "tau_days": float(grp["tau_days"].iloc[0]),
            "tau_years": float(grp["tau_years"].iloc[0]),
            "n_contracts": int(len(grp)),
            "mean_market_price": float(grp["lastPrice"].mean()),
            "mean_heston_price": float(grp["heston_price_am"].mean()),
            "mae_usd": float(grp["abs_error_usd"].mean()),
            "rmse_usd": float(np.sqrt((grp["error_usd"]**2).mean())),
            "max_abs_error_usd": float(grp["abs_error_usd"].max()),
            "mean_rel_error_pct": float(grp["rel_error_pct"].mean()),
            "mean_early_exercise_prem": float(grp["early_exercise_premium"].mean()),
        })
    df_by_tenor = pd.DataFrame(tenor_groups).sort_values("tau_days")
    df_by_tenor.to_csv(out_path / "heston_pricing_by_tenor.csv", index=False)

    # 8. External Calls Contrast (142 calls)
    print("\n--- Evaluating 142 Calls External Contrast ---")
    call_records = []
    for _, row in calls_df.iterrows():
        K = float(row["strike"])
        mkt = float(row["lastPrice"])
        exp_str = str(row["expirationDate"])
        tau_days = float(row["tau_days"])
        tau_years = float(row["tau_years"])

        p_call_eu = pricer.price_european(K, exp_str, best_params, option_type="C", clip_nonnegative=False)
        p_call_am = pricer.price_american(K, exp_str, best_params, option_type="C", clip_to_intrinsic=False)
        err = p_call_eu - mkt
        abs_err = abs(err)
        rel_err = (abs_err / mkt) * 100.0 if mkt > 1e-4 else 0.0

        call_records.append({
            "contractSymbol": row.get("contractSymbol", ""),
            "strike": K,
            "expirationDate": exp_str,
            "tau_days": tau_days,
            "tau_years": tau_years,
            "lastPrice": mkt,
            "heston_call_eu": p_call_eu,
            "heston_call_am": p_call_am,
            "diff_am_eu": p_call_am - p_call_eu,
            "error_usd": err,
            "abs_error_usd": abs_err,
            "rel_error_pct": rel_err
        })
    df_calls_eval = pd.DataFrame(call_records)
    df_calls_eval.to_csv(out_path / "heston_calls_contrast.csv", index=False)

    # 9. Common Sample (84 puts) Comparison against SVI and Constant Flat
    print("\n--- Computing Common Sample (84 Puts) Comparison ---")
    common_df = baseline_df[baseline_df["in_r3_common_84"] == True].copy()
    c_records = []
    for _, row in common_df.iterrows():
        K = float(row["strike"])
        mkt = float(row["lastPrice"])
        exp_str = str(row["expirationDate"])
        tau_yr = float(row["tau_years"])
        r_off = float(row["r_official_zero"])
        p_svi = float(row["p_svi_r3_published_benchmark"])

        p_heston = pricer.price_american(K, exp_str, best_params, option_type="P", clip_to_intrinsic=False)
        p_flat_common = price_american_put_quantlib(
            SPOT_PRICE, K, tau_yr, r_off, sigma=0.45, term_structure=ts_handle, exp_date_str=exp_str
        )
        p_flat_contract = float(row["p_am_ql_official"])

        c_records.append({
            "contractSymbol": row["contractSymbol"],
            "strike": K,
            "expirationDate": exp_str,
            "tau_years": tau_yr,
            "lastPrice": mkt,
            "price_heston": p_heston,
            "price_flat_common_curve": p_flat_common,
            "price_flat_contract_rate": p_flat_contract,
            "price_svi_historical_r3": p_svi,
            "err_heston": p_heston - mkt,
            "err_flat_common": p_flat_common - mkt,
            "err_flat_contract": p_flat_contract - mkt,
            "err_svi_historical": p_svi - mkt,
            "abs_err_heston": abs(p_heston - mkt),
            "abs_err_flat_common": abs(p_flat_common - mkt),
            "abs_err_svi": abs(p_svi - mkt),
        })
    df_common_eval = pd.DataFrame(c_records)
    df_common_eval.to_csv(out_path / "heston_common_84_comparison.csv", index=False)

    # 10. Numerical Grid Convergence with Separate Refinements
    print("\n--- Verifying Grid Convergence & Separate Refinements on Representative Contracts ---")
    rep_contracts = [
        ("Short_OTM", 10, 10.0),
        ("Short_ATM", 10, 12.0),
        ("Short_ITM", 10, 14.0),
        ("Medium_OTM", 94, 9.0),
        ("Medium_ATM", 94, 12.0),
        ("Medium_ITM", 94, 15.0),
        ("Long_OTM", 794, 8.0),
        ("Long_ATM", 794, 12.0),
        ("Long_ITM", 794, 17.0),
        ("Sensitive_ITM_212d", 212, 17.0),
    ]
    grid_records = []
    all_budget_passed = True
    for label, dte, K in rep_contracts:
        exp_date_val = eval_date + dte
        conv = pricer.evaluate_grid_convergence(K, exp_date_val, best_params, option_type="P")
        conv["label"] = label
        conv["dte"] = dte
        grid_records.append(conv)
        if not conv["budget_passed"]:
            all_budget_passed = False

    df_grid_conv = pd.DataFrame(grid_records)
    df_grid_conv.to_csv(out_path / "heston_grid_convergence.csv", index=False)
    print(f"All {len(rep_contracts)} grid tests passed budget <= 0.0020 USD: {all_budget_passed}")

    # 11. Rigorous Shape, Arbitrage, and Monotonicity Checks across ALL Tenors
    print("\n--- Verifying Arbitrage Bounds, Strike Monotonicity, and Divided-Difference Convexity across ALL Tenors ---")
    shape_records = []
    strike_mono_violations = 0
    convexity_violations = 0
    lower_bound_violations = 0
    upper_bound_violations = 0
    eep_violations = 0

    for exp_str, grp in df_full_eval.groupby("expirationDate"):
        subset = grp.sort_values("strike").reset_index(drop=True)
        strikes = subset["strike"].values
        p_am_vals = subset["heston_price_am"].values
        p_eu_vals = subset["heston_price_eu"].values
        n_k = len(strikes)

        for i in range(n_k):
            K_i = strikes[i]
            p_i = p_am_vals[i]
            p_eu_i = p_eu_vals[i]

            lower_b = max(K_i - SPOT_PRICE, 0.0)
            upper_b = K_i
            lower_ok = (p_i >= lower_b - 1e-6)
            upper_ok = (p_i <= upper_b + 1e-6)
            eep_ok = (p_i >= p_eu_i - 1e-5)

            if not lower_ok:
                lower_bound_violations += 1
            if not upper_ok:
                upper_bound_violations += 1
            if not eep_ok:
                eep_violations += 1

            if i == 0:
                mono_k = True
                mono_status = "FIRST_STRIKE"
            else:
                mono_k = (p_am_vals[i] >= p_am_vals[i - 1] - 1e-4)
                mono_status = "PASS" if mono_k else "FAIL"
                if not mono_k:
                    strike_mono_violations += 1

            if i == 0 or i == n_k - 1:
                conv_val = 0.0
                conv_status = "NOT_TESTABLE"
            else:
                s_left = (p_am_vals[i] - p_am_vals[i - 1]) / (strikes[i] - strikes[i - 1])
                s_right = (p_am_vals[i + 1] - p_am_vals[i]) / (strikes[i + 1] - strikes[i])
                conv_val = 2.0 * (s_right - s_left) / (strikes[i + 1] - strikes[i - 1])
                if conv_val >= -0.0020:
                    conv_status = "PASS"
                else:
                    conv_status = "FAIL"
                    convexity_violations += 1

            shape_records.append({
                "expirationDate": exp_str,
                "strike": K_i,
                "price_am_raw": p_i,
                "price_eu_raw": p_eu_i,
                "lower_bound": lower_b,
                "upper_bound": upper_b,
                "lower_bound_gap": p_i - lower_b,
                "upper_bound_gap": upper_b - p_i,
                "early_exercise_premium": p_i - p_eu_i,
                "lower_bound_ok": bool(lower_ok),
                "upper_bound_ok": bool(upper_ok),
                "am_ge_eu_ok": bool(eep_ok),
                "strike_monotonicity_status": mono_status,
                "convexity_second_divided_diff": conv_val,
                "convexity_status": conv_status,
            })
    df_shape = pd.DataFrame(shape_records)
    df_shape.to_csv(out_path / "heston_shape_arbitrage_checks.csv", index=False)

    # 12. Fixed-Strike Tenor Monotonicity across ALL Multi-Tenor Strikes
    print("\n--- Verifying Tenor Monotonicity at Fixed Strikes across ALL Multi-Tenor Pairs ---")
    tenor_mono_records = []
    tenor_mono_violations = 0
    multi_strikes = df_full_eval["strike"].value_counts()[lambda x: x > 1].index.sort_values().tolist()

    for K_fixed in multi_strikes:
        k_df = df_full_eval[df_full_eval["strike"] == K_fixed].sort_values("tau_days").reset_index(drop=True)
        for j in range(len(k_df) - 1):
            t1_days = k_df.loc[j, "tau_days"]
            t2_days = k_df.loc[j + 1, "tau_days"]
            exp1 = k_df.loc[j, "expirationDate"]
            exp2 = k_df.loc[j + 1, "expirationDate"]
            p1 = k_df.loc[j, "heston_price_am"]
            p2 = k_df.loc[j + 1, "heston_price_am"]

            diff_tenor = p2 - p1
            mono_tenor_ok = (diff_tenor >= -0.0020)
            if not mono_tenor_ok:
                tenor_mono_violations += 1

            tenor_mono_records.append({
                "strike": K_fixed,
                "tenor_1_days": t1_days,
                "tenor_2_days": t2_days,
                "expiration_1": exp1,
                "expiration_2": exp2,
                "price_1": p1,
                "price_2": p2,
                "price_diff": diff_tenor,
                "tenor_monotonicity_ok": bool(mono_tenor_ok)
            })
    df_tenor_mono = pd.DataFrame(tenor_mono_records)
    df_tenor_mono.to_csv(out_path / "heston_tenor_monotonicity_checks.csv", index=False)

    # 13. Near-Optimal Candidate Predictive Dispersion
    print("\n--- Evaluating Predictive Dispersion of Near-Optimal Multistart Candidates ---")
    near_opt_subset = df_multistarts[df_multistarts["final_sse"] <= 1.05 * df_multistarts["final_sse"].min()]
    pred_disp_records = []
    test_points = [(12.0, 31, "2026-12-18"), (17.0, 794, "2029-01-19"), (30.0, 794, "2029-01-19")]
    for K_diag, dte_diag, exp_diag in test_points:
        cand_prices = []
        for cand_row in near_opt_subset.itertuples():
            cand_p = HestonParams(cand_row.v0, cand_row.kappa, cand_row.theta, cand_row.xi, cand_row.rho)
            p_c = pricer.price_american(K_diag, exp_diag, cand_p, option_type="P", clip_to_intrinsic=False)
            cand_prices.append(p_c)
        min_p = min(cand_prices)
        max_p = max(cand_prices)
        pred_disp_records.append({
            "strike": K_diag,
            "dte": dte_diag,
            "min_predicted_price": min_p,
            "max_predicted_price": max_p,
            "price_range_usd": max_p - min_p,
            "n_candidates": len(near_opt_subset)
        })
    df_pred_disp = pd.DataFrame(pred_disp_records)
    df_pred_disp.to_csv(out_path / "heston_candidate_predictive_dispersion.csv", index=False)

    # 14. Executive Summary Metrics
    train_mae = float(df_train_eval["abs_error_usd"].mean())
    train_rmse = float(np.sqrt((df_train_eval["error_usd"]**2).mean()))
    strike_mae = float(df_strike_eval["abs_error_usd"].mean())
    strike_rmse = float(np.sqrt((df_strike_eval["error_usd"]**2).mean()))
    tenor_mae = float(df_tenor_eval["abs_error_usd"].mean())
    tenor_rmse = float(np.sqrt((df_tenor_eval["error_usd"]**2).mean()))
    full_mae = float(df_full_eval["abs_error_usd"].mean())
    full_rmse = float(np.sqrt((df_full_eval["error_usd"]**2).mean()))

    calls_mae = float(df_calls_eval["abs_error_usd"].mean())
    calls_rmse = float(np.sqrt((df_calls_eval["error_usd"]**2).mean()))

    c84_heston_mae = float(df_common_eval["abs_err_heston"].mean())
    c84_svi_mae = float(df_common_eval["abs_err_svi"].mean())
    c84_flat_mae = float(df_common_eval["abs_err_flat_common"].mean())

    summary_rows = [
        {"metric": "Train MAE (60 puts)", "target_gate": "<= 0.080 USD", "achieved": f"{train_mae:.4f} USD", "status": "PASS" if train_mae <= 0.080 else "FAIL"},
        {"metric": "Train RMSE (60 puts)", "target_gate": "<= 0.120 USD", "achieved": f"{train_rmse:.4f} USD", "status": "PASS" if train_rmse <= 0.120 else "FAIL"},
        {"metric": "Strike Holdout MAE (22 puts)", "target_gate": "<= 0.100 USD", "achieved": f"{strike_mae:.4f} USD", "status": "PASS" if strike_mae <= 0.100 else "FAIL"},
        {"metric": "Tenor Holdout MAE (15 puts)", "target_gate": "<= 0.100 USD", "achieved": f"{tenor_mae:.4f} USD", "status": "PASS" if tenor_mae <= 0.100 else "FAIL"},
        {"metric": "Numerical Grid Budget", "target_gate": "<= 0.0020 USD", "achieved": f"Max |Med-Fine| = {df_grid_conv['diff_ultrafine_usd'].max():.6f} USD", "status": "PASS" if all_budget_passed else "FAIL"},
        {"metric": "Lower Arbitrage Bound Violations", "target_gate": "0 violations", "achieved": f"{lower_bound_violations} violations", "status": "PASS" if lower_bound_violations == 0 else "FAIL"},
        {"metric": "Upper Arbitrage Bound Violations", "target_gate": "0 violations", "achieved": f"{upper_bound_violations} violations", "status": "PASS" if upper_bound_violations == 0 else "FAIL"},
        {"metric": "Early Exercise Premium Violations", "target_gate": "0 violations", "achieved": f"{eep_violations} violations", "status": "PASS" if eep_violations == 0 else "FAIL"},
        {"metric": "Strike Monotonicity Violations", "target_gate": "0 violations", "achieved": f"{strike_mono_violations} violations", "status": "PASS" if strike_mono_violations == 0 else "FAIL"},
        {"metric": "Tenor Monotonicity Violations", "target_gate": "0 violations", "achieved": f"{tenor_mono_violations} violations", "status": "PASS" if tenor_mono_violations == 0 else "FAIL"},
        {"metric": "Convexity Violations", "target_gate": "0 violations", "achieved": f"{convexity_violations} violations", "status": "PASS" if convexity_violations == 0 else "FAIL"},
        {"metric": "Full Sample MAE (97 puts)", "target_gate": "Diagnostic", "achieved": f"{full_mae:.4f} USD", "status": "INFO"},
        {"metric": "External Calls MAE (142 calls)", "target_gate": "Diagnostic", "achieved": f"{calls_mae:.4f} USD", "status": "INFO"},
        {"metric": "Common 84 Heston MAE", "target_gate": "Diagnostic", "achieved": f"{c84_heston_mae:.4f} USD", "status": "INFO"},
        {"metric": "Common 84 SVI Historical MAE", "target_gate": "Reference R3", "achieved": f"{c84_svi_mae:.4f} USD", "status": "INFO"},
        {"metric": "Common 84 Flat Baseline MAE", "target_gate": "Common Curve", "achieved": f"{c84_flat_mae:.4f} USD", "status": "INFO"},
        {"metric": "Feller Ratio (Best Candidate)", "target_gate": "Reported without filter", "achieved": f"{best_params.feller_ratio:.4f} (Satisfied: {best_params.feller_satisfied})", "status": "INFO"},
    ]
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(out_path / "heston_phase1_summary.csv", index=False)

    # 15. Comprehensive Gate Verdict
    all_gate_criteria_met = (
        train_mae <= 0.080 and
        train_rmse <= 0.120 and
        strike_mae <= 0.100 and
        tenor_mae <= 0.100 and
        all_budget_passed and
        lower_bound_violations == 0 and
        upper_bound_violations == 0 and
        eep_violations == 0 and
        strike_mono_violations == 0 and
        tenor_mono_violations == 0 and
        convexity_violations == 0
    )

    manifest = {
        "phase": "PHASE_1_POC_HESTON_REMEDIATION_2",
        "retrieval_timestamp_historical": "2026-11-21T16:20:00-05:00",
        "execution_timestamp": start_time_utc,
        "runtime_wall_seconds": round(time.time() - t_start_wall, 2),
        "environment": {
            "python_version": "3.12.6",
            "quantlib_version": QUANTLIB_VERSION,
            "scipy_version": SCIPY_VERSION,
            "os": "Windows",
        },
        "unified_production_grid": {
            "time_factor": pricer.PROD_TIME_FACTOR,
            "min_time_steps": pricer.PROD_MIN_TIME_STEPS,
            "spot_steps": pricer.PROD_SPOT_STEPS,
            "vol_steps": pricer.PROD_VOL_STEPS,
        },
        "input_hashes": file_hashes,
        "predeclared_bounds": {
            "v0": list(HESTON_BOUNDS[0]),
            "kappa": list(HESTON_BOUNDS[1]),
            "theta": list(HESTON_BOUNDS[2]),
            "xi": list(HESTON_BOUNDS[3]),
            "rho": list(HESTON_BOUNDS[4]),
        },
        "predeclared_numerical_budget_usd": 0.0020,
        "gate_criteria": {
            "train_mae_max": 0.080,
            "train_rmse_max": 0.120,
            "strike_holdout_mae_max": 0.100,
            "tenor_holdout_mae_max": 0.100,
            "numerical_budget_max": 0.0020,
            "max_lower_bound_violations": 0,
            "max_upper_bound_violations": 0,
            "max_early_exercise_violations": 0,
            "max_strike_monotonicity_violations": 0,
            "max_tenor_monotonicity_violations": 0,
            "max_convexity_violations": 0,
        },
        "best_model_parameters": best_params.to_dict(),
        "parameter_dispersion": dispersion,
        "performance_metrics": {
            "train_mae": train_mae,
            "train_rmse": train_rmse,
            "strike_holdout_mae": strike_mae,
            "strike_holdout_rmse": strike_rmse,
            "tenor_holdout_mae": tenor_mae,
            "tenor_holdout_rmse": tenor_rmse,
            "full_sample_mae": full_mae,
            "full_sample_rmse": full_rmse,
            "calls_contrast_mae": calls_mae,
            "calls_contrast_rmse": calls_rmse,
            "common_84_heston_mae": c84_heston_mae,
            "common_84_svi_mae": c84_svi_mae,
            "common_84_flat_mae": c84_flat_mae,
        },
        "diagnostic_counts": {
            "lower_bound_violations": lower_bound_violations,
            "upper_bound_violations": upper_bound_violations,
            "early_exercise_premium_violations": eep_violations,
            "strike_monotonicity_violations": strike_mono_violations,
            "tenor_monotonicity_violations": tenor_mono_violations,
            "convexity_violations": convexity_violations,
        },
        "gate_verdict": "PASSED" if all_gate_criteria_met else "FAILED",
        "output_files": [f.name for f in out_path.iterdir() if f.is_file()]
    }

    manifest_path = out_path / "phase1_execution_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to {manifest_path}")
    print(f"Comprehensive Gate Verdict: {manifest['gate_verdict']}")
    print(f"Total pipeline elapsed time: {manifest['runtime_wall_seconds']} seconds.")

    return manifest


if __name__ == "__main__":
    run_phase1_pipeline()
