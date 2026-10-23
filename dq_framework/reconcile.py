"""Source-to-target reconciliation: counts, control totals, and key-level diffs."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _f(name, check, column, severity, failed, detail):
    return {"dataset": name, "check": check, "column": column, "severity": severity,
            "failed_rows": int(failed), "detail": detail}


def reconcile(name: str, src: pd.DataFrame, tgt: pd.DataFrame, spec: dict) -> tuple[list, list]:
    sev = spec.get("severity", "error")
    key = spec["key"]
    tol = spec.get("tolerance", 0.0)
    findings, exceptions = [], []

    if spec.get("row_count", True):
        diff = len(src) - len(tgt)
        findings.append(_f(name, "recon_row_count", None, sev, abs(diff),
                           f"source={len(src):,} target={len(tgt):,} diff={diff:+,}"))

    for col in spec.get("column_sums", []):
        s, t = float(src[col].sum()), float(tgt[col].sum())
        findings.append(_f(name, "recon_control_total", col, sev, 0 if abs(s - t) <= tol else 1,
                           f"source={s:,.2f} target={t:,.2f} diff={s - t:+,.2f}"))

    s_idx = src.assign(_k=src[key].astype(str).agg("|".join, axis=1)).drop_duplicates("_k").set_index("_k")
    t_idx = tgt.assign(_k=tgt[key].astype(str).agg("|".join, axis=1)).drop_duplicates("_k").set_index("_k")

    missing = s_idx.index.difference(t_idx.index)
    extra = t_idx.index.difference(s_idx.index)
    findings.append(_f(name, "recon_missing_in_target", None, sev, len(missing), "in source, absent from target"))
    findings.append(_f(name, "recon_extra_in_target", None, sev, len(extra), "in target, absent from source"))
    exceptions += [{"dataset": name, "check": "recon_missing_in_target", "column": None, "severity": sev,
                    "record_key": k, "value": None} for k in missing]
    exceptions += [{"dataset": name, "check": "recon_extra_in_target", "column": None, "severity": sev,
                    "record_key": k, "value": None} for k in extra]

    common = s_idx.index.intersection(t_idx.index)
    for col in spec.get("compare_columns", []):
        a, b = s_idx.loc[common, col], t_idx.loc[common, col]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            neq = ~np.isclose(a.astype(float), b.astype(float), atol=tol, equal_nan=True)
        else:
            same = (a.astype(object) == b.astype(object)) | (a.isna() & b.isna())   # null == null
            neq = (~same).values
        bad = common[neq]
        findings.append(_f(name, "recon_value_mismatch", col, sev, len(bad), f"{len(bad)} records differ"))
        exceptions += [{"dataset": name, "check": "recon_value_mismatch", "column": col, "severity": sev,
                        "record_key": k, "value": f"src={a[k]} | tgt={b[k]}"} for k in bad]
    return findings, exceptions
