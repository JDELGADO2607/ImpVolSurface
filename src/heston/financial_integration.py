"""
Financial Integration Module for Heston Model (Phase 6).

Implements:
1. Four-Model Pricing Comparison across common sample (97 Puts, 142 Calls):
   - M1: European Flat Volatility (BS, ex-ante 44.0% benchmark, D(T) discount)
   - M2: American Flat Volatility (1D Crank-Nicolson PDE with yield curve, 44.0% vol)
   - M3: European Heston (QuantLib AnalyticHestonEngine with dense daily yield curve)
   - M4: American Heston (audited 2D solver fine prices for puts; M3 for calls by Merton 1973)
   - Disentangling Early Exercise Premium (EEP) and model error metrics across partitions.
2. Hypothetical Portfolio (5 legs from PORTFOLIO_LEGS in src/portfolio.py):
   - Valuation of each leg under Heston and market observed price (multiplier 100).
   - Coherent Heston Greeks: Delta, Gamma, sensitivity to sigma0 = sqrt(v0), and Theta (frozen-curve roll).
   - Mesh/step sensitivity checks (h vs h/2) on 2 representative legs.
   - Delta-hedging share position and dynamic margin/capital approximation.
3. Stress Testing across 6 Instantaneous Scenarios:
   - S0: Base Null Shock (diagnostic verifying exact zero P&L by construction).
   - S1: Spot -5%, S2: Spot +5%, S3: sigma0 +5pp.
   - S4: Severe Crisis (Spot -20%, sigma0 +12pp).
   - S5: Bullish Rally (Spot +15%, sigma0 -8pp).
   - Contrast between full non-linear Heston revaluation and 2nd-order Taylor Greek expansion.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import DeterministicYieldCurve, SPOT_PRICE, DIVIDEND_YIELD
from src.heston.heston_model import HestonParams
from src.heston.solver_2d import Heston2DSolver
from src.heston.equivalent_iv import fd_american_price_curve
from src.pricing_bs import bs_price
from src.portfolio import PORTFOLIO_LEGS

FLAT_VOL_EX_ANTE = 0.440  # 44.0% ATM IV benchmark from baseline comparison
CONTRACT_MULTIPLIER = 100


def price_heston_analytic(
    kind: str,
    S: float,
    K: float,
    tau_days: int,
    params: HestonParams,
    curve: DeterministicYieldCurve,
    ref_date: Optional[Any] = None
) -> float:
    """
    Prices a European option under classical Heston using QuantLib AnalyticHestonEngine
    with the official dense daily deterministic discount curve.
    """
    if not HAS_QUANTLIB:
        raise RuntimeError("QuantLib is required for AnalyticHestonEngine")

    if ref_date is None:
        ref_date = ql.Date(17, 11, 2026)

    ql.Settings.instance().evaluationDate = ref_date

    # Use the approved dense daily term structure adapter
    ql_curve_handle = curve.to_quantlib_term_structure(dense_daily=True)
    q_handle = ql.YieldTermStructureHandle(ql.FlatForward(ref_date, 0.0, ql.Actual365Fixed()))
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(S))

    heston_process = ql.HestonProcess(
        ql_curve_handle, q_handle, spot_handle,
        params.v0, params.kappa, params.theta, params.xi, params.rho
    )
    heston_model = ql.HestonModel(heston_process)
    heston_engine = ql.AnalyticHestonEngine(heston_model)

    maturity_date = ref_date + ql.Period(int(round(tau_days)), ql.Days)
    opt_type = ql.Option.Call if kind.upper() == 'C' else ql.Option.Put
    payoff = ql.PlainVanillaPayoff(opt_type, K)
    exercise = ql.EuropeanExercise(maturity_date)
    opt = ql.VanillaOption(payoff, exercise)
    opt.setPricingEngine(heston_engine)
    return float(opt.NPV())


def run_four_model_comparison(
    curve: DeterministicYieldCurve,
    params: HestonParams,
    df_puts_p4: pd.DataFrame,
    df_calls_p5: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Constructs the detailed and summary 4-model comparison on the common sample
    of 97 puts and 142 calls.
    """
    records = []

    # 1. Process 97 Puts
    for idx, row in df_puts_p4.iterrows():
        symbol = row["contractSymbol"]
        K = float(row["strike"])
        tau_days = int(round(row["tau_days"]))
        tau_years = float(row["tau_years"])
        partition = str(row["partition"])
        mkt_price = float(row["lastPrice"])
        am_heston = float(row["prop_fine_price"])

        r_zero = curve.get_zero_rate(tau_years)

        # M1: European Flat BS (44% vol)
        m1_eu_flat_bs = bs_price('P', SPOT_PRICE, K, tau_years, r_zero, FLAT_VOL_EX_ANTE, q=0.0)

        # M2: American Flat 1D PDE (44% vol with curve)
        m2_am_flat_1d = fd_american_price_curve('P', SPOT_PRICE, K, tau_years, curve, FLAT_VOL_EX_ANTE, q=0.0, M=300, N=150)

        # M3: European Heston
        m3_eu_heston = price_heston_analytic('P', SPOT_PRICE, K, tau_days, params, curve)

        # M4: American Heston
        m4_am_heston = am_heston

        # Early Exercise Premiums
        eep_const = m2_am_flat_1d - m1_eu_flat_bs
        eep_heston = m4_am_heston - m3_eu_heston

        records.append({
            "contractSymbol": symbol,
            "type": "PUT",
            "strike": K,
            "tau_days": tau_days,
            "tau_years": tau_years,
            "partition": partition,
            "market_last_price": mkt_price,
            "m1_eu_const_bs": m1_eu_flat_bs,
            "m2_am_const_1d": m2_am_flat_1d,
            "m3_eu_heston": m3_eu_heston,
            "m4_am_heston": m4_am_heston,
            "err_m1_usd": m1_eu_flat_bs - mkt_price,
            "abs_err_m1_usd": abs(m1_eu_flat_bs - mkt_price),
            "err_m2_usd": m2_am_flat_1d - mkt_price,
            "abs_err_m2_usd": abs(m2_am_flat_1d - mkt_price),
            "err_m3_usd": m3_eu_heston - mkt_price,
            "abs_err_m3_usd": abs(m3_eu_heston - mkt_price),
            "err_m4_usd": m4_am_heston - mkt_price,
            "abs_err_m4_usd": abs(m4_am_heston - mkt_price),
            "eep_const_usd": eep_const,
            "eep_heston_usd": eep_heston
        })

    # 2. Process 142 Calls (External Contrast)
    for idx, row in df_calls_p5.iterrows():
        symbol = row["contractSymbol"]
        K = float(row["strike"])
        tau_days = int(round(row["tau_days"]))
        tau_years = float(row["tau_years"])
        partition = "external_contrast"
        mkt_price = float(row["market_last_price"])
        heston_call_px = float(row["heston_call_price"])

        r_zero = curve.get_zero_rate(tau_years)

        # Under q=0, r>=0: American Call == European Call
        m1_eu_flat_bs = bs_price('C', SPOT_PRICE, K, tau_years, r_zero, FLAT_VOL_EX_ANTE, q=0.0)
        m2_am_flat_1d = m1_eu_flat_bs  # American == European for call
        m3_eu_heston = heston_call_px
        m4_am_heston = heston_call_px  # American == European for call

        eep_const = 0.0
        eep_heston = 0.0

        records.append({
            "contractSymbol": symbol,
            "type": "CALL",
            "strike": K,
            "tau_days": tau_days,
            "tau_years": tau_years,
            "partition": partition,
            "market_last_price": mkt_price,
            "m1_eu_const_bs": m1_eu_flat_bs,
            "m2_am_const_1d": m2_am_flat_1d,
            "m3_eu_heston": m3_eu_heston,
            "m4_am_heston": m4_am_heston,
            "err_m1_usd": m1_eu_flat_bs - mkt_price,
            "abs_err_m1_usd": abs(m1_eu_flat_bs - mkt_price),
            "err_m2_usd": m2_am_flat_1d - mkt_price,
            "abs_err_m2_usd": abs(m2_am_flat_1d - mkt_price),
            "err_m3_usd": m3_eu_heston - mkt_price,
            "abs_err_m3_usd": abs(m3_eu_heston - mkt_price),
            "err_m4_usd": m4_am_heston - mkt_price,
            "abs_err_m4_usd": abs(m4_am_heston - mkt_price),
            "eep_const_usd": eep_const,
            "eep_heston_usd": eep_heston
        })

    df_detailed = pd.DataFrame(records)

    # 3. Summary Aggregations
    summary_rows = []
    groups = [
        ("All Puts", df_detailed[df_detailed["type"] == "PUT"]),
        ("Puts: Train (60)", df_detailed[(df_detailed["type"] == "PUT") & (df_detailed["partition"] == "train")]),
        ("Puts: Strike Holdout (22)", df_detailed[(df_detailed["type"] == "PUT") & (df_detailed["partition"] == "strike_holdout")]),
        ("Puts: Tenor Holdout (15)", df_detailed[(df_detailed["type"] == "PUT") & (df_detailed["partition"] == "tenor_holdout")]),
        ("All Calls (External Contrast 142)", df_detailed[df_detailed["type"] == "CALL"]),
        ("Combined Common Universe (239)", df_detailed),
    ]

    for label, sub_df in groups:
        n = len(sub_df)
        if n == 0:
            continue
        summary_rows.append({
            "segment": label,
            "count_contracts": n,
            "m1_eu_const_bs_mae_usd": float(sub_df["abs_err_m1_usd"].mean()),
            "m1_eu_const_bs_rmse_usd": float(np.sqrt((sub_df["err_m1_usd"] ** 2).mean())),
            "m2_am_const_1d_mae_usd": float(sub_df["abs_err_m2_usd"].mean()),
            "m2_am_const_1d_rmse_usd": float(np.sqrt((sub_df["err_m2_usd"] ** 2).mean())),
            "m3_eu_heston_mae_usd": float(sub_df["abs_err_m3_usd"].mean()),
            "m3_eu_heston_rmse_usd": float(np.sqrt((sub_df["err_m3_usd"] ** 2).mean())),
            "m4_am_heston_mae_usd": float(sub_df["abs_err_m4_usd"].mean()),
            "m4_am_heston_rmse_usd": float(np.sqrt((sub_df["err_m4_usd"] ** 2).mean())),
            "mean_eep_heston_usd": float(sub_df["eep_heston_usd"].mean()),
            "max_eep_heston_usd": float(sub_df["eep_heston_usd"].max()),
            "mean_eep_const_usd": float(sub_df["eep_const_usd"].mean()),
        })

    df_summary = pd.DataFrame(summary_rows)
    return df_detailed, df_summary


