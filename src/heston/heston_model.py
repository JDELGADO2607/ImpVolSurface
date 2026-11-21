"""
Heston (1993) classical stochastic volatility option pricing engine using QuantLib.

Model Dynamics under Risk-Neutral Measure Q:
    dS_t = (r_t - q_t) S_t dt + sqrt(v_t) S_t dW_t^S
    dv_t = kappa * (theta - v_t) dt + xi * sqrt(v_t) dW_t^v
    dW_t^S dW_t^v = rho dt

Global Parameter Vector Q:
    v0    : initial variance (v0 >= 0)
    kappa : rate of mean reversion (kappa > 0)
    theta : long-term variance (theta > 0)
    xi    : volatility of variance / vol-of-vol (xi > 0)
    rho   : instantaneous correlation between asset and variance Brownians (rho in [-1, 1])

Feller Condition:
    2 * kappa * theta >= xi^2 (guarantees v_t strictly positive almost surely)
    Feller Ratio = 2 * kappa * theta / xi^2

Pricing Engines:
    1. American Options: ql.FdHestonVanillaEngine (Douglas / Hundsdorfer-Verwer ADI FDM scheme
       with early exercise boundary projection, consuming unified term structure).
    2. European Options: ql.AnalyticHestonEngine (semi-analytic characteristic function integration,
       exact machine-precision benchmark control).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
import numpy as np
import pandas as pd

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import DeterministicYieldCurve, get_official_yield_curve, SPOT_PRICE, DIVIDEND_YIELD


@dataclass
class HestonParams:
    """Immutable representation of classical 5-parameter Heston Q specification."""
    v0: float
    kappa: float
    theta: float
    xi: float
    rho: float

    @property
    def feller_ratio(self) -> float:
        """Calculates Feller ratio: 2 * kappa * theta / xi^2."""
        if self.xi <= 1e-12:
            return float("inf")
        return float(2.0 * self.kappa * self.theta / (self.xi ** 2))

    @property
    def feller_satisfied(self) -> bool:
        """Returns True if Feller condition 2 * kappa * theta >= xi^2 is satisfied."""
        return self.feller_ratio >= 1.0

    @property
    def spot_vol(self) -> float:
        """Spot volatility sqrt(v0)."""
        return float(np.sqrt(max(self.v0, 0.0)))

    @property
    def long_term_vol(self) -> float:
        """Long-term volatility sqrt(theta)."""
        return float(np.sqrt(max(self.theta, 0.0)))

    def to_array(self) -> np.ndarray:
        return np.array([self.v0, self.kappa, self.theta, self.xi, self.rho], dtype=float)

    @classmethod
    def from_array(cls, arr: Union[List[float], np.ndarray]) -> "HestonParams":
        return cls(
            v0=float(arr[0]),
            kappa=float(arr[1]),
            theta=float(arr[2]),
            xi=float(arr[3]),
            rho=float(arr[4])
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "v0": self.v0,
            "kappa": self.kappa,
            "theta": self.theta,
            "xi": self.xi,
            "rho": self.rho,
            "feller_ratio": self.feller_ratio,
            "feller_satisfied": bool(self.feller_satisfied),
            "spot_vol": self.spot_vol,
            "long_term_vol": self.long_term_vol,
        }


class HestonOptionPricer:
    """
    High-performance QuantLib pricing engine for American and European options under Heston.
    Consumes a common YieldTermStructureHandle to ensure unified risk-free discounting.
    """

    def __init__(
        self,
        yield_term_structure: Optional["ql.YieldTermStructureHandle"] = None,
        eval_date: Optional["ql.Date"] = None,
        spot: float = SPOT_PRICE,
        dividend: float = DIVIDEND_YIELD
    ):
        if not HAS_QUANTLIB:
            raise RuntimeError("QuantLib is required for HestonOptionPricer.")

        self.eval_date = eval_date or ql.Date(17, 11, 2026)
        ql.Settings.instance().evaluationDate = self.eval_date
        self.day_counter = ql.Actual365Fixed()

        self.spot_quote = ql.SimpleQuote(spot)
        self.spot_handle = ql.QuoteHandle(self.spot_quote)

        self.div_curve = ql.FlatForward(self.eval_date, dividend, self.day_counter)
        self.div_handle = ql.YieldTermStructureHandle(self.div_curve)

        if yield_term_structure is None:
            curve = get_official_yield_curve(method="bootstrap")
            self.ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
        else:
            self.ts_handle = yield_term_structure

    def _build_model_and_process(self, params: HestonParams) -> Tuple["ql.HestonProcess", "ql.HestonModel"]:
        """Builds QuantLib HestonProcess and HestonModel from parameters."""
        proc = ql.HestonProcess(
            self.ts_handle,
            self.div_handle,
            self.spot_handle,
            float(params.v0),
            float(params.kappa),
            float(params.theta),
            float(params.xi),
            float(params.rho)
        )
        model = ql.HestonModel(proc)
        return proc, model

    def _parse_exp_date(self, exp_date_val: Union[str, "ql.Date", datetime]) -> "ql.Date":
        """Converts date string (YYYY-MM-DD), datetime, or ql.Date into a QuantLib Date."""
        if isinstance(exp_date_val, ql.Date):
            return exp_date_val
        elif isinstance(exp_date_val, str):
            dt = datetime.strptime(exp_date_val, "%Y-%m-%d")
            return ql.Date(dt.day, dt.month, dt.year)
        elif isinstance(exp_date_val, datetime):
            return ql.Date(exp_date_val.day, exp_date_val.month, exp_date_val.year)
        else:
            raise ValueError(f"Unsupported expiration date format: {exp_date_val}")

    def price_american(
        self,
        K: float,
        exp_date_val: Union[str, "ql.Date", datetime],
        params: HestonParams,
        option_type: str = "P",
        time_steps: Optional[int] = None,
        spot_steps: int = 100,
        vol_steps: int = 50
    ) -> float:
        """
        Prices an American option using FdHestonVanillaEngine.
        If time_steps is None, uses adaptive scaling with tenor T: max(50, int(100 * T)).
        """
        exp_date = self._parse_exp_date(exp_date_val)
        T = self.day_counter.yearFraction(self.eval_date, exp_date)

        if T <= 1e-6:
            S0 = self.spot_quote.value()
            if option_type.upper() in ("P", "PUT"):
                return max(K - S0, 0.0)
            else:
                return max(S0 - K, 0.0)

        if time_steps is None:
            # Adaptive scaling ensuring time-step size dt <= 0.01 yr across all tenors
            time_steps = max(50, int(round(100.0 * T)))

        _, model = self._build_model_and_process(params)
        engine = ql.FdHestonVanillaEngine(model, time_steps, spot_steps, vol_steps)

        ql_type = ql.Option.Put if option_type.upper() in ("P", "PUT") else ql.Option.Call
        payoff = ql.PlainVanillaPayoff(ql_type, float(K))
        exercise = ql.AmericanExercise(self.eval_date, exp_date)
        option = ql.VanillaOption(payoff, exercise)
        option.setPricingEngine(engine)

        npv = option.NPV()
        S0 = self.spot_quote.value()
        intrinsic = max(K - S0, 0.0) if ql_type == ql.Option.Put else max(S0 - K, 0.0)
        return float(max(npv, intrinsic))

    def price_european(
        self,
        K: float,
        exp_date_val: Union[str, "ql.Date", datetime],
        params: HestonParams,
        option_type: str = "P"
    ) -> float:
        """
        Prices a European option using semi-analytic AnalyticHestonEngine.
        Exact machine-precision integration benchmark.
        """
        exp_date = self._parse_exp_date(exp_date_val)
        T = self.day_counter.yearFraction(self.eval_date, exp_date)

        if T <= 1e-6:
            S0 = self.spot_quote.value()
            if option_type.upper() in ("P", "PUT"):
                return max(K - S0, 0.0)
            else:
                return max(S0 - K, 0.0)

        _, model = self._build_model_and_process(params)
        engine = ql.AnalyticHestonEngine(model)

        ql_type = ql.Option.Put if option_type.upper() in ("P", "PUT") else ql.Option.Call
        payoff = ql.PlainVanillaPayoff(ql_type, float(K))
        exercise = ql.EuropeanExercise(exp_date)
        option = ql.VanillaOption(payoff, exercise)
        option.setPricingEngine(engine)

        npv = option.NPV()
        return float(max(npv, 0.0))

    def evaluate_grid_convergence(
        self,
        K: float,
        exp_date_val: Union[str, "ql.Date", datetime],
        params: HestonParams,
        option_type: str = "P"
    ) -> Dict[str, Any]:
        """
        Evaluates a contract under 3 grid resolutions:
        - Coarse:  tg = max(25, int(50*T)),   xg = 60,  vg = 30
        - Medium:  tg = max(50, int(100*T)),  xg = 120, vg = 60
        - Fine:    tg = max(100, int(200*T)), xg = 200, vg = 100

        Verifies if |P_medium - P_fine| <= 0.0020 USD (gate numerical budget).
        """
        exp_date = self._parse_exp_date(exp_date_val)
        T = self.day_counter.yearFraction(self.eval_date, exp_date)

        _, model = self._build_model_and_process(params)
        ql_type = ql.Option.Put if option_type.upper() in ("P", "PUT") else ql.Option.Call
        payoff = ql.PlainVanillaPayoff(ql_type, float(K))
        exercise = ql.AmericanExercise(self.eval_date, exp_date)
        opt = ql.VanillaOption(payoff, exercise)

        # Coarse
        eng_c = ql.FdHestonVanillaEngine(model, max(25, int(round(50 * T))), 60, 30)
        opt.setPricingEngine(eng_c)
        p_coarse = opt.NPV()

        # Medium
        eng_m = ql.FdHestonVanillaEngine(model, max(50, int(round(100 * T))), 120, 60)
        opt.setPricingEngine(eng_m)
        p_medium = opt.NPV()

        # Fine
        eng_f = ql.FdHestonVanillaEngine(model, max(100, int(round(200 * T))), 200, 100)
        opt.setPricingEngine(eng_f)
        p_fine = opt.NPV()

        diff_med_fine = abs(p_medium - p_fine)
        diff_coarse_med = abs(p_coarse - p_medium)

        return {
            "strike": K,
            "exp_date": str(exp_date),
            "tau_years": T,
            "price_coarse": p_coarse,
            "price_medium": p_medium,
            "price_fine": p_fine,
            "diff_coarse_medium": diff_coarse_med,
            "diff_medium_fine": diff_med_fine,
            "budget_threshold_usd": 0.0020,
            "budget_passed": bool(diff_med_fine <= 0.0020)
        }
