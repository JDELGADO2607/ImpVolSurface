"""
Phase 5 Pipeline: Implied Volatility (IV) Surface Generation and Validation.

Executes:
1. Re-evaluation / verification of 6 1D control cases against QuantLib constant volatility American put.
2. Inversion of 97 American Puts into equivalent implied volatility using 1D Crank-Nicolson PDE
   with official bootstrap yield curve.
3. Pricing and analytical Black-Scholes IV inversion of 142 external contrast Calls.
4. Descriptive 35-point grid (5 strikes x 7 tenors) valuation and IV inversion for puts and calls.
5. Export of structured tables, convergence diagnostics, summary metrics, and visualizations.
6. Generation of cryptographic execution manifest.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import os
import json
import time
import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import (
    DeterministicYieldCurve,
    SPOT_PRICE,
    DIVIDEND_YIELD,
    VALUATION_DATETIME,
)
from src.heston.heston_model import HestonParams
from src.heston.solver_2d import Heston2DSolver
from src.heston.equivalent_iv import (
    fd_american_price_curve,
    invert_american_put_iv,
    price_heston_european_call,
    invert_european_call_iv,
)


def compute_sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_1d_quantlib_controls(curve: DeterministicYieldCurve) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes the 6 required 1D control cases vs QuantLib and the 3-mesh sensitivity analysis.
    """
    ref_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = ref_date

    tenors = curve.tenors
    dates = [ref_date] + [ref_date + ql.Period(int(round(t * 365)), ql.Days) for t in tenors]
    dfs = [1.0] + [curve.get_discount_factor(t) for t in tenors]
    ql_curve = ql.DiscountCurve(dates, dfs, ql.Actual365Fixed())
    ql_curve_handle = ql.YieldTermStructureHandle(ql_curve)
    q_handle = ql.YieldTermStructureHandle(ql.FlatForward(ref_date, 0.0, ql.Actual365Fixed()))
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE))

    cases = [
        (9.0, 31, 0.25),
        (12.33, 31, 0.45),
        (17.0, 31, 0.70),
        (9.0, 430, 0.70),
        (12.33, 94, 0.25),
        (17.0, 430, 0.45)
    ]

    records = []
    for K, days, sigma in cases:
        tau = days / 365.0
        maturity = ref_date + ql.Period(days, ql.Days)
        payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
        exercise = ql.AmericanExercise(ref_date, maturity)
        option = ql.VanillaOption(payoff, exercise)

        flat_vol = ql.BlackConstantVol(ref_date, ql.NullCalendar(), sigma, ql.Actual365Fixed())
        vol_handle = ql.BlackVolTermStructureHandle(flat_vol)
        bs_process = ql.BlackScholesMertonProcess(spot_handle, q_handle, ql_curve_handle, vol_handle)
        engine = ql.FdBlackScholesVanillaEngine(bs_process, 400, 400)
        option.setPricingEngine(engine)
        ql_price = float(option.NPV())

        # Test with M=300, N=150 (standard production mesh)
        fd_price = fd_american_price_curve('P', SPOT_PRICE, K, tau, curve, sigma, q=0.0, M=300, N=150)
        diff = abs(fd_price - ql_price)

        records.append({
            'strike': K,
            'days': days,
            'tau_years': tau,
            'sigma': sigma,
            'ql_american_price': ql_price,
            'fd_1d_price_m300_n150': fd_price,
            'abs_diff_usd': diff,
            'target_budget_usd': 0.0020,
            'passed_gate': diff <= 0.0020
        })

    df_controls = pd.DataFrame(records)

    # 3-mesh sensitivity on the 2 sensitive cases: (12.33, 94, 0.25) and (12.33, 31, 0.45)
    sensitive_cases = [(12.33, 94, 0.25), (12.33, 31, 0.45)]
    meshes = [
        ('coarse', 200, 100),
        ('standard', 300, 150),
        ('fine', 400, 300)
    ]

    mesh_records = []
    for K, days, sigma in sensitive_cases:
        tau = days / 365.0
        # Reference QL price
        maturity = ref_date + ql.Period(days, ql.Days)
        payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
        exercise = ql.AmericanExercise(ref_date, maturity)
        option = ql.VanillaOption(payoff, exercise)
        flat_vol = ql.BlackConstantVol(ref_date, ql.NullCalendar(), sigma, ql.Actual365Fixed())
        vol_handle = ql.BlackVolTermStructureHandle(flat_vol)
        bs_process = ql.BlackScholesMertonProcess(spot_handle, q_handle, ql_curve_handle, vol_handle)
        engine = ql.FdBlackScholesVanillaEngine(bs_process, 400, 400)
        option.setPricingEngine(engine)
        ql_price = float(option.NPV())

        for mesh_name, M, N in meshes:
            p_mesh = fd_american_price_curve('P', SPOT_PRICE, K, tau, curve, sigma, q=0.0, M=M, N=N)
            diff_ql = abs(p_mesh - ql_price)
            mesh_records.append({
                'strike': K,
                'days': days,
                'sigma': sigma,
                'mesh_label': mesh_name,
                'M_spatial': M,
                'N_temporal': N,
                'fd_price': p_mesh,
                'ql_reference': ql_price,
                'abs_diff_vs_ql_usd': diff_ql,
                'passed_002_budget': diff_ql <= 0.0020
            })

    df_mesh_sens = pd.DataFrame(mesh_records)
    return df_controls, df_mesh_sens


