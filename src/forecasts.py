"""
Volatility Forecasting Engine for NU US Equity (Bloque P0-D):
Historical Volatility, EWMA (RiskMetrics lambda=0.94), and HAR-RV (Corsi, 2009).
Strictly enforces causality via Purged Walk-Forward Out-of-Sample Validation:
any training observation s is purged if its forward 21-day target window had not fully
matured by forecast date t (i.e., s <= t - horizon).
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

VALUATION_DATE_STR = "2026-11-17"

def load_or_fetch_historical_nu(
    csv_path: str = "data/processed/nu_historical_daily.csv"
) -> pd.DataFrame:
    """
    Loads historical daily OHLCV bars for NU up to valuation date 2026-11-17.
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"Historical dataset not found: {p}")

    df = pd.read_csv(p, index_col=0)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    # Filter strictly up to valuation date
    df = df.loc[df.index <= VALUATION_DATE_STR].copy()

    # Log returns and realized variance proxy
    if 'log_ret' not in df.columns:
        df['log_ret'] = np.log(df['Close'] / df['Close'].shift(1))
    if 'rv_daily' not in df.columns:
        df['rv_daily'] = df['log_ret'] ** 2
    if 'vol_21d' not in df.columns:
        df['vol_21d'] = df['log_ret'].rolling(21).std() * np.sqrt(252.0)

    return df

