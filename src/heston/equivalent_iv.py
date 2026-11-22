"""
Equivalent Implied Volatility (IV) Surface Engine for Heston Model (Phase 5).

Implements:
1. 1D American PDE solver with term structure / deterministic yield curve support
   (Crank-Nicolson + Rannacher initial smoothing + Forsyth-Vetzal penalty iteration).
2. Brent's root-finding inversion for American Puts against 1D PDE engine.
3. QuantLib semi-analytic European Call pricing for classical Heston model under
   deterministic yield curve (under q=0, r>=0, American Call == European Call).
4. Analytical Black-Scholes IV inversion for European Calls with exact D(T) discount.
5. Rigorous economic boundary checks, zero-vega / near-intrinsic unidentifiability detection,
   and explicit status classification without artificial boundary forcing or row omission.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.optimize import brentq
from scipy.interpolate import PchipInterpolator
from scipy.linalg import solve_banded

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.pricing_bs import bs_price
from src.heston.rates_curve import (
    DeterministicYieldCurve,
    SPOT_PRICE,
    DIVIDEND_YIELD,
    NY_TZ,
    VALUATION_DATETIME,
)
from src.heston.heston_model import HestonParams


def solve_tridiagonal(lower: np.ndarray, diag: np.ndarray, upper: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """
    Solves A x = rhs where A is tridiagonal using scipy.linalg.solve_banded.
    """
    n = len(diag)
    ab = np.zeros((3, n))
    ab[0, 1:] = upper
    ab[1, :] = diag
    ab[2, :-1] = lower
    return solve_banded((1, 1), ab, rhs)


def fd_american_grid_curve(
    kind: str,
    S_ref: float,
    K: float,
    tau: float,
    curve_or_r: Union[DeterministicYieldCurve, float],
    sigma: float,
    q: float = 0.0,
    M: int = 300,
    N: int = 150,
    S_max: Optional[float] = None,
    S_max_mult: float = 4.0,
    rannacher_steps: int = 4,
    penalty_rho: float = 1e7,
    max_penalty_iter: int = 30,
    penalty_tol: float = 1e-7,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Solves the 1D American PDE on a fixed spatial grid S in [0, S_max]
    with optional deterministic term structure / yield curve.

    When curve_or_r is a curve object, evaluates the instantaneous forward rate
    r(t = T - tau) at each backward time step.
    When curve_or_r is a float/int, uses constant scalar r (exact historical behavior).
    """
    kind = kind.upper()
    if kind not in ('C', 'P'):
        raise ValueError(f"Invalid kind: {kind}")

    if S_max is None:
        S_max = float(S_max_mult * max(S_ref, K))

    dS = S_max / M
    S_grid = np.linspace(0.0, S_max, M + 1)

    # Obstacle / Payoff function
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

    # Helper for forward rate and discount queries
    is_curve = hasattr(curve_or_r, 'get_instantaneous_forward_rate') or callable(curve_or_r)
    
    def _get_rate(t_cal: float) -> float:
        if isinstance(curve_or_r, (int, float)):
            return float(curve_or_r)
        if hasattr(curve_or_r, 'get_instantaneous_forward_rate'):
            return float(curve_or_r.get_instantaneous_forward_rate(t_cal))
        if callable(curve_or_r):
            return float(curve_or_r(t_cal))
        return float(curve_or_r)

    def _get_discount(tau_val: float) -> float:
        if isinstance(curve_or_r, (int, float)):
            return float(np.exp(-float(curve_or_r) * tau_val))
        if hasattr(curve_or_r, 'get_discount_factor'):
            return float(curve_or_r.get_discount_factor(tau_val))
        return float(np.exp(-_get_rate(max(tau - tau_val, 1e-6)) * tau_val))

    # Degenerate volatility case
    if sigma <= 1e-12:
        df = _get_discount(tau)
        fwd = S_grid * np.exp(-q * tau) / df if df > 0 else S_grid
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

    # Spatial operator indexing
    j = np.arange(1, M)
    j2 = j ** 2
    sig2 = sigma ** 2

    # Precalculate if constant r
    if not is_curve:
        r_const = float(curve_or_r)
        alpha_const = 0.5 * sig2 * j2 - 0.5 * (r_const - q) * j
        beta_const = -sig2 * j2 - r_const
        gamma_const = 0.5 * sig2 * j2 + 0.5 * (r_const - q) * j

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
        if is_curve:
            tau_mid = current_tau + 0.5 * step_dt
            t_cal = max(tau - tau_mid, 1e-6)
            r_step = _get_rate(t_cal)
            alpha = 0.5 * sig2 * j2 - 0.5 * (r_step - q) * j
            beta = -sig2 * j2 - r_step
            gamma = 0.5 * sig2 * j2 + 0.5 * (r_step - q) * j
        else:
            r_step = r_const
            alpha = alpha_const
            beta = beta_const
            gamma = gamma_const

        current_tau += step_dt
        explicit_weight = 1.0 - theta
        implicit_weight = theta

        # Explicit operator on current V
        L_V = alpha * V[0:M-1] + beta * V[1:M] + gamma * V[2:M+1]
        rhs_base = V[1:M] + step_dt * explicit_weight * L_V

        # Boundary conditions at current_tau
        if kind == 'C':
            V_0_new = 0.0
            V_M_new = S_max - K * _get_discount(current_tau)
        else:
            V_0_new = K
            V_M_new = 0.0

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
            exhausted_any = True
            all_converged = False
            max_iter_observed = max_penalty_iter

        if step_rel_diff > max_rel_diff_observed:
            max_rel_diff_observed = step_rel_diff

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
    S_eval: Union[float, np.ndarray],
    K: float,
    kind: str = 'P',
    interp_method: str = 'pchip'
) -> Union[float, np.ndarray]:
    """
    Interpolates option value from solved grid (S_grid, V) at S_eval.
    Enforces monotonicity via PCHIP and American intrinsic lower bound.
    """
    kind = kind.upper()
    is_scalar = np.isscalar(S_eval)
    s_arr = np.atleast_1d(np.asarray(S_eval, dtype=float))

    if interp_method == 'pchip':
        interp = PchipInterpolator(S_grid, V)
    else:
        from scipy.interpolate import interp1d
        interp = interp1d(S_grid, V, kind=interp_method, fill_value='extrapolate')

    val = interp(s_arr)

    # Intrinsic value lower bound control
    if kind == 'C':
        intrinsic = np.maximum(s_arr - K, 0.0)
    else:
        intrinsic = np.maximum(K - s_arr, 0.0)

    val = np.maximum(val, intrinsic)
    return float(val[0]) if is_scalar else val


