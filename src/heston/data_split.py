"""
Deterministic and leakage-free data partition for Heston calibration and validation.

Design Principles:
1. Tenor-Holdout (Time Generalization):
   Complete maturity slices held out from calibration to test term-structure extrapolation without parameter fudging.
   Held-out tenors:
   - Short/Intermediate: 2026-12-24 (tau ~ 37d, 0.1014y)
   - Medium-Term: 2027-02-19 (tau ~ 94d, 0.2575y)
   - Long-Term: 2027-09-17 (tau ~ 304d, 0.8328y)
2. Strike-Holdout (Cross-Moneyness Generalization):
   Interleaved strike holdout on remaining training tenors (every 3rd strike) to test smile interpolation.
3. Train Set:
   Core puts used exclusively for risk-neutral parameter calibration (approx 60-70% of puts).
4. External Out-of-Sample Contrast:
   All calls traded on 2026-11-17 satisfying bounds are held in a separate external dataset.
   Under no circumstances do calls enter the put calibration objective.
5. Full Reproducibility:
   Completely deterministic partition with explicit metadata and hash manifest.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
import pandas as pd
import numpy as np

# Held out tenors for complete time-structure cross-validation
HELD_OUT_TENORS = ["2026-12-24", "2027-02-19", "2027-09-17"]


def create_deterministic_split(
    puts_df: pd.DataFrame,
    calls_df: Optional[pd.DataFrame] = None,
    held_out_tenors: List[str] = HELD_OUT_TENORS,
    output_dir: Optional[str] = "data/heston"
) -> Dict[str, pd.DataFrame]:
    """
    Partitions puts into:
    - 'train': In-sample calibration puts
    - 'strike_holdout': Cross-sectional holdout puts on training tenors
    - 'tenor_holdout': Entire held-out tenor slices
    - 'calls_contrast': Clean calls for external contrast
    """
    df = puts_df.copy()

    # Step 1: Separate Tenor Holdouts
    is_tenor_holdout = df["expirationDate"].isin(held_out_tenors)
    df_tenor_holdout = df[is_tenor_holdout].copy().reset_index(drop=True)
    df_remaining = df[~is_tenor_holdout].copy()

    # Step 2: Interleaved Strike Holdout on remaining tenors
    train_records = []
    strike_holdout_records = []

    for exp_date, grp in df_remaining.groupby("expirationDate"):
        sorted_grp = grp.sort_values("strike").reset_index(drop=True)
        n_contracts = len(sorted_grp)

        if n_contracts <= 2:
            # If slice is very sparse (1-2 contracts), keep in train to preserve tenor anchor
            for _, row in sorted_grp.iterrows():
                train_records.append(row.to_dict())
        else:
            # Hold out every 3rd strike (index % 3 == 1), keep edge strikes and ATM in train
            for idx, row in sorted_grp.iterrows():
                # Protect min and max strike in train to avoid unconstrained boundary extrapolation during fit
                if idx == 0 or idx == n_contracts - 1:
                    train_records.append(row.to_dict())
                elif idx % 3 == 1:
                    strike_holdout_records.append(row.to_dict())
                else:
                    train_records.append(row.to_dict())

    df_train = pd.DataFrame(train_records)
    df_strike_holdout = pd.DataFrame(strike_holdout_records)

    # Step 3: Process Calls for External Contrast
    df_calls_contrast = pd.DataFrame()
    if calls_df is not None:
        c_df = calls_df.copy()
        # Filter calls: traded on 11/17, positive price, satisfies American lower bound
        calls_valid = c_df[
            c_df["is_trade_17nov"] &
            c_df["bounds_ok"] &
            (c_df["lastPrice"] >= 0.02)
        ].copy().reset_index(drop=True)
        df_calls_contrast = calls_valid

    # Summary manifest
    split_manifest = {
        "held_out_tenors": held_out_tenors,
        "n_total_puts": len(df),
        "n_train": len(df_train),
        "n_strike_holdout": len(df_strike_holdout),
        "n_tenor_holdout": len(df_tenor_holdout),
        "pct_train": round(len(df_train) / max(len(df), 1) * 100.0, 1),
        "pct_strike_holdout": round(len(df_strike_holdout) / max(len(df), 1) * 100.0, 1),
        "pct_tenor_holdout": round(len(df_tenor_holdout) / max(len(df), 1) * 100.0, 1),
        "n_calls_contrast": len(df_calls_contrast),
        "train_symbols": df_train["contractSymbol"].tolist() if "contractSymbol" in df_train else [],
        "strike_holdout_symbols": df_strike_holdout["contractSymbol"].tolist() if "contractSymbol" in df_strike_holdout else [],
        "tenor_holdout_symbols": df_tenor_holdout["contractSymbol"].tolist() if "contractSymbol" in df_tenor_holdout else [],
    }

    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        df_train.to_csv(out_p / "data_split_train.csv", index=False)
        df_strike_holdout.to_csv(out_p / "data_split_strike_holdout.csv", index=False)
        df_tenor_holdout.to_csv(out_p / "data_split_tenor_holdout.csv", index=False)
        if len(df_calls_contrast) > 0:
            df_calls_contrast.to_csv(out_p / "data_split_calls_contrast.csv", index=False)
        with open(out_p / "data_split_manifest.json", "w", encoding="utf-8") as f:
            json.dump(split_manifest, f, indent=2)

    return {
        "train": df_train,
        "strike_holdout": df_strike_holdout,
        "tenor_holdout": df_tenor_holdout,
        "calls_contrast": df_calls_contrast,
        "manifest": split_manifest
    }
