"""Column-level profiling: types, completeness, cardinality, distribution."""
from __future__ import annotations

import pandas as pd


def profile_dataframe(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        num = pd.api.types.is_numeric_dtype(s)
        rows.append({
            "dataset": dataset, "column": col, "dtype": str(s.dtype), "rows": n,
            "null_count": int(s.isna().sum()),
            "null_pct": float(s.isna().mean()) if n else 0.0,
            "distinct": int(s.nunique(dropna=True)),
            "distinct_pct": float(s.nunique(dropna=True) / n) if n else 0.0,
            "min": s.min() if num else (s.dropna().min() if s.notna().any() else None),
            "max": s.max() if num else (s.dropna().max() if s.notna().any() else None),
            "mean": float(s.mean()) if num else None,
            "std": float(s.std()) if num else None,
            "top_value": s.mode(dropna=True).iloc[0] if s.notna().any() else None,
        })
    return pd.DataFrame(rows)


def profile_findings(profile: pd.DataFrame, max_null_pct: float = 0.05) -> list[dict]:
    """Turn profile stats into reportable findings."""
    out = []
    for r in profile.itertuples():
        if r.null_pct > max_null_pct:
            out.append({"dataset": r.dataset, "check": "profile_null_pct", "column": r.column,
                        "severity": "warn", "failed_rows": r.null_count,
                        "detail": f"{r.null_pct:.1%} nulls exceeds {max_null_pct:.0%}"})
        if r.rows > 1 and r.distinct <= 1 and r.null_count < r.rows:
            out.append({"dataset": r.dataset, "check": "profile_constant_column", "column": r.column,
                        "severity": "warn", "failed_rows": 0, "detail": "column has a single distinct value"})
    return out
