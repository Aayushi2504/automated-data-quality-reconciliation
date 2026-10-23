from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def build_summary(findings: pd.DataFrame) -> dict:
    failed = findings[findings.failed_rows > 0]
    return {
        "checks_run": len(findings),
        "checks_failed": len(failed),
        "errors": int((failed.severity == "error").sum()),
        "warnings": int((failed.severity == "warn").sum()),
        "records_flagged": int(failed.failed_rows.sum()),
        "status": "FAIL" if (failed.severity == "error").any() else ("PASS_WITH_WARNINGS" if len(failed) else "PASS"),
    }


def write_markdown(path: Path, run_ts: str, summary: dict, findings: pd.DataFrame) -> None:
    lines = [f"# Data Quality Report", f"", f"- Run: `{run_ts}`", f"- Status: **{summary['status']}**",
             f"- Checks run: {summary['checks_run']} | failed: {summary['checks_failed']} "
             f"(errors {summary['errors']}, warnings {summary['warnings']})",
             f"- Records flagged: {summary['records_flagged']:,}", ""]
    failed = findings[findings.failed_rows > 0].sort_values(["severity", "dataset", "check"])
    if failed.empty:
        lines.append("All checks passed.")
    else:
        lines += ["## Failed checks", "", "| Dataset | Check | Column | Severity | Rows | Detail |", "|---|---|---|---|---|---|"]
        for r in failed.itertuples():
            col = r.column if pd.notna(r.column) else ""
            det = r.detail if pd.notna(r.detail) else ""
            lines.append(f"| {r.dataset} | {r.check} | {col} | {r.severity} | {r.failed_rows:,} | {det} |")
    passed = findings[findings.failed_rows == 0]
    lines += ["", f"## Passed checks ({len(passed)})", ""]
    lines += [f"- {r.dataset}: {r.check}" + (f" ({r.column})" if pd.notna(r.column) else "") for r in passed.itertuples()]
    path.write_text("\n".join(lines))


def persist(engine, run_id: str, findings: pd.DataFrame, exceptions: pd.DataFrame, summary: dict) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    f = findings.assign(run_id=run_id, run_ts=ts)
    f.to_sql("dq_results", engine, if_exists="append", index=False)
    if not exceptions.empty:
        exceptions.assign(run_id=run_id, run_ts=ts).to_sql("dq_exceptions", engine, if_exists="append", index=False)
    pd.DataFrame([{**summary, "run_id": run_id, "run_ts": ts}]).to_sql("dq_run_summary", engine, if_exists="append", index=False)
