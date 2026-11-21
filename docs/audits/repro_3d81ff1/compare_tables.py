"""Compare common data and market outputs from frozen R2 and R3 directories."""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd


def error_summary(errors):
    value = pd.to_numeric(errors, errors="coerce").dropna().to_numpy()
    return dict(n=len(value), mae=float(np.mean(abs(value))), rmse=float(np.sqrt(np.mean(value**2))),
                max_abs=float(np.max(abs(value)))) if len(value) else dict(n=0)


def tables(root):
    root = Path(root) / "outputs" / "tables"
    return {f.stem: pd.read_csv(f) for f in root.glob("*.csv")}


def main():
    versions = [tables(arg) for arg in sys.argv[1:3]]
    iv = [data["options_with_iv"].set_index("contractSymbol", verify_integrity=True) for data in versions]
    for r, data in zip(("R2", "R3"), versions):
        frame = data["options_with_iv"]
        print(r, "contracts", len(frame), "tenors", frame.tau_recalc.nunique(),
              "reconstruction", error_summary(frame.price_reconstruction_error))
        if "iv_status" in frame:
            print(r, "inversion statuses", frame.iv_status.value_counts(dropna=False).to_dict())
        for name in ("surface_leave_one_out_validation", "surface_final_holdout_validation"):
            if name in data:
                f = data[name]
                print(r, name, "rows", len(f), "schema", list(f))
                for field in ("price_error_usd", "iv_error_pp"):
                    if field in f:
                        print(field, error_summary(f[field]))
                for field in ("status", "holdout_status", "rejection_reason", "quality", "quality_status"):
                    if field in f:
                        print(field, f[field].value_counts(dropna=False).to_dict())
        for name in ("model_comparison_summary", "volatility_forecast_evaluation"):
            if name in data:
                print(r, name, data[name].to_csv(index=False))
        f = data["hypothetical_portfolio"]
        cols = [c for c in f if c.startswith("position_")]
        print(r, "portfolio", f[cols].sum().to_dict(), "stock", f[f.type.eq("STOCK")].quantity.to_list())
        f = data["stress_test_matrix"]
        cols = [c for c in ("scenario_id", "convention", "economic_margin_capital", "total_port_pnl_stress_mod",
                            "total_port_pnl_taylor", "taylor_discrepancy") if c in f]
        print(r, "stress", f[cols].to_csv(index=False))
    common = iv[0].index.intersection(iv[1].index)
    print("contract overlap", len(common), "R2-only", len(iv[0].index.difference(common)),
          "R3-only", len(iv[1].index.difference(common)))
    for field in ("lastPrice", "tau_recalc", "k_log_moneyness", "our_iv_pct", "price_reconstruction_error"):
        diff = iv[1].loc[common, field] - iv[0].loc[common, field]
        print("R3 minus R2", field, json.dumps(error_summary(diff)), "signed_mean", diff.mean())


if __name__ == "__main__":
    main()
