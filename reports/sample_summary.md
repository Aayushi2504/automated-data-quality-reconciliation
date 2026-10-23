# Data Quality Report

- Run: `b663467f9072`
- Status: **FAIL**
- Checks run: 31 | failed: 19 (errors 17, warnings 2)
- Records flagged: 724

## Failed checks

| Dataset | Check | Column | Severity | Rows | Detail |
|---|---|---|---|---|---|
| customers | duplicates | email | error | 2 | 2 rows share a duplicate email |
| customers | rule:valid_email_shape |  | error | 1 | email.notna() and not email.str.contains('@') |
| customers_source_to_warehouse | recon_missing_in_target |  | error | 3 | in source, absent from target |
| customers_source_to_warehouse | recon_row_count |  | error | 3 | source=500 target=497 diff=+3 |
| orders | allowed_values | status | error | 7 |  |
| orders | duplicates | order_id | error | 24 | 24 rows share a duplicate order_id |
| orders | missing_values | customer_id | error | 18 |  |
| orders | referential_integrity | customer_id | error | 5 | customer_id not found in parent customer_id |
| orders | rule:delivered_requires_ship_date |  | error | 11 | status == 'delivered' and shipped_date.isna() |
| orders | rule:non_negative_total |  | error | 9 | order_total < 0 |
| orders | rule:ship_before_order |  | error | 6 | shipped_date < order_date |
| orders_source_to_warehouse | recon_control_total | order_total | error | 1 | source=336,140.40 target=334,317.67 diff=+1,822.73 |
| orders_source_to_warehouse | recon_extra_in_target |  | error | 1 | in target, absent from source |
| orders_source_to_warehouse | recon_missing_in_target |  | error | 15 | in source, absent from target |
| orders_source_to_warehouse | recon_row_count |  | error | 26 | source=3,012 target=2,986 diff=+26 |
| orders_source_to_warehouse | recon_value_mismatch | order_total | error | 8 | 8 records differ |
| orders_source_to_warehouse | recon_value_mismatch | status | error | 4 | 4 records differ |
| orders | profile_null_pct | shipped_date | warn | 577 | 19.2% nulls exceeds 5% |
| orders | rule:suspiciously_large_order |  | warn | 3 | order_total > 10000 |

## Passed checks (12)

- orders: missing_values (order_id)
- orders: missing_values (order_date)
- orders: missing_values (order_total)
- orders: missing_values (status)
- customers: missing_values (customer_id)
- customers: missing_values (email)
- customers: missing_values (country)
- customers: duplicates (customer_id)
- orders_source_to_warehouse: recon_value_mismatch (customer_id)
- customers_source_to_warehouse: recon_extra_in_target
- customers_source_to_warehouse: recon_value_mismatch (email)
- customers_source_to_warehouse: recon_value_mismatch (country)