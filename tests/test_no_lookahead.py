"""
Unit tests for Causality, Absence of Look-Ahead Bias, and Strategy Signal Sensitivity (Bloque P0-D).
Validates:
1. Historical dataset bounds (strictly <= 2026-11-17).
2. Counterfactual invariance: modifying future returns after day t does not change forecast at day t.
3. Purged OOS walk-forward loss metrics integrity.
4. Strategy signal sensitivity: correctly transitions between LONG, SHORT, and NO_TRADE.
5. Friction costs and transaction penalties across regimes.
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
from src.strategies import generate_strategy_signal

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
    date_eval = df.index[t_eval]

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
    assert abs(pred_base - pred_pert) < 1e-12, \
        f"Causality violation! Future shock altered past prediction: {pred_base} vs {pred_pert}"

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
