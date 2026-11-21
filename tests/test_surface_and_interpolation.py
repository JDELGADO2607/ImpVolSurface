"""
Unit tests for Volatility Surface and SVI calibration.
Validates surface evaluation, absence of calendar arbitrage, parameter bounds,
and out-of-sample prediction accuracy.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
import pandas as pd
from src.surface import VolatilitySurface, raw_svi_total_variance

@pytest.fixture(scope="module")
def surface_instance():
    iv_csv = Path("outputs/tables/options_with_iv.csv")
    assert iv_csv.exists(), "options_with_iv.csv not found"
    df = pd.read_csv(iv_csv)
    return VolatilitySurface(df)

def test_surface_evaluation(surface_instance):
    surface = surface_instance
    # Test ATM queries across maturities
    for tau in [0.05, 0.1, 0.25, 0.5, 1.0, 1.5]:
        res = surface.surface_iv(k=0.0, tau=tau)
        assert not np.isnan(res['iv'])
        assert 0.20 < res['iv'] < 1.20, f"Unreasonable ATM IV at tau={tau}: {res['iv']}"
        assert res['w'] > 0

def test_no_calendar_arbitrage_monotonic_total_variance(surface_instance):
    surface = surface_instance
    k_test = 0.0 # ATM
    taus = np.linspace(0.05, 1.8, 30)
    w_vals = [surface.surface_iv(k=k_test, tau=t)['w'] for t in taus]

    # Total variance w(tau) must be non-decreasing in tau
    diffs = np.diff(w_vals)
    # Allow tiny numerical tolerance of 1e-5
    min_diff = np.min(diffs)
    assert min_diff >= -1e-5, f"Calendar arbitrage detected: total variance decreased by {-min_diff}"

def test_svi_parameters_bounds():
    params_csv = Path("outputs/tables/svi_slice_parameters.csv")
    assert params_csv.exists()
    df = pd.read_csv(params_csv)

    for _, row in df.iterrows():
        if row['method'] == 'Raw SVI':
            b = row['param_b']
            rho = row['param_rho']
            eta = row['param_eta']
            assert b >= 0.0, f"b negative: {b}"
            assert abs(rho) <= 1.0, f"rho outside [-1, 1]: {rho}"
            assert eta > 0.0, f"eta non-positive: {eta}"
            assert row['pct_no_butterfly_arb'] >= 80.0, f"Excess butterfly arbitrage: {row['pct_no_butterfly_arb']}"

def test_leave_one_out_accuracy():
    val_csv = Path("outputs/tables/surface_leave_one_out_validation.csv")
    assert val_csv.exists()
    df = pd.read_csv(val_csv)

    assert len(df) > 100
    mae_px = df['price_error_usd'].abs().mean()
    # Out of sample price error must be well under 10 cents
    assert mae_px < 0.10, f"Leave-one-out MAE price too high: ${mae_px:.3f}"
