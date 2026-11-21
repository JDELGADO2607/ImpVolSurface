"""
Black-Scholes analytical pricing and Greeks for European and American Call/Put options.
For q=0 and r >= 0, American Call price is analytically identical to European Call.
Includes exact formulas for Price, Delta, Gamma, Vega, Theta, Vanna, and Volga.
"""

from typing import Union
import numpy as np
from scipy.stats import norm

def bs_d1_d2(
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0
) -> tuple[float, float]:
    """
    Computes d1 and d2 in the Black-Scholes framework.
    """
    if tau <= 1e-12:
        if S > K:
            return 1e6, 1e6
        elif S < K:
            return -1e6, -1e6
        else:
            return 0.0, 0.0
    if sigma <= 1e-12:
        fwd = S * np.exp((r - q) * tau)
        if fwd > K:
            return 1e6, 1e6
        elif fwd < K:
            return -1e6, -1e6
        else:
            return 0.0, 0.0

    vol_sqrt_tau = sigma * np.sqrt(tau)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * tau) / vol_sqrt_tau
    d2 = d1 - vol_sqrt_tau
    return float(d1), float(d2)

def bs_price(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0
) -> float:
    """
    Calculates analytical Black-Scholes option price.
    kind: 'C' for Call, 'P' for Put.
    """
    kind = kind.upper()
    if kind not in ('C', 'P'):
        raise ValueError(f"Invalid option kind: {kind}. Must be 'C' or 'P'.")

    # Payoff at expiration or zero time
    if tau <= 1e-12:
        return float(max(S - K, 0.0) if kind == 'C' else max(K - S, 0.0))

    # Boundary cases
    if S <= 1e-12:
        return 0.0 if kind == 'C' else float(K * np.exp(-r * tau))
    if K <= 1e-12:
        return float(S * np.exp(-q * tau)) if kind == 'C' else 0.0

    # Near-zero volatility: intrinsic discounted
    if sigma <= 1e-12:
        fwd = S * np.exp((r - q) * tau)
        df = np.exp(-r * tau)
        if kind == 'C':
            return float(df * max(fwd - K, 0.0))
        else:
            return float(df * max(K - fwd, 0.0))

    d1, d2 = bs_d1_d2(S, K, tau, r, sigma, q)
    df_r = np.exp(-r * tau)
    df_q = np.exp(-q * tau)

    if kind == 'C':
        price = S * df_q * norm.cdf(d1) - K * df_r * norm.cdf(d2)
    else:
        price = K * df_r * norm.cdf(-d2) - S * df_q * norm.cdf(-d1)

    return float(max(price, 0.0))

def bs_greeks(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0
) -> dict[str, float]:
    """
    Calculates exact analytical Greeks under Black-Scholes.
    - Delta: dV/dS
    - Gamma: d2V/dS2
    - Vega: dV/d(sigma), scaled to 1 percentage point (0.01) of vol
    - Theta: dV/dt (annualized) and theta_daily = Theta / 365
    - Vanna: dDelta/d(sigma) = dVega/dS, per 1 percentage point of vol
    - Volga (Vomma): d2V/d(sigma)2, per 1 percentage point of vol
    """
    kind = kind.upper()
    if tau <= 1e-12 or sigma <= 1e-12 or S <= 1e-12:
        # Degenerate Greek limits
        delta = 1.0 if (kind == 'C' and S > K) else (-1.0 if (kind == 'P' and S < K) else 0.0)
        return {
            'delta': float(delta),
            'gamma': 0.0,
            'vega': 0.0,
            'theta_annual': 0.0,
            'theta_daily': 0.0,
            'vanna': 0.0,
            'volga': 0.0
        }

    d1, d2 = bs_d1_d2(S, K, tau, r, sigma, q)
    df_r = np.exp(-r * tau)
    df_q = np.exp(-q * tau)
    pdf_d1 = norm.pdf(d1)
    sqrt_tau = np.sqrt(tau)

    # Gamma (identical for Call and Put)
    gamma = (df_q * pdf_d1) / (S * sigma * sqrt_tau)

    # Vega (standard definition dV/d(sigma), scaled to 1 pp of vol: 0.01)
    vega_raw = S * df_q * sqrt_tau * pdf_d1
    vega_1pp = vega_raw * 0.01

    if kind == 'C':
        delta = df_q * norm.cdf(d1)
        theta_annual = (
            -(S * df_q * pdf_d1 * sigma) / (2.0 * sqrt_tau)
            - r * K * df_r * norm.cdf(d2)
            + q * S * df_q * norm.cdf(d1)
        )
    else:
        delta = -df_q * norm.cdf(-d1)
        theta_annual = (
            -(S * df_q * pdf_d1 * sigma) / (2.0 * sqrt_tau)
            + r * K * df_r * norm.cdf(-d2)
            - q * S * df_q * norm.cdf(-d1)
        )

    theta_daily = theta_annual / 365.0

    # Cross and second order Greeks
    # Vanna: d(Delta)/d(sigma) = -df_q * pdf_d1 * (d2 / sigma)
    vanna_raw = -df_q * pdf_d1 * (d2 / sigma)
    vanna_1pp = vanna_raw * 0.01

    # Volga: d(Vega)/d(sigma) = vega_raw * d1 * d2 / sigma
    volga_raw = vega_raw * (d1 * d2 / sigma)
    volga_1pp = volga_raw * 0.01 * 0.01 # per 1 pp squared

    return {
        'delta': float(delta),
        'gamma': float(gamma),
        'vega': float(vega_1pp),
        'theta_annual': float(theta_annual),
        'theta_daily': float(theta_daily),
        'vanna': float(vanna_1pp),
        'volga': float(volga_1pp)
    }

if __name__ == "__main__":
    S0 = 12.33
    K = 12.0
    tau = 30.0 / 365.0
    r = 0.0427
    sigma = 0.45

    c_px = bs_price('C', S0, K, tau, r, sigma)
    p_px = bs_price('P', S0, K, tau, r, sigma)
    parity = c_px - p_px
    parity_theo = S0 - K * np.exp(-r * tau)
    print(f"Call: ${c_px:.4f}, Put: ${p_px:.4f}")
    print(f"Parity C - P: ${parity:.4f}, Theoretical: ${parity_theo:.4f}, Diff: {abs(parity - parity_theo):.1e}")

    greeks = bs_greeks('C', S0, K, tau, r, sigma)
    for g, val in greeks.items():
        print(f"  {g}: {val:.6f}")
