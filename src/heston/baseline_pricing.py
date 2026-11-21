"""
Baseline pricing engine for NU Equity American options under constant volatility and frozen SVI.

Disentangles rate curve revision from option model and numerical solver differences (F0-02):
1. Pure Curve Effect: Evaluates identical model, sigma and engine on Official 11/17 curve vs Historical R3 curve.
2. Engine Discrepancy: Compares QuantLib 1.44 vs Repo Crank-Nicolson PDE under identical curves.
3. Historical Published SVI Benchmark: Preserves the audited R3 reference values (3d81ff1) as an independent baseline.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from scipy.stats import norm

from src.heston.rates_curve import (
    SPOT_PRICE,
    DIVIDEND_YIELD,
    DeterministicYieldCurve,
    get_official_yield_curve,
    HISTORICAL_R3_PAR_CURVE,
    OFFICIAL_TREASURY_CMT_2026_11_17
)

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
    QUANTLIB_VERSION = ql.__version__
except ImportError:
    HAS_QUANTLIB = False
    QUANTLIB_VERSION = None

from src.pricing_american_fd import price_american_option


def price_bs_european_put(S0: float, K: float, tau: float, r: float, sigma: float = 0.45, q: float = 0.0) -> float:
    """
    Analytic Black-Scholes European put price.
    """
    if tau <= 1e-8:
        return max(K - S0, 0.0)
    if sigma <= 1e-8:
        return max(K * np.exp(-r * tau) - S0 * np.exp(-q * tau), 0.0)

    d1 = (np.log(S0 / K) + (r - q + 0.5 * sigma**2) * tau) / (sigma * np.sqrt(tau))
    d2 = d1 - sigma * np.sqrt(tau)

    put_price = K * np.exp(-r * tau) * norm.cdf(-d2) - S0 * np.exp(-q * tau) * norm.cdf(-d1)
    return float(max(put_price, 0.0))


def price_american_put_quantlib(
    S0: float,
    K: float,
    tau: float,
    r: float,
    sigma: float = 0.45,
    q: float = 0.0,
    exp_date_str: Optional[str] = None,
    term_structure: Optional[Any] = None,
    time_steps: int = 150,
    grid_points: int = 150
) -> float:
    """
    Prices an American put option using QuantLib's FdBlackScholesVanillaEngine.
    Supports either a contract-specific rate r or a full YieldTermStructureHandle.
    """
    if not HAS_QUANTLIB:
        return price_american_option(kind="P", S=S0, K=K, tau=tau, r=r, q=q, sigma=sigma, M=grid_points, N=time_steps)

    if tau <= 1e-6:
        return max(K - S0, 0.0)

    calendar = ql.NullCalendar()
    day_counter = ql.Actual365Fixed()
    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date

    if exp_date_str:
        dt = datetime.strptime(exp_date_str, "%Y-%m-%d")
        exp_date = ql.Date(dt.day, dt.month, dt.year)
    else:
        days = int(round(tau * 365.0))
        exp_date = eval_date + days

    payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
    exercise = ql.AmericanExercise(eval_date, exp_date)
    option = ql.VanillaOption(payoff, exercise)

    spot_handle = ql.QuoteHandle(ql.SimpleQuote(S0))
    div_handle = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, q, day_counter))
    vol_handle = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(eval_date, calendar, sigma, day_counter))

    if term_structure is not None:
        rate_handle = term_structure
    else:
        rate_handle = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, r, day_counter))

    bs_process = ql.BlackScholesMertonProcess(spot_handle, div_handle, rate_handle, vol_handle)
    engine = ql.FdBlackScholesVanillaEngine(bs_process, time_steps, grid_points)
    option.setPricingEngine(engine)

    price = option.NPV()
    return float(max(price, max(K - S0, 0.0)))


def compute_baseline_benchmarks(
    puts_df: pd.DataFrame,
    curve_official: Optional[DeterministicYieldCurve] = None,
    output_dir: Optional[str] = "data/heston"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates baseline price comparisons with clean separation of:
    1. Pure rate curve ablation (same engine and sigma, varying only rates)
    2. Engine discrepancy (QuantLib vs Repo Crank-Nicolson PDE under identical rates)
    3. Historical audited R3 benchmark
    """
    if curve_official is None:
        curve_official = get_official_yield_curve(method="bootstrap")

    curve_r3 = DeterministicYieldCurve(HISTORICAL_R3_PAR_CURVE, method="par_conversion")

    # Load frozen SVI published benchmark from R3 if available
    svi_lookup = {}
    mc_path = Path("outputs/tables/model_comparison_detailed.csv")
    if mc_path.exists():
        df_mc = pd.read_csv(mc_path)
        for _, row in df_mc.iterrows():
            svi_lookup[row["contractSymbol"]] = {
                "m4_am_surf": row["m4_am_surf"],
                "sigma_surface": row["sigma_surface"],
                "err_m4": row["err_m4"]
            }

    records = []
    for _, row in puts_df.iterrows():
        contract = row["contractSymbol"]
        K = float(row["strike"])
        tau = float(row["tau_years"])
        p_market = float(row["lastPrice"])
        exp_date_s = str(row["expirationDate"])
        k_mon = float(row["k_log_moneyness"]) if "k_log_moneyness" in row else np.log(K / (SPOT_PRICE * np.exp(0.04 * tau)))

        r_off = curve_official.get_zero_rate(tau)
        r_r3 = curve_r3.get_zero_rate(tau)

        # 1. European BS Flat 45% (Pure curve ablation)
        p_eu_flat_off = price_bs_european_put(SPOT_PRICE, K, tau, r_off, sigma=0.45, q=DIVIDEND_YIELD)
        p_eu_flat_r3 = price_bs_european_put(SPOT_PRICE, K, tau, r_r3, sigma=0.45, q=DIVIDEND_YIELD)
        rate_effect_eu_usd = p_eu_flat_off - p_eu_flat_r3

        # 2. American Flat 45% under QuantLib 1.44 (Pure curve ablation)
        p_am_ql_off = price_american_put_quantlib(SPOT_PRICE, K, tau, r_off, sigma=0.45, q=DIVIDEND_YIELD, exp_date_str=exp_date_s)
        p_am_ql_r3 = price_american_put_quantlib(SPOT_PRICE, K, tau, r_r3, sigma=0.45, q=DIVIDEND_YIELD, exp_date_str=exp_date_s)
        rate_effect_am_ql_usd = p_am_ql_off - p_am_ql_r3

        # 3. American Flat 45% under Repo PDE (Pure curve ablation)
        p_am_pde_off = price_american_option("P", SPOT_PRICE, K, tau, r_off, sigma=0.45)
        p_am_pde_r3 = price_american_option("P", SPOT_PRICE, K, tau, r_r3, sigma=0.45)
        rate_effect_am_pde_usd = p_am_pde_off - p_am_pde_r3

        # Discrepancy between QuantLib and Repo PDE under identical official rates
        engine_disc_am_flat_usd = p_am_ql_off - p_am_pde_off

        # 4. SVI Surface Evaluation:
        if contract in svi_lookup:
            p_svi_r3_pub = float(svi_lookup[contract]["m4_am_surf"])
            sigma_svi = float(svi_lookup[contract]["sigma_surface"])
            # Pure curve ablation on SVI using the SAME Repo PDE engine
            p_svi_pde_off = price_american_option("P", SPOT_PRICE, K, tau, r_off, sigma=sigma_svi)
            p_svi_pde_r3 = price_american_option("P", SPOT_PRICE, K, tau, r_r3, sigma=sigma_svi)
            rate_effect_svi_pure_pde_usd = p_svi_pde_off - p_svi_pde_r3

            # SVI under QuantLib with official rates
            p_svi_ql_off = price_american_put_quantlib(SPOT_PRICE, K, tau, r_off, sigma=sigma_svi, q=DIVIDEND_YIELD, exp_date_str=exp_date_s)
            engine_disc_svi_usd = p_svi_ql_off - p_svi_pde_off
        else:
            p_svi_r3_pub = np.nan
            sigma_svi = np.nan
            p_svi_pde_off = np.nan
            p_svi_pde_r3 = np.nan
            rate_effect_svi_pure_pde_usd = np.nan
            p_svi_ql_off = np.nan
            engine_disc_svi_usd = np.nan

        eep_off = p_am_ql_off - p_eu_flat_off

        records.append({
            "contractSymbol": contract,
            "strike": K,
            "expirationDate": exp_date_s,
            "tau_days": row["tau_days"],
            "tau_years": tau,
            "k_log_moneyness": k_mon,
            "lastPrice": p_market,
            "r_official_zero": r_off,
            "r_historical_r3": r_r3,
            # European BS Flat 45%
            "p_eu_flat_official": p_eu_flat_off,
            "p_eu_flat_r3": p_eu_flat_r3,
            "rate_effect_eu_usd": rate_effect_eu_usd,
            # American Flat 45%
            "p_am_ql_official": p_am_ql_off,
            "p_am_ql_r3": p_am_ql_r3,
            "rate_effect_am_ql_usd": rate_effect_am_ql_usd,
            "p_am_pde_official": p_am_pde_off,
            "p_am_pde_r3": p_am_pde_r3,
            "rate_effect_am_pde_usd": rate_effect_am_pde_usd,
            "engine_disc_am_flat_usd": engine_disc_am_flat_usd,
            "early_exercise_premium": eep_off,
            # SVI Surface
            "sigma_svi": sigma_svi,
            "p_svi_r3_published_benchmark": p_svi_r3_pub,
            "p_svi_pde_official": p_svi_pde_off,
            "p_svi_pde_r3": p_svi_pde_r3,
            "rate_effect_svi_pure_pde_usd": rate_effect_svi_pure_pde_usd,
            "p_svi_ql_official": p_svi_ql_off,
            "engine_disc_svi_usd": engine_disc_svi_usd,
            # Errors against market
            "err_eu_flat_usd": p_eu_flat_off - p_market,
            "err_am_flat_ql_usd": p_am_ql_off - p_market,
            "err_am_flat_pde_usd": p_am_pde_off - p_market,
            "err_svi_published_r3_usd": (p_svi_r3_pub - p_market) if pd.notna(p_svi_r3_pub) else np.nan,
            "err_svi_pure_pde_official_usd": (p_svi_pde_off - p_market) if pd.notna(p_svi_pde_off) else np.nan,
            "in_r3_common_84": row.get("in_r3_common_84", True)
        })

    df_details = pd.DataFrame(records)

    def _metrics(series: pd.Series) -> Dict[str, float]:
        clean = series.dropna()
        if len(clean) == 0:
            return {"N": 0, "MAE": np.nan, "RMSE": np.nan, "MaxErr": np.nan, "Bias": np.nan}
        return {
            "N": len(clean),
            "MAE": float(clean.abs().mean()),
            "RMSE": float(np.sqrt((clean**2).mean())),
            "MaxErr": float(clean.abs().max()),
            "Bias": float(clean.mean())
        }

    summary_rows = [
        {"Model": "M1_European_BS_Flat45_OfficialRates", **_metrics(df_details["err_eu_flat_usd"])},
        {"Model": "M2_American_Flat45_QuantLib_OfficialRates", **_metrics(df_details["err_am_flat_ql_usd"])},
        {"Model": "M2_American_Flat45_RepoPDE_OfficialRates", **_metrics(df_details["err_am_flat_pde_usd"])},
        {"Model": "M3_Frozen_SVI_Published_R3_Benchmark", **_metrics(df_details["err_svi_published_r3_usd"])},
        {"Model": "M3_Frozen_SVI_RepoPDE_OfficialRates", **_metrics(df_details["err_svi_pure_pde_official_usd"])},
    ]
    df_summary = pd.DataFrame(summary_rows)

    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        df_details.to_csv(out_p / "baseline_comparison_detailed.csv", index=False)
        df_summary.to_csv(out_p / "baseline_comparison_summary.csv", index=False)

    return df_details, df_summary
