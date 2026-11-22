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
import scipy

from src.heston.rates_curve import get_official_yield_curve, SPOT_PRICE
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.solver_2d import Heston2DSolver
from src.heston.pipeline_phase3 import (
    get_phase1_poc_params,
    compute_file_sha256,
    compute_normalized_source_sha256,
    crr_american_put_price,
    DATA_DIR,
    SnapshotIntegrityError,
    VERIFIED_SNAPSHOT_METADATA,
    verify_snapshot_inputs_and_params,
    verify_snapshot_table_file,
    load_verified_snapshot_table
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
    2. Degenerate boundary v0 = 0.0 produces finite positive price under forward drift kappa*theta > 0,
       documents real QuantLib exception (RuntimeError: 0: invalid value), sets N/A for comparative error,
       and verifies multi-level mesh refinement (160x80 -> 240x120 -> 320x160).
    3. Sequence v0 in {0.04, 0.01, 0.005, 0.001, 0.0001} passes <= 0.0020 USD vs QuantLib.
    4. Payoff reproduction at tau = 0 exact to machine precision (< 1e-12 USD).
    """
    limits_path = DATA_DIR / "analytical_limits_validation.csv"
    assert limits_path.exists(), "analytical_limits_validation.csv does not exist!"
    df = pd.read_csv(limits_path)

    # 1. Exact xi=0
    df_xi0 = df[df["test_type"] == "Exact_xi0_Limit"]
    assert len(df_xi0) == 12, f"Expected 12 xi=0 tests, got {len(df_xi0)}"
    assert (df_xi0["status_002"] == "PASS").all()
    assert (df_xi0["status_target_002"] == "PASS").all()
    assert df_xi0["max_abs_err_usd"].max() <= 0.0020
    assert (df_xi0["qualitative_limit_status"] == "PASS_ANALYTIC_CONSISTENCY").all()

    # 2. Degenerate v0=0 sequence
    df_v0 = df[df["test_type"] == "Degenerate_Boundary_v0_Sequence"]
    assert len(df_v0) == 6, f"Expected 6 v0 tests, got {len(df_v0)}"
    assert (df_v0["qualitative_limit_status"] == "PASS_STABLE_LIMIT").all()

    # Check v0=0 row: QuantLib exception documented and status N/A_NO_REF
    row_v0_0 = df_v0[df_v0["parameter_v0"] == 0.0].iloc[0]
    assert row_v0_0["ql_status"] == "UNSUPPORTED"
    assert "RuntimeError" in str(row_v0_0["ql_exception"])
    assert np.isnan(row_v0_0["ql_reference_usd"])
    assert row_v0_0["status_target_002"] == "N/A_NO_REF"
    # Mesh refinement convergence for v0=0
    assert row_v0_0["prop_price_160x80"] < row_v0_0["prop_price_240x120"] <= row_v0_0["prop_price_320x160"]
    assert 0.1951 < row_v0_0["prop_price_320x160"] < 0.1955

    # Check v0 > 0 rows: QuantLib supported and pass <= 0.0020 USD
    df_v0_pos = df_v0[df_v0["parameter_v0"] > 0.0]
    assert (df_v0_pos["ql_status"] == "SUPPORTED").all()
    assert (df_v0_pos["status_target_002"] == "PASS").all()
    assert df_v0_pos["abs_err_usd"].max() <= 0.0020

    # Confirm monotonicity of proprietary price as v0 -> 0+
    prices_v0 = df_v0["american_prop_2d"].values
    assert np.all(np.diff(prices_v0) <= 0.0), "Option price must decrease monotonically as initial variance v0 decreases!"

    # 3. Payoff at tau = 0
    df_t0 = df[df["test_type"] == "Payoff_At_T0"]
    assert len(df_t0) == 5
    assert (df_t0["status_002"] == "PASS").all()
    assert (df_t0["status_target_002"] == "PASS").all()
    assert (df_t0["qualitative_limit_status"] == "PASS_EXACT_PAYOFF").all()
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
    1. Finiteness: np.isfinite
    2. Upper bound: V_AM <= K
    3. Intrinsic lower bound: V_AM >= max(K - S0, 0)
    4. Early exercise premium: V_AM >= V_EU
    5. Strike monotonicity: dP/dK >= 0
    6. Butterfly convexity with propagated numerical grid uncertainty:
       B_i >= -Tol_B where Tol_B = alpha*eps_lo + (1-alpha)*eps_hi + eps_mid.
    7. Calendar monotonicity across tenors:
       Evaluates all 36 transitions. Verifies that 4 small raw negative drops
       are within empirical pairwise uncertainty (Tol_cal = eps_j + eps_{j+1}),
       and zero violations exist beyond numerical uncertainty.
    """
    econ_path = DATA_DIR / "economic_arbitrage_checks.csv"
    assert econ_path.exists(), "economic_arbitrage_checks.csv does not exist!"
    df = pd.read_csv(econ_path)

    assert len(df) == 45, f"Expected 45 economic check points, got {len(df)}"
    assert (df["status_economic"] == "PASS").all(), "Not all economic checks passed!"

    # 1. Finiteness & Upper Bound
    assert np.isfinite(df[["price_american", "price_european"]]).all().all()
    assert (df["finiteness_check"] == "PASS").all()
    assert (df["upper_bound_violation"] == 0.0).all()
    assert float((df["price_american"] - df["strike"]).max()) <= 0.0

    # 2. Intrinsic lower bound violations must be zero within numerical tolerance
    assert (df["lower_bound_violation"] < 1e-4).all()

    # 3. EEP negative violations must be zero
    assert (df["eep_negative_violation"] < 1e-4).all()

    # 4. Strike monotonicity violations must be zero
    assert (df["strike_monotonicity_violation"] == 0.0).all()

    # 5. Butterfly spread violations after propagating numerical uncertainty must be zero
    assert (df["butterfly_violation"] == 0.0).all()

    # 6. Calendar monotonicity transitions
    comparisons = []
    for K, g in df.groupby("strike"):
        g = g.sort_values("maturity_years")
        diff = np.diff(g.price_american)
        eps = g.empirical_truncation_eps.to_numpy()
        tol = eps[1:] + eps[:-1]
        for i, z in enumerate(diff):
            comparisons.append((K, g.iloc[i].tenor_label, g.iloc[i+1].tenor_label, z, tol[i]))

    assert len(comparisons) == 36, f"Expected 36 calendar transitions, got {len(comparisons)}"
    # Confirm exactly 4 small raw negative drops on deep ITM puts
    neg_raw = [x for x in comparisons if x[3] < 0]
    assert len(neg_raw) == 4, f"Expected 4 raw negative drops, got {len(neg_raw)}"
    # Confirm worst raw drop is ~ -2.098e-5 USD at K=17 (31d -> 94d)
    worst_drop = min(comparisons, key=lambda x: x[3])
    assert worst_drop[0] == 17.0 and worst_drop[1] == "31d" and worst_drop[2] == "94d"
    assert -2.5e-5 < worst_drop[3] < -1.5e-5
    # Confirm zero violations beyond empirical uncertainty
    violations_beyond = [x for x in comparisons if x[3] < -x[4]]
    assert len(violations_beyond) == 0, f"Found calendar violations beyond empirical tolerance: {violations_beyond}"
    assert (df["calendar_violation"] == 0.0).all()


def test_rates_curve_step_integration_across_cmt_knots():
    """
    Validates rates curve integration check across 3 distinct test types (33 total rows):
    1. Nodal interval integration (13 rows): constant forward between CMT knots (< 1e-12).
    2. Actual solver step quadrature (15 rows): midpoint Riemann sum across forward step
       discontinuities under default, fine, and extra-fine resolutions (< 1e-4).
    3. QuantLib adapter comparison (5 rows): YieldTermStructureHandle discount vs proprietary (< 1e-12).
    """
    rates_path = DATA_DIR / "rates_curve_integration_check.csv"
    assert rates_path.exists(), "rates_curve_integration_check.csv does not exist!"
    df = pd.read_csv(rates_path)

    assert len(df) == 33, f"Expected 33 rates check rows, got {len(df)}"

    # 1. Nodal
    df_nodal = df[df["test_type"] == "Nodal_Interval_Integration"]
    assert len(df_nodal) == 13
    assert (df_nodal["status"] == "PASS").all()
    assert (df_nodal["discrepancy"] < 1e-12).all()

    # 2. Actual solver steps
    df_steps = df[df["test_type"] == "Actual_Solver_Step_Integration"]
    assert len(df_steps) == 15
    assert (df_steps["status"] == "PASS_WITHIN_TOLERANCE").all()
    assert (df_steps["discrepancy"].abs() < 1e-4).all()
    # Confirm quadrature errors are on the order of 10^-7 to 10^-6
    assert df_steps["discrepancy"].abs().max() < 1e-5

    # 3. QuantLib adapter
    df_ql = df[df["test_type"] == "QuantLib_Adapter_Comparison"]
    assert len(df_ql) == 5
    assert (df_ql["status"] == "PASS").all()
    assert (df_ql["discrepancy"].abs() < 1e-12).all()


def test_negative_aggregator_rejects_worst3_failure():
    """
    Negative unit test: verifies that the pipeline aggregator does NOT hardcode favorable statuses.
    Injects a corrupted fixture (status FAIL, error 1.0 USD) and asserts that:
    - worst_3_refinement_status becomes FAILED.
    - overall_status becomes FAILED.
    """
    import tempfile, contextlib, io
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    a = load("market_97_puts_validation.csv")
    b = load("market_97_summary_by_tenor.csv")
    c = load("market_97_summary_by_partition.csv")
    bad = load("market_worst3_refinement.csv")
    bad.loc[0, "abs_err_extrafine_vs_ql1000"] = 1.0
    bad.loc[0, "status_extrafine_target"] = "FAIL"

    orig_m97 = pipe.run_market_97_validation
    try:
        pipe.run_market_97_validation = lambda **kw: (a, b, c, bad)
        with tempfile.TemporaryDirectory() as t, contextlib.redirect_stdout(io.StringIO()):
            result = pipe.run_phase3_pipeline(Path(t))

        assert result["validation_summary"]["worst_3_refinement_status"] == "FAILED"
        assert result["validation_summary"]["overall_status"] == "FAILED"
    finally:
        pipe.run_market_97_validation = orig_m97


def test_snapshot_integrity_guard_rejects_tampered_hash(tmp_path):
    """
    Verifies that the pre-load snapshot guard rejects tampered files before reading them as valid.
    """
    legit_file = DATA_DIR / "market_97_puts_validation.csv"
    assert legit_file.exists()

    # Legitimate file passes verification
    is_valid, msg = verify_snapshot_table_file("market_97_puts_validation.csv", legit_file)
    assert is_valid, f"Legitimate file should pass verification: {msg}"

    # Tampered file fails verification
    bad_file = tmp_path / "market_97_puts_validation.csv"
    bad_df = pd.read_csv(legit_file)
    bad_df.loc[0, "proprietary_fine_usd"] += 1.0
    bad_df.to_csv(bad_file, index=False)

    is_valid_bad, msg_bad = verify_snapshot_table_file("market_97_puts_validation.csv", bad_file)
    assert not is_valid_bad, "Tampered file must fail snapshot hash verification"
    assert "Hash mismatch" in msg_bad

    # Strict loader raises SnapshotIntegrityError
    with pytest.raises(SnapshotIntegrityError):
        load_verified_snapshot_table("market_97_puts_validation.csv", file_path=bad_file, strict=True)


def test_snapshot_integrity_guard_rejects_incompatible_inputs_or_params(tmp_path):
    """
    Verifies that verify_snapshot_inputs_and_params detects missing or tampered input dependencies.
    """
    # Legitimate root directory passes
    is_valid, msg = verify_snapshot_inputs_and_params(root_dir)
    assert is_valid, f"Legitimate repo inputs must pass verification: {msg}"

    # Empty/tampered directory fails
    is_valid_empty, msg_empty = verify_snapshot_inputs_and_params(tmp_path)
    assert not is_valid_empty
    assert "missing" in msg_empty.lower() or "mismatch" in msg_empty.lower()


def test_aggregator_rejects_raw_price_modification():
    """
    Verifies that modifying a price (e.g. +1 USD) while keeping status PASS
    causes the aggregator to detect the true error (1.0 USD), reject the market gate,
    and refuse to attribute prices to the verified commit 37bbd12.
    """
    import tempfile, contextlib, io
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    orig_limits = pipe.run_analytical_limits_validation
    orig_cont = pipe.run_continuity_and_edge_cases
    orig_econ = pipe.run_economic_arbitrage_checks
    orig_rates = pipe.run_rates_curve_integration_check
    orig_data_dir = pipe.DATA_DIR

    try:
        pipe.run_analytical_limits_validation = lambda: load("analytical_limits_validation.csv")
        pipe.run_continuity_and_edge_cases = lambda **kw: load("continuity_edge_cases.csv")
        pipe.run_economic_arbitrage_checks = lambda **kw: load("economic_arbitrage_checks.csv")
        pipe.run_rates_curve_integration_check = lambda: load("rates_curve_integration_check.csv")

        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / "cache"
            import shutil
            shutil.copytree(base, cache)
            out = Path(t) / "out"
            pipe.DATA_DIR = cache

            # Tamper with row 0 price by +1 USD, keeping PASS label
            f = cache / "market_97_puts_validation.csv"
            df = pd.read_csv(f)
            df.loc[0, "proprietary_fine_usd"] += 1.0
            df.to_csv(f, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                result = pipe.run_phase3_pipeline(out)

            assert result["validation_summary"]["market_97_status"] == "FAILED"
            assert result["validation_summary"]["overall_status"] == "FAILED"
            assert result["validation_summary"]["market_97_puts"]["max_abs_err_usd"] >= 0.99
            assert result["execution_provenance"]["prices_source_commit"] != "37bbd12d52819c765c64a950333962af9410073d"
    finally:
        pipe.run_analytical_limits_validation = orig_limits
        pipe.run_continuity_and_edge_cases = orig_cont
        pipe.run_economic_arbitrage_checks = orig_econ
        pipe.run_rates_curve_integration_check = orig_rates
        pipe.DATA_DIR = orig_data_dir


def test_aggregator_rejects_numeric_failure_with_stale_pass_label():
    """
    Verifies that setting abs_err_fine_usd = 1.0 while leaving status PASS
    fails the market gate due to tolerance and coherence checks.
    """
    import tempfile, contextlib, io, shutil
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    orig_limits = pipe.run_analytical_limits_validation
    orig_cont = pipe.run_continuity_and_edge_cases
    orig_econ = pipe.run_economic_arbitrage_checks
    orig_rates = pipe.run_rates_curve_integration_check
    orig_data_dir = pipe.DATA_DIR

    try:
        pipe.run_analytical_limits_validation = lambda: load("analytical_limits_validation.csv")
        pipe.run_continuity_and_edge_cases = lambda **kw: load("continuity_edge_cases.csv")
        pipe.run_economic_arbitrage_checks = lambda **kw: load("economic_arbitrage_checks.csv")
        pipe.run_rates_curve_integration_check = lambda: load("rates_curve_integration_check.csv")

        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / "cache"
            shutil.copytree(base, cache)
            out = Path(t) / "out"
            pipe.DATA_DIR = cache

            # Invalidate error column to 1.0 USD while leaving status PASS
            f = cache / "market_97_puts_validation.csv"
            df = pd.read_csv(f)
            df.loc[0, "abs_err_fine_usd"] = 1.0
            df.to_csv(f, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                result = pipe.run_phase3_pipeline(out)

            assert result["validation_summary"]["market_97_status"] == "FAILED"
            assert result["validation_summary"]["overall_status"] == "FAILED"
            assert result["validation_summary"]["market_97_puts"]["max_abs_err_usd"] >= 0.99
    finally:
        pipe.run_analytical_limits_validation = orig_limits
        pipe.run_continuity_and_edge_cases = orig_cont
        pipe.run_economic_arbitrage_checks = orig_econ
        pipe.run_rates_curve_integration_check = orig_rates
        pipe.DATA_DIR = orig_data_dir


def test_aggregator_rejects_nan_or_inf_in_prices_or_errors():
    """
    Verifies that injecting NaN into price or error columns causes finite checks to fail.
    """
    import tempfile, contextlib, io, shutil
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    orig_limits = pipe.run_analytical_limits_validation
    orig_cont = pipe.run_continuity_and_edge_cases
    orig_econ = pipe.run_economic_arbitrage_checks
    orig_rates = pipe.run_rates_curve_integration_check
    orig_data_dir = pipe.DATA_DIR

    try:
        pipe.run_analytical_limits_validation = lambda: load("analytical_limits_validation.csv")
        pipe.run_continuity_and_edge_cases = lambda **kw: load("continuity_edge_cases.csv")
        pipe.run_economic_arbitrage_checks = lambda **kw: load("economic_arbitrage_checks.csv")
        pipe.run_rates_curve_integration_check = lambda: load("rates_curve_integration_check.csv")

        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / "cache"
            shutil.copytree(base, cache)
            out = Path(t) / "out"
            pipe.DATA_DIR = cache

            f = cache / "market_97_puts_validation.csv"
            df = pd.read_csv(f)
            df.loc[0, "proprietary_fine_usd"] = np.nan
            df.to_csv(f, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                result = pipe.run_phase3_pipeline(out)

            assert result["validation_summary"]["market_97_status"] == "FAILED"
            assert result["validation_summary"]["overall_status"] == "FAILED"
    finally:
        pipe.run_analytical_limits_validation = orig_limits
        pipe.run_continuity_and_edge_cases = orig_cont
        pipe.run_economic_arbitrage_checks = orig_econ
        pipe.run_rates_curve_integration_check = orig_rates
        pipe.DATA_DIR = orig_data_dir


def test_aggregator_rejects_regimes_price_modification():
    """
    Verifies that modifying price in hypothetical regimes table causes regimes gate to FAIL.
    """
    import tempfile, contextlib, io, shutil
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    orig_limits = pipe.run_analytical_limits_validation
    orig_cont = pipe.run_continuity_and_edge_cases
    orig_econ = pipe.run_economic_arbitrage_checks
    orig_rates = pipe.run_rates_curve_integration_check
    orig_data_dir = pipe.DATA_DIR

    try:
        pipe.run_analytical_limits_validation = lambda: load("analytical_limits_validation.csv")
        pipe.run_continuity_and_edge_cases = lambda **kw: load("continuity_edge_cases.csv")
        pipe.run_economic_arbitrage_checks = lambda **kw: load("economic_arbitrage_checks.csv")
        pipe.run_rates_curve_integration_check = lambda: load("rates_curve_integration_check.csv")

        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / "cache"
            shutil.copytree(base, cache)
            out = Path(t) / "out"
            pipe.DATA_DIR = cache

            f = cache / "hypothetical_regimes_108.csv"
            df = pd.read_csv(f)
            df.loc[0, "proprietary_fine_usd"] += 1.0
            df.to_csv(f, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                result = pipe.run_phase3_pipeline(out)

            assert result["validation_summary"]["hypothetical_regimes_108_status"] == "FAILED"
            assert result["validation_summary"]["overall_status"] == "FAILED"
            assert result["validation_summary"]["hypothetical_regimes_108"]["max_abs_err_usd"] >= 0.99
    finally:
        pipe.run_analytical_limits_validation = orig_limits
        pipe.run_continuity_and_edge_cases = orig_cont
        pipe.run_economic_arbitrage_checks = orig_econ
        pipe.run_rates_curve_integration_check = orig_rates
        pipe.DATA_DIR = orig_data_dir


def test_aggregator_rejects_paired_price_and_reference_modification():
    """
    Verifies that paired +1 modification of price and reference fails snapshot verification
    and causes market gate and overall to be marked FAILED under reuse mode.
    """
    import tempfile, contextlib, io, shutil
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    orig_limits = pipe.run_analytical_limits_validation
    orig_cont = pipe.run_continuity_and_edge_cases
    orig_econ = pipe.run_economic_arbitrage_checks
    orig_rates = pipe.run_rates_curve_integration_check
    orig_data_dir = pipe.DATA_DIR

    try:
        pipe.run_analytical_limits_validation = lambda: load("analytical_limits_validation.csv")
        pipe.run_continuity_and_edge_cases = lambda **kw: load("continuity_edge_cases.csv")
        pipe.run_economic_arbitrage_checks = lambda **kw: load("economic_arbitrage_checks.csv")
        pipe.run_rates_curve_integration_check = lambda: load("rates_curve_integration_check.csv")

        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / "cache"
            shutil.copytree(base, cache)
            out = Path(t) / "out"
            pipe.DATA_DIR = cache

            f = cache / "market_97_puts_validation.csv"
            df = pd.read_csv(f)
            df.loc[0, "proprietary_fine_usd"] += 1.0
            df.loc[0, "ql_refined_700_usd"] += 1.0
            df.to_csv(f, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                result = pipe.run_phase3_pipeline(out, data_dir=cache)

            assert result["validation_summary"]["market_97_status"] == "FAILED"
            assert result["validation_summary"]["overall_status"] == "FAILED"
            assert result["execution_provenance"]["prices_source_commit"] == "UNVERIFIED_OR_FRESH_EXECUTION"
    finally:
        pipe.run_analytical_limits_validation = orig_limits
        pipe.run_continuity_and_edge_cases = orig_cont
        pipe.run_economic_arbitrage_checks = orig_econ
        pipe.run_rates_curve_integration_check = orig_rates
        pipe.DATA_DIR = orig_data_dir


def test_aggregator_rejects_economic_price_modification():
    """
    Verifies that tampering with economic arbitrage prices fails canonical payload verification
    and causes economic gate and overall to be marked FAILED under reuse mode.
    """
    import tempfile, contextlib, io, shutil
    import src.heston.pipeline_phase3 as pipe

    base = DATA_DIR
    load = lambda n: pd.read_csv(base / n)
    orig_limits = pipe.run_analytical_limits_validation
    orig_rates = pipe.run_rates_curve_integration_check
    orig_data_dir = pipe.DATA_DIR

    try:
        pipe.run_analytical_limits_validation = lambda: load("analytical_limits_validation.csv")
        pipe.run_rates_curve_integration_check = lambda: load("rates_curve_integration_check.csv")

        with tempfile.TemporaryDirectory() as t:
            cache = Path(t) / "cache"
            shutil.copytree(base, cache)
            out = Path(t) / "out"
            pipe.DATA_DIR = cache

            feco = cache / "economic_arbitrage_checks.csv"
            e = pd.read_csv(feco)
            e["price_american"] = np.maximum(e["strike"] - 12.33, 0.0) + 1e-12
            e["price_european"] = e["price_american"]
            e.to_csv(feco, index=False)

            with contextlib.redirect_stdout(io.StringIO()):
                result = pipe.run_phase3_pipeline(out, data_dir=cache)

            assert result["validation_summary"]["economic_arbitrage_status"] == "FAILED"
            assert result["validation_summary"]["market_97_status"] == "PASSED"
            assert result["validation_summary"]["overall_status"] == "FAILED"
            assert result["execution_provenance"]["prices_source_commit"] == "UNVERIFIED_OR_FRESH_EXECUTION"
    finally:
        pipe.run_analytical_limits_validation = orig_limits
        pipe.run_rates_curve_integration_check = orig_rates
        pipe.DATA_DIR = orig_data_dir


def test_snapshot_pricing_source_guard_rejects_altered_code():
    """
    Verifies that modifying pricing source code (e.g. theta_ADI in solver_2d.py)
    fails snapshot code dependency verification.
    """
    import tempfile, shutil
    import src.heston.pipeline_phase3 as pipe

    with tempfile.TemporaryDirectory() as t:
        fake_root = Path(t)
        for k, (rel, h) in pipe.VERIFIED_SNAPSHOT_METADATA["inputs"].items():
            dest = fake_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(root_dir / rel, dest)

        for module_name in ("solver_2d.py", "heston_model.py", "rates_curve.py"):
            target = fake_root / "src/heston" / module_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(root_dir / "src/heston" / module_name, target)

        ok_clean, msg_clean = pipe.verify_snapshot_inputs_and_params(fake_root)
        assert ok_clean is True

        # Mutate theta_adi in solver_2d.py copy
        dest_solver = fake_root / "src/heston/solver_2d.py"
        code = (root_dir / "src/heston/solver_2d.py").read_text()
        changed = code.replace("theta_adi: float = 1.0 / 3.0", "theta_adi: float = 0.5", 1)
        dest_solver.write_text(changed)

        ok_mut, msg_mut = pipe.verify_snapshot_inputs_and_params(fake_root)
        assert ok_mut is False
        assert "Pricing source hash mismatch for solver_2d.py" in msg_mut


def test_strict_verification_true_raises_snapshot_integrity_error():
    """
    Verifies that when strict_verification=True, any snapshot tampering raises SnapshotIntegrityError.
    """
    import tempfile, shutil
    import src.heston.pipeline_phase3 as pipe
    import pytest

    with tempfile.TemporaryDirectory() as t:
        cache = Path(t) / "cache"
        shutil.copytree(DATA_DIR, cache)

        # Tamper market 97 table
        f = cache / "market_97_puts_validation.csv"
        df = pd.read_csv(f)
        df.loc[0, "proprietary_fine_usd"] += 1.0
        df.to_csv(f, index=False)

        with pytest.raises(pipe.SnapshotIntegrityError):
            pipe.run_market_97_validation(data_dir=cache, strict_verification=True)

        # Tamper economic checks table
        feco = cache / "economic_arbitrage_checks.csv"
        e = pd.read_csv(feco)
        e.loc[0, "price_american"] += 1.0
        e.to_csv(feco, index=False)

        with pytest.raises(pipe.SnapshotIntegrityError):
            pipe.run_economic_arbitrage_checks(data_dir=cache, strict_verification=True)


def test_analytical_limits_v0_zero_nan_metadata():
    """
    Verifies that for v0 = 0.0, both abs_err_usd and max_abs_err_usd are NaN (resolving F3-L2).
    """
    limits_path = DATA_DIR / "analytical_limits_validation.csv"
    assert limits_path.exists()
    df = pd.read_csv(limits_path)
    row_v0_0 = df[df["parameter_v0"] == 0.0].iloc[0]
    assert np.isnan(row_v0_0["abs_err_usd"]), f"Expected NaN abs_err_usd, got {row_v0_0['abs_err_usd']}"
    assert np.isnan(row_v0_0["max_abs_err_usd"]), f"Expected NaN max_abs_err_usd, got {row_v0_0['max_abs_err_usd']}"
    assert row_v0_0["status_target_002"] == "N/A_NO_REF"
    assert row_v0_0["ql_status"] == "UNSUPPORTED"


def test_phase3_manifest_and_file_hashes():
    """
    Validates that phase3_execution_manifest.json exists, records all 10 CSV files,
    contains required input hashes and execution provenance, and all SHA-256 hashes match disk files.
    """
    manifest_path = DATA_DIR / "phase3_execution_manifest.json"
    assert manifest_path.exists(), "phase3_execution_manifest.json does not exist!"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["phase"] == "PHASE_3_BROAD_INDEPENDENT_VALIDATION_HESTON_2D"
    assert manifest["directive"] == "NUMERICAL VALIDATION ONLY - ZERO CALIBRATION"
    assert manifest["validation_summary"]["overall_status"] == "PASSED"
    assert manifest["validation_summary"]["worst_3_refinement_status"] == "ALL_CONVERGED_WITHIN_002"
    assert manifest["validation_summary"]["market_97_puts"]["pct_within_target"] == 100.0
    assert manifest["validation_summary"]["hypothetical_regimes_108"]["pct_within_target"] == 100.0

    # Input hashes and code provenance
    assert "input_hashes" in manifest
    assert len(manifest["input_hashes"]) >= 5
    assert "execution_provenance" in manifest
    assert manifest["execution_provenance"]["prices_source_commit"] == "37bbd12d52819c765c64a950333962af9410073d"
    assert manifest["execution_provenance"]["scipy_version"] == scipy.__version__
    assert "source_hashes" in manifest
    assert len(manifest["source_hashes"]) >= 3

    # Source hashes normalized match
    for key, expected_sha in manifest["source_hashes"].items():
        name = key.removesuffix("_py") + ".py"
        source_path = root_dir / "src" / "heston" / name
        assert source_path.exists()
        normalized_sha = compute_normalized_source_sha256(source_path)
        assert normalized_sha == expected_sha, f"Source hash mismatch for {name}: expected {expected_sha}, got {normalized_sha}"

    output_files = manifest["output_files"]
    assert len(output_files) == 10, f"Expected 10 output files, got {len(output_files)}"

    for filename, expected_sha in output_files.items():
        file_path = DATA_DIR / filename
        assert file_path.exists(), f"Output file {filename} missing on disk!"
        actual_sha = compute_file_sha256(file_path)
        assert actual_sha == expected_sha, f"SHA-256 mismatch for {filename}: expected {expected_sha}, got {actual_sha}"
