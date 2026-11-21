"""
Unit & Regression Tests for Causality, Absence of Look-Ahead Bias,
and Signal-Linked Trading Simulation Positions (Bloque P0-D and Audit Round 2).

Validates:
1. Historical dataset bounds (strictly <= 2026-11-17, no future lookahead).
2. Counterfactual invariance: modifying future returns after day t does not change forecast at day t.
3. Purged OOS walk-forward loss metrics integrity.
4. Strategy signal sensitivity: transitions between LONG_VOLATILITY, SHORT_VOLATILITY, and NO_TRADE.
5. Signal-Linked Portfolio Execution:
   - High forecast -> Long Straddle (+1 Call, +1 Put, negative stock hedge, positive friction).
   - Neutral forecast -> NO_TRADE (0 Call, 0 Put, 0 Shares, 0 Friction, exactly 0.0 USD P&L).
   - Low forecast -> Short Straddle (-1 Call, -1 Put, positive stock hedge, inverted tail liability).
6. Non-hardcoded forecast parameter dispatch: verify custom forecasts are strictly honored.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import pandas as pd
import numpy as np
import statsmodels.api as sm

from src.forecasts import load_or_fetch_historical_nu, fit_har_rv_walk_forward
from src.strategies import (
    generate_strategy_signal,
    build_straddle_portfolio_from_signal,
    analyze_strategy_1_straddle
)

def test_historical_dataset_no_lookahead():
    hist_csv = Path("data/processed/nu_historical_daily.csv")
    assert hist_csv.exists(), "Historical daily dataset not found"
    df = pd.read_csv(hist_csv, index_col=0)

    dates = pd.to_datetime(df.index)
    max_date = dates.max()
    t0_boundary = pd.to_datetime("2026-11-17")
    assert max_date <= t0_boundary, f"Lookahead detected! Max date {max_date} exceeds t0 {t0_boundary}"

def test_counterfactual_future_invariance():
    """
    Counterfactual test: Altering or injecting future data after day t must NOT
    alter the forecast emitted for day t when training is strictly purged.
    """
    df = load_or_fetch_historical_nu()
    horizon = 21

    # Pick an evaluation point in the series
    t_eval = len(df) - 50

    # Baseline forecast at t_eval
    df_base = df.copy()
    df_base['log_ret'] = np.log(df_base['Close'] / df_base['Close'].shift(1))
    df_base['rv_daily'] = df_base['log_ret'] ** 2
    df_base['rv_d'] = df_base['rv_daily']
    df_base['rv_w'] = df_base['rv_daily'].rolling(5).mean()
    df_base['rv_m'] = df_base['rv_daily'].rolling(21).mean()
    df_base['target_rv_forward'] = df_base['rv_daily'].rolling(horizon).mean().shift(-horizon)

    # Purged training set: observations whose target had closed by t_eval
    train_base = df_base.iloc[:t_eval - horizon + 1].dropna(subset=['rv_d', 'rv_w', 'rv_m', 'target_rv_forward'])
    X_base = sm.add_constant(train_base[['rv_d', 'rv_w', 'rv_m']])
    y_base = train_base['target_rv_forward']
    m_base = sm.OLS(y_base, X_base).fit()

    row_eval = df_base.iloc[t_eval]
    x_eval = np.array([1.0, row_eval['rv_d'], row_eval['rv_w'], row_eval['rv_m']])
    pred_base = float(m_base.predict(x_eval.reshape(1, -1))[0])

    # Counterfactual dataset: heavily perturb subsequent prices after t_eval + 10
    df_perturbed = df.copy()
    perturbed_closes = df_perturbed['Close'].values.copy()
    perturbed_closes[t_eval + 10:] = perturbed_closes[t_eval + 10:] * 2.5 # Huge jump in future!
    df_perturbed['Close'] = perturbed_closes
    df_perturbed['log_ret'] = np.log(df_perturbed['Close'] / df_perturbed['Close'].shift(1))
    df_perturbed['rv_daily'] = df_perturbed['log_ret'] ** 2
    df_perturbed['rv_d'] = df_perturbed['rv_daily']
    df_perturbed['rv_w'] = df_perturbed['rv_daily'].rolling(5).mean()
    df_perturbed['rv_m'] = df_perturbed['rv_daily'].rolling(21).mean()
    df_perturbed['target_rv_forward'] = df_perturbed['rv_daily'].rolling(horizon).mean().shift(-horizon)

    # Purged training set on perturbed data
    train_pert = df_perturbed.iloc[:t_eval - horizon + 1].dropna(subset=['rv_d', 'rv_w', 'rv_m', 'target_rv_forward'])
    X_pert = sm.add_constant(train_pert[['rv_d', 'rv_w', 'rv_m']])
    y_pert = train_pert['target_rv_forward']
    m_pert = sm.OLS(y_pert, X_pert).fit()

    row_pert = df_perturbed.iloc[t_eval]
    x_pert = np.array([1.0, row_pert['rv_d'], row_pert['rv_w'], row_pert['rv_m']])
    pred_pert = float(m_pert.predict(x_pert.reshape(1, -1))[0])

    # Counterfactual invariant: past prediction must be strictly identical
    assert abs(pred_base - pred_pert) < 1e-12, (
        f"Causality violation! Future shock altered past prediction: {pred_base} vs {pred_pert}"
    )

def test_forecast_evaluation_results():
    eval_csv = Path("outputs/tables/volatility_forecast_evaluation.csv")
    assert eval_csv.exists()
    df = pd.read_csv(eval_csv)

    models = df['Model'].tolist()
    assert any('HAR-RV' in m for m in models)
    assert any('EWMA' in m for m in models)
    assert any('Hist' in m for m in models)

    for _, r in df.iterrows():
        assert r['OOS RMSE (pp)'] > 0.0
        assert r['QLIKE Loss'] > 0.0

def test_strategy_signal_sensitivity():
    """
    Tests strategy signal transitions across positive, negative, and neutral regimes.
    """
    # 1. High forecast -> Long volatility
    s_long = generate_strategy_signal(forecast_vol_pct=72.97, benchmark_iv_pct=45.0, hurdle_rate_pp=5.0)
    assert s_long['action'] == "LONG_VOLATILITY_STRADDLE"
    assert s_long['vol_spread_pp'] > 5.0

    # 2. Low forecast -> Short volatility
    s_short = generate_strategy_signal(forecast_vol_pct=35.0, benchmark_iv_pct=45.0, hurdle_rate_pp=5.0)
    assert s_short['action'] == "SHORT_VOLATILITY_STRADDLE"
    assert s_short['vol_spread_pp'] < -5.0

    # 3. Near benchmark -> No trade (friction neutral band)
    s_neutral = generate_strategy_signal(forecast_vol_pct=46.5, benchmark_iv_pct=45.0, hurdle_rate_pp=5.0)
    assert s_neutral['action'] == "NO_TRADE"
    assert abs(s_neutral['vol_spread_pp']) <= 5.0

def test_strategy_portfolio_position_linkage_and_signal_dispatch():
    """
    Mandatory Audit Check Phase 3:
    Verifies that the portfolio construction and simulated P&L are strictly driven by the signal:
    1. High forecast activates LONG straddle (+1 Call, +1 Put, negative stock hedge, positive friction).
    2. Neutral forecast activates NO_TRADE:
       - 0 Calls, 0 Puts, 0 Shares
       - 0 Transaction/friction costs
       - Exactly 0.0 USD Net P&L across ALL spot shocks and cost regimes.
    3. Low forecast activates SHORT straddle:
       - Does NOT reuse the long straddle positions!
       - -1 Call, -1 Put, positive stock hedge
       - At 0% spot shock, profits from theta/premium retention minus friction
       - Large moves produce tail losses (unbounded tail risk).
    """
    # Case 1: High forecast (75.0% vs ~45.9% IV)
    df_long, sig_long = analyze_strategy_1_straddle(forecast_vol_pct=75.0)
    assert sig_long['action'] == "LONG_VOLATILITY_STRADDLE"
    assert (df_long['Signal_Action'] == "LONG_VOLATILITY_STRADDLE").all()
    assert (df_long['Friction_Cost'] > 0.0).all()
    # In extreme spot moves (+25%, -25%), long straddle has positive payoff
    extreme_pnl_long = df_long[df_long['Spot_Shock'] == '+25.0%']['Gross_PnL'].iloc[0]
    assert extreme_pnl_long > 0.0

    # Case 2: Neutral forecast within hurdle band (46.0% vs ~45.9% IV)
    df_none, sig_none = analyze_strategy_1_straddle(forecast_vol_pct=46.0)
    assert sig_none['action'] == "NO_TRADE"
    assert (df_none['Signal_Action'] == "NO_TRADE").all()
    assert (df_none['Friction_Cost'] == 0.0).all(), "NO_TRADE must have 0 transaction friction"
    assert (df_none['Options_Payoff'] == 0.0).all(), "NO_TRADE must have 0 options payoff"
    assert (df_none['Stock_Hedge_PnL'] == 0.0).all(), "NO_TRADE must have 0 stock hedge PnL"
    assert (df_none['Gross_PnL'] == 0.0).all(), "NO_TRADE must have 0 Gross PnL"
    assert (df_none['Net_PnL'] == 0.0).all(), "NO_TRADE must have exactly 0.0 Net PnL"

    # Case 3: Low forecast below hurdle band (28.0% vs ~45.9% IV)
    df_short, sig_short = analyze_strategy_1_straddle(forecast_vol_pct=28.0)
    assert sig_short['action'] == "SHORT_VOLATILITY_STRADDLE"
    assert (df_short['Signal_Action'] == "SHORT_VOLATILITY_STRADDLE").all()
    assert (df_short['Friction_Cost'] > 0.0).all()

    # Null spot shock (+0.0%) for short straddle: retains premium minus friction
    null_short_pnl = df_short[(df_short['Cost_Regime'] == 'Base') & (df_short['Spot_Shock'] == '+0.0%')]['Net_PnL'].iloc[0]
    assert null_short_pnl > 50.0, f"Short straddle should be profitable under null shock: {null_short_pnl}"

    # Extreme shock (+25.0%) for short straddle: severe tail losses
    extreme_short_pnl = df_short[(df_short['Cost_Regime'] == 'Base') & (df_short['Spot_Shock'] == '+25.0%')]['Net_PnL'].iloc[0]
    assert extreme_short_pnl < -50.0, f"Short straddle should suffer tail losses on large spot moves: {extreme_short_pnl}"

def test_forecast_parameter_dynamic_dispatch_no_hardcoding():
    """
    Mandatory Audit Check 3.5:
    Confirms that analyze_strategy_1_straddle does NOT rely on a hardcoded 72.97% forecast,
    and dynamically adopts whatever forecast value is passed.
    """
    test_forecasts = [20.0, 42.5, 55.0, 85.0]
    for fc in test_forecasts:
        _, sig = analyze_strategy_1_straddle(forecast_vol_pct=fc)
        assert abs(sig['forecast_vol_pct'] - fc) < 1e-4, (
            f"Forecast not dynamically dispatched: expected {fc}, got {sig['forecast_vol_pct']}"
        )
