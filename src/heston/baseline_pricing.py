"""
Baseline pricing engine for NU Equity American options under constant volatility and frozen SVI.

Models evaluated on common benchmark contracts (84 puts):
1. M1: European Black-Scholes Flat Volatility (sigma = 0.45)
2. M2: American Constant Volatility (sigma = 0.45) via QuantLib / 1D PDE
3. M3: Frozen SVI American Model (from audited R3 reference 3d81ff1)

Also performs curve ablation:
- Evaluates baseline under Historical R3 curve vs Official 11/17 Bootstrap curve
- Disentangles rate curve revision from option model structural differences.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
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
except ImportError:
    HAS_QUANTLIB = False

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
    time_steps: int = 150,
    grid_points: int = 150
) -> float:
    """
    Prices an American put option using QuantLib's FdBlackScholesVanillaEngine.
    """
    if not HAS_QUANTLIB:
        # Fall back to high-precision 1D PDE Crank-Nicolson
        return price_american_option(kind="put", S=S0, K=K, tau=tau, r=r, q=q, sigma=sigma, M=grid_points, N=time_steps)

    if tau <= 1e-6:
        return max(K - S0, 0.0)

    calendar = ql.NullCalendar()
    day_counter = ql.Actual365Fixed()
    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date

    # Expiration date from string or exact day count
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
    rate_handle = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, r, day_counter))
    div_handle = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, q, day_counter))
    vol_handle = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(eval_date, calendar, sigma, day_counter))

    bs_process = ql.BlackScholesMertonProcess(spot_handle, div_handle, rate_handle, vol_handle)
    engine = ql.FdBlackScholesVanillaEngine(bs_process, time_steps, grid_points)
    option.setPricingEngine(engine)

    price = option.NPV()
    # Enforce intrinsic lower bound
    return float(max(price, max(K - S0, 0.0)))


def compute_baseline_benchmarks(
    puts_df: pd.DataFrame,
    curve_official: Optional[DeterministicYieldCurve] = None,
    output_dir: Optional[str] = "data/heston"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates baseline price comparisons across:
    - BS European Flat Vol (45%)
    - American Flat Vol (45%) via QuantLib / Crank-Nicolson
    - Frozen SVI American Model (from R3 outputs)
    - Ablation on Official 11/17 curve vs Historical R3 curve
    """
    if curve_official is None:
        curve_official = get_official_yield_curve(method="bootstrap")

    curve_r3 = DeterministicYieldCurve(HISTORICAL_R3_PAR_CURVE, method="par_conversion")

    # Load frozen SVI data if available
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
        k_mon = float(row["k_log_moneyness"]) if "k_log_moneyness" in row else np.log(K / (SPOT_PRICE * np.exp(0.04 * tau)))

        # Rates under official curve
        r_off = curve_official.get_zero_rate(tau)
        # Rates under historical R3 curve
        r_r3 = curve_r3.get_zero_rate(tau)

        exp_date_s = str(row["expirationDate"])

        # 1. European BS (Flat 45%) under official curve
        p_eu_flat_off = price_bs_european_put(SPOT_PRICE, K, tau, r_off, sigma=0.45, q=DIVIDEND_YIELD)
        # European BS (Flat 45%) under R3 curve
        p_eu_flat_r3 = price_bs_european_put(SPOT_PRICE, K, tau, r_r3, sigma=0.45, q=DIVIDEND_YIELD)

        # 2. American Flat (45%) under official curve
        p_am_flat_off = price_american_put_quantlib(SPOT_PRICE, K, tau, r_off, sigma=0.45, q=DIVIDEND_YIELD, exp_date_str=exp_date_s)
        # American Flat (45%) under R3 curve
        p_am_flat_r3 = price_american_put_quantlib(SPOT_PRICE, K, tau, r_r3, sigma=0.45, q=DIVIDEND_YIELD, exp_date_str=exp_date_s)

        # 3. Frozen SVI American price from R3
        if contract in svi_lookup:
            p_svi_r3 = float(svi_lookup[contract]["m4_am_surf"])
            sigma_svi = float(svi_lookup[contract]["sigma_surface"])
            # Re-evaluate SVI with official rates to isolate curve effect
            p_svi_off = price_american_put_quantlib(SPOT_PRICE, K, tau, r_off, sigma=sigma_svi, q=DIVIDEND_YIELD, exp_date_str=exp_date_s)
        else:
            p_svi_r3 = np.nan
            p_svi_off = np.nan
            sigma_svi = np.nan

        # Early exercise premiums
        eep_off = p_am_flat_off - p_eu_flat_off

        # Errors (Model - Market)
        err_eu_off = p_eu_flat_off - p_market
        err_am_off = p_am_flat_off - p_market
        err_svi_r3 = (p_svi_r3 - p_market) if pd.notna(p_svi_r3) else np.nan
        err_svi_off = (p_svi_off - p_market) if pd.notna(p_svi_off) else np.nan

        # Curve revision effect on American Flat price (Official vs R3)
        rate_curve_effect = p_am_flat_off - p_am_flat_r3

        records.append({
            "contractSymbol": contract,
            "strike": K,
            "expirationDate": row["expirationDate"],
            "tau_days": row["tau_days"],
            "tau_years": tau,
            "k_log_moneyness": k_mon,
            "lastPrice": p_market,
            "r_official": r_off,
            "r_historical_r3": r_r3,
            "p_eu_flat_official": p_eu_flat_off,
            "p_am_flat_official": p_am_flat_off,
            "early_exercise_premium": eep_off,
            "p_svi_historical_r3": p_svi_r3,
            "p_svi_official_curve": p_svi_off,
            "sigma_svi": sigma_svi,
            "err_eu_flat_usd": err_eu_off,
            "err_am_flat_usd": err_am_off,
            "err_svi_historical_usd": err_svi_r3,
            "err_svi_official_usd": err_svi_off,
            "rate_curve_effect_cents": rate_curve_effect * 100.0,
            "in_r3_common_84": row.get("in_r3_common_84", True)
        })

    df_details = pd.DataFrame(records)

    # Compute summary metrics table
    def _metrics(err_series: pd.Series) -> Dict[str, float]:
        clean = err_series.dropna()
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
        {"Model": "M2_American_Flat45_OfficialRates", **_metrics(df_details["err_am_flat_usd"])},
        {"Model": "M3_Frozen_SVI_HistoricalR3", **_metrics(df_details["err_svi_historical_usd"])},
        {"Model": "M3_Frozen_SVI_OfficialRates", **_metrics(df_details["err_svi_official_usd"])},
    ]
    df_summary = pd.DataFrame(summary_rows)

    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        df_details.to_csv(out_p / "baseline_comparison_detailed.csv", index=False)
        df_summary.to_csv(out_p / "baseline_comparison_summary.csv", index=False)

    return df_details, df_summary
