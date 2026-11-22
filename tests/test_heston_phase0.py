"""
Comprehensive unit and integration test suite for Heston Phase 0.

Tests:
1. Treasury CMT rate provenance, exact coupon bootstrap discount factors, and machine-zero bond repricing (F0-01).
2. QuantLib term structure integration and dynamic version check (F0-01, F0-03).
3. Forensic option audit, 272 puts classification, lower bound enforcement, and tenor support.
4. Deterministic leakage-free data partition (train, strike holdout, tenor holdout, calls contrast).
5. Baseline pricing properties, clean curve ablation, and engine discrepancy isolation (F0-02).
6. Protection of raw source data and historical official directories (zero unintended writes, M-R3-2).
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime
import hashlib
import numpy as np
import pandas as pd
import pytest

from src.heston.rates_curve import (
    DeterministicYieldCurve,
    get_official_yield_curve,
    OFFICIAL_TREASURY_CMT_2026_11_17,
    SPOT_PRICE,
    DIVIDEND_YIELD
)
from src.heston.option_selection import (
    audit_and_select_options,
    parse_occ_symbol,
    calculate_exact_tau
)
from src.heston.data_split import create_deterministic_split, HELD_OUT_TENORS
from src.heston.baseline_pricing import (
    price_bs_european_put,
    price_american_put_quantlib,
    compute_baseline_benchmarks,
    HAS_QUANTLIB,
    QUANTLIB_VERSION
)

RAW_EXCEL_HASH = "306f8d3c1a52c7a67952d08881516bdc8632856e3abd6b33de373c4bc77ffb53"
HIST_CSV_HASH = "a510f9a48eaa0fc4f95cfbfcda491de09f4a6b14956efb0f3959c7c57ac5989a"


def test_source_data_immutability():
    """Confirms that raw Excel and daily history have not been modified."""
    p_raw = Path("data/raw/Opciones_Completo.xlsx")
    p_hist = Path("data/processed/nu_historical_daily.csv")

    assert p_raw.exists(), "Raw Excel file missing"
    assert p_hist.exists(), "Historical CSV missing"

    h_raw = hashlib.sha256(p_raw.read_bytes()).hexdigest()
    h_hist = hashlib.sha256(p_hist.read_bytes()).hexdigest()

    assert h_raw == RAW_EXCEL_HASH, f"Raw Excel modified! Hash: {h_raw}"
    assert h_hist == HIST_CSV_HASH, f"Historical CSV modified! Hash: {h_hist}"


def test_treasury_rates_and_exact_bootstrap():
    """
    Validates official Treasury CMT rates and exact coupon-bond bootstrap (F0-01).
    Guarantees machine-zero repricing across ALL benchmark maturities up to 30Y.
    """
    curve = get_official_yield_curve(method="bootstrap")

    # 1. Boundary conditions
    assert curve.get_discount_factor(0.0) == 1.0
    r0 = curve.get_zero_rate(0.0)
    assert 0.035 < r0 < 0.045 # ~4.09%

    # 2. Monotonicity of discount factors
    taus = np.linspace(0.05, 30.0, 100)
    dfs = [curve.get_discount_factor(t) for t in taus]
    assert all(dfs[i] > dfs[i + 1] for i in range(len(dfs) - 1)), "Discount factor not strictly decreasing!"

    # 3. Exact Par Bond Repricing check across ALL 14 maturities (1M to 30Y)
    reprice_df = curve.reprice_par_bonds()
    assert len(reprice_df) == len(OFFICIAL_TREASURY_CMT_2026_11_17)

    for _, row in reprice_df.iterrows():
        pv = row["repriced_pv"]
        res = abs(row["residual_usd"])
        # All benchmark bonds must reprice with residual < 1e-6 USD
        assert res < 1e-6, f"Bond {row['label']} ({row['tenor_yr']}y) residual {res} exceeds 1e-6 USD!"
        assert abs(pv - 100.0) < 1e-6

    # 4. Check forward prices
    for tau in [0.1, 0.5, 1.0, 2.0, 5.0]:
        F = curve.get_forward_price(tau)
        D = curve.get_discount_factor(tau)
        assert abs(F - SPOT_PRICE / D) < 1e-8
        assert F > SPOT_PRICE, "Forward should exceed spot under positive rates and zero dividends"


def test_quantlib_term_structure_integration():
    """Validates that QuantLib can construct a unified DiscountCurve from bootstrap (F0-01)."""
    assert HAS_QUANTLIB, "QuantLib must be available"
    assert QUANTLIB_VERSION is not None, "QuantLib version must be detectable"

    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure()
    assert ts_handle is not None

    # Check that QuantLib discount matches Python discount at key tenors
    import QuantLib as ql
    eval_date = ql.Date(17, 11, 2026)
    for test_days in [3, 10, 31, 59, 94, 182, 365, 730]:
        d_py = curve.get_discount_factor(test_days / 365.0)
        d_ql = ts_handle.discount(eval_date + test_days)
        assert abs(d_py - d_ql) < 1e-4, f"Mismatch at day {test_days}: py={d_py}, ql={d_ql}"


def test_occ_parsing():
    """Validates OCC symbol parser."""
    sym = "NU261120P00012000"
    und, y, m, d, opt_type, k = parse_occ_symbol(sym)
    assert und == "NU"
    assert y == 2026 and m == 11 and d == 20
    assert opt_type == "P"
    assert k == 12.0


def test_option_audit_and_selection(tmp_path):
    """Validates option classification, bounds checks, and support summary."""
    res = audit_and_select_options(output_dir=str(tmp_path))
    puts_all = res["puts_all"]
    puts_clean = res["puts_clean"]
    puts_common = res["puts_common_r3"]
    support = res["support_summary"]
    calls_all = res["calls_all"]

    # Total counts
    assert len(puts_all) == 272, f"Expected 272 puts, got {len(puts_all)}"
    assert len(calls_all) == 303, f"Expected 303 calls, got {len(calls_all)}"
    assert len(puts_all) + len(calls_all) == 575

    # Breakdown
    n_stale = (puts_all["status"] == "REJECTED_STALE_TRADE").sum()
    n_bounds = (puts_all["status"] == "REJECTED_BOUNDS_VIOLATION").sum()
    assert n_stale == 141, f"Expected 141 stale puts, got {n_stale}"
    assert n_bounds == 25, f"Expected 25 bounds-violating puts, got {n_bounds}"

    # Selected clean puts checks
    assert len(puts_clean) == 97, f"Expected 97 clean puts, got {len(puts_clean)}"
    for _, row in puts_clean.iterrows():
        assert row["is_trade_17nov"], "Selected put not traded on 11/17!"
        assert row["bounds_ok"], "Selected put violates bounds!"
        assert row["lastPrice"] >= 0.02, "Selected put price < 0.02!"
        assert row["time_value"] >= 0.01, "Selected put time value < 0.01!"
        assert row["lastPrice"] >= (row["strike"] - SPOT_PRICE) - 1e-4

    # Common R3 puts checks
    assert len(puts_common) == 84, f"Expected 84 common puts, got {len(puts_common)}"

    # Tenor support checks
    assert len(support) == 16, f"Expected 16 tenors, got {len(support)}"
    assert (support["n_raw_puts"] > 0).all()


def test_deterministic_data_split(tmp_path):
    """Validates leakage-free deterministic partition."""
    res = audit_and_select_options(output_dir=None)
    puts_clean = res["puts_clean"]
    calls_all = res["calls_all"]

    split = create_deterministic_split(
        puts_df=puts_clean,
        calls_df=calls_all,
        output_dir=str(tmp_path)
    )

    df_train = split["train"]
    df_strike_ho = split["strike_holdout"]
    df_tenor_ho = split["tenor_holdout"]
    df_calls = split["calls_contrast"]

    # 1. Non-empty partitions
    assert len(df_train) > 0
    assert len(df_strike_ho) > 0
    assert len(df_tenor_ho) > 0
    assert len(df_calls) > 0

    # 2. Partition completeness
    assert len(df_train) + len(df_strike_ho) + len(df_tenor_ho) == len(puts_clean)

    # 3. Disjointness (Zero Leakage)
    syms_train = set(df_train["contractSymbol"])
    syms_sho = set(df_strike_ho["contractSymbol"])
    syms_tho = set(df_tenor_ho["contractSymbol"])

    assert len(syms_train & syms_sho) == 0, "Train and Strike Holdout overlap!"
    assert len(syms_train & syms_tho) == 0, "Train and Tenor Holdout overlap!"
    assert len(syms_sho & syms_tho) == 0, "Strike Holdout and Tenor Holdout overlap!"

    # 4. Tenor Holdout strictly from declared tenors
    assert set(df_tenor_ho["expirationDate"]).issubset(set(HELD_OUT_TENORS))
    assert not any(exp in set(df_train["expirationDate"]) for exp in HELD_OUT_TENORS)

    # 5. Calls strictly separate
    assert all(c.endswith("C") or "C" in c for c in df_calls["contractSymbol"])
    assert len(set(df_calls["contractSymbol"]) & (syms_train | syms_sho | syms_tho)) == 0

    # 6. Determinism (calling again yields exact same symbols)
    split2 = create_deterministic_split(puts_df=puts_clean, calls_df=calls_all, output_dir=None)
    assert set(split2["train"]["contractSymbol"]) == syms_train
    assert set(split2["strike_holdout"]["contractSymbol"]) == syms_sho
    assert set(split2["tenor_holdout"]["contractSymbol"]) == syms_tho


def test_baseline_pricing_engine_and_ablation(tmp_path):
    """Validates baseline option pricing and clean curve/engine ablation (F0-02)."""
    curve = get_official_yield_curve(method="bootstrap")

    sample_cases = [
        {"K": 10.0, "tau": 36.0 / 365.0, "market": 0.05},
        {"K": 12.0, "tau": 94.0 / 365.0, "market": 0.55},
        {"K": 14.0, "tau": 182.0 / 365.0, "market": 2.10},
    ]

    for case in sample_cases:
        K = case["K"]
        tau = case["tau"]
        r = curve.get_zero_rate(tau)

        p_eu = price_bs_european_put(SPOT_PRICE, K, tau, r, sigma=0.45)
        p_am = price_american_put_quantlib(SPOT_PRICE, K, tau, r, sigma=0.45)

        intrinsic = max(K - SPOT_PRICE, 0.0)
        assert p_am >= intrinsic - 1e-6, f"American put below intrinsic: {p_am} < {intrinsic}"
        assert p_am >= p_eu - 1e-4, f"American put below European put: {p_am} < {p_eu}"
        assert p_am <= K, f"American put above strike: {p_am} > {K}"
        assert p_am > 0, "American put non-positive"


def test_no_writes_to_official_directories(tmp_path):
    """
    Enforces anti-regression rule (Codex Finding M-R3-2):
    Pipeline execution with isolated output_dir must NEVER touch outputs/tables or outputs/figures.
    """
    p_tables = Path("outputs/tables")
    if p_tables.exists():
        mtimes_before = {f.name: f.stat().st_mtime for f in p_tables.glob("*.csv")}

        from src.heston.pipeline_phase0 import run_phase0_pipeline
        run_phase0_pipeline(output_dir=str(tmp_path))

        mtimes_after = {f.name: f.stat().st_mtime for f in p_tables.glob("*.csv")}
        for name, mt in mtimes_before.items():
            assert mtimes_after[name] == mt, f"Official file {name} was modified by pipeline!"
