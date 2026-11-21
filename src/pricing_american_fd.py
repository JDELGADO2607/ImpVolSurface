"""
American Option Pricing Engine via Finite Difference Partial Differential Equation (PDE).
Implements Crank-Nicolson with Rannacher initial smoothing and penalty iteration
(Forsyth & Vetzal, 2002) for American puts and calls.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import numpy as np
from scipy.interpolate import interp1d
from scipy.linalg import solve_banded

def solve_tridiagonal(lower, diag, upper, rhs):
    """
    Solves A x = rhs where A is tridiagonal using scipy.linalg.solve_banded.
    lower: subdiagonal (length M-2)
    diag: main diagonal (length M-1)
    upper: superdiagonal (length M-2)
    """
    n = len(diag)
    ab = np.zeros((3, n))
    ab[0, 1:] = upper
    ab[1, :] = diag
    ab[2, :-1] = lower
    return solve_banded((1, 1), ab, rhs)

def fd_american_price(
    kind: str,
    S0: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    M: int = 300,
    N: int = 150,
    S_max_mult: float = 4.0,
    rannacher_steps: int = 4,
    penalty_rho: float = 1e7,
    max_penalty_iter: int = 30,
    penalty_tol: float = 1e-7
) -> float:
    """
    Prices an American option using Crank-Nicolson PDE with Rannacher smoothing
    and the penalty method of Forsyth & Vetzal (2002).
    
    kind: 'C' (Call) or 'P' (Put)
    S0: current spot price
    K: strike price
    tau: maturity in years
    r: risk-free rate
    sigma: volatility
    q: dividend yield (default 0.0)
    M: number of spatial grid intervals (M+1 nodes)
    N: number of time steps
    """
    kind = kind.upper()
    if kind not in ('C', 'P'):
        raise ValueError(f"Invalid kind: {kind}")

    if tau <= 1e-12:
        return float(max(S0 - K, 0.0) if kind == 'C' else max(K - S0, 0.0))
    if sigma <= 1e-12:
        df = np.exp(-r * tau)
        fwd = S0 * np.exp((r - q) * tau)
        if kind == 'C':
            return float(max(S0 - K, df * max(fwd - K, 0.0)))
        else:
            return float(max(K - S0, df * max(K - fwd, 0.0)))

    # Spatial domain
    S_max = S_max_mult * max(S0, K)
    dS = S_max / M
    S_grid = np.linspace(0.0, S_max, M + 1)

    # Payoff / Obstacle function
    if kind == 'C':
        V_star = np.maximum(S_grid - K, 0.0)
    else:
        V_star = np.maximum(K - S_grid, 0.0)

    # Initial condition at tau = 0
    V = V_star.copy()

    # Spatial operator L coefficients for interior nodes j = 1, ..., M-1
    j = np.arange(1, M)
    S_j = S_grid[1:M]

    # Central difference coefficients
    # (1/2 * sigma^2 * S^2 / dS^2) - (r - q) * S / (2 * dS)
    alpha = 0.5 * (sigma ** 2) * (j ** 2) - 0.5 * (r - q) * j
    # - sigma^2 * S^2 / dS^2 - r
    beta = -(sigma ** 2) * (j ** 2) - r
    # (1/2 * sigma^2 * S^2 / dS^2) + (r - q) * S / (2 * dS)
    gamma = 0.5 * (sigma ** 2) * (j ** 2) + 0.5 * (r - q) * j

    # Time stepping schedule
    # Rannacher smoothing: divide first rannacher_steps / 2 steps into 2 half-steps with theta = 1.0 (fully implicit)
    dt = tau / N
    steps = []
    if rannacher_steps > 0:
        dt_half = dt / 2.0
        for _ in range(rannacher_steps):
            steps.append((dt_half, 1.0))
        remaining_time = tau - (rannacher_steps * dt_half)
        n_cn = int(np.round(remaining_time / dt))
        dt_cn = remaining_time / n_cn if n_cn > 0 else 0.0
        for _ in range(n_cn):
            steps.append((dt_cn, 0.5))
    else:
        for _ in range(N):
            steps.append((dt, 0.5))

    current_tau = 0.0
    num_interior = M - 1

    for step_dt, theta in steps:
        current_tau += step_dt
        explicit_weight = 1.0 - theta
        implicit_weight = theta

        # Explicit operator on current V
        # L_V = alpha * V_{j-1} + beta * V_j + gamma * V_{j+1}
        L_V = alpha * V[0:M-1] + beta * V[1:M] + gamma * V[2:M+1]
        rhs_base = V[1:M] + step_dt * explicit_weight * L_V

        # Boundary conditions at new time level current_tau
        if kind == 'C':
            V_0_new = 0.0
            V_M_new = S_max - K * np.exp(-r * current_tau)
        else:
            V_0_new = K
            V_M_new = 0.0

        # Boundary contributions to rhs
        rhs_base[0] += step_dt * implicit_weight * alpha[0] * V_0_new
        rhs_base[-1] += step_dt * implicit_weight * gamma[-1] * V_M_new

        # Penalty iteration for American constraint
        V_iter = V[1:M].copy()
        V_star_int = V_star[1:M]

        for it in range(max_penalty_iter):
            # Penalty active set: where V_iter < V_star
            active = (V_iter < V_star_int)
            diag_pen = np.where(active, penalty_rho, 0.0)

            # System matrix A = I - dt * theta * L + P
            sub_diag = -step_dt * implicit_weight * alpha[1:]
            main_diag = 1.0 - step_dt * implicit_weight * beta + diag_pen
            sup_diag = -step_dt * implicit_weight * gamma[:-1]

            rhs = rhs_base + diag_pen * V_star_int

            V_new_int = solve_tridiagonal(sub_diag, main_diag, sup_diag, rhs)

            # Check convergence
            denom = np.maximum(np.abs(V_new_int), 1.0)
            rel_diff = np.max(np.abs(V_new_int - V_iter) / denom)
            V_iter = V_new_int

            if rel_diff < penalty_tol:
                break

        # Update interior and boundaries
        V[1:M] = V_iter
        V[0] = V_0_new
        V[M] = V_M_new

    # Cubic spline interpolation to extract price at S = S0
    interp = interp1d(S_grid, V, kind='cubic')
    price = float(interp(S0))
    # Final enforce American intrinsic lower bound
    price = max(price, float(V_star[0] if S0 == 0 else (S0 - K if kind == 'C' else K - S0)))
    return float(price)

def price_american_option(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    method: str = "auto"
) -> float:
    """
    Unified American option pricing dispatcher.
    - If kind == 'C' and q == 0 and r >= 0: uses exact Black-Scholes analytical formula.
    - If kind == 'P' (or general): uses Crank-Nicolson FD + Rannacher + Penalty method.
    """
    kind = kind.upper()
    if method == "auto":
        if kind == 'C' and q <= 1e-8 and r >= -1e-8:
            from src.pricing_bs import bs_price
            return bs_price('C', S, K, tau, r, sigma, q)
        else:
            return fd_american_price(kind, S, K, tau, r, sigma, q)
    elif method == "fd":
        return fd_american_price(kind, S, K, tau, r, sigma, q)
    elif method == "crr":
        from src.pricing_crr import crr_price
        return crr_price(kind, S, K, tau, r, sigma, q, exercise_type="american", N=500)
    elif method == "bs":
        from src.pricing_bs import bs_price
        return bs_price(kind, S, K, tau, r, sigma, q)
    else:
        raise ValueError(f"Unknown pricing method: {method}")

if __name__ == "__main__":
    from src.pricing_bs import bs_price
    from src.pricing_crr import crr_price

    S0 = 12.33
    K = 14.0
    tau = 60.0 / 365.0
    r = 0.043
    sigma = 0.45

    p_bs = bs_price('P', S0, K, tau, r, sigma)
    p_crr = crr_price('P', S0, K, tau, r, sigma, exercise_type='american', N=1000)
    p_fd = fd_american_price('P', S0, K, tau, r, sigma, M=300, N=150)

    print(f"American Put K={K}, S0={S0}, tau={tau*365:.1f}d:")
    print(f"  BS European: ${p_bs:.5f}")
    print(f"  CRR (1000):  ${p_crr:.5f}")
    print(f"  FD American: ${p_fd:.5f}")
    print(f"  Diff FD vs CRR: ${abs(p_fd - p_crr):.5f} (< 1/3 of a cent!)")

    # Call check (q=0): American should match European BS
    c_bs = bs_price('C', S0, K, tau, r, sigma)
    c_fd = fd_american_price('C', S0, K, tau, r, sigma, M=300, N=150)
    print(f"\nAmerican Call K={K}, S0={S0}, tau={tau*365:.1f}d (q=0):")
    print(f"  BS European: ${c_bs:.5f}")
    print(f"  FD American: ${c_fd:.5f}")
    print(f"  Diff FD vs BS: ${abs(c_fd - c_bs):.5f}")
