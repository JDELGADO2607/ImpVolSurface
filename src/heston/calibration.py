"""
Heston multi-start calibration engine on American Put training set.

Calibration Specification:
- Model: Classical 5-parameter Heston Q (v0, kappa, theta, xi, rho)
- Pricing Engine: QuantLib FdHestonVanillaEngine with AmericanExercise
- Loss Function: Unweighted Sum of Squared Errors (SSE) on observed market prices in train:
      SSE(Theta) = sum_{i in train} (P_i^model(Theta) - P_i^mkt)^2
- Optimizer: Scipy L-BFGS-B respecting strictly pre-declared parameter bounds
- Multi-start: 5 dispersed starts covering positive and negative rho, varying Feller regimes
"""

import time
from typing import Dict, List, Tuple, Optional, Any, Callable
import numpy as np
import pandas as pd
from scipy.optimize import minimize

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

from src.heston.rates_curve import DeterministicYieldCurve, get_official_yield_curve, SPOT_PRICE, DIVIDEND_YIELD
from src.heston.heston_model import HestonParams, HestonOptionPricer


# Pre-declared search bounds for Heston parameters
HESTON_BOUNDS: List[Tuple[float, float]] = [
    (0.01, 1.5),    # v0: initial variance
    (0.10, 15.0),   # kappa: mean reversion rate
    (0.01, 1.5),    # theta: long-term variance
    (0.05, 3.0),    # xi: vol-of-vol
    (-0.95, 0.95),  # rho: spot-vol correlation
]

# Pre-declared 5 dispersed starting points across parameter hypercube
HESTON_5_STARTS: List[Dict[str, Any]] = [
    {
        "index": 1,
        "name": "Start_1_Canonical_Skew",
        "description": "Canonical equity negative correlation with moderate mean reversion",
        "params": [0.20, 2.0, 0.20, 0.50, -0.50],
    },
    {
        "index": 2,
        "name": "Start_2_Positive_Rho",
        "description": "Positive correlation to test optimizer navigation without imposing negative sign a priori",
        "params": [0.15, 1.0, 0.25, 0.40, 0.30],
    },
    {
        "index": 3,
        "name": "Start_3_High_VolVol_Low_Kappa",
        "description": "High vol-of-vol, low mean reversion, intentionally starting in Feller violation regime",
        "params": [0.35, 0.5, 0.35, 1.20, -0.70],
    },
    {
        "index": 4,
        "name": "Start_4_Fast_Mean_Reversion",
        "description": "High kappa (rapid variance decay), moderate vol-of-vol",
        "params": [0.10, 5.0, 0.15, 0.80, -0.20],
    },
    {
        "index": 5,
        "name": "Start_5_Zero_Correlation",
        "description": "Zero correlation benchmark (symmetric stochastic volatility smile)",
        "params": [0.25, 1.5, 0.20, 0.60, 0.00],
    },
]


