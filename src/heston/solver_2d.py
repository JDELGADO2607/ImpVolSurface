"""
Proprietary 2D Finite-Difference Solver for European and American Options under Classical Heston (1993).

Method: H-005A — Modified Craig-Sneyd (MCS) ADI scheme (theta_ADI = 1/3)
Early Exercise: Ikonen-Toivanen (IT) operator splitting with auxiliary Lagrange multiplier.

Zero QuantLib dependency in this core solver. QuantLib is used strictly as an external
reference benchmark in testing and audit modules.

Mathematical Formulation:
--------------------------
Let S in [0, S_max] be the asset price, v in [0, v_max] be the instantaneous variance,
tau = T - t in [0, T] be the backward time-to-maturity, where calendar time is t = T - tau.

The 2D Heston Pricing PDE in backward time tau is:
    dV/dtau = L V
with PDE operator:
    L V = A0 V + A1 V + A2 V
where:
    A0 V = rho * xi * v * S * (d^2 V / (dS dv))                       [Mixed cross-derivative]
    A1 V = 0.5 * v * S^2 * (d^2 V / dS^2) + (r(t) - q) * S * (dV/dS) - 0.5 * r(t) * V
    A2 V = 0.5 * xi^2 * v * (d^2 V / dv^2) + kappa * (theta - v) * (dV/dv) - 0.5 * r(t) * V

For European options:
    dV/dtau = L V,   V(S, v, 0) = g(S) = max(K - S, 0)
For American options (Linear Complementarity Problem / PDCP):
    min( V - g,  dV/dtau - L V ) = 0
or equivalently:
    dV/dtau - L V = lambda,  lambda >= 0,  V >= g,  lambda * (V - g) = 0
where lambda(S, v, tau) is the early exercise obstacle Lagrange multiplier.

Modified Craig-Sneyd (MCS) Time-Stepping (theta = 1/3, In 't Hout & Foulon 2010):
---------------------------------------------------------------------------------
From tau_{n-1} to tau_n = tau_{n-1} + dt:
    Y0      = U^{n-1} + dt * (A0 + A1 + A2) U^{n-1} + dt * lambda^{n-1}
    (I - theta*dt*A1) Y1 = Y0 - theta*dt*A1 U^{n-1}
    (I - theta*dt*A2) Y2 = Y1 - theta*dt*A2 U^{n-1}
    Y0_tilde = Y0 + theta*dt*(A0 Y2 - A0 U^{n-1}) + (0.5 - theta)*dt*(F(Y2) - F(U^{n-1}))
    (I - theta*dt*A1) Y1_tilde = Y0_tilde - theta*dt*A1 U^{n-1}
    (I - theta*dt*A2) Y2_hat   = Y1_tilde - theta*dt*A2 U^{n-1}

Ikonen-Toivanen (IT) Early Exercise Splitting (Haentjens & In 't Hout 2013/2015):
--------------------------------------------------------------------------------
    For European: U^n = Y2_hat,  lambda^n = 0
    For American:
        U^n      = max( Y2_hat - dt * lambda^{n-1},  g )
        lambda^n = max( 0,  lambda^{n-1} + (g - Y2_hat) / dt )
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any, Union
import time
import numpy as np
from scipy.interpolate import RegularGridInterpolator

from src.heston.rates_curve import DeterministicYieldCurve, SPOT_PRICE, DIVIDEND_YIELD
from src.heston.heston_model import HestonParams


@dataclass
class Heston2DSolverResult:
    """
    Detailed output and diagnostics from proprietary 2D Heston solver.
    
    Sensitivities (delta, gamma, d_price_d_v0):
    These are preliminary grid-based finite-difference diagnostics evaluated at (spot, v0).
    They are NOT validated for trading book hedging or dynamic risk management in Phase 2.
    
    Units:
    - price: USD
    - delta: dPrice / dS (unitless / USD per USD)
    - gamma: d^2Price / dS^2 (1 / USD)
    - d_price_d_v0: dPrice / dv0 (USD / unit variance, NOT IV vega)
    - vega: backward-compatible alias for d_price_d_v0 (USD / unit variance)
    - theta: None (not available in Phase 2; preliminary placeholder removed)
    - max_algebraic_complementarity_residual: max |lambda * (U - g)| (USD^2 / year)
    - max_complementarity_residual: backward-compatible alias (USD^2 / year)
    - max_feasibility_violation: max(g - U, 0) (USD)
    - max_multiplier_violation: max(-lambda, 0) (USD / year)
    """
    price: float
    delta: float
    gamma: float
    d_price_d_v0: float
    vega: float
    theta: Optional[float]
    option_type: str
    is_american: bool
    strike: float
    maturity_years: float
    spot: float
    v0: float
    params: HestonParams
    n_s: int
    n_v: int
    m_t: int
    s_max: float
    v_max: float
    theta_adi: float
    wall_time_seconds: float
    max_feasibility_violation: float
    max_multiplier_violation: float
    max_algebraic_complementarity_residual: float
    max_complementarity_residual: float
    grid_s: np.ndarray
    grid_v: np.ndarray
    grid_v_surface: np.ndarray
    grid_lambda: np.ndarray


class Grid2D:
    """
    Non-uniform Cartesian grid in (S, v) space with smooth hyperbolic sine concentration.
    
    Axes convention:
    - Axis 0 (rows): Spot price S, shape (N_s + 1,)
    - Axis 1 (cols): Variance v, shape (N_v + 1,)
    
    Spatial clustering:
    - S grid: clustered around strike K using arcsinh transformation:
        S(xi) = K + d_s * sinh(xi)
      where xi in [xi_min, xi_max], guaranteeing S(0) = 0 and S(xi_max) = S_max.
    - v grid: clustered near v = 0 and v = v0 using arcsinh transformation:
        v(eta) = d_v * sinh(eta)
      where eta in [0, eta_max], guaranteeing v(0) = 0 and v(eta_max) = v_max.
    """

    def __init__(
        self,
        strike: float,
        v0: float,
        n_s: int = 160,
        n_v: int = 80,
        s_max: Optional[float] = None,
        v_max: Optional[float] = None,
        d_s_scale: float = 0.10,
        d_v_scale: float = 0.50
    ):
        self.strike = float(strike)
        self.v0 = float(v0)
        self.n_s = int(n_s)
        self.n_v = int(n_v)
        
        # Grid boundaries
        self.s_max = float(s_max) if s_max is not None else max(5.0 * self.strike, 100.0)
        self.v_max = float(v_max) if v_max is not None else max(10.0 * self.v0, 10.0)
        
        # Scale parameters for clustering
        self.d_s = max(self.strike * d_s_scale, 0.50)
        self.d_v = max(self.v0 * d_v_scale, 0.05)
        
        # Build coordinates
        self.s = self._build_s_grid()
        self.v = self._build_v_grid()
        
        # 2D Meshes
        self.s_mesh, self.v_mesh = np.meshgrid(self.s, self.v, indexing="ij")
        
        # Finite difference stencils on non-uniform 1D meshes
        self.st_s = self._compute_1d_stencils(self.s)
        self.st_v = self._compute_1d_stencils(self.v)

    def _build_s_grid(self) -> np.ndarray:
        xi_min = np.arcsinh(-self.strike / self.d_s)
        xi_max = np.arcsinh((self.s_max - self.strike) / self.d_s)
        xi = np.linspace(xi_min, xi_max, self.n_s + 1)
        s = self.strike + self.d_s * np.sinh(xi)
        s[0] = 0.0
        s[-1] = self.s_max
        return s

    def _build_v_grid(self) -> np.ndarray:
        eta_max = np.arcsinh(self.v_max / self.d_v)
        eta = np.linspace(0.0, eta_max, self.n_v + 1)
        v = self.d_v * np.sinh(eta)
        v[0] = 0.0
        v[-1] = self.v_max
        return v

    @staticmethod
    def _compute_1d_stencils(x: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Computes 2nd-order finite difference coefficients on non-uniform 1D mesh.
        
        For interior node x_i with h_l = x_i - x_{i-1} and h_r = x_{i+1} - x_i:
            f'(x_i)  approx alpha_i * f_{i-1} + beta_i * f_i + gamma_i * f_{i+1}
            f''(x_i) approx delta_i * f_{i-1} + epsilon_i * f_i + zeta_i * f_{i+1}
        """
        n = len(x) - 1
        h = np.diff(x)
        
        alpha = np.zeros(n + 1)
        beta = np.zeros(n + 1)
        gamma = np.zeros(n + 1)
        
        delta = np.zeros(n + 1)
        epsilon = np.zeros(n + 1)
        zeta = np.zeros(n + 1)
        
        h_l = h[:-1]
        h_r = h[1:]
        sum_h = h_l + h_r
        
        alpha[1:-1] = -h_r / (h_l * sum_h)
        beta[1:-1] = (h_r - h_l) / (h_l * h_r)
        gamma[1:-1] = h_l / (h_r * sum_h)
        
        delta[1:-1] = 2.0 / (h_l * sum_h)
        epsilon[1:-1] = -2.0 / (h_l * h_r)
        zeta[1:-1] = 2.0 / (h_r * sum_h)
        
        return {
            "alpha": alpha, "beta": beta, "gamma": gamma,
            "delta": delta, "epsilon": epsilon, "zeta": zeta,
            "h": h
        }


