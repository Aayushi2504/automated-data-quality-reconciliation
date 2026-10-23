"""Orchestrates profiling, checks, and reconciliation. CLI entry point.

    python -m dq_framework.runner --rules config/rules.yaml --connections config/connections.yaml
Exit code 1 when any error-severity check fails (use it as a pipeline gate).
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import pandas as pd

from . import checks, reconcile, reporting
from .config import ROOT, build_engines, load_yaml
from .profiler import profile_dataframe, profile_findings


def read_table(engine, table: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table}", engine)


def run(rules_path: str, conn_path: str, out_dir: str = "reports", persist_results: bool = True) -> dict:
    rules, conn_cfg = load_yaml(rules_path), load_yaml(conn_path)
    engines = build_engines(conn_cfg)
    run_id = uuid.uuid4().hex[:12]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    findings, exceptions, profiles = [], [], []
    cache: dict[tuple, pd.DataFrame] = {}

    def table(conn, name):
        if (conn, name) not in cache:
            cache[(conn, name)] = read_table(engines[conn], name)
        return cache[(conn, name)]

    # 1. profile + row-level checks
    for ds, spec in rules.get("datasets", {}).items():
        df = table(spec["connection"], spec["table"])
        pk = spec.get("primary_key", [])
        prof = profile_dataframe(df, ds)
        profiles.append(prof)
        findings += profile_findings(prof, spec.get("profile_thresholds", {}).get("max_null_pct", 0.05))
        for fn, args in [
            (checks.missing_values, (spec.get("required_columns", []),)),
            (checks.duplicates, (spec.get("unique", []),)),
            (checks.allowed_values, (spec.get("allowed_values"),)),
            (checks.business_rules, (spec.get("business_rules"),)),
        ]:
            f, e = fn(df, ds, pk, *args)
            findings += f
            exceptions += e
        for ref in spec.get("referential", []):
            parent = table(ref["ref_connection"], ref["ref_table"])
            f, e = checks.referential_integrity(df, ds, pk, ref["column"], parent, ref["ref_column"],
                                                ref.get("severity", "error"))
            findings += f
            exceptions += e

    # 2. source-to-target reconciliation
    for spec in rules.get("reconciliation", []):
        src = table(spec["source"]["connection"], spec["source"]["table"])
        tgt = table(spec["target"]["connection"], spec["target"]["table"])
        f, e = reconcile.reconcile(spec["name"], src, tgt, spec)
        findings += f
        exceptions += e

    cols = ["dataset", "check", "column", "severity", "failed_rows", "detail"]
    fdf = pd.DataFrame(findings, columns=cols)
    edf = pd.DataFrame(exceptions, columns=["dataset", "check", "column", "severity", "record_key", "value"])
    summary = reporting.build_summary(fdf)

    # 3. reporting
    pd.concat(profiles).to_csv(out / "column_profile.csv", index=False)
    fdf.to_csv(out / "check_results.csv", index=False)
    edf.to_csv(out / "exceptions.csv", index=False)
    reporting.write_markdown(out / "dq_report.md", run_id, summary, fdf)
    if persist_results:
        reporting.persist(engines[conn_cfg.get("audit_connection", "target")], run_id, fdf, edf, summary)
    return {"run_id": run_id, "summary": summary, "findings": fdf, "exceptions": edf}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=str(ROOT / "config" / "rules.yaml"))
    ap.add_argument("--connections", default=str(ROOT / "config" / "connections.yaml"))
    ap.add_argument("--out", default="reports")
    ap.add_argument("--no-persist", action="store_true")
    a = ap.parse_args(argv)
    res = run(a.rules, a.connections, a.out, persist_results=not a.no_persist)
    s = res["summary"]
    print(f"Run {res['run_id']}: {s['status']} | {s['checks_run']} checks, {s['checks_failed']} failed "
          f"({s['errors']} errors, {s['warnings']} warnings), {len(res['exceptions']):,} exception rows")
    failed = res["findings"][res["findings"].failed_rows > 0]
    if len(failed):
        print(failed[["dataset", "check", "column", "severity", "failed_rows"]].to_string(index=False))
    print(f"Reports written to {a.out}/")
    return 1 if s["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
