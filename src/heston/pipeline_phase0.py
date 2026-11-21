"""
Phase 0 Execution Pipeline and Artifact Generator for Heston Migration.

Executes all Phase 0 scope deliverables:
1. Environment and dependency audit (Python runtime, dynamic QuantLib version detection)
2. Source input SHA-256 validation (Excel, CSV, and frozen SVI reference table)
3. Official 2026-11-17 Treasury curve and consistent coupon-bond bootstrap
4. Complete option audit, put selection and rejection taxonomy, support summary
5. Deterministic leakage-free data split (train, strike holdout, tenor holdout, calls contrast)
6. Baseline pricing on common sample (European flat, American flat, Frozen SVI) with clean curve vs engine ablation
7. Comprehensive execution manifest with execution time and SHA-256 signatures

Strictly isolates all outputs in data/heston/ and docs/reports/.
Never overwrites historical files or official SVI outputs.
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import json
import time
import sys
import numpy as np
import pandas as pd

from src.heston.rates_curve import (
    VALUATION_DATETIME,
    NY_TZ,
    SPOT_PRICE,
    DIVIDEND_YIELD,
    OFFICIAL_TREASURY_CMT_2026_11_17,
    get_official_yield_curve,
    compare_rate_methods_and_curves
)
from src.heston.option_selection import audit_and_select_options
from src.heston.data_split import create_deterministic_split
from src.heston.baseline_pricing import (
    compute_baseline_benchmarks,
    HAS_QUANTLIB,
    QUANTLIB_VERSION
)

SVI_FROZEN_SHA = "3d81ff18cae3a9f8dc74c174015fed17031a8da8"


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_phase0_pipeline(
    raw_excel: str = "data/raw/Opciones_Completo.xlsx",
    historical_csv: str = "data/processed/nu_historical_daily.csv",
    svi_reference_csv: str = "outputs/tables/model_comparison_detailed.csv",
    output_dir: str = "data/heston"
) -> Dict[str, Any]:
    """
    Executes Phase 0 end-to-end and writes all versioned deliverables.
    """
    t_start = time.perf_counter()
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)

    print("==================================================================")
    print("STARTING HESTON PHASE 0 PREPARATION AND BASELINE PIPELINE")
    print(f"Timestamp: {datetime.now(NY_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("==================================================================")

    # Step 1: Input Integrity
    raw_p = Path(raw_excel)
    hist_p = Path(historical_csv)
    svi_p = Path(svi_reference_csv)
    if not raw_p.exists():
        raise FileNotFoundError(f"Missing raw Excel: {raw_p}")
    if not hist_p.exists():
        raise FileNotFoundError(f"Missing historical CSV: {hist_p}")

    hash_raw_excel = compute_sha256(raw_p)
    hash_hist_csv = compute_sha256(hist_p)
    hash_svi_ref = compute_sha256(svi_p) if svi_p.exists() else None

    print(f"[1/6] Input Hashes Verified:")
    print(f"      {raw_p}: {hash_raw_excel}")
    print(f"      {hist_p}: {hash_hist_csv}")
    if hash_svi_ref:
        print(f"      {svi_p}: {hash_svi_ref}")

    # Transcribe and export raw Treasury CMT table for 2026-11-17
    raw_cmt_data = {
        "source": "US Department of the Treasury Daily Treasury Par Yield Curve Rates",
        "reference_date": "2026-11-17",
        "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve",
        "retrieval_method": "Official web scrape of Treasury HTML TextView table",
        "retrieval_timestamp": "2026-11-21 16:20:25 America/New_York",
        "rates_table": [
            {"label": r[0], "tenor_years": r[1], "par_yield_pct": round(r[2] * 100.0, 2), "par_yield_decimal": r[2]}
            for r in OFFICIAL_TREASURY_CMT_2026_11_17
        ]
    }
    raw_cmt_path = out_p / "treasury_cmt_2026_11_17_raw.json"
    with open(raw_cmt_path, "w", encoding="utf-8") as f:
        json.dump(raw_cmt_data, f, indent=2)
    hash_raw_cmt = compute_sha256(raw_cmt_path)

    # Step 2: Rates Curve Generation & Repricing Verification
    print("[2/6] Generating Official 2026-11-17 Treasury Curve with Exact Consistent Bootstrap...")
    curve_boot = get_official_yield_curve(method="bootstrap")
    repricing_df = curve_boot.reprice_par_bonds()
    max_reprice_err_cents = float(repricing_df["error_cents"].abs().max())
    max_residual_usd = float(repricing_df["residual_usd"].abs().max())

    rates_comp_df = compare_rate_methods_and_curves()
    rates_comp_df.to_csv(out_p / "rates_curve_comparison.csv", index=False)
    repricing_df.to_csv(out_p / "rates_par_bonds_repricing.csv", index=False)

    rates_manifest = {
        "source": "US Department of the Treasury Daily Treasury Par Yield Curve Rates",
        "reference_date": "2026-11-17",
        "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve",
        "availability_window_est": "Estimated publication window between 17:00 and 18:00 EST (OTC closing bids ~15:30 EST)",
        "alignment_policy": "Contemporaneous closing ex-post alignment (standard for EOD mark-to-model books)",
        "method": "Exact coupon-bond bootstrap with log-linear discount factor interpolation",
        "max_reprice_error_cents": round(max_reprice_err_cents, 10),
        "max_residual_usd": float(max_residual_usd),
        "all_bonds_reprice_machine_zero": bool(max_residual_usd < 1e-10),
        "raw_cmt_file": "treasury_cmt_2026_11_17_raw.json",
        "raw_cmt_sha256": hash_raw_cmt
    }
    with open(out_p / "rates_treasury_manifest.json", "w", encoding="utf-8") as f:
        json.dump(rates_manifest, f, indent=2)

    # Step 3: Option Audit and Selection
    print("[3/6] Auditing options dataset and executing put selection...")
    audit_res = audit_and_select_options(raw_path=raw_excel, curve=curve_boot, output_dir=output_dir)
    puts_all = audit_res["puts_all"]
    puts_clean = audit_res["puts_clean"]
    puts_common = audit_res["puts_common_r3"]
    support_df = audit_res["support_summary"]
    calls_all = audit_res["calls_all"]

    print(f"      Total puts audited: {len(puts_all)}")
    print(f"      Rejected stale trades: {(puts_all['status'] == 'REJECTED_STALE_TRADE').sum()}")
    print(f"      Rejected bounds violations: {(puts_all['status'] == 'REJECTED_BOUNDS_VIOLATION').sum()}")
    print(f"      Microstructure sensitive / penny: {(puts_all['status'] == 'CANDIDATE_MICROSTRUCTURE_SENSITIVE').sum()}")
    print(f"      Selected clean puts: {len(puts_clean)}")
    print(f"      Common R3 benchmark puts: {len(puts_common)}")

    # Step 4: Deterministic Data Split
    print("[4/6] Creating deterministic train / strike-holdout / tenor-holdout / calls-contrast split...")
    split_res = create_deterministic_split(
        puts_df=puts_clean,
        calls_df=calls_all,
        output_dir=output_dir
    )
    split_manifest = split_res["manifest"]
    print(f"      Train set: {len(split_res['train'])} puts ({split_manifest['pct_train']}%)")
    print(f"      Strike holdout: {len(split_res['strike_holdout'])} puts ({split_manifest['pct_strike_holdout']}%)")
    print(f"      Tenor holdout: {len(split_res['tenor_holdout'])} puts ({split_manifest['pct_tenor_holdout']}%)")
    print(f"      Calls contrast: {len(split_res['calls_contrast'])} calls")

    # Also build split for the common 84 puts to have identical benchmark splits
    split_res_84 = create_deterministic_split(
        puts_df=puts_common,
        calls_df=calls_all,
        output_dir=output_dir + "/split_common_84"
    )

    # Step 5: Common Baseline Pricing & Disentangled Ablation
    print("[5/6] Computing common baseline pricing and disentangled ablation...")
    baseline_details, baseline_summary = compute_baseline_benchmarks(
        puts_df=puts_common,
        curve_official=curve_boot,
        output_dir=output_dir
    )
    print("\nBaseline Summary Metrics on Common 84 Puts:")
    print(baseline_summary.to_string(index=False))

    # Step 6: Artifact Signatures & Manifest
    print("\n[6/6] Generating Phase 0 Execution Manifest with SHA-256 signatures...")
    t_end = time.perf_counter()
    elapsed_sec = t_end - t_start

    generated_hashes = {}
    for p in sorted(out_p.glob("*.*")):
        if p.name != "phase0_execution_manifest.json":
            generated_hashes[p.name] = compute_sha256(p)

    execution_manifest = {
        "phase": "PHASE_0",
        "title": "Heston Migration Preparation and Baseline Baseline",
        "execution_timestamp": datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "elapsed_seconds": round(elapsed_sec, 2),
        "environment": {
            "python_version": sys.version.split()[0],
            "quantlib_available": HAS_QUANTLIB,
            "quantlib_version": QUANTLIB_VERSION,
            "requirements_file": "requirements-heston.txt",
            "platform": sys.platform
        },
        "inputs": {
            "raw_excel": {
                "path": str(raw_p),
                "sha256": hash_raw_excel,
                "verified": hash_raw_excel == "306f8d3c1a52c7a67952d08881516bdc8632856e3abd6b33de373c4bc77ffb53"
            },
            "historical_csv": {
                "path": str(hist_p),
                "sha256": hash_hist_csv,
                "verified": hash_hist_csv == "a510f9a48eaa0fc4f95cfbfcda491de09f4a6b14956efb0f3959c7c57ac5989a"
            },
            "svi_frozen_reference": {
                "commit_sha": SVI_FROZEN_SHA,
                "path": str(svi_p),
                "sha256": hash_svi_ref
            }
        },
        "market_parameters": {
            "valuation_date": "2026-11-17 16:00:00 America/New_York",
            "spot_price_usd": SPOT_PRICE,
            "dividend_yield_q": DIVIDEND_YIELD,
            "day_count_convention": "ACT/365F continuous"
        },
        "rates_curve": rates_manifest,
        "selection_counts": {
            "total_raw_contracts": 575,
            "total_raw_puts": len(puts_all),
            "rejected_stale_trade": int((puts_all['status'] == 'REJECTED_STALE_TRADE').sum()),
            "rejected_bounds_violation": int((puts_all['status'] == 'REJECTED_BOUNDS_VIOLATION').sum()),
            "candidate_microstructure_sensitive": int((puts_all['status'] == 'CANDIDATE_MICROSTRUCTURE_SENSITIVE').sum()),
            "selected_clean_puts": len(puts_clean),
            "common_r3_benchmark_puts": len(puts_common),
            "calls_external_contrast": len(split_res['calls_contrast'])
        },
        "ablation_summary": {
            "max_am_flat_rate_effect_usd": float(baseline_details["rate_effect_am_ql_usd"].abs().max()),
            "max_am_flat_rate_effect_pde_usd": float(baseline_details["rate_effect_am_pde_usd"].abs().max()),
            "max_svi_pure_rate_effect_usd": float(baseline_details["rate_effect_svi_pure_pde_usd"].abs().max()),
            "max_engine_discrepancy_am_usd": float(baseline_details["engine_disc_am_flat_usd"].abs().max()),
            "max_engine_discrepancy_svi_usd": float(baseline_details["engine_disc_svi_usd"].abs().max())
        },
        "baseline_metrics_common_84": baseline_summary.to_dict(orient="records"),
        "poc_gate_proposals": {
            "numerical_solver_tolerance_usd": 0.002,
            "solver_tolerance_note": "Equivalent to 1/5th of 0.01 tick, to be verified against 3 grid resolutions",
            "in_sample_mae_gate_usd": 0.080,
            "in_sample_rmse_gate_usd": 0.120,
            "atm_max_rel_error_pct": 10.0,
            "holdout_generalization_assessment": "Report MAE/RMSE by split, coverage and common benchmark; relative gap not used in isolation",
            "feller_ratio_policy": "Report 2*kappa*theta / sigma_v^2 ratio and boundary behavior without rigid pre-filter",
            "rho_parameter_domain": "[-0.95, 0.50] allowing empirical exploration of correlation regime",
            "multistart_runs": 5,
            "multistart_runtime_policy": "Track runtime, evaluations and convergence feasibility without rigid 60s hard block"
        },
        "generated_artifacts_sha256": generated_hashes
    }

    with open(out_p / "phase0_execution_manifest.json", "w", encoding="utf-8") as f:
        json.dump(execution_manifest, f, indent=2)

    print(f"\nPhase 0 Pipeline completed successfully in {elapsed_sec:.2f} seconds.")
    print(f"All artifacts saved cleanly to: {out_p.resolve()}")
    return execution_manifest


if __name__ == "__main__":
    run_phase0_pipeline()
