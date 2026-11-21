"""
Cox-Ross-Rubinstein (CRR, 1979) binomial tree pricing engine.
Serves as an independent numerical validation benchmark for European and American options.
Vectorized implementation for computational performance.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np

def crr_price(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    exercise_type: str = "american",
    N: int = 500
) -> float:
    """
    Prices an option using the Cox-Ross-Rubinstein binomial tree model.
    kind: 'C' for Call, 'P' for Put.
    exercise_type: 'american' or 'european'.
    N: number of time steps (default 500).
    """
    kind = kind.upper()
    exercise_type = exercise_type.lower()
    if kind not in ('C', 'P'):
        raise ValueError(f"Invalid option kind: {kind}")
    if exercise_type not in ('american', 'european'):
        raise ValueError(f"Invalid exercise type: {exercise_type}")

    if tau <= 1e-12:
        return float(max(S - K, 0.0) if kind == 'C' else max(K - S, 0.0))
    if sigma <= 1e-12:
        df = np.exp(-r * tau)
        fwd = S * np.exp((r - q) * tau)
        if exercise_type == 'european':
            return float(df * max(fwd - K, 0.0) if kind == 'C' else df * max(K - fwd, 0.0))
        else:
            if kind == 'C':
                return float(max(S - K, df * max(fwd - K, 0.0)))
            else:
                return float(max(K - S, df * max(K - fwd, 0.0)))

    dt = tau / N
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    disc = np.exp(-r * dt)
    drift = np.exp((r - q) * dt)

    p = (drift - d) / (u - d)
    # Check probability bounds
    if not (0.0 <= p <= 1.0):
        # Fallback adjustment if dt is large relative to drift/vol
        p = min(max(p, 0.0), 1.0)
    q_prob = 1.0 - p

    # Asset prices at terminal step N
    j_indices = np.arange(N + 1)
    S_T = S * (u ** j_indices) * (d ** (N - j_indices))

    # Terminal payoffs
    if kind == 'C':
        V = np.maximum(S_T - K, 0.0)
    else:
        V = np.maximum(K - S_T, 0.0)

    is_american = (exercise_type == "american")

    # Backward induction
    for i in range(N - 1, -1, -1):
        V = disc * (p * V[1:i + 2] + q_prob * V[0:i + 1])
        if is_american:
            j_i = np.arange(i + 1)
            S_i = S * (u ** j_i) * (d ** (i - j_i))
            if kind == 'C':
                V = np.maximum(V, S_i - K)
            else:
                V = np.maximum(V, K - S_i)

    return float(V[0])

if __name__ == "__main__":
    from src.pricing_bs import bs_price
    S0 = 12.33
    K = 14.0 # ITM Put
    tau = 60.0 / 365.0
    r = 0.043
    sigma = 0.45

    bs_p = bs_price('P', S0, K, tau, r, sigma)
    crr_eu = crr_price('P', S0, K, tau, r, sigma, exercise_type='european', N=1000)
    crr_am = crr_price('P', S0, K, tau, r, sigma, exercise_type='american', N=1000)

    print(f"ITM Put K={K}, S0={S0}:")
    print(f"  BS European:       ${bs_p:.5f}")
    print(f"  CRR European 1000: ${crr_eu:.5f} (Diff vs BS: {abs(crr_eu - bs_p):.5f})")
    print(f"  CRR American 1000: ${crr_am:.5f} (Early Exercise Premium: ${crr_am - crr_eu:.5f})")
