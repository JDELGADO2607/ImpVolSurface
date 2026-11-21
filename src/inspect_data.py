"""
Diagnostic inspection script for Opciones_Completo.xlsx.
Analyzes sheets, columns, types, ranges, anomalies, and cross-sheet consistency.
Outputs diagnostic summaries to outputs/data_diagnostics/.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

def run_diagnostics():
    raw_path = Path("data/raw/Opciones_Completo.xlsx")
    diag_dir = Path("outputs/data_diagnostics")
    diag_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading Excel file from: {raw_path}")
    xls = pd.ExcelFile(raw_path)
    sheet_names = xls.sheet_names
    print(f"Sheet names: {sheet_names}")

    diagnostics_log = []
    diagnostics_log.append(f"EXCEL INSPECTION REPORT: {raw_path.name}")
    diagnostics_log.append(f"Sheets found ({len(sheet_names)}): {sheet_names}\n")

    dfs = {}
    for sheet in sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet)
        dfs[sheet] = df
        diagnostics_log.append("=" * 80)
        diagnostics_log.append(f"SHEET: {sheet}")
        diagnostics_log.append(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
        diagnostics_log.append("Columns and Data Types:")
        for col in df.columns:
            non_nulls = df[col].notna().sum()
            nulls = df[col].isna().sum()
            sample_val = df[col].dropna().iloc[0] if non_nulls > 0 else "ALL_NULL"
            diagnostics_log.append(f"  - {col}: dtype={df[col].dtype}, non-null={non_nulls}, null={nulls}, sample={repr(sample_val)}")
        
        diagnostics_log.append("\nSummary Statistics (Numeric):")
        numeric_desc = df.describe(include=[np.number]).T
        diagnostics_log.append(numeric_desc.to_string())
        diagnostics_log.append("\n")

        # Save individual sheet structure dump
        csv_dump = diag_dir / f"dump_{sheet.replace(' ', '_')}.csv"
        df.to_csv(csv_dump, index=False)
        print(f"Dumped {sheet} to {csv_dump}")

    # Cross-sheet comparison if there are 2 sheets
    if len(sheet_names) >= 2:
        s1_name, s2_name = sheet_names[0], sheet_names[1]
        df1, df2 = dfs[s1_name], dfs[s2_name]
        diagnostics_log.append("=" * 80)
        diagnostics_log.append(f"CROSS-SHEET COMPARISON: {s1_name} vs {s2_name}")
        diagnostics_log.append(f"Row count: {len(df1)} vs {len(df2)}")
        
        # Check matching columns
        common_cols = list(set(df1.columns).intersection(set(df2.columns)))
        only_s1 = list(set(df1.columns) - set(df2.columns))
        only_s2 = list(set(df2.columns) - set(df1.columns))
        diagnostics_log.append(f"Common columns: {common_cols}")
        diagnostics_log.append(f"Columns only in {s1_name}: {only_s1}")
        diagnostics_log.append(f"Columns only in {s2_name}: {only_s2}")

        # Check identifiers (e.g. contractSymbol or bloombergOptionTicker)
        for id_col in ['contractSymbol', 'bloombergOptionTicker']:
            if id_col in df1.columns and id_col in df2.columns:
                match = (df1[id_col].astype(str) == df2[id_col].astype(str)).all()
                diagnostics_log.append(f"Exact match on {id_col} row-by-row: {match}")
                # check set difference
                set1 = set(df1[id_col].dropna().astype(str))
                set2 = set(df2[id_col].dropna().astype(str))
                diff = set1.symmetric_difference(set2)
                diagnostics_log.append(f"Unique values in {id_col}: {len(set1)} vs {len(set2)}, set symmetric diff count: {len(diff)}")

    # Specific inspections for known fields
    primary_df = dfs[sheet_names[0]]
    diagnostics_log.append("=" * 80)
    diagnostics_log.append("SPECIFIC FIELD ANOMALY CHECKS:")
    
    # 1. Option types and counts
    if 'type' in primary_df.columns:
        counts = primary_df['type'].value_counts(dropna=False).to_dict()
        diagnostics_log.append(f"Contract types count: {counts}")
    
    # 2. Expirations
    if 'expirationDate' in primary_df.columns:
        exp_counts = primary_df['expirationDate'].value_counts().sort_index()
        diagnostics_log.append(f"Distinct expirations ({len(exp_counts)}):\n{exp_counts.to_string()}")

    # 3. Last trade dates
    if 'lastTradeDate' in primary_df.columns:
        ltd = pd.to_datetime(primary_df['lastTradeDate'], errors='coerce')
        diagnostics_log.append(f"lastTradeDate min: {ltd.min()}, max: {ltd.max()}")
        ltd_date = ltd.dt.date
        date_counts = ltd_date.value_counts().sort_index()
        diagnostics_log.append(f"Trade date distribution:\n{date_counts.to_string()}")

    # 4. Bid/Ask/Mid = 0 checks
    for col in ['bid', 'ask', 'midPrice', 'lastPrice']:
        if col in primary_df.columns:
            zeros = (primary_df[col] == 0).sum()
            pos = (primary_df[col] > 0).sum()
            nulls = primary_df[col].isna().sum()
            diagnostics_log.append(f"{col}: zeros={zeros}, positive={pos}, nulls={nulls}")

    # 5. yearsToExpiry anomaly check
    if 'yearsToExpiry' in primary_df.columns:
        yte = primary_df['yearsToExpiry']
        diagnostics_log.append(f"yearsToExpiry min={yte.min()}, max={yte.max()}, median={yte.median()}")
        anom_yte = primary_df[yte > 10.0]
        diagnostics_log.append(f"yearsToExpiry > 10.0 count: {len(anom_yte)}")

    # 6. impliedVolatility Yahoo check
    if 'impliedVolatility' in primary_df.columns:
        iv = primary_df['impliedVolatility']
        diagnostics_log.append(f"impliedVolatility min={iv.min()}, max={iv.max()}, median={iv.median()}")
        anom_iv = primary_df[iv > 5.0]
        diagnostics_log.append(f"impliedVolatility > 5.0 (500%) count: {len(anom_iv)}")

    # Write log to file
    out_txt = diag_dir / "diagnostics_summary.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(diagnostics_log))
    print(f"Diagnostics written to {out_txt}")
    print("\n--- Summary Preview ---")
    print("\n".join(diagnostics_log[:40]))

if __name__ == "__main__":
    run_diagnostics()
