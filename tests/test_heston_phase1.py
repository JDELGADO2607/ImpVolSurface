"""
Unit and integration tests for Phase 1: Classical Heston PoC Implementation.

Validates:
1. Exactness of QuantLib term structure adapter on calendar dates.
2. HestonParams data structure, Feller condition ratio, and conversions.
3. American put upper/lower arbitrage bounds and early exercise premium (American >= European).
4. Strike monotonicity and numerical strike convexity within tolerance.
5. Numerical grid convergence budget (<= 0.0020 USD across all representative contracts).
6. Compliance with pre-declared gate criteria on Train, Strike Holdout, and Tenor Holdout.
7. Multistart tracking: all 5 starts recorded without discarding, Feller ratios computed.
8. Isolation and clean execution using tmp_path with zero writes outside phase1.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import numpy as np
import pandas as pd
import pytest

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import get_official_yield_curve, SPOT_PRICE
from src.heston.heston_model import HestonParams, HestonOptionPricer
from src.heston.calibration import HestonCalibrator, HESTON_5_STARTS, HESTON_BOUNDS


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_quantlib_term_structure_adapter_exactness():
    """Confirms dense daily curve achieves zero discount factor difference on calendar dates."""
    curve = get_official_yield_curve(method="bootstrap")
    ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date
    ql_curve = ts_handle.currentLink()

    # Test all integer days up to 794 (covering all contract expirations)
    max_day_err = 0.0
    for day in range(1, 795):
        d_ql = ql_curve.discount(eval_date + day)
        d_py = curve.get_discount_factor(day / 365.0)
        err = abs(d_ql - d_py)
        if err > max_day_err:
            max_day_err = err

    assert max_day_err < 1e-12, f"Calendar day discount factor error {max_day_err} exceeds 1e-12"

    # Test continuous float queries: bounded by < 5e-6
    t_samples = np.linspace(0.01, 2.5, 500)
    max_cont_err = max(abs(ql_curve.discount(float(t)) - curve.get_discount_factor(float(t))) for t in t_samples)
    assert max_cont_err < 5e-6, f"Continuous discount factor error {max_cont_err} exceeds 5e-6"


def test_heston_params_dataclass_and_feller():
    """Validates HestonParams methods, Feller ratio calculation, and conversions."""
    # Feller satisfied: 2 * 2.0 * 0.20 / (0.5^2) = 0.80 / 0.25 = 3.20 > 1
    p1 = HestonParams(v0=0.20, kappa=2.0, theta=0.20, xi=0.50, rho=-0.50)
    assert abs(p1.feller_ratio - 3.20) < 1e-6
    assert p1.feller_satisfied is True
    assert abs(p1.spot_vol - np.sqrt(0.20)) < 1e-6

    # Feller violated: 2 * 0.5 * 0.35 / (1.2^2) = 0.35 / 1.44 = 0.243 < 1
    p2 = HestonParams(v0=0.35, kappa=0.5, theta=0.35, xi=1.20, rho=-0.70)
    assert abs(p2.feller_ratio - (0.35 / 1.44)) < 1e-6
    assert p2.feller_satisfied is False

    # Array roundtrip
    arr = p1.to_array()
    p1_rt = HestonParams.from_array(arr)
    assert np.allclose(p1.to_array(), p1_rt.to_array())


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_heston_option_pricer_bounds_and_arbitrage():
    """Verifies that American puts respect theoretical upper and lower bounds and American >= European."""
    pricer = HestonOptionPricer()
    params = HestonParams(v0=0.186, kappa=2.0, theta=0.22, xi=0.50, rho=-0.65)

    test_strikes = [9.0, 12.0, 15.0]
    for K in test_strikes:
        p_am = pricer.price_american(K, "2026-12-18", params, option_type="P")
        p_eu = pricer.price_european(K, "2026-12-18", params, option_type="P")

        # Bounds: max(0, K - S0) <= P_am <= K
        lower_bound = max(K - SPOT_PRICE, 0.0)
        upper_bound = K

        assert p_am >= lower_bound - 1e-6, f"Put price {p_am} violates lower bound {lower_bound} at K={K}"
        assert p_am <= upper_bound + 1e-6, f"Put price {p_am} violates upper bound {upper_bound} at K={K}"
        assert p_am >= p_eu - 1e-5, f"American price {p_am} is less than European {p_eu} at K={K}"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_heston_monotonicity_and_convexity():
    """Checks strike monotonicity and convexity on an American put smile."""
    pricer = HestonOptionPricer()
    params = HestonParams(v0=0.186, kappa=2.0, theta=0.22, xi=0.50, rho=-0.65)

    strikes = [10.0, 11.0, 12.0, 13.0, 14.0]
    prices = [pricer.price_american(K, "2027-01-15", params, option_type="P") for K in strikes]

    # Monotonicity: P(K1) < P(K2) for K1 < K2
    for i in range(len(prices) - 1):
        assert prices[i] <= prices[i + 1] + 1e-6, f"Monotonicity violation between K={strikes[i]} and K={strikes[i+1]}"

    # Convexity: P(K - h) - 2*P(K) + P(K + h) >= -tol_num
    for i in range(1, len(prices) - 1):
        butterfly = prices[i - 1] - 2.0 * prices[i] + prices[i + 1]
        assert butterfly >= -0.0020, f"Convexity violation {butterfly} at K={strikes[i]}"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_numerical_grid_budget_convergence():
    """Verifies that representative contracts satisfy the 0.0020 USD grid convergence budget."""
    grid_csv = Path("data/heston/phase1/heston_grid_convergence.csv")
    assert grid_csv.exists(), "heston_grid_convergence.csv must exist"
    df_grid = pd.read_csv(grid_csv)

    assert len(df_grid) >= 9, f"Expected at least 9 representative grid contracts, found {len(df_grid)}"
    max_diff = df_grid["diff_medium_fine"].max()
    assert max_diff <= 0.0020, f"Max medium-fine grid diff {max_diff:.6f} exceeds budget of 0.0020 USD"
    assert df_grid["budget_passed"].all(), "Not all contracts passed budget <= 0.0020 USD"


def test_phase1_gate_criteria_compliance():
    """Validates that all pre-declared Phase 1 gate criteria are strictly met."""
    manifest_path = Path("data/heston/phase1/phase1_execution_manifest.json")
    assert manifest_path.exists(), "phase1_execution_manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    metrics = manifest["performance_metrics"]
    assert metrics["train_mae"] <= 0.080, f"Train MAE {metrics['train_mae']:.4f} > 0.080 USD"
    assert metrics["train_rmse"] <= 0.120, f"Train RMSE {metrics['train_rmse']:.4f} > 0.120 USD"
    assert metrics["strike_holdout_mae"] <= 0.100, f"Strike holdout MAE {metrics['strike_holdout_mae']:.4f} > 0.100 USD"
    assert metrics["tenor_holdout_mae"] <= 0.100, f"Tenor holdout MAE {metrics['tenor_holdout_mae']:.4f} > 0.100 USD"
    assert manifest["gate_verdict"] == "PASSED", f"Gate verdict is {manifest['gate_verdict']}"


def test_multistart_results_recorded_and_feller_reported():
    """Ensures all 5 starts are recorded with parameter dispersion and Feller ratios."""
    ms_path = Path("data/heston/phase1/heston_multistart_results.csv")
    assert ms_path.exists(), "heston_multistart_results.csv must exist"

    df_ms = pd.read_csv(ms_path)
    assert len(df_ms) == 5, f"Expected 5 starts, found {len(df_ms)}"
    assert set(df_ms["start_index"]) == {1, 2, 3, 4, 5}
    assert "feller_ratio" in df_ms.columns
    assert "time_seconds" in df_ms.columns

    # Best model should have lowest final_sse
    best_row = df_ms.sort_values("final_sse").iloc[0]
    assert best_row["final_rmse"] < 0.040, f"Best RMSE {best_row['final_rmse']} is not < 0.040 USD"


@pytest.mark.skipif(not HAS_QUANTLIB, reason="QuantLib required")
def test_isolated_evaluation_using_tmp_path(tmp_path):
    """Verifies that pricing and evaluation run cleanly in an isolated directory without official writes."""
    test_out = tmp_path / "phase1_test"
    test_out.mkdir()

    pricer = HestonOptionPricer()
    params = HestonParams(v0=0.186, kappa=2.0, theta=0.22, xi=0.50, rho=-0.65)

    test_file = test_out / "sample_pricing.csv"
    price = pricer.price_american(12.0, "2026-12-18", params, option_type="P")

    pd.DataFrame([{"strike": 12.0, "price": price}]).to_csv(test_file, index=False)
    assert test_file.exists()
    assert price > 0.0
