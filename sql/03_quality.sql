-- =====================================================================
-- 03 DATA QUALITY
-- Every check produces one row in dq.results, including checks that
-- pass, so the report proves what was tested and not just what broke.
-- Row level problems go to dq.exceptions for whoever owns the source.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS dq;

-- line value against the list price in force on the order date
CREATE OR REPLACE TABLE dq.line_price_check AS
SELECT l.line_id, l.order_id, l.sku, l.qty, l.unit_price, pl.list_price,
       l.unit_price / nullif(pl.list_price, 0) AS price_ratio,
       (l.unit_price / nullif(pl.list_price, 0) NOT BETWEEN 0.5 AND 2.0) AS is_exception,
       abs(l.qty * l.unit_price - l.qty * pl.list_price * (1 - l.discount_pct)) AS value_at_risk
FROM silver.sales_order_lines l
JOIN silver.sales_orders o USING (order_id)
LEFT JOIN silver.price_list pl
       ON pl.sku = l.sku AND o.order_date BETWEEN pl.effective_from AND pl.effective_to;

CREATE OR REPLACE TABLE dq.results AS
WITH c AS (
    SELECT 'DQ01' AS check_id, 'Duplicate order rows in ERP export' AS check_name, 'Bronze to Silver' AS layer,
           'erp_sales_orders' AS source_table,
           (SELECT count(*) FROM bronze.erp_sales_orders) AS rows_checked,
           (SELECT count(*) FROM bronze.erp_sales_orders) - (SELECT count(*) FROM silver.sales_orders) AS rows_failed,
           0.0 AS value_at_risk, 'Medium' AS severity,
           'Removed in silver, one row kept per order' AS action_taken
    UNION ALL
    SELECT 'DQ02', 'Duplicate order line rows in ERP export', 'Bronze to Silver', 'erp_sales_order_lines',
           (SELECT count(*) FROM bronze.erp_sales_order_lines),
           (SELECT count(*) FROM bronze.erp_sales_order_lines) - (SELECT count(*) FROM silver.sales_order_lines),
           0.0, 'Medium', 'Removed in silver, one row kept per line'
    UNION ALL
    SELECT 'DQ03', 'Project state entered in a non standard format', 'Silver', 'crm_projects',
           (SELECT count(*) FROM silver.projects),
           (SELECT count(*) FROM silver.projects WHERE state_as_entered <> state),
           0.0, 'Low', 'Standardised through the state mapping table'
    UNION ALL
    SELECT 'DQ04', 'Project state that cannot be mapped', 'Silver', 'crm_projects',
           (SELECT count(*) FROM silver.projects),
           (SELECT count(*) FROM silver.projects WHERE state = 'UNKNOWN'),
           0.0, 'High', 'Would block load and be raised with the CRM owner'
    UNION ALL
    SELECT 'DQ05', 'Order not linked to a CRM project', 'Silver', 'erp_sales_orders',
           (SELECT count(*) FROM silver.order_project_match),
           (SELECT count(*) FROM silver.order_project_match WHERE match_method IN ('Unmatched', 'Blank')),
           (SELECT coalesce(sum(l.qty * l.unit_price), 0)
              FROM silver.sales_order_lines l
              JOIN silver.order_project_match m USING (order_id)
              JOIN silver.sales_orders o USING (order_id)
             WHERE m.match_method IN ('Unmatched', 'Blank') AND o.order_status <> 'Cancelled'),
           'Medium', 'Reported under Unassigned project, list sent to sales admin'
    UNION ALL
    SELECT 'DQ06', 'Dispatched order with no dispatch date', 'Silver', 'erp_sales_orders',
           (SELECT count(*) FROM silver.sales_orders WHERE order_status = 'Dispatched'),
           (SELECT count(*) FROM silver.sales_orders WHERE order_status = 'Dispatched' AND dispatch_date IS NULL),
           0.0, 'High', 'Excluded from delivery metrics, flagged to operations'
    UNION ALL
    SELECT 'DQ07', 'Line price outside 50 to 200 percent of price list', 'Silver', 'erp_sales_order_lines',
           (SELECT count(*) FROM dq.line_price_check),
           (SELECT count(*) FROM dq.line_price_check WHERE is_exception),
           (SELECT coalesce(sum(value_at_risk), 0) FROM dq.line_price_check WHERE is_exception),
           'High', 'Kept and flagged, value at risk reported, finance to correct at source'
    UNION ALL
    SELECT 'DQ08', 'Order line with no order header', 'Silver', 'erp_sales_order_lines',
           (SELECT count(*) FROM silver.sales_order_lines),
           (SELECT count(*) FROM silver.sales_order_lines l
              WHERE NOT EXISTS (SELECT 1 FROM silver.sales_orders o WHERE o.order_id = l.order_id)),
           0.0, 'High', 'Would be quarantined'
    UNION ALL
    SELECT 'DQ09', 'Order line with unknown SKU', 'Silver', 'erp_sales_order_lines',
           (SELECT count(*) FROM silver.sales_order_lines),
           (SELECT count(*) FROM silver.sales_order_lines l
              WHERE NOT EXISTS (SELECT 1 FROM silver.products p WHERE p.sku = l.sku)),
           0.0, 'High', 'Would be quarantined'
    UNION ALL
    SELECT 'DQ10', 'Order with unknown customer', 'Silver', 'erp_sales_orders',
           (SELECT count(*) FROM silver.sales_orders),
           (SELECT count(*) FROM silver.sales_orders o
              WHERE NOT EXISTS (SELECT 1 FROM silver.accounts a WHERE a.account_id = o.customer_account_id)),
           0.0, 'High', 'Would be quarantined'
    UNION ALL
    SELECT 'DQ11', 'Zero or negative quantity', 'Silver', 'erp_sales_order_lines',
           (SELECT count(*) FROM silver.sales_order_lines),
           (SELECT count(*) FROM silver.sales_order_lines WHERE qty <= 0),
           0.0, 'Medium', 'Would be flagged'
    UNION ALL
    SELECT 'DQ12', 'Promised date earlier than order date', 'Silver', 'erp_sales_orders',
           (SELECT count(*) FROM silver.sales_orders),
           (SELECT count(*) FROM silver.sales_orders WHERE promised_date < order_date),
           0.0, 'Medium', 'Would be flagged'
    UNION ALL
    SELECT 'DQ13', 'Purchase order received before it was raised', 'Silver', 'erp_purchase_orders',
           (SELECT count(*) FROM silver.purchase_orders),
           (SELECT count(*) FROM silver.purchase_orders WHERE received_date < po_date),
           0.0, 'High', 'Would be flagged'
    UNION ALL
    SELECT 'DQ14', 'Transactional source older than seven days at load', 'Freshness', 'orders, production, inventory, purchasing', 4,
           (SELECT count(*) FROM (
                SELECT max(order_date) AS latest FROM silver.sales_orders
                UNION ALL SELECT max(production_date) FROM silver.production
                UNION ALL SELECT max(week_ending) FROM silver.inventory_weekly
                UNION ALL SELECT max(po_date) FROM silver.purchase_orders
            ) WHERE latest < DATE '2026-09-30' - INTERVAL 7 DAY),
           0.0, 'High', 'Report would show a stale data banner'
    UNION ALL
    SELECT 'DQ15', 'On time measured two ways gives different answers', 'Definitions', 'erp_sales_orders',
           (SELECT count(*) FROM silver.sales_orders WHERE order_status = 'Dispatched' AND dispatch_date IS NOT NULL),
           (SELECT count(*) FROM silver.sales_orders
             WHERE order_status = 'Dispatched' AND dispatch_date IS NOT NULL
               AND dispatch_date <= promised_date AND dispatch_date > requested_date),
           0.0, 'Medium', 'Split into two locked metrics: On Time Delivery (Promise) and Request Met Rate'
)
SELECT *,
       round(100.0 * rows_failed / nullif(rows_checked, 0), 2) AS pct_failed,
       CASE WHEN rows_failed = 0 THEN 'Pass'
            WHEN severity = 'High' THEN 'Fail'
            ELSE 'Warn' END AS status
FROM c
ORDER BY check_id;

-- row level exceptions for the owners of each source
CREATE OR REPLACE TABLE dq.exceptions AS
SELECT 'DQ05' AS check_id, order_id AS record_id,
       'Project reference: ' || coalesce(nullif(trim(project_ref_raw), ''), '(blank)') AS detail
FROM silver.order_project_match WHERE match_method IN ('Unmatched', 'Blank')
UNION ALL
SELECT 'DQ06', order_id, 'Status Dispatched, dispatch date missing'
FROM silver.sales_orders WHERE order_status = 'Dispatched' AND dispatch_date IS NULL
UNION ALL
SELECT 'DQ07', CAST(line_id AS VARCHAR),
       order_id || ' ' || sku || ': charged ' || CAST(round(unit_price, 2) AS VARCHAR)
       || ' vs list ' || CAST(round(list_price, 2) AS VARCHAR)
FROM dq.line_price_check WHERE is_exception;
