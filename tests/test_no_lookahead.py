"""
Unit tests for Causality, Absence of Look-Ahead Bias, and Strategy Invariants.
Validates that market data and forecasting strictly respect the t0 boundary (2026-11-17),
and checks strategy risk profiles.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import pandas as pd
import numpy as np

def test_historical_dataset_no_lookahead():
    hist_csv = Path("data/processed/nu_historical_daily.csv")
    assert hist_csv.exists(), "Historical daily dataset not found"
    df = pd.read_csv(hist_csv, index_col=0)

    # Dates must be strictly <= 2026-11-17
    dates = pd.to_datetime(df.index)
    max_date = dates.max()
    t0_boundary = pd.to_datetime("2026-11-17")
    assert max_date <= t0_boundary, f"Lookahead detected! Max date {max_date} exceeds t0 {t0_boundary}"

def test_forecast_evaluation_results():
    eval_csv = Path("outputs/tables/volatility_forecast_evaluation.csv")
    assert eval_csv.exists()
    df = pd.read_csv(eval_csv)

    # Must contain benchmarks and HAR-RV
    models = df['Model'].tolist()
    assert any('HAR-RV' in m for m in models)
    assert any('EWMA' in m for m in models)
    assert any('Hist' in m for m in models)

    # Losses must be positive finite numbers
    for _, r in df.iterrows():
        assert r['OOS RMSE (pp)'] > 0.0
        assert r['QLIKE Loss'] > 0.0

def test_strategy_payoffs_and_cost_penalties():
    s1_csv = Path("outputs/tables/strategy1_straddle_scenarios.csv")
    s2_csv = Path("outputs/tables/strategy2_calendar_scenarios.csv")
    assert s1_csv.exists()
    assert s2_csv.exists()

    df1 = pd.read_csv(s1_csv)
    df2 = pd.read_csv(s2_csv)

    # Friction cost must be strictly positive
    assert (df1['Friction_Cost'] > 0.0).all()
    assert (df2['Friction_Cost_USD'] > 0.0).all()

    # Conservative frictions must be greater than Optimistic
    fric_opt = df1[df1['Cost_Regime'] == 'Optimistic']['Friction_Cost'].iloc[0]
    fric_cons = df1[df1['Cost_Regime'] == 'Conservative']['Friction_Cost'].iloc[0]
    assert fric_cons > fric_opt
