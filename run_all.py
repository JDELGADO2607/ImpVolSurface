"""
Master Pipeline Orchestrator — NU US Equity American Options Project.
Executes all stages from raw data ingestion to final reports, tables, figures, and tests.
Enforces strict error propagation, output validation, and non-zero exit codes on any critical failure.
"""

import sys
import time
from pathlib import Path
from typing import Callable, Any
import pandas as pd
import numpy as np
import pytest

# Add project root to path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Table Data Contracts: Schema and finite value requirements across all pipeline tables
DATA_CONTRACTS: dict[str, dict[str, Any]] = {
    "options_clean.csv": {
        'min_rows': 200,
        'required_cols': ['contractSymbol', 'expirationDate', 'strike', 'type', 'lastPrice', 'tau_recalc'],
        'finite_cols': ['strike', 'lastPrice', 'tau_recalc']
    },
    "options_audit.csv": {
        'min_rows': 200,
        'required_cols': ['contractSymbol', 'tier', 'rejection_reasons'],
        'finite_cols': ['strike', 'lastPrice']
    },
    "options_with_iv.csv": {
        'min_rows': 200,
        'required_cols': ['contractSymbol', 'our_iv_decimal', 'k_log_moneyness'],
        'finite_cols': ['our_iv_decimal', 'k_log_moneyness']
    },
    "svi_slice_parameters.csv": {
        'min_rows': 16,
        'required_cols': ['expirationDate', 'tau_days', 'tau_years', 'method', 'production_status'],
        'finite_cols': ['tau_days', 'tau_years']
    },
    "surface_release_grid.csv": {
        'min_rows': 100,
        'required_cols': [
            'tau_days', 'tau_years', 'strike', 'forward', 'log_moneyness',
            'raw_total_variance', 'projected_total_variance', 'surface_iv_pct',
            'call_price_model', 'put_price_model', 'dC_dK', 'd2C_dK2',
            'is_convex', 'calendar_spread_vs_prev_tau', 'is_calendar_arbitrage_free',
            'american_put_time_monotonic', 'dominant_tenor_tau', 'delta_w_projected',
            'is_extrapolated_strike', 'is_extrapolated_tau', 'is_production_ready',
            'quality_flag', 'slice_support_K_min', 'slice_support_K_max'
        ],
        'finite_cols': ['tau_days', 'strike', 'forward', 'surface_iv_pct', 'call_price_model', 'put_price_model', 'd2C_dK2']
    },
    "surface_quality_diagnostics.csv": {
        'min_rows': 16,
        'required_cols': ['expirationDate', 'tau_days', 'method', 'cross_sectional_arb_status', 'production_status'],
        'finite_cols': ['tau_days', 'tau_years']
    },
    "surface_final_holdout_validation.csv": {
        'min_rows': 190,
        'required_cols': ['contractSymbol', 'expirationDate', 'strike', 'type', 'true_iv_pct', 'pred_iv_pct', 'iv_error_pp', 'obs_price', 'pred_price', 'price_error_usd'],
        'finite_cols': ['true_iv_pct', 'pred_iv_pct', 'iv_error_pp', 'price_error_usd']
    },
    "surface_leave_one_out_validation.csv": {
        'min_rows': 190,
        'required_cols': ['contractSymbol', 'expirationDate', 'strike', 'type', 'iv_error_pp', 'price_error_usd'],
        'finite_cols': ['iv_error_pp', 'price_error_usd']
    },
    "model_comparison_summary.csv": {
        'min_rows': 4,
        'required_cols': ['Evaluation_Type', 'Segment', 'N', 'M1 Eu Flat MAE', 'M1 RMSE', 'M4 Am Surf MAE', 'M4 RMSE'],
        'finite_cols': ['M1 Eu Flat MAE', 'M1 RMSE', 'M4 Am Surf MAE', 'M4 RMSE']
    },
    "model_comparison_detailed.csv": {
        'min_rows': 200,
        'required_cols': ['contractSymbol', 'type', 'strike', 'lastPrice', 'm4_am_surf', 'err_m4'],
        'finite_cols': ['lastPrice', 'm4_am_surf', 'err_m4']
    },
    "hypothetical_portfolio.csv": {
        'min_rows': 4,
        'required_cols': ['label', 'contractSymbol', 'type', 'strike', 'quantity', 'position_delta', 'position_gamma', 'position_vega_1pp'],
        'finite_cols': ['strike', 'quantity', 'position_delta', 'position_gamma', 'position_vega_1pp']
    },
    "stress_test_matrix.csv": {
        'min_rows': 10,
        'required_cols': ['scenario_id', 'scenario_name', 'total_port_pnl_stress_mod', 'economic_margin_capital'],
        'finite_cols': ['total_port_pnl_stress_mod', 'economic_margin_capital']
    },
    "stress_test_leg_breakdown.csv": {
        'min_rows': 25,
        'required_cols': ['scenario_id', 'contractSymbol', 'leg_pnl_stress_mod'],
        'finite_cols': ['leg_pnl_stress_mod']
    },
    "volatility_forecast_evaluation.csv": {
        'min_rows': 2,
        'required_cols': ['Model', 'OOS MAE (pp)', 'OOS RMSE (pp)', 'QLIKE Loss'],
        'finite_cols': ['OOS MAE (pp)', 'OOS RMSE (pp)', 'QLIKE Loss']
    },
    "strategy1_straddle_scenarios.csv": {
        'min_rows': 15,
        'required_cols': ['Spot_Shock', 'Signal_Action', 'Net_PnL', 'Friction_Cost'],
        'finite_cols': ['Net_PnL', 'Friction_Cost']
    },
    "strategy2_calendar_scenarios.csv": {
        'min_rows': 15,
        'required_cols': ['Cost_Regime', 'Spot_Move', 'Net_PnL_USD', 'Friction_Cost_USD'],
        'finite_cols': ['Net_PnL_USD', 'Friction_Cost_USD']
    }
}

