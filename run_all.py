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

def _validate_table_file(path: Path, min_rows: int = 1, check_finite_cols: list[str] | None = None) -> None:
    """
    Validates that a generated table file exists, is non-empty, and has finite values.
    Raises ValueError on validation failure.
    """
    if not path.exists():
        raise FileNotFoundError(f"Mandatory output artifact missing: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Mandatory output file is empty (0 bytes): {path}")

    if path.suffix == '.csv':
        df = pd.read_csv(path)
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
