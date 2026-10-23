"""Run the DQ + reconciliation framework as a gate in the daily pipeline.

  profile_and_check  -> run the framework (writes reports + audit tables)
  evaluate_gate      -> fails the DAG (and blocks downstream tasks) on error-severity failures
  notify             -> always runs; summarizes the outcome (replace with Slack/email)
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.utils.trigger_rule import TriggerRule

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dq_framework.runner import run  # noqa: E402


@dag(
    dag_id="data_quality_reconciliation",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    default_args={"owner": "analytics", "retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["data-quality", "reconciliation"],
)
def data_quality_reconciliation():
    @task
    def profile_and_check() -> dict:
        res = run(str(ROOT / "config" / "rules.yaml"), str(ROOT / "config" / "connections.yaml"),
                  out_dir=str(ROOT / "reports"))
        return {"run_id": res["run_id"], **res["summary"]}

    @task
    def evaluate_gate(summary: dict) -> dict:
        if summary["errors"] > 0:
            raise AirflowFailException(
                f"Run {summary['run_id']}: {summary['errors']} error-severity checks failed. "
                f"See reports/dq_report.md and the dq_exceptions table.")
        return summary

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def notify(summary: dict | None = None):
        # Replace with Slack/email. Pull from the audit table so the message is accurate even on failure.
        print("DQ run finished:", summary)

    s = profile_and_check()
    gate = evaluate_gate(s)
    notify(s)
    # downstream load/transform tasks should depend on `gate`
    return gate


data_quality_reconciliation()