REQUIRED_FIGURES = [
    Path("outputs/figures/smile_2d_slices.png"),
    Path("outputs/figures/term_structure_atm.png"),
    Path("outputs/figures/surface_3d_volatility.png"),
    Path("outputs/figures/model_comparison_errors.png"),
    Path("outputs/figures/stress_test_pnl_waterfall.png"),
    Path("outputs/figures/stress_crisis_leg_breakdown.png"),
    Path("outputs/figures/nu_historical_vol_and_forecasts.png"),
    Path("outputs/figures/strategy1_payoff_scenarios.png"),
    Path("outputs/figures/strategy2_calendar_payoff.png")
]

def _validate_table_file(path: Path, min_rows: int = 1, check_finite_cols: list[str] | None = None) -> None:
    """
    Validates that a generated table file exists, is non-empty, matches data contract schema, and has finite values.
    Raises ValueError on validation failure.
    """
    if not path.exists():
        raise FileNotFoundError(f"Mandatory output artifact missing: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Mandatory output file is empty (0 bytes): {path}")

    if path.suffix == '.csv':
        df = pd.read_csv(path)
        contract = DATA_CONTRACTS.get(path.name)
        if contract:
            req_rows = contract.get('min_rows', min_rows)
            if len(df) < req_rows:
                raise ValueError(f"Data contract violation: {path.name} contains {len(df)} rows (minimum required: {req_rows})")

            req_cols = contract.get('required_cols', [])
            missing_cols = [c for c in req_cols if c not in df.columns]
            if missing_cols:
                raise ValueError(f"Data contract violation: {path.name} is missing required columns: {missing_cols}")

            finite_cols = contract.get('finite_cols', check_finite_cols)
            if finite_cols:
                for col in finite_cols:
                    if col in df.columns:
                        vals = df[col].dropna()
                        if len(vals) == 0:
                            raise ValueError(f"Data contract violation: Column '{col}' in {path.name} contains no valid values.")
                        if np.isinf(vals).any():
                            raise ValueError(f"Data contract violation: Column '{col}' in {path.name} contains non-finite/infinite values.")
        else:
            if len(df) < min_rows:
                raise ValueError(f"Table {path.name} contains {len(df)} rows (minimum required: {min_rows})")
            if check_finite_cols:
                for col in check_finite_cols:
                    if col in df.columns:
                        vals = df[col].dropna()
                        if len(vals) == 0:
                            raise ValueError(f"Column '{col}' in {path.name} contains no valid values.")
                        if np.isinf(vals).any():
                            raise ValueError(f"Column '{col}' in {path.name} contains non-finite/infinite values.")

