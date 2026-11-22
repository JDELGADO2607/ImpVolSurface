"""
Market data configuration, interest rate curve, and underlying parameters for NU.

Valuation anchor: 2026-11-17 16:00:00 EST.
Spot price: S0 = 12.33 USD (last regular trading close on NYSE).
Dividends: q = 0.00 (NU does not pay dividends).
Day Count Convention: Actual/365 for option maturities and discounting.
Risk-Free Curve Source: US Department of the Treasury Daily Treasury Par Yield Curve Rates (2026-11-17).
Conversion to continuous zero rates:
  - Short tenors (t <= 0.5y): Money market continuous zero rate r_c = ln(1 + y * t) / t.
  - Medium/long tenors (t > 0.5y): Semi-annual bond equivalent continuous rate r_c = 2 * ln(1 + y / 2).
  - Discount factor: D(0, tau) = exp(-r(tau) * tau).
  - Forward price: F(0, tau) = S0 * exp((r(tau) - q) * tau).
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np

# Timezone and valuation timestamp
NY_TZ = ZoneInfo("America/New_York")
VALUATION_DATETIME = datetime(2026, 11, 17, 16, 0, 0, tzinfo=NY_TZ)

# Underlying NU Equity parameters
SPOT_PRICE = 12.33
DIVIDEND_YIELD = 0.00
CONTRACT_MULTIPLIER = 100

# US Treasury Yield Curve as of 2026-11-17 / 2026-11-18
# Tenors in years and par yield rates in decimal (e.g. 0.0410 = 4.10%)
TREASURY_PAR_CURVE = [
    (1.0 / 12.0, 0.0410),   # 1M: 4.10%
    (1.5 / 12.0, 0.0424),   # 1.5M: 4.24%
    (2.0 / 12.0, 0.0427),   # 2M: 4.27%
    (3.0 / 12.0, 0.0434),   # 3M: 4.34%
    (4.0 / 12.0, 0.0435),   # 4M: 4.35%
    (6.0 / 12.0, 0.0443),   # 6M: 4.43%
    (1.0, 0.0462),          # 1Y: 4.62%
    (2.0, 0.0480),          # 2Y: 4.80%
    (3.0, 0.0484),          # 3Y: 4.84%
    (5.0, 0.0490),          # 5Y: 4.90%
    (10.0, 0.0510),         # 10Y: 5.10%
]

def get_zero_rate(tau: float) -> float:
    """
    Returns the continuously compounded risk-free rate r(tau) for maturity tau (in years).
    Converts par yields to continuous zero rates and linearly interpolates.
    """
    if tau <= 0:
        return np.log(1.0 + TREASURY_PAR_CURVE[0][1] * TREASURY_PAR_CURVE[0][0]) / TREASURY_PAR_CURVE[0][0]

    # Convert par yields to continuously compounded zero rates
    tenors = []
    zero_rates = []
    for t_m, y in TREASURY_PAR_CURVE:
        tenors.append(t_m)
        if t_m <= 0.5:
            # Short-term money market / T-bill continuous zero rate
            r_c = np.log(1.0 + y * t_m) / t_m
        else:
            # Semi-annual coupon bond equivalent continuous rate
            r_c = 2.0 * np.log(1.0 + y / 2.0)
        zero_rates.append(r_c)

    # Linear interpolation in tau, flat extrapolation at wings
    r_interp = np.interp(tau, tenors, zero_rates)
    return float(r_interp)

def get_discount_factor(tau: float) -> float:
    """
    Calculates the discount factor D(0, tau) = exp(-r(tau) * tau).
    """
    r = get_zero_rate(tau)
    return float(np.exp(-r * tau))

def get_forward_price(tau: float, S0: float = SPOT_PRICE) -> float:
    """
    Calculates the forward price F(0, tau) = S0 / D(0, tau) = S0 * exp(r(tau) * tau) with q=0.
    """
    r = get_zero_rate(tau)
    return float(S0 * np.exp((r - DIVIDEND_YIELD) * tau))

if __name__ == "__main__":
    print(f"Valuation base: {VALUATION_DATETIME}")
    print(f"Spot price NU: ${SPOT_PRICE:.2f}")
    sample_taus = [3.0 / 365.0, 30.0 / 365.0, 0.25, 0.5, 1.0, 2.0]
    for tau in sample_taus:
        r = get_zero_rate(tau)
        D = get_discount_factor(tau)
        F = get_forward_price(tau)
        print(f"tau={tau:.4f} yr ({tau*365:.1f} d) -> r={r*100:.3f}%, D={D:.5f}, Forward=${F:.3f}")