class HestonCalibrator:
    """
    Calibrates classical Heston model to American put options on the training split.
    Tracks all starts, convergence, diagnostics, and parameter identification.
    """

    def __init__(
        self,
        train_df: pd.DataFrame,
        yield_term_structure: Optional["ql.YieldTermStructureHandle"] = None,
        eval_date: Optional["ql.Date"] = None,
        bounds: Optional[List[Tuple[float, float]]] = None,
        grid_t_factor: float = 50.0,
        grid_x: int = 70,
        grid_v: int = 35,
        min_time_steps: int = 25
    ):
        if not HAS_QUANTLIB:
            raise RuntimeError("QuantLib is required for HestonCalibrator.")

        self.train_df = train_df.copy()
        self.bounds = bounds or HESTON_BOUNDS
        self.grid_t_factor = grid_t_factor
        self.grid_x = grid_x
        self.grid_v = grid_v
        self.min_time_steps = min_time_steps
        self.eval_error_count: int = 0
        self.eval_count: int = 0

        self.eval_date = eval_date or ql.Date(17, 11, 2026)
        ql.Settings.instance().evaluationDate = self.eval_date
        self.day_counter = ql.Actual365Fixed()

        self.spot_quote = ql.SimpleQuote(SPOT_PRICE)
        self.spot_handle = ql.QuoteHandle(self.spot_quote)
        self.div_curve = ql.FlatForward(self.eval_date, DIVIDEND_YIELD, self.day_counter)
        self.div_handle = ql.YieldTermStructureHandle(self.div_curve)

        if yield_term_structure is None:
            curve = get_official_yield_curve(method="bootstrap")
            self.ts_handle = curve.to_quantlib_term_structure(dense_daily=True)
        else:
            self.ts_handle = yield_term_structure

        self.last_eval_error: Optional[str] = None
        # Pre-instantiate contracts to avoid overhead during optimization
        self.contracts = self._prepare_contracts()

    def _prepare_contracts(self) -> List[Tuple[Any, float, float, float]]:
        """Pre-constructs American put option objects and extracts targets."""
        contract_list = []
        for _, row in self.train_df.iterrows():
            K = float(row["strike"])
            mkt_price = float(row["lastPrice"])
            dt_parts = [int(x) for x in str(row["expirationDate"]).split("-")]
            exp_date = ql.Date(dt_parts[2], dt_parts[1], dt_parts[0])
            T = self.day_counter.yearFraction(self.eval_date, exp_date)

            payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
            exercise = ql.AmericanExercise(self.eval_date, exp_date)
            opt = ql.VanillaOption(payoff, exercise)
            contract_list.append((opt, mkt_price, K, T))
        return contract_list

    def evaluate_sse(self, params_arr: np.ndarray) -> float:
        """
        Evaluates unweighted Sum of Squared Errors on the training set.
        Returns heavy penalty if parameters fall strictly outside bounds.
        """
        for val, (b_low, b_high) in zip(params_arr, self.bounds):
            if val < b_low or val > b_high:
                return 1e8

        v0, kappa, theta, xi, rho = params_arr
        try:
            proc = ql.HestonProcess(
                self.ts_handle,
                self.div_handle,
                self.spot_handle,
                float(v0),
                float(kappa),
                float(theta),
                float(xi),
                float(rho)
            )
            model = ql.HestonModel(proc)

            sse = 0.0
            for opt, mkt, K, T in self.contracts:
                time_steps = max(self.min_time_steps, int(round(self.grid_t_factor * T)))
                engine = ql.FdHestonVanillaEngine(model, time_steps, self.grid_x, self.grid_v)
                opt.setPricingEngine(engine)
                price = opt.NPV()
                diff = price - mkt
                sse += diff * diff

            self.eval_count += 1
            return float(sse)
        except Exception as e:
            self.last_eval_error = str(e)
            self.eval_error_count += 1
            return 1e8

    def run_single_start(
        self,
        start_def: Dict[str, Any],
        maxiter: int = 35,
        eps: float = 1e-3,
        options: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Runs L-BFGS-B optimization from a single starting point."""
        start_params = np.array(start_def["params"], dtype=float)
        name = start_def["name"]

        t0 = time.time()
        self.last_eval_error = None
        self.eval_error_count = 0
        self.eval_count = 0
        init_sse = self.evaluate_sse(start_params)
        n_contracts = len(self.contracts)
        init_rmse = np.sqrt(init_sse / n_contracts)

        opt_opts = {"maxiter": maxiter, "eps": eps}
        if options is not None:
            opt_opts.update(options)

        opt_res = minimize(
            self.evaluate_sse,
            start_params,
            method="L-BFGS-B",
            bounds=self.bounds,
            options=opt_opts,
            callback=callback
        )
        elapsed = time.time() - t0

        final_params = HestonParams.from_array(opt_res.x)
        final_sse = float(opt_res.fun)
        final_rmse = np.sqrt(final_sse / n_contracts)

        # Distinguish convergence status
        status_code = int(opt_res.status)
        if status_code == 0:
            termination_type = "CONVERGED"
            is_success = True
        elif status_code == 1:
            termination_type = "MAX_ITERATIONS"
            is_success = False  # iteration limit reached, not guaranteed gradient minimum
        elif status_code == 2:
            termination_type = "ABNORMAL_TERMINATION"
            is_success = False
        else:
            termination_type = f"STATUS_{status_code}"
            is_success = False

        # Check boundary proximity (< 1e-3 from bounds)
        boundary_hits = []
        param_names = ["v0", "kappa", "theta", "xi", "rho"]
        for p_name, val, (b_low, b_high) in zip(param_names, opt_res.x, self.bounds):
            if abs(val - b_low) < 1e-3:
                boundary_hits.append(f"{p_name}_lower")
            elif abs(val - b_high) < 1e-3:
                boundary_hits.append(f"{p_name}_upper")

        return {
            "start_index": start_def["index"],
            "name": name,
            "description": start_def["description"],
            "init_params": [round(x, 4) for x in start_params],
            "init_params_raw": [float(x) for x in start_params],
            "init_sse": init_sse,
            "init_rmse": init_rmse,
            "final_params": final_params.to_dict(),
            "final_params_raw": [float(x) for x in opt_res.x],
            "final_sse": final_sse,
            "final_rmse": final_rmse,
            "iterations": int(opt_res.nit),
            "function_evals": int(opt_res.nfev),
            "time_seconds": round(elapsed, 2),
            "status": status_code,
            "termination_type": termination_type,
            "success": is_success,
            "message": str(opt_res.message),
            "last_eval_error": self.last_eval_error,
            "engine_failures": self.eval_error_count,
            "feller_ratio": final_params.feller_ratio,
            "feller_satisfied": final_params.feller_satisfied,
            "boundary_hits": boundary_hits,
            "boundary_pegged": len(boundary_hits) > 0,
        }

    def run_all_multistarts(
        self,
        starts: Optional[List[Dict[str, Any]]] = None,
        maxiter: int = 35
    ) -> Tuple[HestonParams, pd.DataFrame, Dict[str, Any]]:
        """
        Runs all pre-declared starts sequentially and selects best model.
        Returns (best_params, results_df, diagnostic_summary).
        """
        starts = starts or HESTON_5_STARTS
        results = []

        for start_def in starts:
            res = self.run_single_start(start_def, maxiter=maxiter)
            results.append(res)

        # Convert to DataFrame
        rows = []
        for r in results:
            fp = r["final_params"]
            rows.append({
                "start_index": r["start_index"],
                "name": r["name"],
                "init_sse": r["init_sse"],
                "init_rmse": r["init_rmse"],
                "final_sse": r["final_sse"],
                "final_rmse": r["final_rmse"],
                "v0": fp["v0"],
                "kappa": fp["kappa"],
                "theta": fp["theta"],
                "xi": fp["xi"],
                "rho": fp["rho"],
                "feller_ratio": fp["feller_ratio"],
                "feller_satisfied": fp["feller_satisfied"],
                "boundary_pegged": r["boundary_pegged"],
                "boundary_hits": ";".join(r["boundary_hits"]),
                "iterations": r["iterations"],
                "function_evals": r["function_evals"],
                "time_seconds": r["time_seconds"],
                "status": r["status"],
                "termination_type": r["termination_type"],
                "success": r["success"],
                "message": r["message"],
            })
        df_results = pd.DataFrame(rows)

        # Select best start by lowest final_sse
        best_row = df_results.sort_values("final_sse").iloc[0]
        best_params = HestonParams(
            v0=float(best_row["v0"]),
            kappa=float(best_row["kappa"]),
            theta=float(best_row["theta"]),
            xi=float(best_row["xi"]),
            rho=float(best_row["rho"])
        )

        # Parameter dispersion among converged runs (status 0, excluding poor local minima)
        converged = df_results[(df_results["status"] == 0) & (df_results["final_rmse"] < 0.050)]
        dispersion = {
            "v0_mean": float(converged["v0"].mean()),
            "v0_std": float(converged["v0"].std()),
            "theta_mean": float(converged["theta"].mean()),
            "theta_std": float(converged["theta"].std()),
            "kappa_mean": float(converged["kappa"].mean()),
            "kappa_std": float(converged["kappa"].std()),
            "xi_mean": float(converged["xi"].mean()),
            "xi_std": float(converged["xi"].std()),
            "rho_mean": float(converged["rho"].mean()),
            "rho_std": float(converged["rho"].std()),
            "best_start_name": str(best_row["name"]),
            "best_start_index": int(best_row["start_index"]),
            "best_train_sse": float(best_row["final_sse"]),
            "best_train_rmse": float(best_row["final_rmse"]),
        }

        return best_params, df_results, dispersion
