"""
Unit tests for OCC contract symbol parsing, maturity calculation,
no-arbitrage bounds, and audit dataset integrity.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime
import pytest
import pandas as pd
import numpy as np

from src.data_cleaning import parse_occ_symbol, calculate_exact_tau
from src.market_data import (
    SPOT_PRICE,
    VALUATION_DATETIME,
    NY_TZ,
    get_zero_rate,
    get_discount_factor
)

def test_parse_occ_symbol_valid():
    und, y, m, d, o_type, k = parse_occ_symbol("NU261120C00001000")
    assert und == "NU"
    assert y == 2026
    assert m == 11
    assert d == 20
    assert o_type == "C"
    assert abs(k - 1.0) < 1e-6

    und, y, m, d, o_type, k = parse_occ_symbol("NU280121P00035000")
    assert und == "NU"
    assert y == 2028
    assert m == 1
    assert d == 21
    assert o_type == "P"
    assert abs(k - 35.0) < 1e-6

def test_parse_occ_symbol_invalid():
    with pytest.raises(ValueError):
        parse_occ_symbol("INVALID_OCC")
    with pytest.raises(ValueError):
        parse_occ_symbol("NU261120X00001000") # X is not C or P

def test_exact_tau_calculation():
    # 2026-11-20 should be exactly 3.0 days = 3.0 / 365.0
    exp_dt = datetime(2026, 11, 20)
    tau = calculate_exact_tau(exp_dt, VALUATION_DATETIME)
    expected = 3.0 / 365.0
    assert abs(tau - expected) < 1e-6

    # 2026-11-27 should be exactly 10.0 days
    exp_dt2 = datetime(2026, 11, 27)
    tau2 = calculate_exact_tau(exp_dt2, VALUATION_DATETIME)
    assert abs(tau2 - 10.0 / 365.0) < 1e-6

    # Monotonicity
    assert tau2 > tau

def test_audit_dataset_properties():
    audit_path = Path("outputs/tables/options_audit.csv")
    clean_path = Path("outputs/tables/options_clean.csv")
    assert audit_path.exists(), "options_audit.csv does not exist"
    assert clean_path.exists(), "options_clean.csv does not exist"

    df_audit = pd.read_csv(audit_path)
    df_clean = pd.read_csv(clean_path)

    # 1. Total row count must be exactly 575
    assert len(df_audit) == 575

    # 2. Exactly 303 calls and 272 puts in raw
    assert (df_audit['type'] == 'C').sum() == 303
    assert (df_audit['type'] == 'P').sum() == 272

    # 3. Clean options must be subset with tiers 1 or 2
    assert set(df_clean['tier'].unique()).issubset({1, 2})
    assert len(df_clean) >= 150 # At least 150 high-quality contracts

    # 4. Clean options must strictly satisfy American bounds
    for _, row in df_clean.iterrows():
        p = row['lastPrice']
        lb = row['lower_bound']
        ub = row['upper_bound']
        assert lb < p < ub, f"Contract {row['contractSymbol']} violates bounds: lb={lb}, p={p}, ub={ub}"
        assert row['time_value'] >= 0.01, f"Contract {row['contractSymbol']} time value < 0.01: {row['time_value']}"
        assert row['is_trade_17nov'] is True, f"Contract {row['contractSymbol']} not from 17-nov"

    # 5. Clean options must span 16 distinct expirations
    expirations = df_clean['expirationDate'].unique()
    assert len(expirations) == 16, f"Expected 16 tenors, found {len(expirations)}"