def run_phase5_pipeline() -> Dict[str, Any]:
    print("=" * 80)
    print("Starting Phase 5 Pipeline: Implied Volatility Surface Generation")
    print("=" * 80)

    start_time = time.time()
    out_dir = Path("data/heston/phase5")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = Path("figures/phase5")
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load canonical parameters and yield curve
    calib_path = Path("data/heston/phase4/heston_calibrated_parameters.json")
    with open(calib_path, "r") as f:
        calib_data = json.load(f)
    params_dict = calib_data["calibrated_parameters"]
    params = HestonParams(**params_dict)
    curve = DeterministicYieldCurve(method="bootstrap")
    print(f"Loaded calibrated parameters: {params_dict}")

    # 2. Control Cases
    print("\n--- Step 1: Running 6 1D Control Cases vs QuantLib ---")
    df_controls, df_mesh_sens = run_1d_quantlib_controls(curve)
    controls_csv = out_dir / "control_cases_1d_quantlib.csv"
    mesh_sens_csv = out_dir / "mesh_sensitivity_1d_controls.csv"
    df_controls.to_csv(controls_csv, index=False)
    df_mesh_sens.to_csv(mesh_sens_csv, index=False)
    print(f"Max 1D discrepancy across 6 cases: {df_controls['abs_diff_usd'].max():.6f} USD (budget <= 0.0020)")
    assert df_controls['passed_gate'].all(), "1D control gate failed!"

    # 3. 97 Puts Table
    print("\n--- Step 2: Inverting 97 American Puts to Equivalent IV ---")
    p4_puts_path = Path("data/heston/phase4/heston_pricing_full_puts.csv")
    df_p4_puts = pd.read_csv(p4_puts_path)
    print(f"Loaded {len(df_p4_puts)} puts from Phase 4 verified table")

    puts_records = []
    for idx, row in df_p4_puts.iterrows():
        symbol = row["contractSymbol"]
        K = float(row["strike"])
        tau_days = int(round(row["tau_days"]))
        tau_years = float(row["tau_years"])
        partition = str(row["partition"])
        mkt_price = float(row["lastPrice"])
        heston_px = float(row["prop_fine_price"])
        provenance = str(row.get("valuation_provenance", "PHASE4_AUDITED_PROP_FINE"))

        # Invert Heston model price to equivalent IV
        inv_heston = invert_american_put_iv(
            target_price=heston_px,
            S0=SPOT_PRICE,
            K=K,
            tau=tau_years,
            curve_or_r=curve,
            q=DIVIDEND_YIELD,
            M=300,
            N=150
        )

        # Invert Market observed price to IV (when identifiable)
        inv_mkt = invert_american_put_iv(
            target_price=mkt_price,
            S0=SPOT_PRICE,
            K=K,
            tau=tau_years,
            curve_or_r=curve,
            q=DIVIDEND_YIELD,
            M=300,
            N=150
        )

        iv_heston = inv_heston['iv']
        iv_mkt = inv_mkt['iv']
        diff_iv = iv_heston - iv_mkt if (not np.isnan(iv_heston) and not np.isnan(iv_mkt)) else np.nan
        abs_diff_iv = abs(diff_iv) if not np.isnan(diff_iv) else np.nan

        puts_records.append({
            "contractSymbol": symbol,
            "strike": K,
            "tau_days": tau_days,
            "tau_years": tau_years,
            "partition": partition,
            "market_last_price": mkt_price,
            "heston_price": heston_px,
            "heston_price_source": provenance,
            "iv_heston_equivalent": iv_heston,
            "residual_heston_1d_usd": inv_heston['residual_usd'],
            "status_heston_inversion": inv_heston['status'],
            "iterations_heston_brent": inv_heston['iterations'],
            "iv_market_observed": iv_mkt,
            "residual_mkt_1d_usd": inv_mkt['residual_usd'],
            "status_market_inversion": inv_mkt['status'],
            "diff_iv_heston_vs_mkt": diff_iv,
            "abs_diff_iv_heston_vs_mkt": abs_diff_iv,
            "abs_err_heston_price_usd": abs(heston_px - mkt_price),
            "heston_inversion_notes": inv_heston['notes']
        })

    df_puts_iv = pd.DataFrame(puts_records)
    puts_iv_csv = out_dir / "heston_iv_surface_97_puts.csv"
    df_puts_iv.to_csv(puts_iv_csv, index=False)
    print(f"97 Puts Table exported to {puts_iv_csv}")
    print(f"Heston Put Inversion Status counts:\n{df_puts_iv['status_heston_inversion'].value_counts()}")
    print(f"Market Put Inversion Status counts:\n{df_puts_iv['status_market_inversion'].value_counts()}")

    # 4. 142 Calls Table
    print("\n--- Step 3: Pricing and Inverting 142 External Calls ---")
    calls_split_path = Path("data/heston/data_split_calls_contrast.csv")
    df_calls_raw = pd.read_csv(calls_split_path)
    print(f"Loaded {len(df_calls_raw)} calls for external contrast")

    calls_records = []
    for idx, row in df_calls_raw.iterrows():
        symbol = row["contractSymbol"]
        K = float(row["strike"])
        tau_days = int(round(row["tau_days"]))
        tau_years = float(row["tau_years"])
        mkt_price = float(row["lastPrice"])

        # Price European Call with Heston model via QuantLib
        heston_call_px = price_heston_european_call(
            S0=SPOT_PRICE,
            K=K,
            tau_days=tau_days,
            params=params,
            curve=curve
        )

        # Invert Heston European Call price to Black-Scholes IV
        inv_call_heston = invert_european_call_iv(
            target_price=heston_call_px,
            S0=SPOT_PRICE,
            K=K,
            tau_years=tau_years,
            curve=curve,
            q=DIVIDEND_YIELD
        )

        # Invert Market Call price to Black-Scholes IV
        inv_call_mkt = invert_european_call_iv(
            target_price=mkt_price,
            S0=SPOT_PRICE,
            K=K,
            tau_years=tau_years,
            curve=curve,
            q=DIVIDEND_YIELD
        )

        iv_call_heston = inv_call_heston['iv']
        iv_call_mkt = inv_call_mkt['iv']
        diff_iv = iv_call_heston - iv_call_mkt if (not np.isnan(iv_call_heston) and not np.isnan(iv_call_mkt)) else np.nan
        abs_diff_iv = abs(diff_iv) if not np.isnan(diff_iv) else np.nan

        calls_records.append({
            "contractSymbol": symbol,
            "strike": K,
            "tau_days": tau_days,
            "tau_years": tau_years,
            "partition": "external_contrast",
            "market_last_price": mkt_price,
            "heston_call_price": heston_call_px,
            "iv_heston_bs": iv_call_heston,
            "residual_heston_call_usd": inv_call_heston['residual_usd'],
            "status_heston_call": inv_call_heston['status'],
            "iterations_heston_brent": inv_call_heston['iterations'],
            "iv_market_bs": iv_call_mkt,
            "residual_mkt_call_usd": inv_call_mkt['residual_usd'],
            "status_market_call": inv_call_mkt['status'],
            "diff_iv_heston_vs_mkt": diff_iv,
            "abs_diff_iv_heston_vs_mkt": abs_diff_iv,
            "abs_err_heston_price_usd": abs(heston_call_px - mkt_price),
            "notes_heston": inv_call_heston['notes'],
            "notes_mkt": inv_call_mkt['notes']
        })

    df_calls_iv = pd.DataFrame(calls_records)
    calls_iv_csv = out_dir / "heston_iv_surface_142_calls.csv"
    df_calls_iv.to_csv(calls_iv_csv, index=False)
    print(f"142 Calls Table exported to {calls_iv_csv}")
    print(f"Heston Call Inversion Status counts:\n{df_calls_iv['status_heston_call'].value_counts()}")
    print(f"Market Call Inversion Status counts:\n{df_calls_iv['status_market_call'].value_counts()}")

    # 5. Representative 35-Point Descriptive Grid
    print("\n--- Step 4: Generating 35-Point Descriptive Grid (Puts & Calls) ---")
    grid_strikes = [9.0, 11.0, 12.33, 15.0, 17.0]
    grid_days = [3, 31, 59, 94, 212, 430, 794]

    solver_2d = Heston2DSolver()

    # Pre-index existing 97 puts for exact reuse
    p4_lookup = {}
    for idx, row in df_p4_puts.iterrows():
        p4_lookup[(round(float(row['strike']), 2), int(round(row['tau_days'])))] = float(row['prop_fine_price'])

    grid_puts = []
    grid_calls = []

    for K in grid_strikes:
        for d in grid_days:
            tau_y = d / 365.0

            # --- PUT ---
            key = (round(K, 2), d)
            if key in p4_lookup:
                p_put = p4_lookup[key]
                p_src = "REUSED_PHASE4_AUDITED"
            else:
                m_t = max(int(np.ceil(tau_y * 252)), 60)
                sol = solver_2d.price(
                    strike=K, maturity_years=tau_y, params=params, curve=curve,
                    spot=SPOT_PRICE, is_american=True, n_s=240, n_v=120, m_t=m_t
                )
                p_put = float(sol.price)
                p_src = "FRESH_2D_SOLVER"

            inv_put = invert_american_put_iv(
                target_price=p_put, S0=SPOT_PRICE, K=K, tau=tau_y,
                curve_or_r=curve, q=DIVIDEND_YIELD, M=300, N=150
            )

            grid_puts.append({
                "strike": K,
                "tau_days": d,
                "tau_years": tau_y,
                "heston_model_price": p_put,
                "price_source": p_src,
                "iv_equivalent": inv_put['iv'],
                "residual_usd": inv_put['residual_usd'],
                "status": inv_put['status'],
                "iterations": inv_put['iterations']
            })

            # --- CALL ---
            c_px = price_heston_european_call(
                S0=SPOT_PRICE, K=K, tau_days=d, params=params, curve=curve
            )
            inv_c = invert_european_call_iv(
                target_price=c_px, S0=SPOT_PRICE, K=K, tau_years=tau_y,
                curve=curve, q=DIVIDEND_YIELD
            )

            grid_calls.append({
                "strike": K,
                "tau_days": d,
                "tau_years": tau_y,
                "heston_model_price": c_px,
                "price_source": "QUANTLIB_ANALYTIC_HESTON",
                "iv_bs": inv_c['iv'],
                "residual_usd": inv_c['residual_usd'],
                "status": inv_c['status'],
                "iterations": inv_c['iterations']
            })

    df_grid_puts = pd.DataFrame(grid_puts)
    df_grid_calls = pd.DataFrame(grid_calls)

    grid_puts_csv = out_dir / "heston_descriptive_grid_35_puts.csv"
    grid_calls_csv = out_dir / "heston_descriptive_grid_35_calls.csv"
    df_grid_puts.to_csv(grid_puts_csv, index=False)
    df_grid_calls.to_csv(grid_calls_csv, index=False)
    print(f"35-Point Grid Puts exported to {grid_puts_csv}")
    print(f"35-Point Grid Calls exported to {grid_calls_csv}")

    # 6. Figures
    print("\n--- Step 5: Generating Visualizations ---")
    # Figure 1: 3D Surface Puts
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    valid_puts = df_puts_iv[df_puts_iv['status_heston_inversion'] == 'CONVERGED']
    unid_puts = df_puts_iv[df_puts_iv['status_heston_inversion'] != 'CONVERGED']

    p_sc = ax.scatter(
        valid_puts['strike'], valid_puts['tau_days'], valid_puts['iv_heston_equivalent'] * 100.0,
        c=valid_puts['iv_heston_equivalent'] * 100.0, cmap='viridis', s=45, depthshade=True,
        label=f'Identified Put IV (n={len(valid_puts)})'
    )
    if len(unid_puts) > 0:
        ax.scatter(
            unid_puts['strike'], unid_puts['tau_days'], np.zeros(len(unid_puts)),
            color='red', marker='x', s=60, label=f'Unidentifiable (n={len(unid_puts)})'
        )
    ax.set_title('American Put Equivalent Implied Volatility Surface (Heston)', fontsize=13, pad=12)
    ax.set_xlabel('Strike K (USD)', labelpad=8)
    ax.set_ylabel('Maturity (Days)', labelpad=8)
    ax.set_zlabel('American Equivalent IV (%)', labelpad=8)
    fig.colorbar(p_sc, ax=ax, shrink=0.6, aspect=12, label='Equivalent IV (%)')
    ax.legend(loc='upper left')
    fig_puts_path = fig_dir / "heston_iv_surface_puts_3d.png"
    plt.tight_layout()
    plt.savefig(fig_puts_path, dpi=300)
    plt.close()

    # Figure 2: 3D Surface Calls
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    valid_calls = df_calls_iv[df_calls_iv['status_heston_call'] == 'CONVERGED']
    unid_calls = df_calls_iv[df_calls_iv['status_heston_call'] != 'CONVERGED']

    c_sc = ax.scatter(
        valid_calls['strike'], valid_calls['tau_days'], valid_calls['iv_heston_bs'] * 100.0,
        c=valid_calls['iv_heston_bs'] * 100.0, cmap='plasma', s=45, depthshade=True,
        label=f'Identified Call IV (n={len(valid_calls)})'
    )
    if len(unid_calls) > 0:
        ax.scatter(
            unid_calls['strike'], unid_calls['tau_days'], np.zeros(len(unid_calls)),
            color='red', marker='x', s=60, label=f'Unidentifiable (n={len(unid_calls)})'
        )
    ax.set_title('European Call Black-Scholes IV Surface (Heston Model Contrast)', fontsize=13, pad=12)
    ax.set_xlabel('Strike K (USD)', labelpad=8)
    ax.set_ylabel('Maturity (Days)', labelpad=8)
    ax.set_zlabel('Black-Scholes IV (%)', labelpad=8)
    fig.colorbar(c_sc, ax=ax, shrink=0.6, aspect=12, label='BS IV (%)')
    ax.legend(loc='upper left')
    fig_calls_path = fig_dir / "heston_iv_surface_calls_3d.png"
    plt.tight_layout()
    plt.savefig(fig_calls_path, dpi=300)
    plt.close()

    # Figure 3: Volatility Smile Slices
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    slice_days = [31, 94, 430]

    for ax_idx, d_slice in enumerate(slice_days):
        ax = axes[ax_idx]
        sub_puts = df_puts_iv[(df_puts_iv['tau_days'] == d_slice) & (df_puts_iv['status_heston_inversion'] == 'CONVERGED')].sort_values('strike')
        sub_calls = df_calls_iv[(df_calls_iv['tau_days'] == d_slice) & (df_calls_iv['status_heston_call'] == 'CONVERGED')].sort_values('strike')

        if len(sub_puts) > 0:
            ax.plot(sub_puts['strike'], sub_puts['iv_heston_equivalent'] * 100.0, 'o-', color='#1f77b4', label='Heston Am Put IV', linewidth=2)
            # Market put where identifiable
            sub_puts_mkt = sub_puts[sub_puts['status_market_inversion'] == 'CONVERGED']
            if len(sub_puts_mkt) > 0:
                ax.plot(sub_puts_mkt['strike'], sub_puts_mkt['iv_market_observed'] * 100.0, 's--', color='#aec7e8', label='Market Put IV', alpha=0.8)

        if len(sub_calls) > 0:
            ax.plot(sub_calls['strike'], sub_calls['iv_heston_bs'] * 100.0, '^-', color='#d62728', label='Heston Call BS IV', linewidth=2)
            sub_calls_mkt = sub_calls[sub_calls['status_market_call'] == 'CONVERGED']
            if len(sub_calls_mkt) > 0:
                ax.plot(sub_calls_mkt['strike'], sub_calls_mkt['iv_market_bs'] * 100.0, 'v--', color='#ff9896', label='Market Call BS IV', alpha=0.8)

        ax.axvline(SPOT_PRICE, color='gray', linestyle=':', label='Spot $12.33' if ax_idx == 0 else "")
        ax.set_title(f'Tenor: {d_slice} Days', fontsize=12)
        ax.set_xlabel('Strike K (USD)')
        if ax_idx == 0:
            ax.set_ylabel('Implied Volatility (%)')
        ax.grid(True, alpha=0.3)
        if ax_idx == 0:
            ax.legend(fontsize=8, loc='upper right')

    plt.suptitle('Implied Volatility Smiles across Representative Tenors', fontsize=14, y=1.02)
    fig_slices_path = fig_dir / "heston_iv_smile_slices.png"
    plt.tight_layout()
    plt.savefig(fig_slices_path, dpi=300)
    plt.close()

    # Figure 4: 35-point descriptive grid heatmaps
    fig, (ax_p, ax_c) = plt.subplots(1, 2, figsize=(14, 6))
    grid_pivot_puts = df_grid_puts.pivot(index='strike', columns='tau_days', values='iv_equivalent') * 100.0
    grid_pivot_calls = df_grid_calls.pivot(index='strike', columns='tau_days', values='iv_bs') * 100.0

    im1 = ax_p.imshow(grid_pivot_puts.values, cmap='viridis', origin='lower', aspect='auto')
    ax_p.set_xticks(range(len(grid_days)))
    ax_p.set_xticklabels(grid_days)
    ax_p.set_yticks(range(len(grid_strikes)))
    ax_p.set_yticklabels(grid_strikes)
    ax_p.set_title('Put Equivalent IV (35-pt Grid, %)', fontsize=12)
    ax_p.set_xlabel('Maturity (Days)')
    ax_p.set_ylabel('Strike K (USD)')
    for i in range(len(grid_strikes)):
        for j in range(len(grid_days)):
            val = grid_pivot_puts.values[i, j]
            txt = f"{val:.1f}%" if not np.isnan(val) else "N/A"
            ax_p.text(j, i, txt, ha='center', va='center', color='white' if val < 60 else 'black', fontsize=9)
    fig.colorbar(im1, ax=ax_p, label='IV (%)')

    im2 = ax_c.imshow(grid_pivot_calls.values, cmap='plasma', origin='lower', aspect='auto')
    ax_c.set_xticks(range(len(grid_days)))
    ax_c.set_xticklabels(grid_days)
    ax_c.set_yticks(range(len(grid_strikes)))
    ax_c.set_yticklabels(grid_strikes)
    ax_c.set_title('Call BS IV (35-pt Grid, %)', fontsize=12)
    ax_c.set_xlabel('Maturity (Days)')
    ax_c.set_ylabel('Strike K (USD)')
    for i in range(len(grid_strikes)):
        for j in range(len(grid_days)):
            val = grid_pivot_calls.values[i, j]
            txt = f"{val:.1f}%" if not np.isnan(val) else "N/A"
            ax_c.text(j, i, txt, ha='center', va='center', color='white' if val < 60 else 'black', fontsize=9)
    fig.colorbar(im2, ax=ax_c, label='IV (%)')

    fig_grid_path = fig_dir / "heston_iv_grid_35_points.png"
    plt.tight_layout()
    plt.savefig(fig_grid_path, dpi=300)
    plt.close()
    print("All figures successfully created.")

    # 7. Summary Metrics
    print("\n--- Step 6: Computing Summary Metrics ---")
    valid_puts_both = df_puts_iv[
        (df_puts_iv['status_heston_inversion'] == 'CONVERGED') &
        (df_puts_iv['status_market_inversion'] == 'CONVERGED')
    ]
    valid_calls_both = df_calls_iv[
        (df_calls_iv['status_heston_call'] == 'CONVERGED') &
        (df_calls_iv['status_market_call'] == 'CONVERGED')
    ]

    metrics = {
        "puts_total": len(df_puts_iv),
        "puts_heston_converged": int((df_puts_iv['status_heston_inversion'] == 'CONVERGED').sum()),
        "puts_heston_unidentifiable": int((df_puts_iv['status_heston_inversion'] != 'CONVERGED').sum()),
        "puts_market_converged": int((df_puts_iv['status_market_inversion'] == 'CONVERGED').sum()),
        "puts_both_converged_for_iv_diff": len(valid_puts_both),
        "puts_price_mae_usd": float(df_puts_iv['abs_err_heston_price_usd'].mean()),
        "puts_price_rmse_usd": float(np.sqrt((df_puts_iv['abs_err_heston_price_usd'] ** 2).mean())),
        "puts_iv_mae_pct": float(valid_puts_both['abs_diff_iv_heston_vs_mkt'].mean() * 100.0) if len(valid_puts_both) > 0 else None,
        "puts_iv_rmse_pct": float(np.sqrt((valid_puts_both['abs_diff_iv_heston_vs_mkt'] ** 2).mean()) * 100.0) if len(valid_puts_both) > 0 else None,
        "calls_total": len(df_calls_iv),
        "calls_heston_converged": int((df_calls_iv['status_heston_call'] == 'CONVERGED').sum()),
        "calls_market_converged": int((df_calls_iv['status_market_call'] == 'CONVERGED').sum()),
        "calls_both_converged_for_iv_diff": len(valid_calls_both),
        "calls_price_mae_usd": float(df_calls_iv['abs_err_heston_price_usd'].mean()),
        "calls_price_rmse_usd": float(np.sqrt((df_calls_iv['abs_err_heston_price_usd'] ** 2).mean())),
        "calls_iv_mae_pct": float(valid_calls_both['abs_diff_iv_heston_vs_mkt'].mean() * 100.0) if len(valid_calls_both) > 0 else None,
        "calls_iv_rmse_pct": float(np.sqrt((valid_calls_both['abs_diff_iv_heston_vs_mkt'] ** 2).mean()) * 100.0) if len(valid_calls_both) > 0 else None,
        "grid_35_puts_converged": int((df_grid_puts['status'] == 'CONVERGED').sum()),
        "grid_35_calls_converged": int((df_grid_calls['status'] == 'CONVERGED').sum()),
        "control_cases_discrepancy_max_usd": float(df_controls['abs_diff_usd'].max()),
        "control_cases_passed_all": bool(df_controls['passed_gate'].all())
    }

    metrics_json = out_dir / "phase5_summary_metrics.json"
    with open(metrics_json, "w") as f:
        json.dump(metrics, f, indent=2)

    # 8. Execution Manifest
    manifest = {
        "phase": "PHASE_5",
        "description": "Equivalent Implied Volatility Surface from Heston Model",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_files": {
            "calibrated_parameters": {
                "path": str(calib_path),
                "sha256": compute_sha256(calib_path)
            },
            "phase4_full_puts": {
                "path": str(p4_puts_path),
                "sha256": compute_sha256(p4_puts_path)
            },
            "calls_contrast": {
                "path": str(calls_split_path),
                "sha256": compute_sha256(calls_split_path)
            }
        },
        "output_files": {
            "control_cases_1d_quantlib": {
                "path": str(controls_csv),
                "rows": len(df_controls),
                "sha256": compute_sha256(controls_csv)
            },
            "mesh_sensitivity_1d_controls": {
                "path": str(mesh_sens_csv),
                "rows": len(df_mesh_sens),
                "sha256": compute_sha256(mesh_sens_csv)
            },
            "heston_iv_surface_97_puts": {
                "path": str(puts_iv_csv),
                "rows": len(df_puts_iv),
                "sha256": compute_sha256(puts_iv_csv)
            },
            "heston_iv_surface_142_calls": {
                "path": str(calls_iv_csv),
                "rows": len(df_calls_iv),
                "sha256": compute_sha256(calls_iv_csv)
            },
            "heston_descriptive_grid_35_puts": {
                "path": str(grid_puts_csv),
                "rows": len(df_grid_puts),
                "sha256": compute_sha256(grid_puts_csv)
            },
            "heston_descriptive_grid_35_calls": {
                "path": str(grid_calls_csv),
                "rows": len(df_grid_calls),
                "sha256": compute_sha256(grid_calls_csv)
            },
            "phase5_summary_metrics": {
                "path": str(metrics_json),
                "sha256": compute_sha256(metrics_json)
            }
        },
        "figures": [
            str(fig_puts_path),
            str(fig_calls_path),
            str(fig_slices_path),
            str(fig_grid_path)
        ],
        "calibrated_parameters_used": params_dict,
        "runtime_seconds": round(time.time() - start_time, 2)
    }

    manifest_json = out_dir / "phase5_execution_manifest.json"
    with open(manifest_json, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest successfully compiled at {manifest_json}")
    print(f"Phase 5 Pipeline completed in {manifest['runtime_seconds']} seconds.")
    print("=" * 80)
    return manifest


if __name__ == "__main__":
    run_phase5_pipeline()