def fd_american_price_curve(
    kind: str,
    S0: float,
    K: float,
    tau: float,
    curve_or_r: Union[DeterministicYieldCurve, float],
    sigma: float,
    q: float = 0.0,
    M: int = 300,
    N: int = 150,
    S_max: Optional[float] = None,
    S_max_mult: float = 4.0,
    rannacher_steps: int = 4,
    penalty_rho: float = 1e7,
    max_penalty_iter: int = 30,
    penalty_tol: float = 1e-7,
    interp_method: str = "pchip",
    return_diagnostics: bool = False
) -> Union[float, Dict[str, Any]]:
    """
    Prices an American option using 1D Crank-Nicolson PDE with deterministic curve support.
    """
    S_grid, V, diag = fd_american_grid_curve(
        kind=kind,
        S_ref=S0,
        K=K,
        tau=tau,
        curve_or_r=curve_or_r,
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
        diag_out = dict(diag)
        diag_out['price'] = float(price)
        diag_out['S_grid'] = S_grid
        diag_out['V'] = V
        return diag_out
    return float(price)


def invert_american_put_iv(
    target_price: float,
    S0: float,
    K: float,
    tau: float,
    curve_or_r: Union[DeterministicYieldCurve, float],
    q: float = 0.0,
    sigma_min: float = 0.01,
    sigma_max: float = 5.0,
    price_tol: float = 1e-5,
    xtol: float = 1e-5,
    rtol: float = 1e-5,
    max_iter: int = 100,
    M: int = 300,
    N: int = 150
) -> Dict[str, Any]:
    """
    Inverts an American Put price to equivalent implied volatility using Brent's method
    over the 1D American PDE solver with deterministic term structure.

    Checks:
    - Target price positivity
    - Intrinsic lower bound: target_price <= max(K - S0, 0)
    - Upper bound: target_price >= K
    - Near-intrinsic unidentifiability / zero vega: bracket verification at sigma_min and sigma_max
    """
    if target_price <= 0.0:
        return {
            'iv': np.nan,
            'status': 'INVALID_PRICE_NONPOSITIVE',
            'model_price_1d': np.nan,
            'residual_usd': np.nan,
            'iterations': 0,
            'notes': f"Target price nonpositive: {target_price}"
        }

    # Strict economic bounds for American Put
    lb = max(K - S0, 0.0)
    ub = float(K)

    if target_price <= lb:
        return {
            'iv': np.nan,
            'status': 'PRICE_BELOW_INTRINSIC',
            'model_price_1d': lb,
            'residual_usd': float(target_price - lb),
            'iterations': 0,
            'notes': f"Target price {target_price:.5f} <= intrinsic lower bound {lb:.5f}"
        }

    if target_price >= ub:
        return {
            'iv': np.nan,
            'status': 'PRICE_ABOVE_UPPER_BOUND',
            'model_price_1d': ub,
            'residual_usd': float(target_price - ub),
            'iterations': 0,
            'notes': f"Target price {target_price:.5f} >= strike upper bound {ub:.5f}"
        }

    # Near-intrinsic sensitivity check
    # In deep ITM puts, intrinsic value is dominant and time value is minute
    time_val = target_price - lb
    if time_val < 1e-4 and (K / S0) > 1.3:
        # Check if 1D PDE can bracket
        pass

    iteration_count = [0]

    def objective(sig: float) -> float:
        iteration_count[0] += 1
        px = fd_american_price_curve(
            'P', S0, K, tau, curve_or_r, sig, q=q, M=M, N=N
        )
        return float(px) - target_price

    try:
        f_min = objective(sigma_min)
    except Exception as e:
        return {
            'iv': np.nan,
            'status': 'SOLVER_ERROR_LOWER',
            'model_price_1d': np.nan,
            'residual_usd': np.nan,
            'iterations': 1,
            'notes': f"Solver error at sigma_min: {e}"
        }

    if abs(f_min) <= price_tol:
        return {
            'iv': float(sigma_min),
            'status': 'CONVERGED_AT_LOWER_BRACKET',
            'model_price_1d': float(f_min + target_price),
            'residual_usd': float(f_min),
            'iterations': iteration_count[0],
            'notes': "Root at bracket boundary sigma_min"
        }

    try:
        f_max = objective(sigma_max)
    except Exception as e:
        return {
            'iv': np.nan,
            'status': 'SOLVER_ERROR_UPPER',
            'model_price_1d': np.nan,
            'residual_usd': np.nan,
            'iterations': 2,
            'notes': f"Solver error at sigma_max: {e}"
        }

    if abs(f_max) <= price_tol:
        return {
            'iv': float(sigma_max),
            'status': 'CONVERGED_AT_UPPER_BRACKET',
            'model_price_1d': float(f_max + target_price),
            'residual_usd': float(f_max),
            'iterations': iteration_count[0],
            'notes': "Root at bracket boundary sigma_max"
        }

    # Check bracket condition
    if f_min * f_max > 0.0:
        if f_min > 0.0:
            status = 'UNIDENTIFIABLE_VOL_TOO_LOW'
            notes = f"Model price at sigma={sigma_min} ({f_min + target_price:.5f}) > target ({target_price:.5f})"
        else:
            status = 'UNIDENTIFIABLE_VOL_TOO_HIGH'
            notes = f"Model price at sigma={sigma_max} ({f_max + target_price:.5f}) < target ({target_price:.5f})"
        return {
            'iv': np.nan,
            'status': status,
            'model_price_1d': float(f_min + target_price if f_min > 0 else f_max + target_price),
            'residual_usd': float(f_min if f_min > 0 else f_max),
            'iterations': iteration_count[0],
            'notes': notes
        }

    # Brent root finding
    try:
        sol, r_res = brentq(
            objective,
            sigma_min,
            sigma_max,
            xtol=xtol,
            rtol=rtol,
            maxiter=max_iter,
            full_output=True,
            disp=False
        )
        model_px = fd_american_price_curve('P', S0, K, tau, curve_or_r, sol, q=q, M=M, N=N)
        residual = float(model_px) - target_price
        
        status = 'CONVERGED' if r_res.converged else 'FAILED_CONVERGENCE'
        return {
            'iv': float(sol),
            'status': status,
            'model_price_1d': float(model_px),
            'residual_usd': residual,
            'iterations': int(r_res.iterations),
            'notes': f"Brent terminated after {r_res.iterations} iterations, residual={residual:.2e}"
        }
    except Exception as e:
        return {
            'iv': np.nan,
            'status': 'BRENT_EXCEPTION',
            'model_price_1d': np.nan,
            'residual_usd': np.nan,
            'iterations': iteration_count[0],
            'notes': f"Brent exception: {e}"
        }


def price_heston_european_call(
    S0: float,
    K: float,
    tau_days: int,
    params: HestonParams,
    curve: DeterministicYieldCurve,
    ref_date: Optional[Any] = None
) -> float:
    """
    Prices European Call under classical Heston model with deterministic yield curve
    using QuantLib AnalyticHestonEngine.
    """
    if not HAS_QUANTLIB:
        raise RuntimeError("QuantLib is required for AnalyticHestonEngine")

    if ref_date is None:
        ref_date = ql.Date(17, 11, 2026)

    ql.Settings.instance().evaluationDate = ref_date

    # QuantLib term structure from curve discount factors
    tenors = curve.tenors
    dates = [ref_date] + [ref_date + ql.Period(int(round(t * 365)), ql.Days) for t in tenors]
    dfs = [1.0] + [curve.get_discount_factor(t) for t in tenors]
    ql_curve = ql.DiscountCurve(dates, dfs, ql.Actual365Fixed())
    ql_curve_handle = ql.YieldTermStructureHandle(ql_curve)
    q_handle = ql.YieldTermStructureHandle(ql.FlatForward(ref_date, 0.0, ql.Actual365Fixed()))
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(S0))

    heston_process = ql.HestonProcess(
        ql_curve_handle, q_handle, spot_handle,
        params.v0, params.kappa, params.theta, params.xi, params.rho
    )
    heston_model = ql.HestonModel(heston_process)
    heston_engine = ql.AnalyticHestonEngine(heston_model)

    maturity_date = ref_date + ql.Period(int(round(tau_days)), ql.Days)
    payoff = ql.PlainVanillaPayoff(ql.Option.Call, K)
    exercise = ql.EuropeanExercise(maturity_date)
    call_opt = ql.VanillaOption(payoff, exercise)
    call_opt.setPricingEngine(heston_engine)
    return float(call_opt.NPV())


