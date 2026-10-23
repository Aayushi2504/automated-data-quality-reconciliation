"""Row-level checks. Each returns (findings, exceptions):
findings   = one summary row per rule
exceptions = one row per offending record (for the exception report)."""
from __future__ import annotations

import pandas as pd


def _key(df: pd.DataFrame, pk: list[str]) -> pd.Series:
    return df[pk].astype(str).agg("|".join, axis=1) if pk else pd.Series(df.index.astype(str), index=df.index)


def _finding(dataset, check, column, severity, failed, detail=""):
    return {"dataset": dataset, "check": check, "column": column, "severity": severity,
            "failed_rows": int(failed), "detail": detail}


def _exceptions(dataset, check, column, severity, df, mask, pk):
    bad = df[mask]
    if bad.empty:
        return []
    keys = _key(bad, pk)
    vals = bad[column] if column in bad.columns else pd.Series([None] * len(bad), index=bad.index)
    return [{"dataset": dataset, "check": check, "column": column, "severity": severity,
             "record_key": k, "value": v} for k, v in zip(keys, vals)]


def missing_values(df, dataset, pk, required_columns, severity="error"):
    f, e = [], []
    for c in required_columns:
        if c not in df.columns:
            f.append(_finding(dataset, "missing_column", c, severity, len(df), "required column absent"))
            continue
        mask = df[c].isna() | (df[c].astype(str).str.strip() == "")
        f.append(_finding(dataset, "missing_values", c, severity, mask.sum()))
        e += _exceptions(dataset, "missing_values", c, severity, df, mask, pk)
    return f, e


def duplicates(df, dataset, pk, unique_sets, severity="error"):
    f, e = [], []
    for cols in unique_sets:
        mask = df.duplicated(subset=cols, keep=False) & df[cols].notna().all(axis=1)
        label = "+".join(cols)
        f.append(_finding(dataset, "duplicates", label, severity, mask.sum(),
                          f"{int(mask.sum())} rows share a duplicate {label}"))
        e += _exceptions(dataset, "duplicates", cols[0], severity, df, mask, pk)
    return f, e


def allowed_values(df, dataset, pk, spec, severity="error"):
    f, e = [], []
    for col, allowed in (spec or {}).items():
        mask = df[col].notna() & ~df[col].isin(allowed)
        f.append(_finding(dataset, "allowed_values", col, severity, mask.sum()))
        e += _exceptions(dataset, "allowed_values", col, severity, df, mask, pk)
    return f, e


def business_rules(df, dataset, pk, rules):
    """`expression` is a pandas query that selects VIOLATING rows. Rules come from
    the team's own config file, so treat rules.yaml as trusted code."""
    f, e = [], []
    for r in rules or []:
        try:
            mask = df.eval(r["expression"], engine="python").fillna(False).astype(bool)
        except Exception as ex:  # a broken rule must be visible, never silently pass
            f.append(_finding(dataset, f"rule_error:{r['name']}", None, "error", 0, f"could not evaluate: {ex}"))
            continue
        f.append(_finding(dataset, f"rule:{r['name']}", None, r.get("severity", "error"), mask.sum(), r["expression"]))
        col = next((c for c in df.columns if c in r["expression"]), None)
        e += _exceptions(dataset, f"rule:{r['name']}", col, r.get("severity", "error"), df, mask, pk)
    return f, e


def referential_integrity(df, dataset, pk, col, ref_df, ref_col, severity="error"):
    mask = df[col].notna() & ~df[col].isin(ref_df[ref_col])
    f = [_finding(dataset, "referential_integrity", col, severity, mask.sum(), f"{col} not found in parent {ref_col}")]
    return f, _exceptions(dataset, "referential_integrity", col, severity, df, mask, pk)