def solve_tridiagonal_vectorized(
    sub: np.ndarray,
    diag: np.ndarray,
    sup: np.ndarray,
    rhs: np.ndarray
) -> np.ndarray:
    """
    Solves A X = RHS for multiple right-hand sides simultaneously using Thomas algorithm.
    
    Parameters:
    -----------
    sub  : (N-1,) or (N-1, M) array, subdiagonal
    diag : (N,) or (N, M) array, main diagonal
    sup  : (N-1,) or (N-1, M) array, superdiagonal
    rhs  : (N, M) array, right hand sides
    
    Returns:
    --------
    X : (N, M) array, solution
    """
    n, m = rhs.shape
    cp = np.zeros((n, m), dtype=float)
    dp = np.zeros((n, m), dtype=float)
    
    sub_mat = np.tile(sub[:, None], (1, m)) if sub.ndim == 1 else sub
    diag_mat = np.tile(diag[:, None], (1, m)) if diag.ndim == 1 else diag
    sup_mat = np.tile(sup[:, None], (1, m)) if sup.ndim == 1 else sup
    
    # Forward sweep
    cp[0] = sup_mat[0] / diag_mat[0]
    dp[0] = rhs[0] / diag_mat[0]
    
    for i in range(1, n - 1):
        denom = diag_mat[i] - sub_mat[i - 1] * cp[i - 1]
        cp[i] = sup_mat[i] / denom
        dp[i] = (rhs[i] - sub_mat[i - 1] * dp[i - 1]) / denom
        
    denom_last = diag_mat[n - 1] - sub_mat[n - 2] * cp[n - 2]
    dp[n - 1] = (rhs[n - 1] - sub_mat[n - 2] * dp[n - 2]) / denom_last
    
    # Back substitution
    sol = np.zeros((n, m), dtype=float)
    sol[n - 1] = dp[n - 1]
    for i in range(n - 2, -1, -1):
        sol[i] = dp[i] - cp[i] * sol[i + 1]
        
    return sol


