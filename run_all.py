"""
Master Pipeline Orchestrator — NU US Equity American Options Project.
Executes all stages from raw data ingestion to final reports, tables, figures, and tests.
Guarantees full deterministic reproducibility.
"""

import sys
import time
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

def run_pipeline():
    start_time = time.time()
    print("=" * 80)
    print("STARTING COMPLETE QUANTITATIVE PIPELINE: NU AMERICAN OPTIONS")
    print("=" * 80)

    # Step 1: Clean and Audit Raw Data
    print("\n>>> Step 1/7: Ingesting, Cleaning and Auditing Options Chain...")
    from src.data_cleaning import clean_and_audit_options
    clean_and_audit_options()

    # Step 2: IV Inversion via Brent and Crank-Nicolson FD
    print("\n>>> Step 2/7: Inverting Implied Volatilities (Brent + FD / BS)...")
    from src.iv_inversion import invert_clean_dataset
    invert_clean_dataset()

    # Step 3: Volatility Surface Calibration (Raw SVI & Spline)
    print("\n>>> Step 3/7: Calibrating Implied Volatility Surface & Validation...")
    from src.surface import generate_surface_plots_and_tables
    generate_surface_plots_and_tables()

    # Step 4: 4-Model Pricing Comparison
    print("\n>>> Step 4/7: Running 4-Model Pricing Comparison...")
    from src.model_comparison import run_model_comparison
    run_model_comparison()

    # Step 5: Portfolio Construction and Delta Hedging
    print("\n>>> Step 5/7: Building Delta-Neutral Portfolio & Greek Profiling...")
    from src.portfolio import build_hypothetical_portfolio
    build_hypothetical_portfolio()

    # Step 6: Fixed-Chain Stress Testing
    print("\n>>> Step 6/7: Executing Fixed-Chain Multi-Factor Stress Testing...")
    from src.stress_testing import run_stress_testing
    run_stress_testing()

    # Step 7: Historical Forecasts & Hypothetical Strategies
    print("\n>>> Step 7/8: Estimating HAR-RV Forecasts and Trading Strategies...")
    from src.forecasts import run_forecast_pipeline
    from src.strategies import run_strategies_analysis
    run_forecast_pipeline()
    run_strategies_analysis()

    # Step 8: Automated Verification Test Suite (Pytest)
    print("\n>>> Step 8/8: Executing Complete Automated Verification Test Suite...")
    import pytest
    test_exit_code = pytest.main(["-v", "tests/"])
    if test_exit_code != 0:
        print(f"\n[WARNING] Pytest reported test failures (exit code: {test_exit_code})")
    else:
        print("\n[SUCCESS] All unit, regression, and stability tests passed successfully!")

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"PIPELINE EXECUTED SUCCESSFULLY IN {elapsed:.1f} SECONDS!")
    print("All tables exported to: outputs/tables/")
    print("All figures exported to: outputs/figures/")
    print(f"Test suite exit code: {test_exit_code}")
    print("=" * 80)

if __name__ == "__main__":
    run_pipeline()
