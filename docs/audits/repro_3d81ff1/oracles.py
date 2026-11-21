"""Independent numerical oracles for the R3 audit."""
import numpy as np
from scipy.special import ndtr


def european_call(spot, strike, discount, dividends_discount, w):
    strike, w = np.broadcast_arrays(strike, w)
    forward = spot * dividends_discount / discount
    sd = np.sqrt(w)
    d1 = np.log(forward / strike) / sd + sd / 2
    return discount * (forward * ndtr(d1) - strike * ndtr(d1 - sd))


def american_put_crr(spot, strike, years, rate, dividend, iv, steps):
    dt = years / steps
    up = np.exp(iv * np.sqrt(dt))
    down = 1 / up
    prob_up = (np.exp((rate - dividend) * dt) - down) / (up - down)
    if not 0 <= prob_up <= 1:
        raise ValueError("CRR probability outside its admissible range")
    discount = np.exp(-rate * dt)
    nodes = spot * up ** (2 * np.arange(steps + 1) - steps)
    value = np.maximum(strike - nodes, 0)
    for level in range(steps - 1, -1, -1):
        nodes = nodes[:level + 1] * up
        continuation = discount * ((1 - prob_up) * value[:-1] + prob_up * value[1:])
        value = np.maximum(strike - nodes, continuation)
    return value[0]


def strike_diagnostics(strikes, prices):
    spacing = np.diff(strikes)
    slopes = np.diff(prices) / spacing
    curvature = np.diff(slopes) / ((strikes[2:] - strikes[:-2]) / 2)
    return slopes, curvature


def previous_audit_grids():
    for days, low, high in ((27.5, 10.0, 15.0), (612.0, 5.0, 30.0)):
        for n in (121, 241, 481):
            yield days, np.linspace(low, high, n)
        u = np.linspace(0, 1, 227)
        yield days, low + (high - low) * (u + 0.045 * np.sin(2 * np.pi * u))