def fit_har_rv_walk_forward(
    df: pd.DataFrame,
    horizon_days: int = 21,
    test_window: int = 250
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """
    Strictly causal, purged walk-forward out-of-sample evaluation of HAR-RV vs EWMA vs Rolling Hist.
    At evaluation step t, the training set clean_data.iloc[:t - horizon_days + 1] contains
    ONLY target labels that had fully matured on or before day t.
    Returns:
    - evaluation_summary_df
    - oos_predictions_df
    - final_causal_forecast_vol_pct (for valuation date 2026-11-17)
    """
    data = df.dropna(subset=['log_ret', 'rv_daily']).copy()

    # Construct HAR regressors
    data['rv_d'] = data['rv_daily']
    data['rv_w'] = data['rv_daily'].rolling(5).mean()
    data['rv_m'] = data['rv_daily'].rolling(21).mean()

    # Forward 21-day average target variance
    data['target_rv_forward'] = data['rv_daily'].rolling(horizon_days).mean().shift(-horizon_days)

    clean_data = data.dropna(subset=['rv_d', 'rv_w', 'rv_m', 'target_rv_forward']).copy()
    n_total = len(clean_data)
    train_end_idx = n_total - test_window
    lambda_param = 0.94

    print(f"Running Strictly Purged HAR-RV Walk-Forward Validation: {test_window} OOS days...")

    oos_records = []

    for t in range(train_end_idx, n_total):
        # PURGING: Train ONLY on observations whose forward 21-day target has already closed!
        # Observation s has target realized between s+1 and s+horizon.
        # It is known at day t if and only if s + horizon <= t <=> s <= t - horizon.
        purge_cutoff = t - horizon_days + 1
        train_sub = clean_data.iloc[:max(purge_cutoff, 50)]
        current_row = clean_data.iloc[t]
        date_t = current_row.name

        # 1. Benchmark 1: Rolling 21-day historical volatility
        pred_var_hist = float(current_row['rv_m'])

        # 2. Benchmark 2: EWMA variance (RiskMetrics lambda=0.94)
        recent_ret = clean_data.iloc[:t+1]['log_ret'].values
        weights = (1.0 - lambda_param) * (lambda_param ** np.arange(len(recent_ret)-1, -1, -1))
        weights /= weights.sum()
        pred_var_ewma = float(np.sum(weights * (recent_ret ** 2)))

        # 3. HAR-RV OLS regression (strictly causal on purged train set)
        X_train = sm.add_constant(train_sub[['rv_d', 'rv_w', 'rv_m']])
        y_train = train_sub['target_rv_forward']
        model = sm.OLS(y_train, X_train).fit()

        x_current = np.array([1.0, current_row['rv_d'], current_row['rv_w'], current_row['rv_m']])
        pred_var_har = float(model.predict(x_current.reshape(1, -1))[0])
        pred_var_har = max(pred_var_har, 1e-6)

        true_forward_var = float(current_row['target_rv_forward'])

        oos_records.append({
            'date': date_t,
            'true_vol_annual': np.sqrt(true_forward_var * 252.0) * 100.0,
            'pred_vol_hist': np.sqrt(pred_var_hist * 252.0) * 100.0,
            'pred_vol_ewma': np.sqrt(pred_var_ewma * 252.0) * 100.0,
            'pred_vol_har': np.sqrt(pred_var_har * 252.0) * 100.0,
            'var_true': true_forward_var,
            'var_pred_hist': pred_var_hist,
            'var_pred_ewma': pred_var_ewma,
            'var_pred_har': pred_var_har
        })

    oos_df = pd.DataFrame(oos_records)

    # Compute loss metrics
    summary_rows = []
    for model_name, col_vol, col_var in [
        ('Rolling 21d Hist', 'pred_vol_hist', 'var_pred_hist'),
        ('EWMA (lambda=0.94)', 'pred_vol_ewma', 'var_pred_ewma'),
        ('HAR-RV (Corsi Purged)', 'pred_vol_har', 'var_pred_har')
    ]:
        err_vol = oos_df[col_vol] - oos_df['true_vol_annual']
        mae_vol = float(err_vol.abs().mean())
        rmse_vol = float(np.sqrt((err_vol**2).mean()))

        # QLIKE Loss on variance: (var_true / var_pred) - ln(var_true / var_pred) - 1
        ratio = oos_df['var_true'] / oos_df[col_var]
        qlike = float((ratio - np.log(ratio) - 1.0).mean())

        summary_rows.append({
            'Model': model_name,
            'OOS MAE (pp)': round(mae_vol, 2),
            'OOS RMSE (pp)': round(rmse_vol, 2),
            'QLIKE Loss': round(qlike, 4)
        })

    eval_df = pd.DataFrame(summary_rows)

    # 4. Final Causal Forecast for Valuation Date 2026-11-17:
    # Use only observations whose 21-day target had matured by 2026-11-17 (i.e. <= -horizon_days)
    full_valid = data.dropna(subset=['rv_d', 'rv_w', 'rv_m']).copy()
    train_for_final = full_valid.iloc[:-horizon_days].dropna(subset=['target_rv_forward'])

    X_final = sm.add_constant(train_for_final[['rv_d', 'rv_w', 'rv_m']])
    y_final = train_for_final['target_rv_forward']
    final_model = sm.OLS(y_final, X_final).fit()

    row_val = full_valid.iloc[-1]
    x_val = np.array([1.0, row_val['rv_d'], row_val['rv_w'], row_val['rv_m']])
    final_pred_var = float(final_model.predict(x_val.reshape(1, -1))[0])
    final_pred_vol_pct = float(np.sqrt(max(final_pred_var, 1e-6) * 252.0) * 100.0)

    print(f"\n--- Final Purged Causal Forecast on {VALUATION_DATE_STR} ---")
    print(f"HAR-RV 21-day Forward Volatility Forecast: {final_pred_vol_pct:.2f}%")
    print("HAR-RV Parameters:")
    for param_name, val in final_model.params.items():
        print(f"  {param_name}: {val:.6f}")

    return eval_df, oos_df, final_pred_vol_pct

def run_forecast_pipeline(
    data_csv: str = "data/processed/nu_historical_daily.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> tuple[pd.DataFrame, float]:
    """
    Executes historical data ingestion, purged walk-forward validation,
    exports summary table, and plots historical vol + forecast.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    df = load_or_fetch_historical_nu(data_csv)
    eval_df, oos_df, final_forecast_pct = fit_har_rv_walk_forward(df, horizon_days=21, test_window=250)

    eval_csv = out_t / "volatility_forecast_evaluation.csv"
    eval_df.to_csv(eval_csv, index=False)
    print(f"Exported forecast evaluation: {eval_csv}")
    print("\n--- Out-of-Sample Evaluation (Strictly Purged) ---")
    print(eval_df.to_string())

    # Plot Historical Volatility and OOS Forecasts
    plt.figure(figsize=(12, 6))
    dates_oos = pd.to_datetime(oos_df['date'])

    plt.plot(dates_oos, oos_df['true_vol_annual'], label='Realized 21-Day Forward Volatility', color='black', linewidth=1.8)
    plt.plot(dates_oos, oos_df['pred_vol_har'], label='HAR-RV (Corsi Purged Forecast)', color='#d7191c', linewidth=1.5)
    plt.plot(dates_oos, oos_df['pred_vol_ewma'], label='EWMA ($\\lambda=0.94$)', color='#2b83ba', linestyle='--', linewidth=1.2)
    plt.plot(dates_oos, oos_df['pred_vol_hist'], label='Rolling 21d Historical', color='#fdae61', linestyle=':', linewidth=1.2)

    plt.xlabel("Date", fontsize=11)
    plt.ylabel("Annualized Volatility (%)", fontsize=11)
    plt.title("Out-of-Sample Volatility Forecasts vs Realized — NU US Equity (Purged Walk-Forward)", fontsize=12, fontweight='bold')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    fig_path = out_f / "nu_historical_vol_and_forecasts.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved historical vol and forecasts plot: {fig_path}")

    return eval_df, final_forecast_pct

if __name__ == "__main__":
    run_forecast_pipeline()
