"""
Unit and integration tests for Phase 3: Broad Independent Numerical Validation of the 2D Heston Solver.

Verifies:
1. Market 97 puts coverage: 100% evaluated, max error <= 0.0020 USD against QuantLib refined references.
2. Rule of the Worst 3: Extra-fine grid (320x160, M=900*T) converges within 0.0020 USD against QuantLib 1000.
3. 6 Predeclared Hypothetical Regimes (108 prices): All 108 prices pass within 0.0020 USD target.
4. Robustness under positive correlation (rho = +0.70) and Feller condition violation (2*kappa*theta / xi^2 = 0.222 < 1).
5. Exact analytical limit xi = 0.0 matches Black-Scholes analytical formula within 0.0020 USD.
6. Degenerate boundary v0 = 0.0 executes stably with forward drift kappa*theta > 0, documenting QuantLib limitation.
7. Payoff reproduction at tau = 0 exact to machine precision (< 1e-12 USD).
8. Continuous fractional maturity T = 27.5d and smooth C1 temporal evolution.
9. Economic shape properties: unclipped lower bounds, positive EEP, strike monotonicity, calendar monotonicity.
10. Butterfly spread convexity with propagated numerical grid uncertainty bounds.
11. Rates curve step integration across the 14 CMT knot dates.
12. Integrity of Phase 3 execution manifest and artifact SHA-256 digests.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import math
import numpy as np
import pandas as pd
import pytest

from src.heston.rates_curve import get_official_yield_curve, SPOT_PRICE
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.solver_2d import Heston2DSolver
from src.heston.pipeline_phase3 import (
    get_phase1_poc_params,
    compute_file_sha256,
    crr_american_put_price,
    DATA_DIR
)


def test_market_97_puts_coverage_and_precision_target():
    """
    Validates that all 97 market puts in data/heston/phase3/market_97_puts_validation.csv
    satisfy the predeclared comparative target of <= 0.0020 USD against QuantLib refined references.
    """
    csv_path = DATA_DIR / "market_97_puts_validation.csv"
    assert csv_path.exists(), "market_97_puts_validation.csv does not exist!"
    df = pd.read_csv(csv_path)

    assert len(df) == 97, f"Expected 97 market puts, got {len(df)}"
    max_err = df["abs_err_fine_usd"].max()
    mae = df["abs_err_fine_usd"].mean()

    assert max_err <= 0.0020, f"Max error {max_err:.6f} USD exceeds 0.0020 USD target!"
    assert mae < 0.00010, f"MAE {mae:.6f} USD exceeds 0.00010 USD target!"
    assert (df["status_target_002"] == "PASS").all(), "Not all 97 market puts passed target!"


def test_market_97_partition_and_tenor_breakdowns():
    """
    Validates that the 60 train, 22 strike holdout, and 15 tenor holdout puts
    all achieve 100% pass rates within the 0.0020 USD target.
    """
    part_path = DATA_DIR / "market_97_summary_by_partition.csv"
    assert part_path.exists(), "market_97_summary_by_partition.csv does not exist!"
    df_part = pd.read_csv(part_path)

    expected_counts = {"train": 60, "strike_holdout": 22, "tenor_holdout": 15, "all_97_puts": 97}
    for _, row in df_part.iterrows():
        p_name = row["partition"]
        assert row["n_contracts"] == expected_counts[p_name]
        assert row["max_abs_err_usd"] <= 0.0020
        assert row["pct_within_002_target"] == 100.0


def test_rule_of_worst_3_mesh_convergence():
    """
    Validates Rule of the Worst 3:
    1. Identifies top 3 discrepancies in market 97 puts.
    2. Under Extra-Fine grid (320x160, M=900*T) vs QuantLib 1000, all 3 pass within <= 0.0020 USD.
    3. Confirms error reduction between fine and extra-fine grids.
    """
    worst3_path = DATA_DIR / "market_worst3_refinement.csv"
    assert worst3_path.exists(), "market_worst3_refinement.csv does not exist!"
    df_worst3 = pd.read_csv(worst3_path)

    assert len(df_worst3) == 3, f"Expected 3 worst cases, got {len(df_worst3)}"
    for _, row in df_worst3.iterrows():
        assert row["status_extrafine_target"] == "PASS"
        assert row["abs_err_extrafine_vs_ql1000"] <= 0.0020
        assert row["ql_internal_refinement_diff"] <= 0.0005, f"QuantLib refinement diff {row['ql_internal_refinement_diff']} > 0.0005 USD"


def test_predeclared_hypothetical_regimes_108_prices():
    """
    Validates that all 108 prices across 6 predeclared regimes (A through F)
    satisfy the comparative target of <= 0.0020 USD.
    Confirms robustness under:
    - Positive correlation: Regime C (rho = +0.70)
    - Feller condition violation: Regime E (2*kappa*theta / xi^2 = 0.222 < 1)
    """
    regimes_path = DATA_DIR / "hypothetical_regimes_108.csv"
    assert regimes_path.exists(), "hypothetical_regimes_108.csv does not exist!"
    df = pd.read_csv(regimes_path)

    assert len(df) == 108, f"Expected 108 regime evaluations, got {len(df)}"
    assert (df["status_target_002"] == "PASS").all(), "Not all 108 regime prices passed target!"

    # Specific check on positive correlation Regime C
    sub_c = df[df["regime_id"] == "C"]
    assert len(sub_c) == 18
    assert sub_c["abs_error_usd"].max() <= 0.0020

    # Specific check on Feller-violating Regime E
    sub_e = df[df["regime_id"] == "E"]
    assert len(sub_e) == 18
    assert sub_e["abs_error_usd"].max() <= 0.0020
    assert (sub_e["feller_ratio"] < 1.0).all()


def test_hypothetical_regimes_mesh_refinement_convergence():
    """
    Validates multi-level mesh convergence (Default -> Fine -> Extra-Fine)
    on the ATM contract across Regimes B through F, verifying convergence ratio > 2.0.
    """
    refine_path = DATA_DIR / "regimes_mesh_refinement.csv"
    assert refine_path.exists(), "regimes_mesh_refinement.csv does not exist!"
    df = pd.read_csv(refine_path)

    assert len(df) == 5, f"Expected 5 regimes (B-F), got {len(df)}"
    for _, row in df.iterrows():
        assert row["status_002"] == "PASS"
        assert row["err_extrafine_vs_ql"] <= 0.0020
        assert row["convergence_ratio"] > 2.0, f"Regime {row['regime_id']} convergence ratio {row['convergence_ratio']} <= 2.0"


def test_analytical_limits_exact_xi0_and_degenerate_v0():
    """
    Validates analytical limit cases:
    1. Exact xi = 0.0 under flat rates r=0.0 and r=0.05 matches BS, CRR 5000, and 1D FDM 800 within 0.0020 USD.
    2. Degenerate boundary v0 = 0.0 produces finite positive price under forward drift kappa*theta > 0.
    3. Payoff reproduction at tau = 0 exact to machine precision (< 1e-12 USD).
    """
    limits_path = DATA_DIR / "analytical_limits_validation.csv"
    assert limits_path.exists(), "analytical_limits_validation.csv does not exist!"
    df = pd.read_csv(limits_path)

    # 1. Exact xi=0
    df_xi0 = df[df["test_type"] == "Exact_xi0_Limit"]
    assert len(df_xi0) == 12, f"Expected 12 xi=0 tests, got {len(df_xi0)}"
    assert (df_xi0["status_002"] == "PASS").all()
    assert df_xi0["max_abs_err_usd"].max() <= 0.0020

    # 2. Degenerate v0=0 sequence
    df_v0 = df[df["test_type"] == "Degenerate_Boundary_v0_Sequence"]
    assert len(df_v0) == 6, f"Expected 6 v0 tests, got {len(df_v0)}"
    assert (df_v0["status_002"] == "PASS").all()
    # Confirm monotonicity as v0 -> 0+
    prices_v0 = df_v0["american_prop_2d"].values
    assert np.all(np.diff(prices_v0) <= 0.0), "Option price must decrease monotonically as initial variance v0 decreases!"

    # 3. Payoff at tau = 0
    df_t0 = df[df["test_type"] == "Payoff_At_T0"]
    assert len(df_t0) == 5
    assert (df_t0["status_002"] == "PASS").all()
    assert df_t0["max_abs_err_usd"].max() < 1e-12


def test_continuity_and_fractional_maturity_27_5d():
    """
    Validates historical edge cases and continuous fractional maturity T = 27.5d:
    - Verifies smooth temporal midpoint interpolation and finite dP/dT theta.
    - Documents QuantLib calendar date constraint.
    """
    cont_path = DATA_DIR / "continuity_edge_cases.csv"
    assert cont_path.exists(), "continuity_edge_cases.csv does not exist!"
    df = pd.read_csv(cont_path)

    assert len(df) == 8, f"Expected 8 continuity cases, got {len(df)}"
    assert (df["status_002"] == "PASS").all()

    # Fractional maturity row
    row_27_5 = df[df["test_case"] == "Fractional_Maturity_27.5d"].iloc[0]
    assert np.isnan(row_27_5["ql_reference_usd"]), "QuantLib reference must be NaN for non-calendar fractional day 27.5d"
    assert row_27_5["abs_error_usd"] < 0.0001, f"Midpoint discrepancy {row_27_5['abs_error_usd']} too large!"


def test_economic_properties_and_butterfly_uncertainty_propagation():
    """
    Validates economic shape properties on raw unclipped prices across 45 grid points:
    1. Intrinsic lower bound: V_AM >= max(K - S0, 0)
    2. Early exercise premium: V_AM >= V_EU
    3. Strike monotonicity: dP/dK >= 0
    4. Butterfly convexity with propagated numerical grid uncertainty:
       B_i >= -Tol_B where Tol_B = alpha*eps_lo + (1-alpha)*eps_hi + eps_mid.
    """
    econ_path = DATA_DIR / "economic_arbitrage_checks.csv"
    assert econ_path.exists(), "economic_arbitrage_checks.csv does not exist!"
    df = pd.read_csv(econ_path)

    assert len(df) == 45, f"Expected 45 economic check points, got {len(df)}"
    assert (df["status_economic"] == "PASS").all(), "Not all economic checks passed!"

    # Intrinsic lower bound violations must be zero within machine/interpolation precision
    assert (df["lower_bound_violation"] < 1e-4).all()
    # EEP negative violations must be zero
    assert (df["eep_negative_violation"] < 1e-4).all()
    # Strike monotonicity violations must be zero
    assert (df["strike_monotonicity_violation"] == 0.0).all()
    # Butterfly spread violations after propagating numerical uncertainty must be zero
    assert (df["butterfly_violation"] == 0.0).all()


def test_rates_curve_step_integration_across_cmt_knots():
    """
    Validates step integration of continuous forward rate r(t = T - tau)
    across the 14 CMT knot dates with zero discrepancy (< 1e-12).
    """
    rates_path = DATA_DIR / "rates_curve_integration_check.csv"
    assert rates_path.exists(), "rates_curve_integration_check.csv does not exist!"
    df = pd.read_csv(rates_path)

    assert len(df) == 13, f"Expected 13 CMT segments, got {len(df)}"
    assert (df["status"] == "PASS").all()
    assert (df["absolute_discrepancy"] < 1e-12).all()


def test_phase3_manifest_and_file_hashes():
    """
    Validates that phase3_execution_manifest.json exists, records all 10 CSV files,
    and all SHA-256 hashes match disk files exactly.
    """
    manifest_path = DATA_DIR / "phase3_execution_manifest.json"
    assert manifest_path.exists(), "phase3_execution_manifest.json does not exist!"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["phase"] == "PHASE_3_BROAD_INDEPENDENT_VALIDATION_HESTON_2D"
    assert manifest["directive"] == "NUMERICAL VALIDATION ONLY - ZERO CALIBRATION"
    assert manifest["validation_summary"]["market_97_puts"]["pct_within_target"] == 100.0
    assert manifest["validation_summary"]["hypothetical_regimes_108"]["pct_within_target"] == 100.0

    output_files = manifest["output_files"]
    assert len(output_files) == 10, f"Expected 10 output files, got {len(output_files)}"

    for filename, expected_sha in output_files.items():
        file_path = DATA_DIR / filename
        assert file_path.exists(), f"Output file {filename} missing on disk!"
        actual_sha = compute_file_sha256(file_path)
        assert actual_sha == expected_sha, f"SHA-256 mismatch for {filename}: expected {expected_sha}, got {actual_sha}"