class Heston2DSolver:
    """
    Proprietary 2D Finite Difference Option Pricing Engine under Classical Heston (1993).
    
    Combines:
    - Modified Craig-Sneyd (MCS) ADI splitting (theta_ADI = 1/3)
    - Ikonen-Toivanen (IT) operator splitting for early exercise obstacle
    - Piecewise forward rate evaluation r(t = T - tau) from official bootstrap yield curve
    - Upwind degenerate boundary conditions at v = 0 and linear boundary at v = v_max
    """

    def __init__(
        self,
        grid_config: Optional[Dict[str, Any]] = None,
        theta_adi: float = 1.0 / 3.0
    ):
        self.grid_config = grid_config or {}
        self.theta_adi = float(theta_adi)

    def price(
        self,
        strike: float,
        maturity_years: float,
        params: HestonParams,
        curve: Union[DeterministicYieldCurve, float],
        spot: float = SPOT_PRICE,
        dividend_yield: float = DIVIDEND_YIELD,
        option_type: str = "P",
        is_american: bool = True,
        n_s: Optional[int] = None,
        n_v: Optional[int] = None,
        m_t: Optional[int] = None,
        s_max: Optional[float] = None,
        v_max: Optional[float] = None
    ) -> Heston2DSolverResult:
        """
        Prices European or American option using 2D MCS-IT finite difference solver.
        
        Parameters:
        -----------
        strike : float
            Option strike price K.
        maturity_years : float
            Maturity T in ACT/365F years.
        params : HestonParams
            Classical 5 Heston parameters (v0, kappa, theta, xi, rho).
        curve : DeterministicYieldCurve or float
            Term structure or constant risk-free rate.
        spot : float, default SPOT_PRICE (12.33)
            Current asset spot price S0.
        dividend_yield : float, default 0.0
            Continuous dividend yield q.
        option_type : str, default 'P'
            'P' for Put, 'C' for Call. (Phase 2 primary is Put).
        is_american : bool, default True
            True for American early exercise, False for European.
        n_s, n_v, m_t : int, optional
            Mesh node counts. Default: n_s=160, n_v=80, m_t=max(60, int(300*T)).
        """
        if option_type.upper() not in ("P", "PUT"):
            raise ValueError(
                f"Option type '{option_type}' is not supported by Heston2DSolver. "
                "The 2D solver is currently authorized strictly for Put options ('P' or 'PUT'). "
                "Call pricing is not supported in Phase 2."
            )

        t_start = time.perf_counter()
        
        if maturity_years <= 0.0:
            payoff_val = max(strike - spot, 0.0)
            return Heston2DSolverResult(
                price=payoff_val,
                delta=-1.0 if spot < strike else 0.0,
                gamma=0.0,
                d_price_d_v0=0.0,
                vega=0.0,
                theta=None,
                option_type="P",
                is_american=is_american,
                strike=strike,
                maturity_years=0.0,
                spot=spot,
                v0=params.v0,
                params=params,
                n_s=0,
                n_v=0,
                m_t=0,
                s_max=0.0,
                v_max=0.0,
                theta_adi=self.theta_adi,
                wall_time_seconds=0.0,
                max_feasibility_violation=0.0,
                max_multiplier_violation=0.0,
                max_algebraic_complementarity_residual=0.0,
                max_complementarity_residual=0.0,
                grid_s=np.array([spot]),
                grid_v=np.array([params.v0]),
                grid_v_surface=np.array([[payoff_val]]),
                grid_lambda=np.array([[0.0]])
            )
            
        # Default grid dimensions
        n_s = n_s or self.grid_config.get("n_s", 160)
        n_v = n_v or self.grid_config.get("n_v", 80)
        if m_t is None:
            m_t = self.grid_config.get("m_t", max(60, int(round(300.0 * maturity_years))))
            
        grid = Grid2D(
            strike=strike,
            v0=params.v0,
            n_s=n_s,
            n_v=n_v,
            s_max=s_max,
            v_max=v_max
        )
        
        dt = maturity_years / m_t
        S = grid.s
        v = grid.v
        st_S = grid.st_s
        st_v = grid.st_v
        
        # Payoff at tau = 0 (Put option only)
        g = np.maximum(strike - grid.s_mesh, 0.0)
        U = g.copy()
        lambd = np.zeros_like(U)
        
        # Sliced 1D stencil weights for fast vectorization
        a_S = st_S["alpha"][1:-1, None]
        b_S = st_S["beta"][1:-1, None]
        c_S = st_S["gamma"][1:-1, None]
        d_S = st_S["delta"][1:-1, None]
        e_S = st_S["epsilon"][1:-1, None]
        z_S = st_S["zeta"][1:-1, None]
        S_int = S[1:-1, None]
        
        a_v = st_v["alpha"][None, 1:-1]
        b_v = st_v["beta"][None, 1:-1]
        c_v = st_v["gamma"][None, 1:-1]
        d_v = st_v["delta"][None, 1:-1]
        e_v = st_v["epsilon"][None, 1:-1]
        z_v = st_v["zeta"][None, 1:-1]
        
        h_v0 = st_v["h"][0]
        h_v_last = st_v["h"][-1]
        drift_v_last = params.kappa * (params.theta - v[-1])
        
        # Helper for forward rate query
        def _get_rate(cal_t: float) -> float:
            if isinstance(curve, (int, float)):
                return float(curve)
            return curve.get_instantaneous_forward_rate(cal_t)
        
        def _get_discount(t_val: float) -> float:
            if isinstance(curve, (int, float)):
                return float(np.exp(-float(curve) * t_val))
            return curve.get_discount_factor(t_val)

        # Vectorized operator application functions
        def apply_A0(U_curr: np.ndarray) -> np.ndarray:
            """Cross-derivative operator A0 V = rho * xi * v * S * V_Sv."""
            D_S = np.zeros_like(U_curr)
            D_S[1:-1, :] = a_S * U_curr[:-2, :] + b_S * U_curr[1:-1, :] + c_S * U_curr[2:, :]
            
            D_v_D_S = np.zeros_like(U_curr)
            D_v_D_S[:, 1:-1] = a_v * D_S[:, :-2] + b_v * D_S[:, 1:-1] + c_v * D_S[:, 2:]
            
            res = params.rho * params.xi * grid.s_mesh * grid.v_mesh * D_v_D_S
            res[0, :] = 0.0
            res[-1, :] = 0.0
            res[:, 0] = 0.0
            res[:, -1] = 0.0
            return res

        def apply_A1(U_curr: np.ndarray, r_val: float) -> np.ndarray:
            """Unmixed S operator A1 V."""
            res = np.zeros_like(U_curr)
            U_SS = d_S * U_curr[:-2, :] + e_S * U_curr[1:-1, :] + z_S * U_curr[2:, :]
            U_S = a_S * U_curr[:-2, :] + b_S * U_curr[1:-1, :] + c_S * U_curr[2:, :]
            res[1:-1, :] = (0.5 * grid.v_mesh[1:-1, :] * (S_int ** 2) * U_SS +
                            (r_val - dividend_yield) * S_int * U_S -
                            0.5 * r_val * U_curr[1:-1, :])
            return res

        def apply_A2(U_curr: np.ndarray, r_val: float) -> np.ndarray:
            """Unmixed v operator A2 V with boundary stencils at v=0 and v=v_max."""
            res = np.zeros_like(U_curr)
            U_vv = d_v * U_curr[:, :-2] + e_v * U_curr[:, 1:-1] + z_v * U_curr[:, 2:]
            U_v = a_v * U_curr[:, :-2] + b_v * U_curr[:, 1:-1] + c_v * U_curr[:, 2:]
            res[:, 1:-1] = (0.5 * (params.xi ** 2) * grid.v_mesh[:, 1:-1] * U_vv +
                            params.kappa * (params.theta - grid.v_mesh[:, 1:-1]) * U_v -
                            0.5 * r_val * U_curr[:, 1:-1])
            # Degenerate boundary at v = 0: forward difference into domain
            res[:, 0] = (params.kappa * params.theta * (U_curr[:, 1] - U_curr[:, 0]) / h_v0 -
                         0.5 * r_val * U_curr[:, 0])
            # Outer boundary at v = v_max: upwind backward difference
            res[:, -1] = (drift_v_last * (U_curr[:, -1] - U_curr[:, -2]) / h_v_last -
                          0.5 * r_val * U_curr[:, -1])
            return res

        # Allocate tridiagonal operator matrices
        sub2 = np.zeros(n_v)
        diag2 = np.zeros(n_v + 1)
        sup2 = np.zeros(n_v)
        
        coeff_vv = 0.5 * (params.xi ** 2) * v[1:-1]
        coeff_v = params.kappa * (params.theta - v[1:-1])
        
        sub2[:-1] = -self.theta_adi * dt * (coeff_vv * st_v["delta"][1:-1] + coeff_v * st_v["alpha"][1:-1])
        sup2[1:] = -self.theta_adi * dt * (coeff_vv * st_v["zeta"][1:-1] + coeff_v * st_v["gamma"][1:-1])
        sup2[0] = -self.theta_adi * dt * (params.kappa * params.theta / h_v0)
        sub2[-1] = -self.theta_adi * dt * (-drift_v_last / h_v_last)
        
        sub1 = np.zeros((n_s, n_v + 1))
        diag1 = np.zeros((n_s + 1, n_v + 1))
        sup1 = np.zeros((n_s, n_v + 1))
        diag1[0, :] = 1.0
        diag1[-1, :] = 1.0

        max_feas = 0.0
        max_mult = 0.0
        max_comp = 0.0

        # Time-stepping loop
        for m in range(1, m_t + 1):
            tau_m = m * dt
            tau_mid = (m - 0.5) * dt
            t_cal = max(maturity_years - tau_mid, 1e-6)
            r_val = _get_rate(t_cal)
            
            # Boundary at S = 0 for put
            if is_american:
                b_S0 = strike
            else:
                b_S0 = strike * _get_discount(maturity_years) / _get_discount(max(maturity_years - tau_m, 1e-6))
                
            # Update A1 tridiagonals with current r
            coeff_SS = 0.5 * v[None, :] * (S[1:-1, None] ** 2)
            coeff_S = (r_val - dividend_yield) * S[1:-1, None]
            sub1[:-1, :] = -self.theta_adi * dt * (coeff_SS * d_S + coeff_S * a_S)
            diag1[1:-1, :] = 1.0 - self.theta_adi * dt * (coeff_SS * e_S + coeff_S * b_S - 0.5 * r_val)
            sup1[1:, :] = -self.theta_adi * dt * (coeff_SS * z_S + coeff_S * c_S)
            
            # Update A2 diagonal with current r
            diag2[0] = 1.0 - self.theta_adi * dt * (-params.kappa * params.theta / h_v0 - 0.5 * r_val)
            diag2[1:-1] = 1.0 - self.theta_adi * dt * (coeff_vv * st_v["epsilon"][1:-1] + coeff_v * st_v["beta"][1:-1] - 0.5 * r_val)
            diag2[-1] = 1.0 - self.theta_adi * dt * (drift_v_last / h_v_last - 0.5 * r_val)

            # Step 0: Explicit Predictor
            A0_U = apply_A0(U)
            A1_U = apply_A1(U, r_val)
            A2_U = apply_A2(U, r_val)
            F_U = A0_U + A1_U + A2_U
            Y0 = U + dt * F_U + dt * lambd
            
            # Step 1: Implicit S solve
            rhs1 = Y0 - self.theta_adi * dt * A1_U
            rhs1[0, :] = b_S0
            rhs1[-1, :] = 0.0
            Y1 = solve_tridiagonal_vectorized(sub1, diag1, sup1, rhs1)
            
            # Step 2: Implicit v solve
            rhs2 = Y1 - self.theta_adi * dt * A2_U
            Y2_T = solve_tridiagonal_vectorized(sub2, diag2, sup2, rhs2.T)
            Y2 = Y2_T.T
            
            # Step 3: Modified Craig-Sneyd Corrector with (1/2 - theta) stabilization
            A0_Y2 = apply_A0(Y2)
            A1_Y2 = apply_A1(Y2, r_val)
            A2_Y2 = apply_A2(Y2, r_val)
            F_Y2 = A0_Y2 + A1_Y2 + A2_Y2
            Y0_tilde = Y0 + self.theta_adi * dt * (A0_Y2 - A0_U) + (0.5 - self.theta_adi) * dt * (F_Y2 - F_U)
            
            # Step 4: Implicit S solve
            rhs3 = Y0_tilde - self.theta_adi * dt * A1_U
            rhs3[0, :] = b_S0
            rhs3[-1, :] = 0.0
            Y1_tilde = solve_tridiagonal_vectorized(sub1, diag1, sup1, rhs3)
            
            # Step 5: Implicit v solve
            rhs4 = Y1_tilde - self.theta_adi * dt * A2_U
            Y2_hat_T = solve_tridiagonal_vectorized(sub2, diag2, sup2, rhs4.T)
            Y2_hat = Y2_hat_T.T
            
            # Step 6: Ikonen-Toivanen Operator Splitting for American Early Exercise
            if is_american:
                U_new = np.maximum(Y2_hat - dt * lambd, g)
                lambd_new = np.maximum(0.0, lambd + (g - Y2_hat) / dt)
                
                # Complementarity & Feasibility diagnostics
                comp_err = np.max(np.abs(lambd_new * (U_new - g)))
                feas_err = np.max(np.maximum(g - U_new, 0.0))
                mult_err = np.max(np.maximum(-lambd_new, 0.0))
                if comp_err > max_comp:
                    max_comp = float(comp_err)
                if feas_err > max_feas:
                    max_feas = float(feas_err)
                if mult_err > max_mult:
                    max_mult = float(mult_err)
                    
                U = U_new
                lambd = lambd_new
            else:
                U = Y2_hat
                lambd = np.zeros_like(U)

        # 2D Interpolation to (spot, v0)
        interp = RegularGridInterpolator((S, v), U, method="cubic")
        price_val = float(interp((spot, params.v0)))
        
        # Finite difference Greeks at (spot, v0)
        h_s_greek = 0.01 * spot
        p_plus_s = float(interp((min(spot + h_s_greek, grid.s_max - 1e-4), params.v0)))
        p_minus_s = float(interp((max(spot - h_s_greek, 1e-4), params.v0)))
        delta_val = (p_plus_s - p_minus_s) / (2.0 * h_s_greek)
        gamma_val = (p_plus_s - 2.0 * price_val + p_minus_s) / (h_s_greek ** 2)
        
        h_v_greek = 0.01 * max(params.v0, 0.01)
        p_plus_v = float(interp((spot, min(params.v0 + h_v_greek, grid.v_max - 1e-4))))
        p_minus_v = float(interp((spot, max(params.v0 - h_v_greek, 1e-6))))
        d_price_d_v0_val = (p_plus_v - p_minus_v) / (2.0 * h_v_greek)
        vega_val = d_price_d_v0_val  # backward-compatible alias for d_price_d_v0 (USD / unit variance)
        
        # Theta is not available in Phase 2 (preliminary placeholder removed)
        theta_val = None
        
        wall_time = time.perf_counter() - t_start
        
        return Heston2DSolverResult(
            price=price_val,
            delta=delta_val,
            gamma=gamma_val,
            d_price_d_v0=d_price_d_v0_val,
            vega=vega_val,
            theta=theta_val,
            option_type="P",
            is_american=is_american,
            strike=strike,
            maturity_years=maturity_years,
            spot=spot,
            v0=params.v0,
            params=params,
            n_s=n_s,
            n_v=n_v,
            m_t=m_t,
            s_max=grid.s_max,
            v_max=grid.v_max,
            theta_adi=self.theta_adi,
            wall_time_seconds=wall_time,
            max_feasibility_violation=max_feas,
            max_multiplier_violation=max_mult,
            max_algebraic_complementarity_residual=max_comp,
            max_complementarity_residual=max_comp,
            grid_s=S,
            grid_v=v,
            grid_v_surface=U,
            grid_lambda=lambd
        )


