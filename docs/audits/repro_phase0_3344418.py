import numpy as np
import pandas as pd
from src.heston.rates_curve import get_official_yield_curve
curve = get_official_yield_curve()
for label, maturity, par in curve.rates_data:
    if maturity <= 0.5:
        continue
    dates = np.arange(1, round(2 * maturity) + 1) / 2
    pv = 100 * par / 2 * sum(curve.get_discount_factor(t) for t in dates)
    pv += 100 * curve.get_discount_factor(maturity)
    print(label, pv, pv - 100)
frame = pd.read_csv("data/heston/baseline_comparison_detailed.csv")
print("Max AmericanFlat curve change USD", frame.rate_curve_effect_cents.abs().max() / 100)
print("Max SVI mixed change USD", (frame.p_svi_official_curve-frame.p_svi_historical_r3).abs().max())
