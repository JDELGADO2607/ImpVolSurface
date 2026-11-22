"""
Acceptance Test Suite: Surface 2D Convexity, Arbitrage Diagnostics,
Extrapolation Contamination Invariance, LEAPS Quarantine, and Release Grid Contracts.
Validates remediation of CODEX Audit Findings B1, H1, H2, H5, M1, and L2.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
import pandas as pd

from src.market_data import SPOT_PRICE, get_zero_rate, get_forward_price
from src.pricing_bs import bs_price
from src.pricing_american_fd import price_american_option
from src.surface import (
    VolatilitySurface,
    check_price_convexity_divided_diffs,
    fit_svi_slice,
    raw_svi_total_variance
)

@pytest.fixture(scope="module")
def surface_and_data():
    iv_path = Path("outputs/tables/options_with_iv.csv")
    assert iv_path.exists(), "options_with_iv.csv must exist before running surface tests"
    df_iv = pd.read_csv(iv_path)
    surface = VolatilitySurface(df_iv)
    return surface, df_iv

def test_b1_counterexample_a_27_5d_convexity_no_butterfly_arbitrage(surface_and_data):
    """
    Audit Finding B1 (Blocker):
    Validates that at interpolated maturity tau = 27.5 days (between 24d and 31d),
    call prices are strictly 100% convex with respect to strike across fine grids (121, 241, 481),
    and butterfly spreads have strictly non-negative premium.
    """
    surface, _ = surface_and_data
    tau_a = 27.5 / 365.0
    r_a = get_zero_rate(tau_a)
    F_a = get_forward_price(tau_a)

    for n in (121, 241, 481):
        strikes = np.linspace(10.0, 15.0, n)
        k_vals = np.log(strikes / F_a)
        calls = [
            bs_price('C', SPOT_PRICE, K, tau_a, r_a, surface.surface_iv(k, tau_a, policy='allow')['iv'])
            for K, k in zip(strikes, k_vals)
        ]
        diag = check_price_convexity_divided_diffs(strikes, np.array(calls), tol=1e-5)
        assert diag['violations'] == 0, f"Counterexample A (27.5d) violated convexity at N={n}: min d2={diag['min_second_diff']}"
        assert diag['pct_convex'] == 100.0
        assert diag['min_second_diff'] >= -1e-5

def test_b1_counterexample_b_612d_convexity_no_butterfly_arbitrage(surface_and_data):
    """
    Audit Finding B1 (Blocker):
    Validates that at interpolated exploratory maturity tau = 612 days (between Jan 2028 and Jan 2029),
    call prices are strictly 100% convex with respect to strike across fine grids (121, 241, 481).
    """
    surface, _ = surface_and_data
    tau_b = 612.0 / 365.0
    r_b = get_zero_rate(tau_b)
    F_b = get_forward_price(tau_b)

    for n in (121, 241, 481):
        strikes = np.linspace(5.0, 30.0, n)
        k_vals = np.log(strikes / F_b)
        calls = [
            bs_price('C', SPOT_PRICE, K, tau_b, r_b, surface.surface_iv(k, tau_b, policy='allow')['iv'])
            for K, k in zip(strikes, k_vals)
        ]
        diag = check_price_convexity_divided_diffs(strikes, np.array(calls), tol=1e-5)
        assert diag['violations'] == 0, f"Counterexample B (612d) violated convexity at N={n}: min d2={diag['min_second_diff']}"
        assert diag['pct_convex'] == 100.0
        assert diag['min_second_diff'] >= -1e-5

def test_h1_no_cross_tenor_extrapolation_contamination_430d(surface_and_data):
    """
    Audit Finding H1 (High):
    Verifies that for Jan 2028 (430d) at K=5.0 (k=-0.9568), where Jan 2028 has a real quote,
    the surface does NOT get contaminated by Dec 2027 (395d) unobserved wing extrapolation.
    """
    surface, _ = surface_and_data
    tau_430 = surface.tenors[14]
    F_430 = get_forward_price(tau_430)
    k_5 = float(np.log(5.0 / F_430))

    raw_w = surface._evaluate_slice_w(tau_430, k_5)
    surf_res = surface.surface_iv(k_5, tau_430, policy='allow')

    assert abs(surf_res['w'] - raw_w) < 1e-4, (
        f"Jan 2028 K=5.0 was contaminated: raw_w={raw_w:.6f}, surf_w={surf_res['w']:.6f}"
    )

def test_h1_no_cross_tenor_extrapolation_contamination_31d(surface_and_data):
    """
    Audit Finding H1 (High):
    Verifies that for Dec 2026 (31d) at K=10.0 (k=-0.2129), where 31d has a real quote,
    the surface does NOT get contaminated by Dec 4 (17d) out-of-support wing.
    """
    surface, _ = surface_and_data
    tau_31 = surface.tenors[4]
    F_31 = get_forward_price(tau_31)
    k_10 = float(np.log(10.0 / F_31))

    raw_w = surface._evaluate_slice_w(tau_31, k_10)
    surf_res = surface.surface_iv(k_10, tau_31, policy='allow')

    assert abs(surf_res['w'] - raw_w) < 1e-4, (
        f"Dec 2026 K=10.0 was contaminated: raw_w={raw_w:.6f}, surf_w={surf_res['w']:.6f}"
    )

def test_h2_jan_2029_svi_calibration_clean_and_quarantine_status(surface_and_data):
    """
    Audit Finding H2 (High):
    Verifies that excluding the single deep ITM outlier at K=3.0 (volume 1) enables SVI to fit
    with RMSE <= 1.5 pp and 100% no-butterfly arbitrage, while properly marking the LEAPS slice
    as quarantined and enforcing production horizon cutoff (tau <= 430 days).
    """
    surface, df_iv = surface_and_data
    grp_29 = df_iv[df_iv['expirationDate'] == '2029-01-19']
    tau_29 = float(grp_29['tau_recalc'].iloc[0])

    # SVI fit on cleaned slice K > 3.0
    clean_sub = grp_29[grp_29['strike'] > 3.0]
    k_clean = clean_sub['k_log_moneyness'].values
    w_clean = (clean_sub['our_iv_decimal'].values ** 2) * tau_29
    sort_idx = np.argsort(k_clean)
    svi_res = fit_svi_slice(k_clean[sort_idx], w_clean[sort_idx], tau_29)

    assert svi_res['success'] is True, "SVI calibration must succeed on clean Jan 2029 slice"
    assert svi_res['rmse_iv'] * 100.0 < 1.5, f"RMSE too high: {svi_res['rmse_iv']*100:.2f} pp"
    assert svi_res['pct_no_butterfly_arb'] == 100.0
    assert svi_res['lee_wing'] < 2.0

    # Surface quarantine status
    s_info = surface.slices[tau_29]
    assert s_info['is_quarantined'] is True
    assert s_info['production_status'] == 'QUARANTINED_LEAPS_EXPLORATORY_ONLY'

    # Strict policy must reject queries beyond production horizon (430 days)
    with pytest.raises(ValueError, match="exceeds production horizon"):
        surface.surface_iv(0.0, tau_29, policy='strict')

def test_h5_american_put_time_monotonicity_31d_to_37d(surface_and_data):
    """
    Audit Finding H5 (High / Additional Blocker):
    Verifies that American Put price at K=14.75 does not drop between 31d and 37d,
    preventing decay of continuation value across maturities.
    """
    surface, _ = surface_and_data
    tau31 = surface.tenors[4]
    tau37 = surface.tenors[5]

    F31 = get_forward_price(tau31)
    F37 = get_forward_price(tau37)

    iv31 = surface.surface_iv(float(np.log(14.75 / F31)), tau31)['iv']
    iv37 = surface.surface_iv(float(np.log(14.75 / F37)), tau37)['iv']

    p31 = price_american_option('P', SPOT_PRICE, 14.75, tau31, get_zero_rate(tau31), iv31)
    p37 = price_american_option('P', SPOT_PRICE, 14.75, tau37, get_zero_rate(tau37), iv37)

    diff = p37 - p31
    assert diff >= -1e-4, f"American put value decreased across maturity: P(37d)={p37:.5f} < P(31d)={p31:.5f}"

def test_m1_nov_20_2026_insufficient_data_status(surface_and_data):
    """
    Audit Finding M1 (Medium):
    Verifies that Nov 20, 2026 (3d, 2 strikes) is explicitly flagged as
    INSUFFICIENT_DATA_TWO_STRIKES, with pct_price_convex marked NaN (no fake 100% claims).
    """
    surface, _ = surface_and_data
    tau_3d = surface.tenors[0]
    s_info = surface.slices[tau_3d]

    assert s_info['n_strikes'] == 2
    assert s_info['production_status'] == 'INSUFFICIENT_DATA_TWO_STRIKES'
    assert np.isnan(s_info['val_diag']['pct_price_convex'])
    assert s_info['val_diag']['cross_sectional_arb_status'] == 'INSUFFICIENT_DATA_TWO_STRIKES'

def test_l2_short_maturity_regularity_exact_identity(surface_and_data):
    """
    Audit Finding L2 (Low):
    Verifies mathematical regularity as tau -> 0:
    Exact identity w = sigma^2 * tau holds with w -> 0, finite IV, and absence of discontinuous floor jumps.
    """
    surface, _ = surface_and_data
    k = 0.0
    for tau in [1e-8, 1e-7, 1e-6]:
        res = surface.surface_iv(k, tau, policy='allow')
        assert np.isfinite(res['iv']) and res['iv'] > 0.0
        assert abs(res['w'] - (res['iv']**2 * tau)) < 1e-10
        assert res['w'] < tau * 2.0

def test_surface_release_grid_schema_and_production_core_contracts():
    """
    Validates that outputs/tables/surface_release_grid.csv exists, contains all 24 required fields,
    and certifies production core contracts at 31d and 59d for strikes $11, 12, 13, 14, 15.
    """
    p_grid = Path("outputs/tables/surface_release_grid.csv")
    assert p_grid.exists(), "surface_release_grid.csv must exist"
    df = pd.read_csv(p_grid)

    required_cols = [
        'tau_days', 'tau_years', 'strike', 'forward', 'log_moneyness',
        'raw_total_variance', 'projected_total_variance', 'surface_iv_pct',
        'call_price_model', 'put_price_model', 'dC_dK', 'd2C_dK2',
        'is_convex', 'calendar_spread_vs_prev_tau', 'is_calendar_arbitrage_free',
        'american_put_time_monotonic', 'dominant_tenor_tau', 'delta_w_projected',
        'is_extrapolated_strike', 'is_extrapolated_tau', 'is_production_ready',
        'quality_flag', 'slice_support_K_min', 'slice_support_K_max'
    ]
    assert len(df.columns) == 24
    assert list(df.columns) == required_cols

    # Core production slice verification (10 contracts)
    core = df[df['tau_days'].isin([31.0, 59.0]) & df['strike'].isin([11.0, 12.0, 13.0, 14.0, 15.0])]
    assert len(core) == 10, f"Expected 10 core contracts, found {len(core)}"
    assert core['is_production_ready'].all(), "All core contracts must be marked production ready"
    assert core['is_convex'].all(), "All core contracts must be price convex"

def test_surface_quality_diagnostics_coverage():
    """
    Validates that outputs/tables/surface_quality_diagnostics.csv exists and covers all 16 calibrated slices.
    """
    p_diag = Path("outputs/tables/surface_quality_diagnostics.csv")
    assert p_diag.exists(), "surface_quality_diagnostics.csv must exist"
    df = pd.read_csv(p_diag)
    assert len(df) == 16, f"Expected 16 slice records, found {len(df)}"

def test_2d_final_holdout_validation_accuracy():
    """
    Validates that outputs/tables/surface_final_holdout_validation.csv exists, has >= 190 contracts,
    and meets quantitative model audit accuracy thresholds.
    """
    p_loo = Path("outputs/tables/surface_final_holdout_validation.csv")
    assert p_loo.exists(), "surface_final_holdout_validation.csv must exist"
    df = pd.read_csv(p_loo)
    assert len(df) >= 190, f"Expected >= 190 validated contracts, got {len(df)}"

    mae_iv = df['iv_error_pp'].abs().mean()
    rmse_iv = np.sqrt((df['iv_error_pp']**2).mean())
    mae_px = df['price_error_usd'].abs().mean()

    assert mae_iv < 5.0, f"IV MAE too high: {mae_iv:.2f} pp"
    assert rmse_iv < 8.0, f"IV RMSE too high: {rmse_iv:.2f} pp"
    assert mae_px < 0.10, f"Price MAE too high: ${mae_px:.4f} USD"

def test_uniform_evaluation_policy_node_continuity(surface_and_data):
    """
    Verifies uniform evaluation policy: evaluation at calibrated nodes matches slice evaluation identically.
    """
    surface, _ = surface_and_data
    for t_i in surface.tenors[:8]:
        k = 0.0
        w_slice, _ = surface.evaluate_slice_total_variance(t_i, k)
        res = surface.surface_iv(k, t_i)
        assert abs(res['w'] - w_slice) < 1e-10, f"Node discontinuity at tenor {t_i}: {res['w']} vs {w_slice}"
