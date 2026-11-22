"""
Four-Model Pricing Comparison Engine (Bloque P1-A):
1. European Flat Volatility (BS)
2. European Surface Volatility (BS with SVI/Spline IV)
3. American Flat Volatility (FD PDE / CRR)
4. American Surface Volatility (FD PDE / BS Call q=0 with SVI/Spline IV)

Disentangles the Early Exercise Premium from the Volatility Skew Effect.
Explicitly distinguishes in-sample cross-sectional fitting from out-of-sample
leave-one-strike-out validation, avoiding misleading claims of price 'underpricing'
or temporal predictability.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.market_data import SPOT_PRICE, get_zero_rate
from src.pricing_bs import bs_price
from src.pricing_american_fd import price_american_option
from src.surface import VolatilitySurface, leave_one_strike_out_validation

FLAT_VOL_EX_ANTE = 0.440 # 44.0% ATM IV benchmark at 30-day tenor

def run_model_comparison(
    iv_csv: str = "outputs/tables/options_with_iv.csv",
    tables_dir: str = "outputs/tables",
    figures_dir: str = "outputs/figures"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Evaluates all clean options under the four models, separating:
    - In-Sample full calibration fit
    - Out-of-Sample Leave-One-Strike-Out cross-validation
    """
    out_t = Path(tables_dir)
    out_f = Path(figures_dir)
    out_t.mkdir(parents=True, exist_ok=True)
    out_f.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(iv_csv)
    surface = VolatilitySurface(df)

    print(f"Running 4-Model Comparison on {len(df)} clean contracts (In-Sample)...")

    detailed_records = []
    for idx, row in df.iterrows():
        kind = row['type']
        K = float(row['strike'])
        tau = float(row['tau_recalc'])
        r = get_zero_rate(tau)
        k = float(row['k_log_moneyness'])
        p_obs = float(row['lastPrice'])

        # Surface volatility
        sig_surf = surface.surface_iv(k, tau)['iv']
        sig_flat = FLAT_VOL_EX_ANTE

        # Model 1: European Flat
        v1_eu_flat = bs_price(kind, SPOT_PRICE, K, tau, r, sig_flat, q=0.0)
        # Model 2: European Surface
        v2_eu_surf = bs_price(kind, SPOT_PRICE, K, tau, r, sig_surf, q=0.0)
        # Model 3: American Flat
        v3_am_flat = price_american_option(kind, SPOT_PRICE, K, tau, r, sig_flat, q=0.0, method="auto")
        # Model 4: American Surface
        v4_am_surf = price_american_option(kind, SPOT_PRICE, K, tau, r, sig_surf, q=0.0, method="auto")

        # Decompositions
        early_exercise_premium = v4_am_surf - v2_eu_surf
        surface_skew_effect = v4_am_surf - v3_am_flat

        detailed_records.append({
            'contractSymbol': row['contractSymbol'],
            'type': kind,
            'strike': K,
            'expirationDate': row['expirationDate'],
            'tau_days': row['tau_days'],
            'k_log_moneyness': k,
            'lastPrice': p_obs,
            'sigma_flat': sig_flat,
            'sigma_surface': sig_surf,
            'm1_eu_flat': round(v1_eu_flat, 4),
            'm2_eu_surf': round(v2_eu_surf, 4),
            'm3_am_flat': round(v3_am_flat, 4),
            'm4_am_surf': round(v4_am_surf, 4),
            'err_m1': round(v1_eu_flat - p_obs, 4),
            'err_m2': round(v2_eu_surf - p_obs, 4),
            'err_m3': round(v3_am_flat - p_obs, 4),
            'err_m4': round(v4_am_surf - p_obs, 4),
            'early_exercise_premium': round(early_exercise_premium, 4),
            'surface_skew_effect': round(surface_skew_effect, 4),
            'sample_scope': 'in_sample_calibration'
        })

    comp_df = pd.DataFrame(detailed_records)
    comp_path = out_t / "model_comparison_detailed.csv"
    comp_df.to_csv(comp_path, index=False)
    print(f"Exported detailed model comparison: {comp_path}")

    # Summary statistics across models and segments
    def compute_metrics(errors):
        return {
            'Bias ($)': round(errors.mean(), 4),
            'MAE ($)': round(errors.abs().mean(), 4),
            'RMSE ($)': round(np.sqrt((errors**2).mean()), 4),
            'Max Err ($)': round(errors.abs().max(), 4)
        }

    segments = {
        'All Contracts': comp_df,
        'Calls Only': comp_df[comp_df['type'] == 'C'],
        'Puts Only': comp_df[comp_df['type'] == 'P'],
        'ITM Options': comp_df[((comp_df['type'] == 'C') & (comp_df['strike'] < SPOT_PRICE)) |
                               ((comp_df['type'] == 'P') & (comp_df['strike'] > SPOT_PRICE))],
        'ATM Options (|k| < 0.05)': comp_df[comp_df['k_log_moneyness'].abs() < 0.05],
        'OTM Options': comp_df[((comp_df['type'] == 'C') & (comp_df['strike'] > SPOT_PRICE)) |
                               ((comp_df['type'] == 'P') & (comp_df['strike'] < SPOT_PRICE))]
    }

    summary_rows = []
    for seg_name, subset in segments.items():
        n = len(subset)
        if n == 0:
            continue
        m1_m = compute_metrics(subset['err_m1'])
        m2_m = compute_metrics(subset['err_m2'])
        m3_m = compute_metrics(subset['err_m3'])
        m4_m = compute_metrics(subset['err_m4'])

        # Compute reduction in MAE from flat to surface
        mae_reduct_pct = (m3_m['MAE ($)'] - m4_m['MAE ($)']) / max(m3_m['MAE ($)'], 1e-6) * 100.0

        summary_rows.append({
            'Evaluation_Type': 'In-Sample Fitting',
            'Segment': seg_name,
            'N': n,
            'M1 Eu Flat MAE': m1_m['MAE ($)'],
            'M1 RMSE': m1_m['RMSE ($)'],
            'M2 Eu Surf MAE': m2_m['MAE ($)'],
            'M2 RMSE': m2_m['RMSE ($)'],
            'M3 Am Flat MAE': m3_m['MAE ($)'],
            'M3 RMSE': m3_m['RMSE ($)'],
            'M4 Am Surf MAE': m4_m['MAE ($)'],
            'M4 RMSE': m4_m['RMSE ($)'],
            'MAE Reduction vs Flat (%)': round(mae_reduct_pct, 1)
        })

    # Add Out-of-Sample row from Leave-One-Strike-Out
    loo_csv = out_t / "surface_leave_one_out_validation.csv"
    if not loo_csv.exists():
        loo_df = leave_one_strike_out_validation(df)
        loo_df.to_csv(loo_csv, index=False)
    else:
        loo_df = pd.read_csv(loo_csv)

    loo_mae = round(loo_df['price_error_usd'].abs().mean(), 4)
    loo_rmse = round(np.sqrt((loo_df['price_error_usd']**2).mean()), 4)

    summary_rows.append({
        'Evaluation_Type': 'Out-of-Sample (LOO Cross-Val)',
        'Segment': 'Held-Out Strikes (American)',
        'N': len(loo_df),
        'M1 Eu Flat MAE': np.nan,
        'M1 RMSE': np.nan,
        'M2 Eu Surf MAE': np.nan,
        'M2 RMSE': np.nan,
        'M3 Am Flat MAE': np.nan,
        'M3 RMSE': np.nan,
        'M4 Am Surf MAE': loo_mae,
        'M4 RMSE': loo_rmse,
        'MAE Reduction vs Flat (%)': np.nan
    })

    summary_df = pd.DataFrame(summary_rows)
    sum_path = out_t / "model_comparison_summary.csv"
    summary_df.to_csv(sum_path, index=False)
    print(f"Exported model comparison summary: {sum_path}")
    print("\n--- Model Comparison Summary ---")
    print(summary_df[['Evaluation_Type', 'Segment', 'N', 'M1 Eu Flat MAE', 'M3 Am Flat MAE', 'M4 Am Surf MAE', 'MAE Reduction vs Flat (%)']].to_string())

    # Comparison Plot: In-Sample MAE across Models
    in_sample_df = summary_df[summary_df['Evaluation_Type'] == 'In-Sample Fitting']
    plt.figure(figsize=(12, 6))
    bar_width = 0.2
    x = np.arange(len(in_sample_df))

    plt.bar(x - 1.5 * bar_width, in_sample_df['M1 Eu Flat MAE'], width=bar_width, label='Model 1: European Flat (BS)', color='#4575b4')
    plt.bar(x - 0.5 * bar_width, in_sample_df['M2 Eu Surf MAE'], width=bar_width, label='Model 2: European Surface', color='#74add1')
    plt.bar(x + 0.5 * bar_width, in_sample_df['M3 Am Flat MAE'], width=bar_width, label='Model 3: American Flat', color='#fdae61')
    plt.bar(x + 1.5 * bar_width, in_sample_df['M4 Am Surf MAE'], width=bar_width, label='Model 4: American Surface (Full Engine)', color='#d73027')

    plt.xticks(x, in_sample_df['Segment'], rotation=15, ha='right', fontsize=10)
    plt.ylabel("In-Sample MAE (USD)", fontsize=11)
    plt.title("In-Sample Pricing Residuals by Architecture (Cross-Sectional Fit) — NU Options", fontsize=12, fontweight='bold')
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.legend(fontsize=10)
    plt.tight_layout()

    fig_path = out_f / "model_comparison_errors.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved model comparison plot: {fig_path}")

    return comp_df, summary_df

if __name__ == "__main__":
    run_model_comparison()