def invert_european_call_iv(
    target_price: float,
    S0: float,
    K: float,
    tau_years: float,
    curve: DeterministicYieldCurve,
    q: float = 0.0,
    sigma_min: float = 0.001,
    sigma_max: float = 5.0,
    price_tol: float = 1e-8,
    xtol: float = 1e-8,
    rtol: float = 1e-8,
    max_iter: int = 100
) -> Dict[str, Any]:
    """
    Inverts European Call price into analytical Black-Scholes IV
    using exact discount factor D(T) from the bootstrap yield curve.
    r_zero = -ln(D(T)) / T.
    """
    if target_price <= 0.0:
        return {
            'iv': np.nan,
            'status': 'INVALID_PRICE_NONPOSITIVE',
            'model_price_bs': np.nan,
            'residual_usd': np.nan,
            'iterations': 0,
            'notes': f"Target price nonpositive: {target_price}"
        }

    D = curve.get_discount_factor(tau_years)
    r_zero = -np.log(D) / tau_years if tau_years > 0 else 0.0

    lb = max(S0 * np.exp(-q * tau_years) - K * D, 0.0)
    ub = S0 * np.exp(-q * tau_years)

    if target_price <= lb:
        return {
            'iv': np.nan,
            'status': 'PRICE_BELOW_LOWER_BOUND',
            'model_price_bs': lb,
            'residual_usd': float(target_price - lb),
            'iterations': 0,
            'notes': f"Target price {target_price:.5f} <= BS lower bound {lb:.5f}"
        }

    if target_price >= ub:
        return {
            'iv': np.nan,
            'status': 'PRICE_ABOVE_UPPER_BOUND',
            'model_price_bs': ub,
            'residual_usd': float(target_price - ub),
            'iterations': 0,
            'notes': f"Target price {target_price:.5f} >= BS upper bound {ub:.5f}"
        }

    iteration_count = [0]

    def objective(sig: float) -> float:
        iteration_count[0] += 1
        px = bs_price('C', S0, K, tau_years, r_zero, sig, q=q)
        return float(px) - target_price

    f_min = objective(sigma_min)
    if abs(f_min) <= price_tol:
        return {
            'iv': float(sigma_min),
            'status': 'CONVERGED_AT_LOWER_BRACKET',
            'model_price_bs': float(f_min + target_price),
            'residual_usd': float(f_min),
            'iterations': iteration_count[0],
            'notes': "Root at bracket boundary sigma_min"
        }

    f_max = objective(sigma_max)
    if abs(f_max) <= price_tol:
        return {
            'iv': float(sigma_max),
            'status': 'CONVERGED_AT_UPPER_BRACKET',
            'model_price_bs': float(f_max + target_price),
            'residual_usd': float(f_max),
            'iterations': iteration_count[0],
            'notes': "Root at bracket boundary sigma_max"
        }

    if f_min * f_max > 0.0:
        if f_min > 0.0:
            status = 'UNIDENTIFIABLE_VOL_TOO_LOW'
            notes = f"Model price at sigma={sigma_min} ({f_min + target_price:.5f}) > target ({target_price:.5f})"
        else:
            status = 'UNIDENTIFIABLE_VOL_TOO_HIGH'
            notes = f"Model price at sigma={sigma_max} ({f_max + target_price:.5f}) < target ({target_price:.5f})"
        return {
            'iv': np.nan,
            'status': status,
            'model_price_bs': float(f_min + target_price if f_min > 0 else f_max + target_price),
            'residual_usd': float(f_min if f_min > 0 else f_max),
            'iterations': iteration_count[0],
            'notes': notes
        }

    try:
        sol, r_res = brentq(
            objective,
            sigma_min,
            sigma_max,
            xtol=xtol,
            rtol=rtol,
            maxiter=max_iter,
            full_output=True,
            disp=False
        )
        model_px = bs_price('C', S0, K, tau_years, r_zero, sol, q=q)
        residual = float(model_px) - target_price
        status = 'CONVERGED' if r_res.converged else 'FAILED_CONVERGENCE'
        return {
            'iv': float(sol),
            'status': status,
            'model_price_bs': float(model_px),
            'residual_usd': residual,
            'iterations': int(r_res.iterations),
            'notes': f"Brent terminated after {r_res.iterations} iterations, residual={residual:.2e}"
        }
    except Exception as e:
        return {
            'iv': np.nan,
            'status': 'BRENT_EXCEPTION',
            'model_price_bs': np.nan,
            'residual_usd': np.nan,
            'iterations': iteration_count[0],
            'notes': f"Brent exception: {e}"
        }