def run_pipeline(
    raise_on_error: bool = True,
    run_tests: bool = True,
    pytest_args: list[str] | None = None
) -> int:
    """
    Executes complete quantitative pipeline sequentially with strict stage validation.
    Returns:
    - 0 on full success across all stages and tests.
    - Non-zero integer (1 or pytest exit code) on failure.
    If raise_on_error is True, exits with sys.exit(exit_code) or raises RuntimeError.
    """
    start_time = time.time()
    print("=" * 80)
    print("STARTING COMPLETE QUANTITATIVE PIPELINE: NU AMERICAN OPTIONS")
    print("=" * 80)

    stages: list[dict[str, Any]] = [
        {
            'step': 1,
            'name': "Ingesting, Cleaning and Auditing Options Chain",
            'module': "src.data_cleaning",
            'func': "clean_and_audit_options",
            'is_blocking': True,
            'artifacts': [
                Path("outputs/tables/options_clean.csv"),
                Path("outputs/tables/options_audit.csv")
            ],
            'check_cols': ['strike', 'lastPrice', 'tau_recalc']
        },
        {
            'step': 2,
            'name': "Inverting Implied Volatilities (Brent + FD / BS)",
            'module': "src.iv_inversion",
            'func': "invert_clean_dataset",
            'is_blocking': True,
            'artifacts': [Path("outputs/tables/options_with_iv.csv")],
            'check_cols': ['our_iv_decimal', 'k_log_moneyness']
        },
        {
            'step': 3,
            'name': "Calibrating Implied Volatility Surface & Validation",
            'module': "src.surface",
            'func': "generate_surface_plots_and_tables",
            'is_blocking': True,
            'artifacts': [
                Path("outputs/tables/svi_slice_parameters.csv"),
                Path("outputs/tables/surface_release_grid.csv"),
                Path("outputs/tables/surface_quality_diagnostics.csv"),
                Path("outputs/tables/surface_final_holdout_validation.csv"),
                Path("outputs/tables/surface_leave_one_out_validation.csv")
            ],
            'check_cols': ['tau_years', 'pct_price_convex']
        },
        {
            'step': 4,
            'name': "Running 4-Model Pricing Comparison",
            'module': "src.model_comparison",
            'func': "run_model_comparison",
            'is_blocking': True,
            'artifacts': [Path("outputs/tables/model_comparison_summary.csv")],
            'check_cols': ['MAE_USD', 'RMSE_USD']
        },
        {
            'step': 5,
            'name': "Building Delta-Neutral Portfolio & Greek Profiling",
            'module': "src.portfolio",
            'func': "build_hypothetical_portfolio",
            'is_blocking': True,
            'artifacts': [Path("outputs/tables/hypothetical_portfolio.csv")],
            'check_cols': ['Delta']
        },
        {
            'step': 6,
            'name': "Executing Fixed-Chain Multi-Factor Stress Testing",
            'module': "src.stress_testing",
            'func': "run_stress_testing",
            'is_blocking': True,
            'artifacts': [
                Path("outputs/tables/stress_test_matrix.csv"),
                Path("outputs/tables/stress_test_leg_breakdown.csv")
            ],
            'check_cols': ['PnL_Total_USD']
        },
        {
            'step': 7,
            'name': "Estimating HAR-RV Forecasts and Trading Strategies",
            'module': "src.strategies",
            'func': "run_strategies_analysis",
            'is_blocking': True,
            'artifacts': [
                Path("outputs/tables/volatility_forecast_evaluation.csv"),
                Path("outputs/tables/strategy1_straddle_scenarios.csv"),
                Path("outputs/tables/strategy2_calendar_scenarios.csv")
            ],
            'check_cols': ['Net_PnL']
        }
    ]

    stage_log = []

    # Execute stages 1 through 7
    for st in stages:
        step_num = st['step']
        name = st['name']
        is_blocking = st['is_blocking']
        print(f"\n>>> Step {step_num}/8: {name}...")

        t_stage_start = time.time()
        try:
            # Dynamically import and run stage function
            import importlib
            mod = importlib.import_module(st['module'])
            func_to_run = getattr(mod, st['func'])
            func_to_run()

            # Post-stage artifact verification
            for art in st['artifacts']:
                _validate_table_file(art, min_rows=1, check_finite_cols=st.get('check_cols'))

            elapsed_stage = time.time() - t_stage_start
            stage_log.append({
                'step': step_num,
                'name': name,
                'status': 'SUCCESS',
                'time_s': round(elapsed_stage, 2),
                'error': None
            })
            print(f"[OK] Step {step_num} completed successfully in {elapsed_stage:.2f}s.")

        except Exception as e:
            elapsed_stage = time.time() - t_stage_start
            err_msg = f"{type(e).__name__}: {str(e)}"
            stage_log.append({
                'step': step_num,
                'name': name,
                'status': 'FAILED',
                'time_s': round(elapsed_stage, 2),
                'error': err_msg
            })
            print(f"\n[CRITICAL ERROR] Pipeline failed at Step {step_num} ({name}):")
            print(f"  --> {err_msg}")

            if is_blocking:
                print(f"\n[ABORTED] Stage {step_num} is BLOCKING. Halting pipeline execution immediately.")
                if raise_on_error:
                    sys.exit(1)
                return 1

    # Validate Publication Figures
    print("\n>>> Validating Publication Figures...")
    for fig_p in REQUIRED_FIGURES:
        if not fig_p.exists():
            raise FileNotFoundError(f"Mandatory figure missing: {fig_p}")
        if fig_p.stat().st_size == 0:
            raise ValueError(f"Mandatory figure is empty (0 bytes): {fig_p}")
    print(f"[OK] All {len(REQUIRED_FIGURES)} publication figures validated successfully.")

    # Step 8: Automated Verification Test Suite (Pytest)
    test_exit_code = 0
    if run_tests:
        print("\n>>> Step 8/8: Executing Complete Automated Verification Test Suite...")
        if pytest_args is None:
            pytest_args = ["-v", "tests/"]

        test_exit_code = int(pytest.main(pytest_args))
        if test_exit_code != 0:
            print(f"\n[CRITICAL ERROR] Pytest verification failed with exit code: {test_exit_code}")
            stage_log.append({
                'step': 8,
                'name': "Pytest Test Suite",
                'status': 'FAILED',
                'time_s': 0.0,
                'error': f"Pytest exit code: {test_exit_code}"
            })
            if raise_on_error:
                sys.exit(test_exit_code)
            return test_exit_code
        else:
            stage_log.append({
                'step': 8,
                'name': "Pytest Test Suite",
                'status': 'SUCCESS',
                'time_s': 0.0,
                'error': None
            })
            print("\n[SUCCESS] All unit, regression, and stability tests passed successfully!")

    total_elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"PIPELINE EXECUTED SUCCESSFULLY IN {total_elapsed:.1f} SECONDS!")
    print("All stages passed verification and all tables/figures are fully validated.")
    print("Tables: outputs/tables/")
    print("Figures: outputs/figures/")
    print(f"Overall status: SUCCESS (Exit Code: 0)")
    print("=" * 80)

    return 0

if __name__ == "__main__":
    run_pipeline(raise_on_error=True)