def compute_temporal_consistency_defect(
    solver: Optional[Heston2DSolver] = None,
    strike: float = 12.33,
    maturity_years: float = 0.25,
    params: Optional[HestonParams] = None,
    rate: float = 0.05,
    m_t_values: Tuple[int, ...] = (20, 40, 80),
    n_s: int = 80,
    n_v: int = 40,
    s_core_range: Tuple[float, float] = (8.0, 18.0),
    v_core_range: Tuple[float, float] = (0.04, 0.40)
) -> List[Dict[str, Any]]:
    """
    Computes the independent interior trapezoidal PDE consistency defect:
        E = U_n - U_{n-1} - dt * [ 0.5 * (L_h U_n + L_h U_{n-1}) + 0.5 * (lambda_n + lambda_{n-1}) ]
    on the interior core domain (s_core_range, v_core_range).
    
    This diagnostic verifies that the temporal time-stepping error behaves as O(dt^2)
    and distinguishes the continuous PDE consistency defect from the algebraic
    Ikonen-Toivanen complementarity identity lambda * (U - g) == 0.
    """
    solver = solver or Heston2DSolver()
    params = params or HestonParams(
        v0=0.18613777847584,
        kappa=2.7254603668370714,
        theta=0.2136796992000426,
        xi=0.4817847258429695,
        rho=-0.9498066630129804
    )
    
    def _derivative_weights(x: np.ndarray, order: int) -> np.ndarray:
        w = []
        for i in range(1, len(x) - 1):
            dx = x[i - 1:i + 2] - x[i]
            mat = np.stack((np.ones(3), dx, dx * dx))
            target = np.array([0.0, 1.0, 0.0]) if order == 1 else np.array([0.0, 0.0, 2.0])
            w.append(np.linalg.solve(mat, target))
        return np.asarray(w)

    def _apply_L(res: Heston2DSolverResult) -> np.ndarray:
        U = res.grid_v_surface
        S = res.grid_s
        v = res.grid_v
        a = _derivative_weights(S, 1)
        b = _derivative_weights(S, 2)
        d = _derivative_weights(v, 1)
        e = _derivative_weights(v, 2)
        
        ds = sum(a[:, j, None] * U[j:len(S) - 2 + j, :] for j in range(3))
        dss = sum(b[:, j, None] * U[j:len(S) - 2 + j, :] for j in range(3))
        dv = sum(d[None, :, j] * U[:, j:len(v) - 2 + j] for j in range(3))
        dvv = sum(e[None, :, j] * U[:, j:len(v) - 2 + j] for j in range(3))
        mixed = sum(d[None, :, j] * ds[:, j:len(v) - 2 + j] for j in range(3))
        
        SS = S[1:-1, None]
        vv = v[None, 1:-1]
        u = U[1:-1, 1:-1]
        
        return (
            0.5 * vv * (SS ** 2) * dss[:, 1:-1]
            + rate * SS * ds[:, 1:-1]
            + 0.5 * (params.xi ** 2) * vv * dvv[1:-1, :]
            + params.kappa * (params.theta - vv) * dv[1:-1, :]
            + params.rho * params.xi * vv * SS * mixed
            - rate * u
        )

    results = []
    prev_norm = None
    for N in m_t_values:
        T = maturity_years
        dt = T / N
        r = solver.price(strike, T, params, rate, is_american=True, n_s=n_s, n_v=n_v, m_t=N)
        prev = solver.price(strike, T - dt, params, rate, is_american=True, n_s=n_s, n_v=n_v, m_t=N - 1)
        
        u = r.grid_v_surface[1:-1, 1:-1]
        up = prev.grid_v_surface[1:-1, 1:-1]
        lam = 0.5 * (r.grid_lambda + prev.grid_lambda)[1:-1, 1:-1]
        
        defect = u - up - dt * (0.5 * (_apply_L(r) + _apply_L(prev)) + lam)
        mask = (
            (r.grid_s[1:-1, None] > s_core_range[0]) & (r.grid_s[1:-1, None] < s_core_range[1]) &
            (r.grid_v[None, 1:-1] > v_core_range[0]) & (r.grid_v[None, 1:-1] < v_core_range[1])
        )
        max_defect_core = float(np.max(np.abs(defect[mask])))
        norm_per_year = max_defect_core / dt
        ratio = (prev_norm / norm_per_year) if prev_norm is not None else None
        prev_norm = norm_per_year
        
        results.append({
            "m_t": N,
            "dt": dt,
            "max_algebraic_comp_residual": r.max_algebraic_complementarity_residual,
            "max_price_step_defect_core": max_defect_core,
            "norm_per_year": norm_per_year,
            "convergence_ratio": ratio
        })
        
    return results
