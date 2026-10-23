-- Warehouse-native equivalents of the Python checks. Useful when data is too large to
-- pull into pandas: push the same logic down to the database.

-- 1. Duplicate keys
SELECT order_id, COUNT(*) AS occurrences
FROM orders GROUP BY order_id HAVING COUNT(*) > 1;

-- 2. Missing values by column (completeness)
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS null_customer_id,
       SUM(CASE WHEN order_total IS NULL THEN 1 ELSE 0 END) AS null_order_total
FROM orders;

-- 3. Referential integrity (orphans)
SELECT o.order_id, o.customer_id
FROM orders o LEFT JOIN customers c ON c.customer_id = o.customer_id
WHERE o.customer_id IS NOT NULL AND c.customer_id IS NULL;

-- 4. Business rule violations
SELECT order_id, order_total FROM orders WHERE order_total < 0;
SELECT order_id FROM orders WHERE status = 'delivered' AND shipped_date IS NULL;
SELECT order_id FROM orders WHERE shipped_date < order_date;

-- 5. Source-to-target reconciliation: counts and control totals
SELECT 'source' AS side, COUNT(*) AS row_count, SUM(order_total) AS total FROM orders
UNION ALL
SELECT 'target', COUNT(*), SUM(order_total) FROM dw_orders;

-- 6. Key-level diff: missing in target / extra in target
SELECT s.order_id, 'missing_in_target' AS issue
FROM (SELECT DISTINCT order_id FROM orders) s
LEFT JOIN dw_orders t ON t.order_id = s.order_id WHERE t.order_id IS NULL
UNION ALL
SELECT t.order_id, 'extra_in_target'
FROM dw_orders t LEFT JOIN (SELECT DISTINCT order_id FROM orders) s ON s.order_id = t.order_id
WHERE s.order_id IS NULL;

-- 7. Value mismatches on matched keys
SELECT s.order_id, s.order_total AS source_total, t.order_total AS target_total
FROM orders s JOIN dw_orders t ON t.order_id = s.order_id
WHERE ABS(s.order_total - t.order_total) > 0.01;

-- 8. Trend the audit table: failures by check over time
SELECT DATE(run_ts) AS run_date, "check", SUM(failed_rows) AS failed_rows
FROM dq_results WHERE failed_rows > 0
GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC;
