"""
Unit tests for Portfolio Construction and Fixed-Chain Stress Testing (Bloque P0-B).
Validates:
1. Delta-neutral portfolio construction and hedge consistency.
2. Null shock scenario returning zero P&L (both full revaluation and Taylor).
3. Exact reconciliation between leg sum and portfolio totals.
4. Separation of mark-to-model initial difference from stress P&L.
5. Taylor Greek discrepancy sanity (finite, explained by non-linearity, no fake explosion).
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
from src.stress_testing import SCENARIOS, run_stress_testing

def test_portfolio_construction_and_delta_neutrality():
    df, summary = build_hypothetical_portfolio()

    # 5 options + 1 stock hedge = 6 rows
    assert len(df) == 6
    stock_row = df[df['type'] == 'STOCK'].iloc[0]
    options_rows = df[df['type'] != 'STOCK']
    assert len(options_rows) == 5

    # Check net delta neutrality
    net_delta = df['position_delta'].sum()
    assert abs(net_delta) < 1.0, f"Portfolio is not delta-neutral: net_delta={net_delta}"

    # Stock hedge shares must be integer
    assert isinstance(summary['hedge_shares'], (int, np.integer))

def test_null_shock_scenario_zero_pnl():
    """
    Scenario 0 (Null Shock: dS=0, dt=0, dVol=0) must produce exactly zero
    stress P&L in both full PDE revaluation and Taylor approximation.
    """
    sc_df, legs_df = run_stress_testing()

    assert 'S0_Null_Shock' in sc_df['scenario_id'].values

    null_rows = sc_df[sc_df['scenario_id'] == 'S0_Null_Shock']
    for _, r in null_rows.iterrows():
        assert abs(r['options_pnl_stress_mod']) < 1e-4, f"Null shock options stress PnL non-zero: {r['options_pnl_stress_mod']}"
        assert abs(r['stock_hedge_pnl']) < 1e-4, f"Null shock stock PnL non-zero: {r['stock_hedge_pnl']}"
        assert abs(r['total_port_pnl_stress_mod']) < 1e-4, f"Null shock total stress PnL non-zero: {r['total_port_pnl_stress_mod']}"
        assert abs(r['total_port_pnl_taylor']) < 1e-4, f"Null shock Taylor PnL non-zero: {r['total_port_pnl_taylor']}"
        assert abs(r['taylor_discrepancy']) < 1e-4, f"Null shock discrepancy non-zero: {r['taylor_discrepancy']}"

def test_reconciliation_leg_sum_equals_total():
    """
    The sum of leg P&Ls must match the total portfolio options P&L exactly across all scenarios.
    """
    sc_df, legs_df = run_stress_testing()

    sticky_m_scenarios = sc_df[sc_df['convention'] == 'sticky_moneyness']

    for sc_id in sticky_m_scenarios['scenario_id'].unique():
        sc_row = sticky_m_scenarios[sticky_m_scenarios['scenario_id'] == sc_id].iloc[0]
        legs_sub = legs_df[legs_df['scenario_id'] == sc_id]

        sum_leg_full = legs_sub['leg_pnl_stress_mod'].sum()
        sum_leg_taylor = legs_sub['leg_pnl_taylor'].sum()

        assert abs(sum_leg_full - sc_row['options_pnl_stress_mod']) < 0.05, \
            f"Leg sum full mismatch in {sc_id}: sum={sum_leg_full}, total={sc_row['options_pnl_stress_mod']}"
        assert abs(sum_leg_taylor - sc_row['options_pnl_taylor']) < 0.05, \
            f"Leg sum Taylor mismatch in {sc_id}: sum={sum_leg_taylor}, total={sc_row['options_pnl_taylor']}"

def test_mark_to_model_separation():
    """
    Verifies that mark-to-model initial difference is separated from stress P&L:
    total_port_pnl_mkt_base == total_port_pnl_stress_mod + mark_to_model_diff_initial
    """
    sc_df, _ = run_stress_testing()

    for _, r in sc_df.iterrows():
        pnl_mod = r['total_port_pnl_stress_mod']
        pnl_mkt = r['total_port_pnl_mkt_base']
        m2m = r['mark_to_model_diff_initial']

        assert abs(pnl_mkt - (pnl_mod + m2m)) < 0.05, \
            f"Accounting mismatch: pnl_mkt={pnl_mkt}, pnl_mod={pnl_mod}, m2m={m2m}"

def test_taylor_discrepancy_rational_magnitude():
    """
    In S3 Severe Crisis (-20% spot, vol spike), Taylor discrepancy must be non-zero
    (reflecting real gamma/vega non-linearity and early exercise boundary effects),
    but must NOT blow up to $3,253 USD due to numerical artifacts.
    """
    sc_df, _ = run_stress_testing()
    s3_row = sc_df[(sc_df['scenario_id'] == 'S3_Severe_Crisis') & (sc_df['convention'] == 'sticky_moneyness')].iloc[0]

    disc = abs(s3_row['taylor_discrepancy'])
    # Must be non-zero but well under $500 USD (genuine financial non-linearity, not numerical explosion)
    assert 10.0 < disc < 500.0, f"Taylor discrepancy outside rational financial bounds: ${disc:.2f}"
