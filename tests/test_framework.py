import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest

from dq_framework import checks, reconcile
from dq_framework.profiler import profile_dataframe, profile_findings
from dq_framework.runner import run
from scripts import seed_demo_db

ROOT = Path(__file__).resolve().parents[1]


def test_duplicates_and_missing_flagged_with_record_keys():
    df = pd.DataFrame({"id": ["a", "a", "b", "c"], "v": [1, 2, None, 4]})
    f, e = checks.duplicates(df, "t", ["id"], [["id"]])
    assert f[0]["failed_rows"] == 2 and {x["record_key"] for x in e} == {"a"}
    f, e = checks.missing_values(df, "t", ["id"], ["v"])
    assert f[0]["failed_rows"] == 1 and e[0]["record_key"] == "b"


def test_business_rule_violations_and_broken_rule_is_visible():
    df = pd.DataFrame({"id": [1, 2, 3], "amt": [10, -5, -1]})
    f, _ = checks.business_rules(df, "t", ["id"], [{"name": "neg", "expression": "amt < 0"}])
    assert f[0]["failed_rows"] == 2
    f, _ = checks.business_rules(df, "t", ["id"], [{"name": "bad", "expression": "nonexistent > 0"}])
    assert f[0]["check"].startswith("rule_error") and f[0]["severity"] == "error"


def test_reconcile_finds_missing_extra_and_drift_and_ignores_matching_nulls():
    src = pd.DataFrame({"k": ["a", "b", "c", "d"], "amt": [1.0, 2.0, 3.0, 4.0], "c": [None, "x", "y", "z"]})
    tgt = pd.DataFrame({"k": ["a", "b", "c", "e"], "amt": [1.0, 2.5, 3.0, 9.0], "c": [None, "x", "y", "q"]})
    spec = {"key": ["k"], "column_sums": ["amt"], "compare_columns": ["amt", "c"], "tolerance": 0.01}
    f, e = reconcile.reconcile("r", src, tgt, spec)
    res = {(x["check"], x["column"]): x["failed_rows"] for x in f}
    assert res[("recon_missing_in_target", None)] == 1
    assert res[("recon_extra_in_target", None)] == 1
    assert res[("recon_value_mismatch", "amt")] == 1
    assert res[("recon_value_mismatch", "c")] == 0            # null == null must not be a mismatch
    assert res[("recon_control_total", "amt")] == 1


def test_profile_flags_high_null_and_constant_columns():
    df = pd.DataFrame({"a": [1, None, None, None], "b": ["x"] * 4})
    found = {x["check"] for x in profile_findings(profile_dataframe(df, "t"), 0.05)}
    assert found == {"profile_null_pct", "profile_constant_column"}


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setattr(seed_demo_db, "ROOT", tmp_path)
    return tmp_path


def _cfg(tmp_path):
    conn = tmp_path / "conn.yaml"
    conn.write_text(f"connections:\n  source: sqlite:///{tmp_path}/demo/source.db\n"
                    f"  target: sqlite:///{tmp_path}/demo/target.db\naudit_connection: target\n")
    return str(ROOT / "config" / "rules.yaml"), str(conn)


def test_end_to_end_clean_data_passes(demo):
    seed_demo_db.main(clean=True)
    rules, conn = _cfg(demo)
    res = run(rules, conn, out_dir=str(demo / "out"))
    assert res["summary"]["errors"] == 0, res["findings"][res["findings"].failed_rows > 0]


def test_end_to_end_defective_data_fails_and_persists_audit(demo):
    seed_demo_db.main(clean=False)
    rules, conn = _cfg(demo)
    res = run(rules, conn, out_dir=str(demo / "out"))
    assert res["summary"]["status"] == "FAIL"
    failed = res["findings"].query("failed_rows > 0").set_index(["dataset", "check", "column"]).failed_rows
    assert failed[("orders", "duplicates", "order_id")] == 24
    assert failed[("orders_source_to_warehouse", "recon_missing_in_target", None)] == 15
    assert (demo / "out" / "exceptions.csv").exists()
    import sqlalchemy as sa
    eng = sa.create_engine(f"sqlite:///{demo}/demo/target.db")
    assert pd.read_sql_query("select count(*) n from dq_run_summary", eng).n[0] == 1
