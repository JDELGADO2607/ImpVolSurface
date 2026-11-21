"""
Phase 1 End-to-End Execution Pipeline: Classical Heston Proof-of-Concept (PoC).

Enforces:
- Clean workspace isolation in data/heston/phase1/
- Zero writes to historical or official directories
- Strict data provenance with separation of historical retrieval timestamp and execution timestamp
- Optimization solely on training split (60 American puts) across 5 pre-declared starts
- Out-of-sample evaluation on strike holdout (22 puts) and tenor holdout (15 puts)
- External contrast on 142 call options
- Common 84 puts comparison against constant flat baseline (under common curve) and historical SVI
- Numerical grid budget (0.0020 USD) verification across 3 grid resolutions
- Comprehensive arbitrage, shape, and monotonicity diagnostics
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


def run_phase1_pipeline(
    data_dir: str = "data/heston",
    output_dir: str = "data/heston/phase1",
    maxiter: int = 35
) -> Dict[str, Any]:
    """
    Executes complete Phase 1 PoC calibration, evaluation, and reporting pipeline.
    """
    start_time_utc = datetime.now(timezone.utc).isoformat()
    t_start_wall = time.time()

    data_path = Path(data_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"=== Starting Heston Phase 1 Pipeline ===")
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

    # 4. Multi-start calibration on Train set
    print("\n--- Running 5 Dispersed Starts Optimization on Train Split (60 Puts) ---")
    calibrator = HestonCalibrator(train_df=train_df, yield_term_structure=ts_handle, eval_date=eval_date)
    best_params, df_multistarts, dispersion = calibrator.run_all_multistarts(starts=HESTON_5_STARTS, maxiter=maxiter)

    multistart_csv = out_path / "heston_multistart_results.csv"
    df_multistarts.to_csv(multistart_csv, index=False)
    print(f"Saved multistart results to {multistart_csv}")
    print(f"Selected Best Start: {dispersion['best_start_name']} (Index {dispersion['best_start_index']})")
    print(f"Best Parameters: {best_params.to_dict()}")

    # 5. Instantiating option pricer with best parameters
    pricer = HestonOptionPricer(yield_term_structure=ts_handle, eval_date=eval_date)

    # 6. Contract-level evaluation helper
    def evaluate_contract_set(df_subset: pd.DataFrame, set_name: str) -> pd.DataFrame:
        records = []
        for _, row in df_subset.iterrows():
            K = float(row["strike"])
            mkt = float(row["lastPrice"])
            exp_str = str(row["expirationDate"])
            tau_days = float(row["tau_days"])
            tau_years = float(row["tau_years"])

            t0_eval = time.time()
            p_am = pricer.price_american(K, exp_str, best_params, option_type="P")
            eval_time_ms = (time.time() - t0_eval) * 1000.0

            p_eu = pricer.price_european(K, exp_str, best_params, option_type="P")
            early_prem = p_am - p_eu
            err = p_am - mkt
            abs_err = abs(err)
            rel_err_pct = (abs_err / mkt) * 100.0 if mkt > 1e-4 else 0.0

            records.append({
                "contractSymbol": row.get("contractSymbol", ""),
                "strike": K,
                "expirationDate": exp_str,
                "tau_days": tau_days,
                "tau_years": tau_years,
                "lastPrice": mkt,
                "heston_price_am": p_am,
                "heston_price_eu": p_eu,
                "early_exercise_premium": early_prem,
                "error_usd": err,
                "abs_error_usd": abs_err,
                "rel_error_pct": rel_err_pct,
                "eval_time_ms": eval_time_ms,
                "dataset_split": set_name
            })
        return pd.DataFrame(records)

    print("\n--- Evaluating Best Model across Partitions ---")
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
            "tau_days": grp["tau_days"].iloc[0],
            "tau_years": grp["tau_years"].iloc[0],
            "n_contracts": len(grp),
            "mean_market_price": grp["lastPrice"].mean(),
            "mean_heston_price": grp["heston_price_am"].mean(),
            "mae_usd": grp["abs_error_usd"].mean(),
            "rmse_usd": np.sqrt((grp["error_usd"]**2).mean()),
            "max_abs_error_usd": grp["abs_error_usd"].max(),
            "mean_rel_error_pct": grp["rel_error_pct"].mean(),
            "mean_early_exercise_prem": grp["early_exercise_premium"].mean(),
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

        # Under q=0, American call price == European call price (Merton 1973)
        p_call_eu = pricer.price_european(K, exp_str, best_params, option_type="C")
        p_call_am = pricer.price_american(K, exp_str, best_params, option_type="C")
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

        # Heston American
        p_heston = pricer.price_american(K, exp_str, best_params, option_type="P")

        # Flat American with common term structure
        p_flat_common = price_american_put_quantlib(
            SPOT_PRICE, K, tau_yr, r_off, sigma=0.45, term_structure=ts_handle, exp_date_str=exp_str
        )

        # Flat American contract rate
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

    # 10. Numerical Grid Convergence & Budget Verification (0.0020 USD)
    print("\n--- Verifying Numerical Grid Budget (0.0020 USD) on Representative Contracts ---")
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
    print(f"All 9 grid convergence tests passed budget <= 0.0020 USD: {all_budget_passed}")

    # 11. Shape, Arbitrage, and Monotonicity Checks
    print("\n--- Verifying Arbitrage Bounds, Monotonicity, and Convexity ---")
    shape_records = []
    # Test across representative smiles
    for exp_str in ["2026-11-27", "2027-02-19", "2029-01-19"]:
        subset = df_full_eval[df_full_eval["expirationDate"] == exp_str].sort_values("strike")
        if len(subset) < 3:
            continue
        strikes = subset["strike"].values
        prices = subset["heston_price_am"].values
        eu_prices = subset["heston_price_eu"].values

        for i in range(len(strikes)):
            K_i = strikes[i]
            p_i = prices[i]
            eu_i = eu_prices[i]

            # Arbitrage bounds for put: max(0, K - S0) <= P <= K
            lower_b = max(K_i - SPOT_PRICE, 0.0)
            upper_b = K_i
            bounds_ok = (p_i >= lower_b - 1e-6) and (p_i <= upper_b + 1e-6)
            am_ge_eu = p_i >= eu_i - 1e-6

            # Monotonicity with strike: dP/dK >= 0
            mono_k = True if i == 0 else (prices[i] >= prices[i - 1] - 1e-4)

            # Convexity: P(K1) - 2*P(K2) + P(K3) >= -tol (where tol is within numerical budget)
            convexity_ok = True
            butterfly = 0.0
            if 0 < i < len(strikes) - 1:
                # Approximate 2nd derivative
                h1 = strikes[i] - strikes[i - 1]
                h2 = strikes[i + 1] - strikes[i]
                if abs(h1 - h2) < 0.01:
                    butterfly = prices[i - 1] - 2.0 * prices[i] + prices[i + 1]
                    convexity_ok = butterfly >= -0.0020  # bounded by numerical budget

            shape_records.append({
                "expirationDate": exp_str,
                "strike": K_i,
                "price_am": p_i,
                "price_eu": eu_i,
                "lower_bound": lower_b,
                "upper_bound": upper_b,
                "bounds_ok": bool(bounds_ok),
                "am_ge_eu": bool(am_ge_eu),
                "strike_monotonicity_ok": bool(mono_k),
                "convexity_ok": bool(convexity_ok),
                "butterfly_spread_val": butterfly,
            })
    df_shape = pd.DataFrame(shape_records)
    df_shape.to_csv(out_path / "heston_shape_arbitrage_checks.csv", index=False)

    # 12. Executive Summary Metrics
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
        {"metric": "Numerical Grid Budget", "target_gate": "<= 0.0020 USD", "achieved": f"Max |Med-Fine| = {df_grid_conv['diff_medium_fine'].max():.6f} USD", "status": "PASS" if all_budget_passed else "FAIL"},
        {"metric": "Full Sample MAE (97 puts)", "target_gate": "Diagnostic", "achieved": f"{full_mae:.4f} USD", "status": "INFO"},
        {"metric": "External Calls MAE (142 calls)", "target_gate": "Diagnostic", "achieved": f"{calls_mae:.4f} USD", "status": "INFO"},
        {"metric": "Common 84 Heston MAE", "target_gate": "Diagnostic", "achieved": f"{c84_heston_mae:.4f} USD", "status": "INFO"},
        {"metric": "Common 84 SVI Historical MAE", "target_gate": "Reference R3", "achieved": f"{c84_svi_mae:.4f} USD", "status": "INFO"},
        {"metric": "Common 84 Flat Baseline MAE", "target_gate": "Common Curve", "achieved": f"{c84_flat_mae:.4f} USD", "status": "INFO"},
        {"metric": "Feller Ratio (Best Model)", "target_gate": "Reported without filter", "achieved": f"{best_params.feller_ratio:.4f} (Satisfied: {best_params.feller_satisfied})", "status": "INFO"},
    ]
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(out_path / "heston_phase1_summary.csv", index=False)

    # 13. Execution Manifest
    manifest = {
        "phase": "PHASE_1_POC_HESTON",
        "retrieval_timestamp_historical": "2026-11-21T18:45:00Z",
        "execution_timestamp": start_time_utc,
        "runtime_wall_seconds": round(time.time() - t_start_wall, 2),
        "environment": {
            "python_version": "3.12.6",
            "quantlib_version": QUANTLIB_VERSION,
            "scipy_version": SCIPY_VERSION,
            "os": "Windows",
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
        "gate_verdict": "PASSED" if (
            train_mae <= 0.080 and
            train_rmse <= 0.120 and
            strike_mae <= 0.100 and
            tenor_mae <= 0.100 and
            all_budget_passed
        ) else "FAILED",
        "output_files": [f.name for f in out_path.iterdir() if f.is_file()]
    }

    manifest_path = out_path / "phase1_execution_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest saved to {manifest_path}")
    print(f"Gate Verdict: {manifest['gate_verdict']}")
    print(f"Total pipeline elapsed time: {manifest['runtime_wall_seconds']} seconds.")

    return manifest


if __name__ == "__main__":
    run_phase1_pipeline()
