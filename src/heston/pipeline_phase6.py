"""
Phase 6 Pipeline: Financial Integration, Model Comparison, Portfolio Risk, and Stress Testing.

Executes:
1. Four-model pricing comparison across the common frozen sample of 97 puts and 142 calls.
2. Valuation and coherent Heston Greeks for the 5-leg hypothetical portfolio.
3. Delta-hedging share calculation, residual tracking, and dynamic margin approximation.
4. Stress testing across 6 instantaneous scenarios contrasting non-linear PDE revaluation vs Taylor expansions.
5. Generation of high-resolution figures in figures/phase6/.
6. Export of summary metrics and cryptographic execution manifest.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import os
import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.heston.rates_curve import DeterministicYieldCurve, SPOT_PRICE, DIVIDEND_YIELD
from src.heston.heston_model import HestonParams
from src.heston.financial_integration import (
    run_four_model_comparison,
    evaluate_portfolio_and_greeks,
    run_portfolio_stress_testing,
    CONTRACT_MULTIPLIER
)


def compute_sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_phase6_pipeline() -> Dict[str, Any]:
    print("=" * 80)
    print("Starting Phase 6 Pipeline: Financial Integration & Portfolio Risk Analysis")
    print("=" * 80)

    start_time = time.time()
    out_dir = Path("data/heston/phase6")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = Path("figures/phase6")
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load inputs
    calib_path = Path("data/heston/phase4/heston_calibrated_parameters.json")
    with open(calib_path, "r") as f:
        calib_data = json.load(f)
    params = HestonParams(**calib_data["calibrated_parameters"])
    curve = DeterministicYieldCurve(method="bootstrap")

    puts_p4_path = Path("data/heston/phase4/heston_pricing_full_puts.csv")
    calls_p5_path = Path("data/heston/phase5/heston_iv_surface_142_calls.csv")
    df_puts_p4 = pd.read_csv(puts_p4_path)
    df_calls_p5 = pd.read_csv(calls_p5_path)

    print(f"Loaded calibrated parameters: {calib_data['calibrated_parameters']}")
    print(f"Loaded {len(df_puts_p4)} puts from Phase 4 and {len(df_calls_p5)} calls from Phase 5")

    # 2. Four-Model Comparison
    print("\n--- Step 1: Running Four-Model Comparison on 239 Contracts ---")
    df_detailed, df_summary = run_four_model_comparison(curve, params, df_puts_p4, df_calls_p5)

    comp_det_csv = out_dir / "models_comparison_detailed.csv"
    comp_sum_csv = out_dir / "models_comparison_summary.csv"
    df_detailed.to_csv(comp_det_csv, index=False)
    df_summary.to_csv(comp_sum_csv, index=False)
    print(f"Detailed comparison saved to {comp_det_csv} (rows: {len(df_detailed)})")
    print(f"Summary comparison saved to {comp_sum_csv}")
    print("\nFour-Model Summary Results:")
    print(df_summary[["segment", "count_contracts", "m1_eu_const_bs_mae_usd", "m2_am_const_1d_mae_usd", "m3_eu_heston_mae_usd", "m4_am_heston_mae_usd", "mean_eep_heston_usd"]].to_string())

    # 3. Portfolio & Greeks
    print("\n--- Step 2: Evaluating 5-Leg Portfolio, Heston Greeks & Delta-Hedge ---")
    df_portfolio, port_summary, df_stability = evaluate_portfolio_and_greeks(curve, params, df_puts_p4, df_calls_p5)

    port_csv = out_dir / "portfolio_greeks_and_valuation.csv"
    stab_csv = out_dir / "portfolio_convergence_checks.csv"
    df_portfolio.to_csv(port_csv, index=False)
    df_stability.to_csv(stab_csv, index=False)
    print(f"Portfolio valuation & Greeks saved to {port_csv}")
    print(f"Step sensitivity checks saved to {stab_csv}")
    print("\nPortfolio Legs Breakdown:")
    print(df_portfolio[["label", "quantity", "obs_price", "heston_price", "position_delta", "position_gamma", "position_sens_sigma0_1pp", "position_theta_daily"]].to_string())
    print("\nPortfolio Summary:")
    for k, v in port_summary.items():
        print(f"  {k}: {v}")

    # 4. Stress Testing
    print("\n--- Step 3: Running 6 Instantaneous Stress Testing Scenarios ---")
    df_stress, df_legs = run_portfolio_stress_testing(df_portfolio, port_summary, curve, params)

    stress_csv = out_dir / "portfolio_stress_scenarios.csv"
    legs_csv = out_dir / "portfolio_stress_leg_detail.csv"
    df_stress.to_csv(stress_csv, index=False)
    df_legs.to_csv(legs_csv, index=False)
    print(f"Stress test summary saved to {stress_csv}")
    print(f"Stress test leg detail saved to {legs_csv}")
    print("\nStress Test Scenarios:")
    print(df_stress[["scenario_id", "spot_shocked_usd", "sigma0_shocked_pct", "options_pnl_reval_usd", "hedge_pnl_usd", "total_portfolio_pnl_reval_usd", "total_portfolio_pnl_taylor_usd", "taylor_divergence_usd"]].to_string())

    # 5. Visualizations
    print("\n--- Step 4: Generating Visualizations ---")
    # Figure 1: Model Comparison Errors by Segment
    fig, ax = plt.subplots(figsize=(12, 6))
    segments = df_summary["segment"].tolist()[:5]  # exclude combined for clarity
    x = np.arange(len(segments))
    width = 0.2

    m1_mae = df_summary.loc[:4, "m1_eu_const_bs_mae_usd"].values
    m2_mae = df_summary.loc[:4, "m2_am_const_1d_mae_usd"].values
    m3_mae = df_summary.loc[:4, "m3_eu_heston_mae_usd"].values
    m4_mae = df_summary.loc[:4, "m4_am_heston_mae_usd"].values

    ax.bar(x - 1.5 * width, m1_mae, width, label='M1: European Flat BS (44%)', color='#9ecae1')
    ax.bar(x - 0.5 * width, m2_mae, width, label='M2: American Flat 1D (44%)', color='#4292c6')
    ax.bar(x + 0.5 * width, m3_mae, width, label='M3: European Heston', color='#fdae6b')
    ax.bar(x + 1.5 * width, m4_mae, width, label='M4: American Heston', color='#e6550d')

    ax.set_ylabel('Mean Absolute Error (USD)', fontsize=11)
    ax.set_title('Four-Model Pricing Comparison Across Partitions (MAE vs Market)', fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels(segments, rotation=15, ha='right', fontsize=9)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')
    fig1_path = fig_dir / "models_comparison_errors_by_partition.png"
    plt.tight_layout()
    plt.savefig(fig1_path, dpi=300)
    plt.close()

    # Figure 2: Early Exercise Premium (EEP) Profile for Puts
    fig, ax = plt.subplots(figsize=(10, 6))
    puts_sub = df_detailed[df_detailed["type"] == "PUT"]
    sc = ax.scatter(
        puts_sub["strike"], puts_sub["eep_heston_usd"] * 100.0,
        c=puts_sub["tau_days"], cmap='viridis', s=50, alpha=0.85, edgecolors='black', linewidth=0.5
    )
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label('Tenor (Days)', fontsize=10)
    ax.set_xlabel('Strike K (USD)', fontsize=11)
    ax.set_ylabel('Heston Early Exercise Premium (Cents USD)', fontsize=11)
    ax.set_title('American Put Early Exercise Premium (EEP = Am Heston - Eu Heston)', fontsize=13)
    ax.axvline(SPOT_PRICE, color='red', linestyle='--', label=f'Spot Price ${SPOT_PRICE:.2f}')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left')
    fig2_path = fig_dir / "early_exercise_premium_profile.png"
    plt.tight_layout()
    plt.savefig(fig2_path, dpi=300)
    plt.close()

    # Figure 3: Stress Testing P&L Profile
    fig, ax = plt.subplots(figsize=(11, 6))
    sc_labels = [s.replace('_', ' ') for s in df_stress["scenario_id"]]
    x_sc = np.arange(len(sc_labels))
    w_sc = 0.28

    ax.bar(x_sc - w_sc, df_stress["options_pnl_reval_usd"], w_sc, label='Options Portfolio (Unhedged)', color='#ef8a62')
    ax.bar(x_sc, df_stress["hedge_pnl_usd"], w_sc, label='Stock Hedge P&L', color='#999999')
    ax.bar(x_sc + w_sc, df_stress["total_portfolio_pnl_reval_usd"], w_sc, label='Total Delta-Hedged Portfolio', color='#2ca25f')

    ax.axhline(0.0, color='black', linewidth=0.8, linestyle='--')
    ax.set_ylabel('Stress P&L (USD)', fontsize=11)
    ax.set_title('Hypothetical Portfolio Stress Testing P&L Across 6 Instantaneous Scenarios', fontsize=13)
    ax.set_xticks(x_sc)
    ax.set_xticklabels(sc_labels, rotation=20, ha='right', fontsize=9)
    ax.legend(loc='lower left')
    ax.grid(True, alpha=0.3, axis='y')
    fig3_path = fig_dir / "portfolio_stress_pnl_profile.png"
    plt.tight_layout()
    plt.savefig(fig3_path, dpi=300)
    plt.close()

    # Figure 4: Taylor vs Revaluation Divergence
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_sc, df_stress["total_portfolio_pnl_reval_usd"], 'o-', color='#2ca25f', label='Full Non-Linear Revaluation', linewidth=2)
    ax.plot(x_sc, df_stress["total_portfolio_pnl_taylor_usd"], 's--', color='#e41a1c', label='2nd-Order Taylor Greek Expansion', linewidth=2)
    ax.axhline(0.0, color='black', linewidth=0.8, linestyle=':')
    ax.set_xticks(x_sc)
    ax.set_xticklabels(sc_labels, rotation=20, ha='right', fontsize=9)
    ax.set_ylabel('Portfolio P&L (USD)', fontsize=11)
    ax.set_title('Non-Linear PDE Revaluation vs 2nd-Order Taylor Approximation (Curvature Gap)', fontsize=12)
    ax.legend(loc='lower left')
    ax.grid(True, alpha=0.3)
    fig4_path = fig_dir / "stress_taylor_vs_revaluation.png"
    plt.tight_layout()
    plt.savefig(fig4_path, dpi=300)
    plt.close()
    print("All figures successfully created.")

    # 6. Summary Metrics
    print("\n--- Step 5: Compiling Summary Metrics ---")
    s0_row = df_stress[df_stress["scenario_id"] == "S0_Base_Null"].iloc[0]

    metrics = {
        "model_comparison": {
            "total_contracts": len(df_detailed),
            "puts_count": int((df_detailed["type"] == "PUT").sum()),
            "calls_count": int((df_detailed["type"] == "CALL").sum()),
            "all_puts_am_heston_mae_usd": float(df_summary.loc[df_summary["segment"] == "All Puts", "m4_am_heston_mae_usd"].values[0]),
            "all_puts_am_heston_rmse_usd": float(df_summary.loc[df_summary["segment"] == "All Puts", "m4_am_heston_rmse_usd"].values[0]),
            "train_puts_am_heston_mae_usd": float(df_summary.loc[df_summary["segment"] == "Puts: Train (60)", "m4_am_heston_mae_usd"].values[0]),
            "strike_holdout_puts_am_heston_mae_usd": float(df_summary.loc[df_summary["segment"] == "Puts: Strike Holdout (22)", "m4_am_heston_mae_usd"].values[0]),
            "tenor_holdout_puts_am_heston_mae_usd": float(df_summary.loc[df_summary["segment"] == "Puts: Tenor Holdout (15)", "m4_am_heston_mae_usd"].values[0]),
            "all_calls_am_heston_mae_usd": float(df_summary.loc[df_summary["segment"] == "All Calls (External Contrast 142)", "m4_am_heston_mae_usd"].values[0]),
            "mean_eep_puts_heston_usd": float(df_summary.loc[df_summary["segment"] == "All Puts", "mean_eep_heston_usd"].values[0]),
            "max_eep_puts_heston_usd": float(df_summary.loc[df_summary["segment"] == "All Puts", "max_eep_heston_usd"].values[0]),
        },
        "portfolio": port_summary,
        "stress_testing": {
            "null_scenario_exact_zero": bool(abs(s0_row["total_portfolio_pnl_reval_usd"]) < 1e-10),
            "s0_null_pnl_usd": float(s0_row["total_portfolio_pnl_reval_usd"]),
            "s1_spot_down_5_pnl_usd": float(df_stress.loc[df_stress["scenario_id"] == "S1_Spot_Down_5", "total_portfolio_pnl_reval_usd"].values[0]),
            "s2_spot_up_5_pnl_usd": float(df_stress.loc[df_stress["scenario_id"] == "S2_Spot_Up_5", "total_portfolio_pnl_reval_usd"].values[0]),
            "s3_vol_spike_5pp_pnl_usd": float(df_stress.loc[df_stress["scenario_id"] == "S3_Vol_Spike_5pp", "total_portfolio_pnl_reval_usd"].values[0]),
            "s4_severe_crisis_pnl_usd": float(df_stress.loc[df_stress["scenario_id"] == "S4_Severe_Crisis", "total_portfolio_pnl_reval_usd"].values[0]),
            "s5_bullish_rally_pnl_usd": float(df_stress.loc[df_stress["scenario_id"] == "S5_Bullish_Rally", "total_portfolio_pnl_reval_usd"].values[0]),
            "max_taylor_divergence_usd": float(df_stress["abs_taylor_divergence_usd"].max()),
        },
        "step_stability_check_passed": bool(df_stability["stable_step_discrepancy"].all())
    }

    metrics_json = out_dir / "phase6_summary_metrics.json"
    with open(metrics_json, "w") as f:
        json.dump(metrics, f, indent=2)

    # 7. Execution Manifest
    manifest = {
        "phase": "PHASE_6",
        "description": "Financial Integration, Four-Model Comparison, Portfolio Risk, and Stress Testing",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_files": {
            "calibrated_parameters": {
                "path": str(calib_path),
                "sha256": compute_sha256(calib_path)
            },
            "phase4_full_puts": {
                "path": str(puts_p4_path),
                "sha256": compute_sha256(puts_p4_path)
            },
            "phase5_calls": {
                "path": str(calls_p5_path),
                "sha256": compute_sha256(calls_p5_path)
            }
        },
        "output_files": {
            "models_comparison_detailed": {
                "path": str(comp_det_csv),
                "rows": len(df_detailed),
                "sha256": compute_sha256(comp_det_csv)
            },
            "models_comparison_summary": {
                "path": str(comp_sum_csv),
                "rows": len(df_summary),
                "sha256": compute_sha256(comp_sum_csv)
            },
            "portfolio_greeks_and_valuation": {
                "path": str(port_csv),
                "rows": len(df_portfolio),
                "sha256": compute_sha256(port_csv)
            },
            "portfolio_convergence_checks": {
                "path": str(stab_csv),
                "rows": len(df_stability),
                "sha256": compute_sha256(stab_csv)
            },
            "portfolio_stress_scenarios": {
                "path": str(stress_csv),
                "rows": len(df_stress),
                "sha256": compute_sha256(stress_csv)
            },
            "portfolio_stress_leg_detail": {
                "path": str(legs_csv),
                "rows": len(df_legs),
                "sha256": compute_sha256(legs_csv)
            },
            "phase6_summary_metrics": {
                "path": str(metrics_json),
                "sha256": compute_sha256(metrics_json)
            }
        },
        "figures": [
            str(fig1_path),
            str(fig2_path),
            str(fig3_path),
            str(fig4_path)
        ],
        "calibrated_parameters_used": calib_data["calibrated_parameters"],
        "runtime_seconds": round(time.time() - start_time, 2)
    }

    manifest_json = out_dir / "phase6_execution_manifest.json"
    with open(manifest_json, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest successfully compiled at {manifest_json}")
    print(f"Phase 6 Pipeline completed in {manifest['runtime_seconds']} seconds.")
    print("=" * 80)
    return manifest


if __name__ == "__main__":
    run_phase6_pipeline()
