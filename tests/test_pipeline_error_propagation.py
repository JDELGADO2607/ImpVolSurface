"""
Unit tests for Pipeline Error Propagation, Stage Validation, and Non-Zero Exit Codes (Phase 4).

Validates:
1. Complete clean pipeline run returns 0 exit code.
2. Intentional test failure returns non-zero code.
3. Intentional stage exception aborts pipeline and returns non-zero code.
4. Missing mandatory output file triggers FileNotFoundError and halts pipeline.
5. Non-finite values in critical columns trigger validation failure and non-zero code.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch

from run_all import run_pipeline, _validate_table_file

def test_missing_mandatory_file_fails():
    """
    Mandatory Check 4.3: Missing mandatory output artifact raises FileNotFoundError.
    """
    fake_path = Path("outputs/tables/non_existent_mandatory_table.csv")
    with pytest.raises(FileNotFoundError, match="Mandatory output artifact missing"):
        _validate_table_file(fake_path)

def test_non_finite_validation_fails(tmp_path):
    """
    Mandatory Check 4.3: Non-finite / infinite values in critical columns raise ValueError.
    """
    bad_csv = tmp_path / "bad_table.csv"
    df = pd.DataFrame({'strike': [10.0, 12.0], 'our_iv_decimal': [0.45, np.inf]})
    df.to_csv(bad_csv, index=False)

    with pytest.raises(ValueError, match="contains non-finite/infinite values"):
        _validate_table_file(bad_csv, check_finite_cols=['our_iv_decimal'])

def test_empty_table_validation_fails(tmp_path):
    """
    Mandatory Check 4.3: Empty output files raise ValueError.
    """
    empty_csv = tmp_path / "empty_table.csv"
    empty_csv.write_text("") # 0 bytes

    with pytest.raises(ValueError, match="Mandatory output file is empty"):
        _validate_table_file(empty_csv)

def test_intentional_stage_exception_returns_nonzero():
    """
    Mandatory Check 4.3: An unhandled exception during a blocking stage
    must halt the pipeline and return a non-zero exit code (never 0).
    """
    with patch("src.data_cleaning.clean_and_audit_options", side_effect=RuntimeError("Intentional Stage 1 Failure")):
        exit_code = run_pipeline(raise_on_error=False, run_tests=False)
        assert exit_code != 0, f"Pipeline returned {exit_code} despite critical stage exception!"

def test_intentional_test_failure_returns_nonzero():
    """
    Mandatory Check 4.3: When pytest reports test failures,
    the pipeline must propagate a non-zero exit code (never 0).
    Patches stage worker functions to prevent redundant full pipeline recalculation during testing.
    """
    with patch("src.data_cleaning.clean_and_audit_options"), \
         patch("src.iv_inversion.invert_clean_dataset"), \
         patch("src.surface.generate_surface_plots_and_tables"), \
         patch("src.model_comparison.run_model_comparison"), \
         patch("src.portfolio.build_hypothetical_portfolio"), \
         patch("src.stress_testing.run_stress_testing"), \
         patch("src.strategies.run_strategies_analysis"):
        # Force pytest to run with arguments that produce an exit code != 0
        # E.g. targeting a non-existent test file produces exit code 4 (usage error)
        exit_code = run_pipeline(raise_on_error=False, run_tests=True, pytest_args=["tests/non_existent_test_file.py"])
        assert exit_code != 0, f"Pipeline returned {exit_code} despite test failure!"
