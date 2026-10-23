# Extending the Framework

**Add a dataset:** add an entry under `datasets:` in `config/rules.yaml` with `connection`, `table`, `primary_key`, and any of `required_columns`, `unique`, `allowed_values`, `business_rules`, `referential`.

**Add a business rule:** write a pandas expression that selects the *violating* rows.
```yaml
- name: refund_exceeds_total
  expression: "refund_amount > order_total"
  severity: error
```
A rule that cannot be evaluated (typo, missing column) is reported as an `error`-severity `rule_error`, so a broken rule can never silently pass.

**Add a reconciliation:** add an entry under `reconciliation:` with `source`, `target`, `key`, and optionally `row_count`, `column_sums`, `compare_columns`, `tolerance`.

**Point at a real warehouse:** change the URLs in `config/connections.yaml`
(e.g. `snowflake://...`, `postgresql://...`) and install the matching SQLAlchemy dialect.

**Severity:** `error` fails the run (exit code 1 / Airflow task failure); `warn` is reported only.

**Security note:** `expression` values are evaluated by pandas. Treat `rules.yaml` like code: review changes in pull requests and do not accept rules from untrusted input.

**Scale:** the framework loads tables into pandas. For very large tables, use the warehouse-native queries in `sql/02_warehouse_native_checks.sql` or add a `WHERE` partition filter in `read_table`.
