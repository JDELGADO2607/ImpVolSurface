"""Compute bootstrap par-price residuals and a short HAR causality witness."""
import numpy as np
import pandas as pd

CMT = {
    1/12: .0409, 1.5/12: .0424, 2/12: .0426, 3/12: .0433,
    4/12: .0432, 6/12: .0441, 1: .0460, 2: .0480,
    3: .0484, 5: .0490, 7: .0499, 10: .0510, 20: .0550, 30: .0546,
}


def semiannual_par_cashflow_price(maturity, coupon, discount):
    n = round(2 * maturity)
    if n < 1 or abs(2 * maturity - n) > 1e-10:
        raise ValueError("Expected maturity on a semiannual coupon date")
    times = np.arange(1, n + 1) / 2
    df = np.array([discount(float(t)) for t in times])
    return df[-1] + coupon / 2 * df.sum()


def har_sample():
    returns = np.random.default_rng(3).normal(0, .025, 120)
    baseline = pd.DataFrame({"log_ret": returns, "rv_daily": returns ** 2},
                            index=pd.bdate_range("2025-01-01", periods=len(returns)))
    modified = baseline.copy(deep=True)
    modified.iloc[45:55, :] *= 10
    return baseline, modified
