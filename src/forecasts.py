"""
Volatility Forecasting Engine for NU US Equity:
Historical Volatility, EWMA (RiskMetrics), and HAR-RV (Corsi, 2009).
Walk-Forward Out-of-Sample Validation strictly enforcing causality (No Look-Ahead).
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
import yfinance as yf
import statsmodels.api as sm
import matplotlib.pyplot as plt

VALUATION_DATE_STR = "2026-11-17"

def fetch_and_save_historical_nu(
    out_csv: str = "data/processed/nu_historical_daily.csv"
) -> pd.DataFrame:
    """
    Fetches daily OHLCV bars for NU from inception up to valuation date 2026-11-17.
    """
    out_p = Path(out_csv)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    print("Fetching historical daily bars for NU up to 2026-11-17...")
    # Fetch end='2026-11-18' to ensure 2026-11-17 is included
    df = yf.download('NU', start='2021-12-01', end='2026-11-18', progress=False)

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.sort_index()
    # Filter strictly up to valuation date
    df = df.loc[df.index <= VALUATION_DATE_STR].copy()

    # Log returns
    df['log_ret'] = np.log(df['Close'] / df['Close'].shift(1))

    # Daily realized variance proxy (close-to-close squared return)
    df['rv_daily'] = df['log_ret'] ** 2

    # Annualized rolling 21-day realized volatility
    df['vol_21d'] = df['log_ret'].rolling(21).std() * np.sqrt(252.0)

    # Garman-Klass volatility estimator (using High, Low, Open, Close)
    log_hl = np.log(df['High'] / df['Low']) ** 2
    log_co = np.log(df['Close'] / df['Open']) ** 2
    df['gk_var_daily'] = 0.5 * log_hl - (2.0 * np.log(2.0) - 1.0) * log_co
    df['vol_gk_21d'] = np.sqrt(df['gk_var_daily'].rolling(21).mean() * 252.0)

    df.to_csv(out_p)
    print(f"Saved {len(df)} historical bars to: {out_p}")
    return df

def fit_har_rv_walk_forward(
    df: pd.DataFrame,
    horizon_days: int = 21,
    test_window: int = 250
) -> tuple[dict[str, Any], pd.DataFrame]:
    """
    Walk-forward out-of-sample evaluation of HAR-RV vs EWMA vs Rolling Historical.
    HAR components:
    - RV_d: 1-day realized variance
    - RV_w: 5-day average realized variance
    - RV_m: 21-day average realized variance
    Target: Future 21-day average realized variance
    """
    data = df.dropna(subset=['log_ret', 'rv_daily']).copy()

    # Construct HAR regressors
    data['rv_d'] = data['rv_daily']
    data['rv_w'] = data['rv_daily'].rolling(5).mean()
    data['rv_m'] = data['rv_daily'].rolling(21).mean()

    # Forward 21-day target variance
    data['target_rv_forward'] = data['rv_daily'].rolling(horizon_days).mean().shift(-horizon_days)

    clean_data = data.dropna(subset=['rv_d', 'rv_w', 'rv_m', 'target_rv_forward']).copy()
    n_total = len(clean_data)
    train_end_idx = n_total - test_window

    print(f"Running HAR-RV Walk-Forward Validation: {test_window} OOS days...")

    oos_records = []
    # EWMA parameters
    lambda_param = 0.94

    for t in range(train_end_idx, n_total):
        # Strictly causal train subset: up to date t
        train_sub = clean_data.iloc[:t]
        current_row = clean_data.iloc[t]
        date_t = current_row.name

        # 1. Benchmark 1: Rolling 21-day historical volatility
        pred_var_hist = current_row['rv_m']

        # 2. Benchmark 2: EWMA variance
        recent_ret = clean_data.iloc[:t+1]['log_ret'].values
        weights = (1.0 - lambda_param) * (lambda_param ** np.arange(len(recent_ret)-1, -1, -1))
        weights /= weights.sum()
        pred_var_ewma = np.sum(weights * (recent_ret ** 2))

        # 3. HAR-RV OLS regression
        X_train = train_sub[['rv_d', 'rv_w', 'rv_m']]
        X_train = sm.add_constant(X_train)
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

    # Compute loss metrics (RMSE, MAE on annualized vol, and QLIKE on variance)
    metrics = []
    for model_name, col_vol, col_var in [
        ('Rolling 21d Hist', 'pred_vol_hist', 'var_pred_hist'),
        ('EWMA (lambda=0.94)', 'pred_vol_ewma', 'var_pred_ewma'),
        ('HAR-RV (Corsi)', 'pred_vol_har', 'var_pred_har')
    ]:
        err_vol = oos_df[col_vol] - oos_df['true_vol_annual']
        mae = float(err_vol.abs().mean())
        rmse = float(np.sqrt((err_vol**2).mean()))

        # QLIKE loss = (var_true / var_pred) - ln(var_true / var_pred) - 1
        ratio = oos_df['var_true'] / oos_df[col_var]
        qlike = float((ratio - np.log(ratio) - 1.0).mean())

        metrics.append({
            'Model': model_name,
            'OOS MAE (pp)': round(mae, 2),
            'OOS RMSE (pp)': round(rmse, 2),
            'QLIKE Loss': round(qlike, 4)
        })

    eval_df = pd.DataFrame(metrics)

    # Fit final HAR model on entire sample up to 2026-11-17 to forecast next 21 days
    X_full = clean_data[['rv_d', 'rv_w', 'rv_m']]
    X_full = sm.add_constant(X_full)
    y_full = clean_data['target_rv_forward']
    final_model = sm.OLS(y_full, X_full).fit()

    last_row = data.iloc[-1]
    x_t0 = np.array([1.0, last_row['rv_d'], last_row['rv_w'], last_row['rv_m']])
    fwd_var_t0 = float(final_model.predict(x_t0.reshape(1, -1))[0])
    fwd_vol_t0 = float(np.sqrt(max(fwd_var_t0, 1e-6) * 252.0))

    summary = {
        't0_date': VALUATION_DATE_STR,
        'spot_close_t0': float(last_row['Close']),
        'realized_vol_21d_t0': float(last_row['vol_21d'] * 100.0),
        'har_forecast_21d_vol_pct': float(fwd_vol_t0 * 100.0),
        'har_r_squared': float(final_model.rsquared),
        'har_params': final_model.params.to_dict()
    }

    return summary, eval_df, oos_df

def run_forecast_pipeline(
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
):
    """
    Executes historical data download, model fitting, and validation plotting.
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    df_hist = fetch_and_save_historical_nu()
    summary, eval_df, oos_df = fit_har_rv_walk_forward(df_hist)

    eval_path = out_t / "volatility_forecast_evaluation.csv"
    eval_df.to_csv(eval_path, index=False)
    print(f"Exported forecast evaluation metrics: {eval_path}")
    print("\n--- Walk-Forward Out-of-Sample Performance ---")
    print(eval_df.to_string())

    print("\n--- Final Volatility Forecast at t0 = 2026-11-17 ---")
    print(f"NU Spot: ${summary['spot_close_t0']:.2f}")
    print(f"Historical 21d Realized Vol: {summary['realized_vol_21d_t0']:.2f}%")
    print(f"HAR-RV 21-Day Forward Forecast: {summary['har_forecast_21d_vol_pct']:.2f}%")
    print(f"HAR Model In-Sample R2: {summary['har_r_squared']:.3f}")

    # Visualizations
    plt.figure(figsize=(12, 6))
    plt.plot(df_hist.index, df_hist['vol_21d'] * 100.0, label='21-Day Realized Vol (Close-to-Close)', color='#2b83ba', alpha=0.8)
    plt.plot(df_hist.index, df_hist['vol_gk_21d'] * 100.0, label='21-Day Garman-Klass Intraday Vol', color='#74add1', alpha=0.6, linestyle='--')
    plt.axvline(pd.to_datetime(VALUATION_DATE_STR), color='red', linestyle=':', label=f't0: {VALUATION_DATE_STR}')
    plt.title("Historical Realized Volatility of NU US Equity (2021 - 2026)", fontsize=13, fontweight='bold')
    plt.ylabel("Annualized Volatility (%)", fontsize=11)
    plt.xlabel("Date", fontsize=11)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(fontsize=10)
    plt.tight_layout()

    fig_hist = out_f / "nu_historical_vol_and_forecasts.png"
    plt.savefig(fig_hist, dpi=300)
    plt.close()
    print(f"Saved historical volatility plot: {fig_hist}")

    return summary, eval_df

if __name__ == "__main__":
    run_forecast_pipeline()