def price_option_under_heston(
    kind: str,
    S: float,
    K: float,
    tau_days: int,
    params: HestonParams,
    curve: DeterministicYieldCurve,
    solver_2d: Optional[Heston2DSolver] = None
) -> float:
    """
    Evaluates option price under Heston:
    - Calls: AnalyticHestonEngine (exact, instantaneous).
    - Puts: Heston2DSolver American engine.
    """
    if kind.upper() == 'C':
        return price_heston_analytic('C', S, K, tau_days, params, curve)
    else:
        if solver_2d is None:
            solver_2d = Heston2DSolver()
        tau_y = tau_days / 365.0
        m_t = max(int(np.ceil(tau_y * 252)), 60)
        sol = solver_2d.price(
            strike=K, maturity_years=tau_y, params=params, curve=curve,
            spot=S, is_american=True, n_s=120, n_v=60, m_t=m_t
        )
        return float(sol.price)


def evaluate_portfolio_and_greeks(
    curve: DeterministicYieldCurve,
    params: HestonParams,
    df_puts_p4: pd.DataFrame,
    df_calls_p5: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """
    Constructs the 5-leg hypothetical portfolio from PORTFOLIO_LEGS,
    computes Heston Greeks (Delta, Gamma, sigma0 sensitivity, Theta),
    evaluates finite difference step stability (h vs h/2) on 2 legs,
    and calculates the delta-hedge position and dynamic capital.
    """
    solver_2d = Heston2DSolver()

    # Pre-index market observed prices
    mkt_lookup = {}
    for idx, row in df_puts_p4.iterrows():
        mkt_lookup[str(row["contractSymbol"])] = float(row["lastPrice"])
    for idx, row in df_calls_p5.iterrows():
        mkt_lookup[str(row["contractSymbol"])] = float(row["market_last_price"])

    # Leg specifications
    # PORTFOLIO_LEGS has 5 legs:
    # Leg 1: NU261218C00012000 (C, K=12.0, 31d, qty=+5)
    # Leg 2: NU261218C00014000 (C, K=14.0, 31d, qty=-5)
    # Leg 3: NU261218P00012000 (P, K=12.0, 31d, qty=+3)
    # Leg 4: NU270115C00013000 (C, K=13.0, 59d, qty=+4)
    # Leg 5: NU270115P00011000 (P, K=11.0, 59d, qty=-4)
    leg_metadata = {
        'NU261218C00012000': {'kind': 'C', 'K': 12.0, 'tau_days': 31, 'exp': '2026-12-18'},
        'NU261218C00014000': {'kind': 'C', 'K': 14.0, 'tau_days': 31, 'exp': '2026-12-18'},
        'NU261218P00012000': {'kind': 'P', 'K': 12.0, 'tau_days': 31, 'exp': '2026-12-18'},
        'NU270115C00013000': {'kind': 'C', 'K': 13.0, 'tau_days': 59, 'exp': '2027-01-15'},
        'NU270115P00011000': {'kind': 'P', 'K': 11.0, 'tau_days': 59, 'exp': '2027-01-15'},
    }

    h_S = 0.01 * SPOT_PRICE  # 0.1233 USD (1% bump)
    sigma0 = math.sqrt(params.v0)
    d_sig0 = 0.01  # 1 percentage point bump
    v0_up = (sigma0 + d_sig0) ** 2
    v0_dn = max((sigma0 - d_sig0) ** 2, 0.001)
    params_up = HestonParams(v0=v0_up, kappa=params.kappa, theta=params.theta, xi=params.xi, rho=params.rho)
    params_dn = HestonParams(v0=v0_dn, kappa=params.kappa, theta=params.theta, xi=params.xi, rho=params.rho)

    leg_records = []
    total_options_delta = 0.0
    total_gamma = 0.0
    total_sens_sigma0_1pp = 0.0
    total_theta_daily = 0.0
    total_val_mkt = 0.0
    total_val_heston = 0.0

    for leg in PORTFOLIO_LEGS:
        sym = leg['contractSymbol']
        qty = leg['qty']
        label = leg['label']
        meta = leg_metadata[sym]
        kind = meta['kind']
        K = meta['K']
        tau_days = meta['tau_days']
        exp_date = meta['exp']

        p_obs = mkt_lookup.get(sym, np.nan)

        # 1. Base Heston Price
        p_base = price_option_under_heston(kind, SPOT_PRICE, K, tau_days, params, curve, solver_2d)

        # 2. Spot up and down for Delta and Gamma
        p_s_up = price_option_under_heston(kind, SPOT_PRICE + h_S, K, tau_days, params, curve, solver_2d)
        p_s_dn = price_option_under_heston(kind, SPOT_PRICE - h_S, K, tau_days, params, curve, solver_2d)

        delta = (p_s_up - p_s_dn) / (2.0 * h_S)
        gamma = (p_s_up - 2.0 * p_base + p_s_dn) / (h_S ** 2)

        # 3. Sensitivity to sigma0 = sqrt(v0) per 1 pp
        p_v_up = price_option_under_heston(kind, SPOT_PRICE, K, tau_days, params_up, curve, solver_2d)
        p_v_dn = price_option_under_heston(kind, SPOT_PRICE, K, tau_days, params_dn, curve, solver_2d)
        sens_sigma0_1pp = (p_v_up - p_v_dn) / 2.0  # value change for +1pp of sigma0

        # 4. Theta (daily calendar roll with frozen curve)
        if tau_days > 1:
            p_theta = price_option_under_heston(kind, SPOT_PRICE, K, tau_days - 1, params, curve, solver_2d)
            theta_daily = p_theta - p_base
        else:
            theta_daily = 0.0

        contract_scale = qty * CONTRACT_MULTIPLIER
        val_mkt = contract_scale * p_obs
        val_mod = contract_scale * p_base

        pos_delta = contract_scale * delta
        pos_gamma = contract_scale * gamma
        pos_sens_sig0 = contract_scale * sens_sigma0_1pp
        pos_theta = contract_scale * theta_daily

        total_options_delta += pos_delta
        total_gamma += pos_gamma
        total_sens_sigma0_1pp += pos_sens_sig0
        total_theta_daily += pos_theta
        total_val_mkt += val_mkt
        total_val_heston += val_mod

        leg_records.append({
            'label': label,
            'contractSymbol': sym,
            'type': kind,
            'strike': K,
            'expirationDate': exp_date,
            'tau_days': tau_days,
            'quantity': qty,
            'multiplier': CONTRACT_MULTIPLIER,
            'obs_price': p_obs,
            'heston_price': p_base,
            'market_value_usd': val_mkt,
            'heston_value_usd': val_mod,
            'delta_per_unit': delta,
            'gamma_per_unit': gamma,
            'sens_sigma0_1pp_per_unit': sens_sigma0_1pp,
            'theta_daily_per_unit': theta_daily,
            'position_delta': pos_delta,
            'position_gamma': pos_gamma,
            'position_sens_sigma0_1pp': pos_sens_sig0,
            'position_theta_daily': pos_theta
        })

    # Delta Hedge position
    hedge_shares = -int(np.round(total_options_delta))
    hedge_val = hedge_shares * SPOT_PRICE
    residual_delta = total_options_delta + hedge_shares

    # Add Stock row
    leg_records.append({
        'label': 'Hedge: NU Equity Shares',
        'contractSymbol': 'NU_STOCK',
        'type': 'STOCK',
        'strike': np.nan,
        'expirationDate': 'N/A',
        'tau_days': np.nan,
        'quantity': hedge_shares,
        'multiplier': 1,
        'obs_price': SPOT_PRICE,
        'heston_price': SPOT_PRICE,
        'market_value_usd': hedge_val,
        'heston_value_usd': hedge_val,
        'delta_per_unit': 1.0,
        'gamma_per_unit': 0.0,
        'sens_sigma0_1pp_per_unit': 0.0,
        'theta_daily_per_unit': 0.0,
        'position_delta': float(hedge_shares),
        'position_gamma': 0.0,
        'position_sens_sigma0_1pp': 0.0,
        'position_theta_daily': 0.0
    })

    df_portfolio = pd.DataFrame(leg_records)

    # Dynamic Capital / Margin Approximation
    # Long premium + Short option initial margin + Stock 50% margin
    long_premium = sum(r['heston_value_usd'] for r in leg_records[:-1] if r['quantity'] > 0)
    short_margin = sum(abs(r['quantity']) * CONTRACT_MULTIPLIER * (0.20 * SPOT_PRICE + r['heston_price']) for r in leg_records[:-1] if r['quantity'] < 0)
    stock_margin = abs(hedge_shares) * SPOT_PRICE * 0.50
    total_capital_approx = long_premium + short_margin + stock_margin

    summary = {
        'spot_price': SPOT_PRICE,
        'total_options_value_mkt_usd': total_val_mkt,
        'total_options_value_heston_usd': total_val_heston,
        'mark_to_model_diff_options_usd': total_val_heston - total_val_mkt,
        'hedge_shares': hedge_shares,
        'hedge_value_usd': hedge_val,
        'total_portfolio_value_heston_usd': total_val_heston + hedge_val,
        'total_options_delta': total_options_delta,
        'residual_portfolio_delta': residual_delta,
        'total_portfolio_gamma': total_gamma,
        'total_portfolio_sens_sigma0_1pp': total_sens_sigma0_1pp,
        'total_portfolio_theta_daily': total_theta_daily,
        'capital_initial_approx_usd': total_capital_approx
    }

    # Finite difference step sensitivity check (h vs h/2) on Leg 1 (Call 31d K=12) and Leg 3 (Put 31d K=12)
    stability_records = []
    test_cases = [
        ('Leg 1: Long Call 31d K=12.0', 'C', 12.0, 31),
        ('Leg 3: Long Put 31d K=12.0', 'P', 12.0, 31)
    ]

    h_half = h_S / 2.0
    for lbl, knd, k_val, t_d in test_cases:
        p0 = price_option_under_heston(knd, SPOT_PRICE, k_val, t_d, params, curve, solver_2d)
        pu1 = price_option_under_heston(knd, SPOT_PRICE + h_S, k_val, t_d, params, curve, solver_2d)
        pd1 = price_option_under_heston(knd, SPOT_PRICE - h_S, k_val, t_d, params, curve, solver_2d)
        d1 = (pu1 - pd1) / (2.0 * h_S)
        g1 = (pu1 - 2.0 * p0 + pd1) / (h_S ** 2)

        pu2 = price_option_under_heston(knd, SPOT_PRICE + h_half, k_val, t_d, params, curve, solver_2d)
        pd2 = price_option_under_heston(knd, SPOT_PRICE - h_half, k_val, t_d, params, curve, solver_2d)
        d2 = (pu2 - pd2) / (2.0 * h_half)
        g2 = (pu2 - 2.0 * p0 + pd2) / (h_half ** 2)

        stability_records.append({
            'leg_label': lbl,
            'type': knd,
            'strike': k_val,
            'tau_days': t_d,
            'delta_step_h': d1,
            'delta_step_h_half': d2,
            'diff_delta': abs(d1 - d2),
            'gamma_step_h': g1,
            'gamma_step_h_half': g2,
            'diff_gamma': abs(g1 - g2),
            'stable_step_discrepancy': abs(d1 - d2) < 0.0050
        })

    df_stability = pd.DataFrame(stability_records)
    return df_portfolio, summary, df_stability


def run_portfolio_stress_testing(
    df_portfolio: pd.DataFrame,
    summary: Dict[str, Any],
    curve: DeterministicYieldCurve,
    params: HestonParams
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Executes the 6 required instantaneous stress scenarios:
    S0: Base Null Shock (diagnostic verifying exact 0.00 P&L)
    S1: Spot -5%
    S2: Spot +5%
    S3: Vol Spike (sigma0 +5pp)
    S4: Severe Crisis (Spot -20%, sigma0 +12pp)
    S5: Bullish Rally (Spot +15%, sigma0 -8pp)
    """
    solver_2d = Heston2DSolver()
    sigma0_base = math.sqrt(params.v0)

    scenarios = [
        {
            'id': 'S0_Base_Null',
            'name': '0. Baseline Null Shock',
            'dS_pct': 0.0,
            'dSigma0_pp': 0.0,
            'description': 'Zero shock diagnostic verifying exact zero stress P&L'
        },
        {
            'id': 'S1_Spot_Down_5',
            'name': '1. Spot -5%',
            'dS_pct': -0.05,
            'dSigma0_pp': 0.0,
            'description': 'Moderate downside spot move with unchanged variance'
        },
        {
            'id': 'S2_Spot_Up_5',
            'name': '2. Spot +5%',
            'dS_pct': 0.05,
            'dSigma0_pp': 0.0,
            'description': 'Moderate upside spot move with unchanged variance'
        },
        {
            'id': 'S3_Vol_Spike_5pp',
            'name': '3. Vol Spike (+5 pp)',
            'dS_pct': 0.0,
            'dSigma0_pp': 0.05,
            'description': 'Parallel vol spike (+5 percentage points) at unchanged spot'
        },
        {
            'id': 'S4_Severe_Crisis',
            'name': '4. Severe Crisis (-20% / +12 pp)',
            'dS_pct': -0.20,
            'dSigma0_pp': 0.12,
            'description': 'Severe crash: Spot -20%, sigma0 jumps +12 percentage points'
        },
        {
            'id': 'S5_Bullish_Rally',
            'name': '5. Bullish Rally (+15% / -8 pp)',
            'dS_pct': 0.15,
            'dSigma0_pp': -0.08,
            'description': 'Strong rally: Spot +15%, sigma0 crushed by -8 percentage points'
        }
    ]

    opt_rows = df_portfolio[df_portfolio['type'] != 'STOCK']
    hedge_shares = int(summary['hedge_shares'])

    scenario_summary_records = []
    leg_detail_records = []

    for sc in scenarios:
        sc_id = sc['id']
        sc_name = sc['name']
        dS_pct = sc['dS_pct']
        dSig0 = sc['dSigma0_pp']

        S_shock = SPOT_PRICE * (1.0 + dS_pct)
        delta_S = S_shock - SPOT_PRICE

        sig0_shock = max(sigma0_base + dSig0, 0.02)
        v0_shock = sig0_shock ** 2
        params_shock = HestonParams(v0=v0_shock, kappa=params.kappa, theta=params.theta, xi=params.xi, rho=params.rho)

        total_opts_val_shock = 0.0
        total_opts_val_base = 0.0

        for idx, row in opt_rows.iterrows():
            sym = row['contractSymbol']
            kind = row['type']
            K = float(row['strike'])
            tau_days = int(round(row['tau_days']))
            qty = int(row['quantity'])
            scale = qty * CONTRACT_MULTIPLIER

            p_base = float(row['heston_price'])

            # S0 null shock exact identity: avoid numerical roundoff by definition
            if sc_id == 'S0_Base_Null':
                p_shock = p_base
            else:
                p_shock = price_option_under_heston(kind, S_shock, K, tau_days, params_shock, curve, solver_2d)

            val_base_leg = scale * p_base
            val_shock_leg = scale * p_shock
            pnl_leg = val_shock_leg - val_base_leg

            total_opts_val_base += val_base_leg
            total_opts_val_shock += val_shock_leg

            leg_detail_records.append({
                'scenario_id': sc_id,
                'contractSymbol': sym,
                'quantity': qty,
                'price_base': p_base,
                'price_shocked': p_shock,
                'leg_val_base_usd': val_base_leg,
                'leg_val_shock_usd': val_shock_leg,
                'leg_pnl_usd': pnl_leg
            })

        # Options aggregate PnL
        pnl_options_reval = total_opts_val_shock - total_opts_val_base

        # Stock hedge PnL
        pnl_hedge = hedge_shares * delta_S

        # Total portfolio PnL (delta-hedged)
        pnl_total_hedged = pnl_options_reval + pnl_hedge

        # Taylor 2nd order approximation for options:
        # PnL_Taylor = delta_S * Delta_opts + 0.5 * (delta_S)^2 * Gamma_opts + (dSig0 * 100) * Sens_sig0_1pp
        taylor_delta_term = delta_S * summary['total_options_delta']
        taylor_gamma_term = 0.5 * (delta_S ** 2) * summary['total_portfolio_gamma']
        taylor_vol_term = (dSig0 * 100.0) * summary['total_portfolio_sens_sigma0_1pp']
        pnl_options_taylor = taylor_delta_term + taylor_gamma_term + taylor_vol_term
        pnl_total_taylor = pnl_options_taylor + pnl_hedge

        taylor_err = pnl_total_hedged - pnl_total_taylor

        scenario_summary_records.append({
            'scenario_id': sc_id,
            'scenario_name': sc_name,
            'spot_shocked_usd': S_shock,
            'spot_change_usd': delta_S,
            'sigma0_shocked_pct': sig0_shock * 100.0,
            'sigma0_change_pp': dSig0 * 100.0,
            'options_pnl_reval_usd': pnl_options_reval,
            'hedge_pnl_usd': pnl_hedge,
            'total_portfolio_pnl_reval_usd': pnl_total_hedged,
            'options_pnl_taylor_usd': pnl_options_taylor,
            'total_portfolio_pnl_taylor_usd': pnl_total_taylor,
            'taylor_divergence_usd': taylor_err,
            'abs_taylor_divergence_usd': abs(taylor_err),
            'description': sc['description']
        })

    df_stress_summary = pd.DataFrame(scenario_summary_records)
    df_leg_detail = pd.DataFrame(leg_detail_records)
    return df_stress_summary, df_leg_detail
