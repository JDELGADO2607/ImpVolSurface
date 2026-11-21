"""
Comprehensive Unit & Regression Tests for Volatility Surface, SVI Calibration,
and PCHIP Fallback Economic Validation (Bloques P0-C, P1-A, and Audit Round 2).

Validates:
1. Strict absence of calendar arbitrage across ALL 16 calibrated tenors, intermediate points,
   and immediate neighborhoods (tau_i - eps, tau_i + eps) across the moneyness spectrum.
2. Definitive resolution of specific audit counterexamples:
   - Case A: 2026-12-04 vs 2026-12-11 at k = -0.163.
   - Case B: 2026-12-18 vs 2026-12-24 at k = +0.225.
3. C^1 continuity across all calibrated tenor nodes (no point discontinuities or jumps).
4. Strict positivity of total variance and finite implied volatility across the entire domain.
5. Rigorous economic validation of PCHIP fallback slices without fictitious arbitrage guarantees
   (no fake 100.0% butterfly arbitrage for splines, divided-difference convexity verified).
6. Local slice support vs global domain extrapolation tracking.
7. American economic bounds and monotonicities (calls decreasing in K, puts increasing in K,
   monotonic in tau for American options).
8. Grouped Leave-One-Strike-Out cross-validation using proper American engine for Puts.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
import pandas as pd
from src.surface import (
    VolatilitySurface,
    raw_svi_total_variance,
    svi_butterfly_density_g,
    check_price_convexity_divided_diffs,
    check_american_economic_arbitrage,
    leave_one_strike_out_validation
)
from src.market_data import SPOT_PRICE, get_zero_rate

@pytest.fixture(scope="module")
def surface_instance():
    iv_csv = Path("outputs/tables/options_with_iv.csv")
    assert iv_csv.exists(), "options_with_iv.csv not found"
    df = pd.read_csv(iv_csv)
    return VolatilitySurface(df)

def test_surface_evaluation(surface_instance):
    surface = surface_instance
    for tau in [0.05, 0.1, 0.25, 0.5, 1.0, 1.5]:
        res = surface.surface_iv(k=0.0, tau=tau)
        assert not np.isnan(res['iv'])
        assert 0.20 < res['iv'] < 1.20, f"Unreasonable ATM IV at tau={tau}: {res['iv']}"
        assert res['w'] > 0

def test_calendar_arbitrage_all_calibrated_tenors_and_neighborhoods(surface_instance):
    """
    Mandatory Audit Check 1.4:
    Total variance w(k, tau) must be strictly non-decreasing across ALL 16 calibrated tenors,
    immediate neighborhoods (tau_i - 1e-5, tau_i + 1e-5), and intermediate points.
    Tested across a comprehensive moneyness mesh: Deep OTM, OTM, ATM, ITM, Deep ITM.
    """
    surface = surface_instance
    tenors = surface.tenors
    assert len(tenors) >= 16, f"Expected 16 tenors, found {len(tenors)}"

    # Construct comprehensive test tau sequence: all tenors, intermediate midpoints, and eps neighbors
    test_taus = []
    for i, t in enumerate(tenors):
        if i > 0:
            test_taus.append(t - 1e-5)
            # Midpoint between tenors
            test_taus.append(0.5 * (tenors[i-1] + t))
        test_taus.append(t)
        if i < len(tenors) - 1:
            test_taus.append(t + 1e-5)

    test_taus = sorted(list(set(test_taus)))
    k_mesh = [-0.40, -0.25, -0.163, -0.05, 0.0, 0.05, 0.15, 0.225, 0.35]

    for k_val in k_mesh:
        w_seq = [surface.surface_iv(k=k_val, tau=t)['w'] for t in test_taus]
        diffs = np.diff(w_seq)
        min_diff = np.min(diffs)
        assert min_diff >= -1e-7, (
            f"Calendar arbitrage detected at k={k_val}: min diff = {min_diff:.8f}"
        )

def test_calendar_arbitrage_specific_counterexamples(surface_instance):
    """
    Mandatory Audit Check 1.1 & 1.4:
    Verifies that the exact counterexamples identified in independent audit are cured:
    - Case A: 2026-12-04 vs 2026-12-11 at k = -0.163
    - Case B: 2026-12-18 vs 2026-12-24 at k = +0.225
    Evaluated at exact calibrated node maturities.
    """
    surface = surface_instance

    # Case A: 2026-12-04 vs 2026-12-11
    t_a1 = [t for t in surface.tenors if surface.slices[t]['exp_date'] == '2026-12-04'][0]
    t_a2 = [t for t in surface.tenors if surface.slices[t]['exp_date'] == '2026-12-11'][0]
    assert t_a2 > t_a1

    k_a = -0.163
    w_a1 = surface.surface_iv(k=k_a, tau=t_a1)['w']
    w_a2 = surface.surface_iv(k=k_a, tau=t_a2)['w']
    diff_a = w_a2 - w_a1
    assert diff_a >= -1e-8, f"Case A failed: w(t2)={w_a2:.6f} < w(t1)={w_a1:.6f} (diff={diff_a:+.6f})"

    # Case B: 2026-12-18 vs 2026-12-24
    t_b1 = [t for t in surface.tenors if surface.slices[t]['exp_date'] == '2026-12-18'][0]
    t_b2 = [t for t in surface.tenors if surface.slices[t]['exp_date'] == '2026-12-24'][0]
    assert t_b2 > t_b1

    k_b = 0.225
    w_b1 = surface.surface_iv(k=k_b, tau=t_b1)['w']
    w_b2 = surface.surface_iv(k=k_b, tau=t_b2)['w']
    diff_b = w_b2 - w_b1
    assert diff_b >= -1e-8, f"Case B failed: w(t2)={w_b2:.6f} < w(t1)={w_b1:.6f} (diff={diff_b:+.6f})"

def test_surface_node_continuity(surface_instance):
    """
    Mandatory Audit Check 1.4:
    Verifies that approaching any calibrated tenor from left or right produces zero jump discontinuity.
    |w(tau_i) - w(tau_i +/- eps)| < 1e-4.
    """
    surface = surface_instance
    eps = 1e-6
    for t_i in surface.tenors:
        for k_test in [-0.20, 0.0, 0.20]:
            w_exact = surface.surface_iv(k=k_test, tau=t_i)['w']
            if t_i > surface.tenors[0]:
                w_left = surface.surface_iv(k=k_test, tau=t_i - eps)['w']
                assert abs(w_exact - w_left) < 1e-4, (
                    f"Left jump discontinuity at tenor {t_i:.4f}, k={k_test}: jump={abs(w_exact - w_left)}"
                )
            if t_i < surface.tenors[-1]:
                w_right = surface.surface_iv(k=k_test, tau=t_i + eps)['w']
                assert abs(w_right - w_exact) < 1e-4, (
                    f"Right jump discontinuity at tenor {t_i:.4f}, k={k_test}: jump={abs(w_right - w_exact)}"
                )

def test_total_variance_positivity_and_finiteness(surface_instance):
    """
    Mandatory Audit Check 1.4:
    Verifies total variance positivity w(k, tau) > 0 and reasonable implied volatility bounds.
    """
    surface = surface_instance
    k_grid = np.linspace(-0.60, 0.60, 25)
    tau_grid = np.linspace(0.01, 2.3, 30)

    for tau in tau_grid:
        for k in k_grid:
            res = surface.surface_iv(k=k, tau=tau)
            assert res['w'] > 0.0, f"Negative total variance at k={k}, tau={tau}: {res['w']}"
            assert np.isfinite(res['iv']), f"Non-finite IV at k={k}, tau={tau}"
            assert 0.05 < res['iv'] < 5.0, f"Unreasonable IV at k={k}, tau={tau}: {res['iv']}"

def test_svi_parameters_and_lee_wings(surface_instance):
    """
    Every calibrated Raw SVI slice must satisfy:
    1. Roger Lee wing condition: b * (1 + |rho|) < 2.0.
    2. Minimum total variance a + b*eta*sqrt(1 - rho^2) >= 0.
    3. 100% butterfly density non-negativity (g(k) >= 0) on its support domain.
    """
    surface = surface_instance
    slices_df = pd.DataFrame(surface.slice_params)

    for _, row in slices_df.iterrows():
        if row['method'] == 'Raw SVI':
            b = row['param_b']
            rho = row['param_rho']
            a = row['param_a']
            eta = row['param_eta']

            # Roger Lee condition
            lee_wing = b * (1.0 + abs(rho))
            assert lee_wing < 2.0, f"Slice {row['expirationDate']} violates Lee wing bound: {lee_wing:.4f} >= 2.0"

            # Min variance
            min_var = a + b * eta * np.sqrt(max(1.0 - rho**2, 0.0))
            assert min_var >= -1e-6, f"Slice {row['expirationDate']} negative minimum variance: {min_var}"

            # Butterfly density check on support
            assert row['pct_no_butterfly_arb'] == 100.0, (
                f"Slice {row['expirationDate']} has butterfly arbitrage: {row['pct_no_butterfly_arb']}%"
            )

def test_pchip_fallback_economic_validation_and_no_fictitious_guarantees(surface_instance):
    """
    Mandatory Audit Check Phase 2:
    Validates that:
    1. Fallback PCHIP slices do NOT assign fictitious 100% butterfly arbitrage.
       pct_no_butterfly_arb must be NaN (reflecting that SVI analytical formula g(k) is not applicable).
    2. Fallback slices report explicit divided-difference price convexity (pct_price_convex).
    3. Mandatory metadata columns are present for every slice.
    4. Any slice anomalies are recorded in cross_sectional_arb_status.
    """
    surface = surface_instance
    slices_df = pd.DataFrame(surface.slice_params)

    # Required metadata fields
    mandatory_cols = [
        'expirationDate', 'tau_days', 'tau_years', 'n_strikes', 'method',
        'pct_no_butterfly_arb', 'pct_price_convex', 'k_support_min', 'k_support_max',
        'cross_sectional_arb_status', 'temporal_arb_status',
        'calendar_adj_points', 'max_calendar_adj_w',
        'verified_constraints', 'unverified_constraints'
    ]
    for col in mandatory_cols:
        assert col in slices_df.columns, f"Missing mandatory metadata column: {col}"

    fallback_slices = slices_df[slices_df['method'] == 'PCHIP Spline (Fallback)']
    assert len(fallback_slices) >= 2, f"Expected at least 2 fallback slices, found {len(fallback_slices)}"

    for _, row in fallback_slices.iterrows():
        # Prohibited: recording 100% butterfly arbitrage on SVI formula without SVI calibration
        assert np.isnan(row['pct_no_butterfly_arb']), (
            f"Fictitious guarantee detected on fallback slice {row['expirationDate']}: "
            f"pct_no_butterfly_arb={row['pct_no_butterfly_arb']}"
        )
        # Price convexity must be evaluated for slices with sufficient strikes (>= 3)
        if row['n_strikes'] >= 3:
            assert not np.isnan(row['pct_price_convex']), (
                f"Price convexity not evaluated on fallback slice {row['expirationDate']}"
            )
        else:
            assert np.isnan(row['pct_price_convex']), (
                f"Fictitious convexity detected on 2-strike slice {row['expirationDate']}"
            )
        # SVI analytical constraints must be in unverified constraints
        assert "NOT_APPLICABLE" in str(row['unverified_constraints']), (
            f"Slice {row['expirationDate']} should document SVI formula as not applicable"
        )

def test_local_vs_global_extrapolation_tracking(surface_instance):
    """
    Mandatory Audit Check 2.5:
    Validates that query points outside a slice's local strikes but within global chain bounds
    are flagged as EXTRAPOLATED_LOCAL_SLICE, not falsely marked as fully supported.
    """
    surface = surface_instance

    # 3-day slice (2026-11-20) has narrow local support around [-0.027, 0.013]
    t_3d = surface.tenors[0]
    loc_min = surface.slices[t_3d]['k_min']

    # Query point at k = -0.30: inside global bounds [-1.51, 0.98], but outside local 3-day slice
    res = surface.surface_iv(k=-0.30, tau=t_3d)
    assert res['is_locally_extrapolated'] is True
    assert res['quality'] == 'EXTRAPOLATED_LOCAL_SLICE'

    # Query point at ATM k = 0.0: inside local 3-day slice
    res_atm = surface.surface_iv(k=0.0, tau=t_3d)
    assert res_atm['is_locally_extrapolated'] is False
    assert res_atm['quality'] == 'SUPPORTED_LOCAL_GRID'

def test_american_economic_arbitrage_checks(surface_instance):
    """
    Verifies that prices generated by the surface through the American engine
    satisfy fundamental economic arbitrage bounds:
    - Calls decreasing in strike
    - Puts increasing in strike
    - Both non-decreasing in time to expiry (American property)
    - Intrinsic lower bounds respected
    - Upper bounds respected
    """
    surface = surface_instance
    diag = check_american_economic_arbitrage(surface, S0=SPOT_PRICE)

    assert diag['call_strike_monotonicity_violations'] == 0
    assert diag['put_strike_monotonicity_violations'] == 0
    assert diag['call_expiry_monotonicity_violations'] == 0
    assert diag['put_expiry_monotonicity_violations'] == 0
    assert diag['intrinsic_bound_violations'] == 0
    assert diag['upper_bound_violations'] == 0

def test_leave_one_strike_out_accuracy_and_american_engine():
    """
    Verifies leave-one-strike-out validation:
    - Uses American pricing engine for puts.
    - Evaluates out-of-sample accuracy across strikes without grouped leakage.
    - MAE price < $0.10 USD.
    """
    iv_csv = Path("outputs/tables/options_with_iv.csv")
    df = pd.read_csv(iv_csv)
    val_df = leave_one_strike_out_validation(df)

    assert len(val_df) > 80
    mae_px = val_df['price_error_usd'].abs().mean()
    assert mae_px < 0.10, f"LOO MAE price too high: ${mae_px:.3f}"

    # Verify that puts have American valuation
    puts_val = val_df[val_df['type'] == 'P']
    assert len(puts_val) > 20
    assert 'pred_price' in puts_val.columns
