"""
Official US Treasury deterministic rate curve and coupon-bond bootstrap for Heston migration.

Reference Valuation Anchor: 2026-11-17 16:00:00 America/New_York (NYSE market close).
Underlying parameters: S0 = 12.33 USD, q = 0.00 (Nu Holdings dividend yield).
Day Count Convention: Actual/365 Fixed (ACT/365F) for option maturities and discounting.

Data Provenance & Policy:
- Source: US Department of the Treasury Daily Treasury Par Yield Curve Rates (2026-11-17).
- URL: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve
- Availability Window: Estimated habitual publication between 17:00 and 18:00 EST (based on OTC market closing bids ~15:30 EST).
- Methodological Alignment: Contemporaneous closing ex-post alignment (standard for EOD derivative books and academic risk valuation).
- Mathematical Distinction:
  * Bootstrap (authoritative for Heston): Exact coupon-bond bootstrapping under consistent log-linear discount factor
    interpolation, guaranteeing exact machine-precision repricing (residual < 1e-10 USD) for ALL benchmark par notes (1Y to 30Y).
  * Par conversion: Frequency conversion (y -> r_c) without coupon unbundling (historical SVI approach, provided for ablation).
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from scipy.optimize import brentq

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

NY_TZ = ZoneInfo("America/New_York")
VALUATION_DATETIME = datetime(2026, 11, 17, 16, 0, 0, tzinfo=NY_TZ)
SPOT_PRICE = 12.33
DIVIDEND_YIELD = 0.00

# Official US Treasury Daily Treasury Par Yield Curve Rates for 2026-11-17
# Benchmark tenors in years and par yield rates in decimal
OFFICIAL_TREASURY_CMT_2026_11_17: List[Tuple[str, float, float]] = [
    ("1M", 1.0 / 12.0, 0.0409),
    ("1.5M", 1.5 / 12.0, 0.0424),
    ("2M", 2.0 / 12.0, 0.0426),
    ("3M", 3.0 / 12.0, 0.0433),
    ("4M", 4.0 / 12.0, 0.0432),
    ("6M", 6.0 / 12.0, 0.0441),
    ("1Y", 1.0, 0.0460),
    ("2Y", 2.0, 0.0480),
    ("3Y", 3.0, 0.0484),
    ("5Y", 5.0, 0.0490),
    ("7Y", 7.0, 0.0499),
    ("10Y", 10.0, 0.0510),
    ("20Y", 20.0, 0.0550),
    ("30Y", 30.0, 0.0546),
]

# Historical R3 Par Yield entries (which mixed 11/18 quotes)
HISTORICAL_R3_PAR_CURVE: List[Tuple[str, float, float]] = [
    ("1M", 1.0 / 12.0, 0.0410),
    ("1.5M", 1.5 / 12.0, 0.0424),
    ("2M", 2.0 / 12.0, 0.0427),
    ("3M", 3.0 / 12.0, 0.0434),
    ("4M", 4.0 / 12.0, 0.0435),
    ("6M", 6.0 / 12.0, 0.0443),
    ("1Y", 1.0, 0.0462),
    ("2Y", 2.0, 0.0480),
    ("3Y", 3.0, 0.0484),
    ("5Y", 5.0, 0.0490),
    ("10Y", 10.0, 0.0510),
]


class DeterministicYieldCurve:
    """
    Deterministic risk-free discount and zero rate curve.
    Supports exact coupon bootstrap or par yield frequency conversion.
    Guarantees internal consistency between bootstrap node stripping and curve queries.
    """

    def __init__(
        self,
        rates_data: List[Tuple[str, float, float]] = OFFICIAL_TREASURY_CMT_2026_11_17,
        method: str = "bootstrap",
        label: str = "Official_CMT_2026-11-17_Bootstrap"
    ):
        self.method = method
        self.label = label
        self.rates_data = rates_data
        self.tenors = np.array([r[1] for r in rates_data], dtype=float)
        self.par_yields = np.array([r[2] for r in rates_data], dtype=float)
        self.labels = [r[0] for r in rates_data]

        if method == "bootstrap":
            self.D_nodes = self._compute_consistent_bootstrap()
            self.benchmark_D = np.array([self.D_nodes[t] for t in self.tenors], dtype=float)
            self.benchmark_zero_rates = -np.log(self.benchmark_D) / self.tenors
        elif method == "par_conversion":
            self.benchmark_zero_rates = self._compute_par_conversion()
            self.benchmark_D = np.exp(-self.benchmark_zero_rates * self.tenors)
            self.D_nodes = {t: d for t, d in zip(self.tenors, self.benchmark_D)}
        else:
            raise ValueError(f"Unknown curve method: {method}. Use 'bootstrap' or 'par_conversion'.")

    def _compute_par_conversion(self) -> np.ndarray:
        """
        Historical par-conversion formula without coupon stripping:
        - t <= 0.5: r_c = ln(1 + y * t) / t
        - t > 0.5: r_c = 2 * ln(1 + y / 2)
        """
        zero_rates = []
        for t, y in zip(self.tenors, self.par_yields):
            if t <= 0.5:
                r_c = np.log(1.0 + y * t) / t
            else:
                r_c = 2.0 * np.log(1.0 + y / 2.0)
            zero_rates.append(r_c)
        return np.array(zero_rates, dtype=float)

    def _interpolate_discount_factor(self, t: float, nodes: Dict[float, float]) -> float:
        """
        Log-linear interpolation in discount factors D(0, t), corresponding to piecewise
        constant instantaneous forward rates between benchmark tenors.
        """
        if t <= 0.0:
            return 1.0

        sorted_t = sorted(nodes.keys())
        if t in nodes:
            return nodes[t]

        # Prior to first node: flat forward from origin to first node
        if t <= sorted_t[0]:
            r0 = -np.log(nodes[sorted_t[0]]) / sorted_t[0]
            return float(np.exp(-r0 * t))

        # Between nodes: log-linear interpolation
        for i in range(len(sorted_t) - 1):
            t1, t2 = sorted_t[i], sorted_t[i + 1]
            if t1 <= t <= t2:
                w = (t - t1) / (t2 - t1)
                log_d = (1.0 - w) * np.log(nodes[t1]) + w * np.log(nodes[t2])
                return float(np.exp(log_d))

        # Beyond last node: flat forward extrapolation using last interval
        t_last = sorted_t[-1]
        t_prev = sorted_t[-2]
        f_last = (np.log(nodes[t_prev]) - np.log(nodes[t_last])) / (t_last - t_prev)
        return float(nodes[t_last] * np.exp(-f_last * (t - t_last)))

    def _compute_consistent_bootstrap(self) -> Dict[float, float]:
        """
        Exact quantitative coupon-bond bootstrap under unified log-linear discount factor interpolation.
        For bills (t <= 0.5y): D(0, t) = 1 / (1 + y * t)
        For coupon notes (t > 0.5y, semiannual coupons c = y/2):
          100 = 100 * c * sum_{j=1}^{2T-1} D(t_j) + 100 * (1 + c) * D(T)
        Solves for D(T) using 1D root-finding (brentq) so that under the EXACT SAME discount function
        queried in production, every par bond reprecies to 100.000000000000 USD (residual < 1e-10).
        """
        D_nodes: Dict[float, float] = {}
        par_dict = {t: y for t, y in zip(self.tenors, self.par_yields)}

        # Short end (money market bills)
        for t in self.tenors:
            if t <= 0.5:
                y = par_dict[t]
                D_nodes[t] = 1.0 / (1.0 + y * t)

        # Long end (semiannual coupon notes)
        for t in sorted(self.tenors):
            if t <= 0.5:
                continue

            par = par_dict[t]
            c = par / 2.0
            coupon_dates = np.arange(1, round(2 * t) + 1) / 2.0
            t_prev = max(k for k in D_nodes.keys())

            def _objective(D_val: float) -> float:
                candidate_nodes = dict(D_nodes)
                candidate_nodes[t] = D_val
                pv = 100.0 * c * sum(self._interpolate_discount_factor(cd, candidate_nodes) for cd in coupon_dates[:-1])
                pv += 100.0 * (1.0 + c) * D_val
                return pv - 100.0

            # Bracket between 1e-4 and previous node discount factor
            upper_bound = D_nodes[t_prev]
            D_sol = brentq(_objective, 1e-4, upper_bound, xtol=1e-14, rtol=1e-14)
            D_nodes[t] = float(D_sol)

        return D_nodes

    def get_discount_factor(self, tau: float) -> float:
        """
        Returns risk-neutral discount factor D(0, tau).
        Under bootstrap method, evaluates the exact unified log-linear discount curve.
        """
        if tau <= 0.0:
            return 1.0

        if self.method == "bootstrap":
            return self._interpolate_discount_factor(tau, self.D_nodes)
        else:
            # Historical par conversion
            r = float(np.interp(tau, self.tenors, self.benchmark_zero_rates))
            return float(np.exp(-r * tau))

    def get_zero_rate(self, tau: float) -> float:
        """
        Returns continuously compounded zero rate r_zero(tau) for maturity tau (in ACT/365F years).
        r_zero(tau) = -ln(D(0, tau)) / tau.
        """
        if tau <= 0.0:
            return float(self.benchmark_zero_rates[0])
        D = self.get_discount_factor(tau)
        return float(-np.log(D) / tau)

    def get_forward_price(self, tau: float, S0: float = SPOT_PRICE) -> float:
        """
        Calculates arbitrage-free forward price F(0, tau) = S0 / D(0, tau) = S0 * exp((r - q) * tau).
        Under q = 0, F(0, tau) = S0 / D(0, tau).
        """
        D = self.get_discount_factor(tau)
        return float(S0 / D)

    def to_quantlib_term_structure(self, dense_daily: bool = True) -> "ql.YieldTermStructureHandle":
        """
        Builds a single QuantLib YieldTermStructureHandle wrapping a DiscountCurve.
        Allows American engines to consume the ENTIRE deterministic curve rather than
        a separate FlatForward per option contract.

        Parameters:
        -----------
        dense_daily : bool, default True
            If True, populates daily discrete nodes (d = 0 ... 31Y) using the exact
            piecewise log-linear discount factor function get_discount_factor(d / 365.0).
            This eliminates calendar-day integer rounding discrepancies:
            - Error on ALL calendar dates (option expirations, coupons): exactly 0.000000 USD.
            - Error on arbitrary continuous time queries: bounded by < 2.7e-6.
            If False, uses only the 14 CMT benchmark tenors.
        """
        if not HAS_QUANTLIB:
            raise RuntimeError("QuantLib is not installed.")

        eval_date = ql.Date(17, 11, 2026)
        day_counter = ql.Actual365Fixed()

        if dense_daily:
            max_days = int(round(max(self.tenors) * 365.0)) + 365  # up to 31 years
            ql_dates = [eval_date + d for d in range(max_days + 1)]
            ql_discounts = [self.get_discount_factor(d / 365.0) for d in range(max_days + 1)]
        else:
            ql_dates = [eval_date]
            ql_discounts = [1.0]
            for t in sorted(self.D_nodes.keys()):
                d = eval_date + int(round(t * 365.0))
                ql_dates.append(d)
                ql_discounts.append(self.D_nodes[t])

        ql_curve = ql.DiscountCurve(ql_dates, ql_discounts, day_counter)
        ql_curve.enableExtrapolation()
        return ql.YieldTermStructureHandle(ql_curve)

    def reprice_par_bonds(self) -> pd.DataFrame:
        """
        Verifies exact repricing of all par coupon bonds against nominal 100.000000 USD
        using the production discount factor method.
        """
        records = []
        for label, t, y in zip(self.labels, self.tenors, self.par_yields):
            if t <= 0.5:
                # Bill: 100 / (1 + y * t) discounted back
                D = self.get_discount_factor(t)
                pv = 100.0 * (1.0 + y * t) * D
                err = pv - 100.0
            else:
                c = y / 2.0
                coupon_dates = np.arange(1, round(2 * t) + 1) / 2.0
                pv = 100.0 * c * sum(self.get_discount_factor(cd) for cd in coupon_dates[:-1])
                pv += 100.0 * (1.0 + c) * self.get_discount_factor(t)
                err = pv - 100.0

            records.append({
                "label": label,
                "tenor_yr": t,
                "par_yield_pct": y * 100.0,
                "zero_rate_pct": self.get_zero_rate(t) * 100.0,
                "discount_factor": self.get_discount_factor(t),
                "repriced_pv": pv,
                "error_cents": err * 100.0,
                "residual_usd": err
            })
        return pd.DataFrame(records)


def get_official_yield_curve(method: str = "bootstrap") -> DeterministicYieldCurve:
    """Factory for official 2026-11-17 curve."""
    return DeterministicYieldCurve(
        rates_data=OFFICIAL_TREASURY_CMT_2026_11_17,
        method=method,
        label=f"Official_11-17_{method}"
    )


def compare_rate_methods_and_curves(tau_samples: Optional[List[float]] = None) -> pd.DataFrame:
    """
    Compares:
    1. Official 11/17 Bootstrap (authoritative Heston curve)
    2. Official 11/17 Par Conversion
    3. Historical R3 Par Conversion (with mixed 11/18 rates)
    """
    if tau_samples is None:
        tau_samples = [
            3.0 / 365.0,   # 3d
            10.0 / 365.0,  # 10d
            31.0 / 365.0,  # 31d
            59.0 / 365.0,  # 59d
            94.0 / 365.0,  # 94d
            0.5,           # 182.5d
            1.0,           # 1Y
            2.0,           # 2Y
            2.1753         # LEAPS 794d
        ]

    c_boot = DeterministicYieldCurve(OFFICIAL_TREASURY_CMT_2026_11_17, method="bootstrap", label="Official_11-17_Boot")
    c_par = DeterministicYieldCurve(OFFICIAL_TREASURY_CMT_2026_11_17, method="par_conversion", label="Official_11-17_Par")
    c_r3 = DeterministicYieldCurve(HISTORICAL_R3_PAR_CURVE, method="par_conversion", label="Historical_R3")

    rows = []
    for tau in tau_samples:
        r_boot = c_boot.get_zero_rate(tau)
        r_par = c_par.get_zero_rate(tau)
        r_r3 = c_r3.get_zero_rate(tau)

        D_boot = c_boot.get_discount_factor(tau)
        D_par = c_par.get_discount_factor(tau)
        D_r3 = c_r3.get_discount_factor(tau)

        F_boot = c_boot.get_forward_price(tau)
        F_r3 = c_r3.get_forward_price(tau)

        rows.append({
            "tau_days": round(tau * 365.0, 1),
            "tau_years": round(tau, 4),
            "r_boot_pct": round(r_boot * 100.0, 4),
            "r_par_pct": round(r_par * 100.0, 4),
            "r_r3_pct": round(r_r3 * 100.0, 4),
            "diff_boot_vs_par_bp": round((r_boot - r_par) * 10000.0, 2),
            "diff_boot_vs_r3_bp": round((r_boot - r_r3) * 10000.0, 2),
            "D_boot": round(D_boot, 6),
            "D_r3": round(D_r3, 6),
            "diff_D_bp": round((D_boot - D_r3) * 10000.0, 2),
            "F_boot": round(F_boot, 4),
            "F_r3": round(F_r3, 4),
            "diff_F_cents": round((F_boot - F_r3) * 100.0, 2),
        })

    return pd.DataFrame(rows)
