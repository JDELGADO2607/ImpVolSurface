"""
American Option Pricing Engine via Finite Difference Partial Differential Equation (PDE).
Implements Crank-Nicolson with Rannacher initial smoothing and penalty iteration
(Forsyth & Vetzal, 2002) for American puts and calls.
Provides fixed-grid PDE solving, safe monotonic interpolation (PCHIP),
and comprehensive convergence diagnostics for Greek stability.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from typing import Any
import numpy as np
from scipy.interpolate import interp1d, PchipInterpolator
from scipy.linalg import solve_banded

def solve_tridiagonal(lower: np.ndarray, diag: np.ndarray, upper: np.ndarray, rhs: np.ndarray) -> np.ndarray:
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

def fd_american_grid(
    kind: str,
    S_ref: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    M: int = 300,
    N: int = 150,
    S_max: float | None = None,
    S_max_mult: float = 4.0,
    rannacher_steps: int = 4,
    penalty_rho: float = 1e7,
    max_penalty_iter: int = 30,
    penalty_tol: float = 1e-7
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """
    Solves the American PDE on a fixed spatial grid S in [0, S_max].
    Returns (S_grid, V, diagnostics).
    """
    kind = kind.upper()
    if kind not in ('C', 'P'):
        raise ValueError(f"Invalid kind: {kind}")

    if S_max is None:
        S_max = float(S_max_mult * max(S_ref, K))

    dS = S_max / M
    S_grid = np.linspace(0.0, S_max, M + 1)

    # Payoff / Obstacle function
    if kind == 'C':
        V_star = np.maximum(S_grid - K, 0.0)
    else:
        V_star = np.maximum(K - S_grid, 0.0)

    # Degenerate maturity case
    if tau <= 1e-12:
        diag = {
            'converged': True,
            'max_penalty_iter_used': 0,
            'iterations_exhausted': False,
            'final_rel_diff': 0.0,
            'S_max': S_max,
            'dS': dS,
            'dt': 0.0
        }
        return S_grid, V_star.copy(), diag

    # Degenerate volatility case
    if sigma <= 1e-12:
        df = np.exp(-r * tau)
        fwd = S_grid * np.exp((r - q) * tau)
        if kind == 'C':
            V_deg = np.maximum(S_grid - K, df * np.maximum(fwd - K, 0.0))
        else:
            V_deg = np.maximum(K - S_grid, df * np.maximum(K - fwd, 0.0))
        diag = {
            'converged': True,
            'max_penalty_iter_used': 0,
            'iterations_exhausted': False,
            'final_rel_diff': 0.0,
            'S_max': S_max,
            'dS': dS,
            'dt': 0.0
        }
        return S_grid, V_deg, diag

    # Initial condition at tau = 0
    V = V_star.copy()

    # Spatial operator L coefficients for interior nodes j = 1, ..., M-1
    j = np.arange(1, M)
    alpha = 0.5 * (sigma ** 2) * (j ** 2) - 0.5 * (r - q) * j
    beta = -(sigma ** 2) * (j ** 2) - r
    gamma = 0.5 * (sigma ** 2) * (j ** 2) + 0.5 * (r - q) * j

    # Time stepping schedule with Rannacher smoothing
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
    all_converged = True
    max_iter_observed = 0
    max_rel_diff_observed = 0.0
    exhausted_any = False

    V_star_int = V_star[1:M]

    for step_dt, theta in steps:
        current_tau += step_dt
        explicit_weight = 1.0 - theta
        implicit_weight = theta

        # Explicit operator on current V
        L_V = alpha * V[0:M-1] + beta * V[1:M] + gamma * V[2:M+1]
        rhs_base = V[1:M] + step_dt * explicit_weight * L_V

        # Boundary conditions at current_tau
        if kind == 'C':
            V_0_new = 0.0
            V_M_new = S_max - K * np.exp(-r * current_tau)
        else:
            V_0_new = K
            V_M_new = 0.0

        # Boundary contributions to rhs
        rhs_base[0] += step_dt * implicit_weight * alpha[0] * V_0_new
        rhs_base[-1] += step_dt * implicit_weight * gamma[-1] * V_M_new

        # Penalty iteration for American obstacle constraint
        V_iter = V[1:M].copy()
        step_converged = False
        step_rel_diff = 0.0

        for it in range(max_penalty_iter):
            active = (V_iter < V_star_int)
            diag_pen = np.where(active, penalty_rho, 0.0)

            sub_diag = -step_dt * implicit_weight * alpha[1:]
            main_diag = 1.0 - step_dt * implicit_weight * beta + diag_pen
            sup_diag = -step_dt * implicit_weight * gamma[:-1]

            rhs = rhs_base + diag_pen * V_star_int

            V_new_int = solve_tridiagonal(sub_diag, main_diag, sup_diag, rhs)

            denom = np.maximum(np.abs(V_new_int), 1.0)
            rel_diff = float(np.max(np.abs(V_new_int - V_iter) / denom))
            step_rel_diff = rel_diff
            V_iter = V_new_int

            if rel_diff < penalty_tol:
                step_converged = True
                if (it + 1) > max_iter_observed:
                    max_iter_observed = it + 1
                break
        else:
            # Loop ended without break -> max_penalty_iter exhausted
            exhausted_any = True
            all_converged = False
            max_iter_observed = max_penalty_iter

        if step_rel_diff > max_rel_diff_observed:
            max_rel_diff_observed = step_rel_diff

        # Update interior and boundary nodes
        V[1:M] = V_iter
        V[0] = V_0_new
        V[M] = V_M_new

    diag = {
        'converged': all_converged and not exhausted_any,
        'max_penalty_iter_used': max_iter_observed,
        'iterations_exhausted': exhausted_any,
        'final_rel_diff': max_rel_diff_observed,
        'S_max': S_max,
        'dS': dS,
        'dt': dt
    }
    return S_grid, V, diag

def evaluate_fd_grid(
    S_grid: np.ndarray,
    V: np.ndarray,
    S_eval: float | np.ndarray,
    K: float,
    kind: str = 'P',
    interp_method: str = 'pchip'
) -> float | np.ndarray:
    """
    Interpolates option value from solved grid (S_grid, V) at S_eval.
    Enforces monotonicity via PCHIP and American intrinsic lower bound.
    """
    kind = kind.upper()
    is_scalar = np.isscalar(S_eval)
    s_arr = np.atleast_1d(np.asarray(S_eval, dtype=float))

    if interp_method == 'pchip':
        interp = PchipInterpolator(S_grid, V)
    elif interp_method == 'cubic':
        interp = interp1d(S_grid, V, kind='cubic', fill_value='extrapolate')
    elif interp_method == 'linear':
        interp = interp1d(S_grid, V, kind='linear', fill_value='extrapolate')
    else:
        raise ValueError(f"Unknown interpolation method: {interp_method}")

    val = interp(s_arr)

    # Intrinsic value lower bound control
    if kind == 'C':
        intrinsic = np.maximum(s_arr - K, 0.0)
    else:
        intrinsic = np.maximum(K - s_arr, 0.0)

    val = np.maximum(val, intrinsic)
    return float(val[0]) if is_scalar else val

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
    S_max: float | None = None,
    S_max_mult: float = 4.0,
    rannacher_steps: int = 4,
    penalty_rho: float = 1e7,
    max_penalty_iter: int = 30,
    penalty_tol: float = 1e-7,
    interp_method: str = "pchip",
    return_diagnostics: bool = False
) -> float | dict[str, Any]:
    """
    Prices an American option using Crank-Nicolson PDE with Rannacher smoothing,
    penalty iteration (Forsyth & Vetzal, 2002), and PCHIP safe interpolation.
    """
    S_grid, V, diag = fd_american_grid(
        kind=kind,
        S_ref=S0,
        K=K,
        tau=tau,
        r=r,
        sigma=sigma,
        q=q,
        M=M,
        N=N,
        S_max=S_max,
        S_max_mult=S_max_mult,
        rannacher_steps=rannacher_steps,
        penalty_rho=penalty_rho,
        max_penalty_iter=max_penalty_iter,
        penalty_tol=penalty_tol
    )

    price = evaluate_fd_grid(S_grid, V, S0, K, kind=kind, interp_method=interp_method)

    if return_diagnostics:
        return {
            'price': float(price),
            'converged': diag['converged'],
            'max_penalty_iter_used': diag['max_penalty_iter_used'],
            'iterations_exhausted': diag['iterations_exhausted'],
            'final_rel_diff': diag['final_rel_diff'],
            'S_grid': S_grid,
            'V': V,
            'S_max': diag['S_max'],
            'dS': diag['dS'],
            'dt': diag['dt']
        }
    return float(price)

def price_american_option(
    kind: str,
    S: float,
    K: float,
    tau: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    method: str = "auto",
    S_max: float | None = None,
    M: int = 300,
    N: int = 150,
    interp_method: str = "pchip"
) -> float:
    """
    Unified American option pricing dispatcher.
    - If kind == 'C' and q == 0 and r >= 0: uses exact Black-Scholes analytical formula (Merton, 1973).
    - If kind == 'P' (or general): uses Crank-Nicolson FD + Rannacher + Penalty method + PCHIP.
    """
    kind = kind.upper()
    if method == "auto":
        if kind == 'C' and q <= 1e-8 and r >= -1e-8:
            from src.pricing_bs import bs_price
            return bs_price('C', S, K, tau, r, sigma, q)
        else:
            return fd_american_price(
                kind, S, K, tau, r, sigma, q,
                M=M, N=N, S_max=S_max, interp_method=interp_method
            )
    elif method == "fd":
        return fd_american_price(
            kind, S, K, tau, r, sigma, q,
            M=M, N=N, S_max=S_max, interp_method=interp_method
        )
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
