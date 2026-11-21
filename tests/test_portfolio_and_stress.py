"""
Unit tests for Portfolio Construction and Fixed-Chain Stress Testing.
Validates delta-neutrality, fixed-contract invariants, time roll-down,
and discrepancy between Taylor expansions and full American PDE revaluations.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
import pandas as pd
from src.portfolio import build_hypothetical_portfolio, PORTFOLIO_LEGS
from src.stress_testing import SCENARIOS

def test_portfolio_construction_and_delta_neutrality():
    port_csv = Path("outputs/tables/hypothetical_portfolio.csv")
    assert port_csv.exists()
    df = pd.read_csv(port_csv)

    # 5 options + 1 stock hedge = 6 rows
    assert len(df) == 6
    stock_row = df[df['type'] == 'STOCK'].iloc[0]
    options_rows = df[df['type'] != 'STOCK']

    # Check net delta
    net_delta = df['position_delta'].sum()
    assert abs(net_delta) < 1.0, f"Portfolio is not delta-neutral: net_delta={net_delta}"

    # Check option quantities
    assert len(options_rows) == 5

def test_stress_test_matrix_integrity():
    matrix_csv = Path("outputs/tables/stress_test_matrix.csv")
    assert matrix_csv.exists()
    df = pd.read_csv(matrix_csv)

    # 5 scenarios * 2 conventions = 10 rows
    assert len(df) == 10
    assert set(df['convention'].unique()) == {'sticky_moneyness', 'sticky_strike'}

    # Scenario 1 (Roll down): dS = 0, so stock hedge PnL must be 0
    s1_rows = df[df['scenario_id'] == 'S1_RollDown_10d']
    for _, r in s1_rows.iterrows():
        assert abs(r['stock_hedge_pnl']) < 1e-4

    # Scenario 3 (Severe crisis): Taylor discrepancy should be significant
    s3_row = df[(df['scenario_id'] == 'S3_Severe_Crisis') & (df['convention'] == 'sticky_moneyness')].iloc[0]
    assert abs(s3_row['taylor_discrepancy']) > 5.0, "Taylor approximation should fail in severe non-linear shock"
