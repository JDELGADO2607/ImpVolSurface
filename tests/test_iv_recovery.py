"""
Unit tests for Implied Volatility (IV) inversion and parameter recovery.
Tests exact synthetic recovery on calls and puts, and validates robust error handling.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
from src.pricing_bs import bs_price
from src.pricing_american_fd import price_american_option
from src.iv_inversion import implied_vol

def test_call_synthetic_recovery():
    S = 12.33
    r = 0.045
    q = 0.0
    true_sigmas = [0.20, 0.35, 0.50, 0.85, 1.20]
    test_cases = [
        (10.0, 30.0 / 365.0),  # ITM
        (12.33, 45.0 / 365.0), # ATM
        (15.0, 90.0 / 365.0),  # OTM
    ]

    for K, tau in test_cases:
        for true_sig in true_sigmas:
            px = bs_price('C', S, K, tau, r, true_sig, q=q)
            res = implied_vol(px, 'C', S, K, tau, r, q=q, method="auto")
            assert res['status'].startswith('CONVERGED')
            recovered_sig = res['sigma']
            assert abs(recovered_sig - true_sig) < 1e-4, \
                f"Call recovery failed: true={true_sig}, recovered={recovered_sig}, diff={abs(recovered_sig - true_sig)}"

def test_american_put_synthetic_recovery():
    S = 12.33
    r = 0.043
    q = 0.0
    true_sigmas = [0.30, 0.45, 0.60]
    test_cases = [
        (11.0, 45.0 / 365.0),  # OTM Put
        (12.33, 45.0 / 365.0), # ATM Put
        (13.5, 45.0 / 365.0),  # ITM Put
    ]

    for K, tau in test_cases:
        for true_sig in true_sigmas:
            px = price_american_option('P', S, K, tau, r, true_sig, q=q, method="auto")
            res = implied_vol(px, 'P', S, K, tau, r, q=q, method="auto")
            assert res['status'].startswith('CONVERGED')
            recovered_sig = res['sigma']
            assert abs(recovered_sig - true_sig) < 2e-3, \
                f"Put recovery failed: true={true_sig}, recovered={recovered_sig}, diff={abs(recovered_sig - true_sig)}"

def test_iv_uninvertible_bounds_handling():
    S = 12.33
    K = 12.0
    tau = 30.0 / 365.0
    r = 0.04

    # 1. Negative price
    res_neg = implied_vol(-0.5, 'C', S, K, tau, r)
    assert res_neg['status'] == 'INVALID_PRICE_NONPOSITIVE'
    assert np.isnan(res_neg['sigma'])

    # 2. Call price below European lower bound
    lb = S - K * np.exp(-r * tau)
    res_below = implied_vol(lb - 0.05, 'C', S, K, tau, r)
    assert res_below['status'] == 'PRICE_BELOW_LOWER_BOUND'
    assert np.isnan(res_below['sigma'])

    # 3. Call price above upper bound S
    res_above = implied_vol(S + 1.0, 'C', S, K, tau, r)
    assert res_above['status'] == 'PRICE_ABOVE_UPPER_BOUND'
    assert np.isnan(res_above['sigma'])
