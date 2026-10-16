-- =====================================================================
-- 04 GOLD
-- Star schema for reporting. Natural business keys are used at this
-- scale for readability; a production build would add surrogate keys
-- so dimensions can track history.
-- Fact grains:
--   fact_sales_order      one row per order
--   fact_sales_line       one row per order line (cancelled orders excluded)
--   fact_production       one row per day per panel SKU
--   fact_inventory_weekly one row per week per site per SKU (snapshot)
--   fact_purchase_order   one row per purchase order
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------- dim_date
CREATE OR REPLACE TABLE gold.dim_date AS
WITH d AS (
    SELECT CAST(range AS DATE) AS date
    FROM range(DATE '2024-04-01', DATE '2027-01-01', INTERVAL 1 DAY)
)
SELECT d.date,
       year(d.date)                                              AS calendar_year,
       month(d.date)                                             AS month_number,
       strftime(d.date, '%b')                                    AS month_short,
       CAST(date_trunc('month', d.date) AS DATE)                 AS month_start,
       CASE WHEN month(d.date) >= 7 THEN year(d.date) + 1 ELSE year(d.date) END AS fy_number,
       'FY' || right(CAST(CASE WHEN month(d.date) >= 7 THEN year(d.date) + 1 ELSE year(d.date) END AS VARCHAR), 2) AS fy,
       ((month(d.date) + 5) % 12) // 3 + 1                         AS fy_quarter_number,
       'FY' || right(CAST(CASE WHEN month(d.date) >= 7 THEN year(d.date) + 1 ELSE year(d.date) END AS VARCHAR), 2)
            || ' Q' || CAST(((month(d.date) + 5) % 12) // 3 + 1 AS VARCHAR) AS fy_quarter,
       ((month(d.date) + 5) % 12) + 1                             AS fy_month_number,
       CAST(d.date + ((7 - isodow(d.date)) % 7) * INTERVAL 1 DAY AS DATE) AS week_ending,
       isodow(d.date)                                            AS iso_weekday,
       (isodow(d.date) <= 5 AND c.calendar_date IS NULL)         AS is_workday,
       c.reason                                                  AS closure_reason
FROM d
LEFT JOIN silver.calendar_closures c ON c.calendar_date = d.date;

-- ---------------------------------------------------------- dimensions
CREATE OR REPLACE TABLE gold.dim_product AS
SELECT sku, description, category, coalesce(profile, 'Not applicable') AS profile, uom
FROM silver.products;

CREATE OR REPLACE TABLE gold.dim_site AS
SELECT site_code, site_name, state, site_type, active_from, active_to,
       (active_to IS NULL) AS is_current
FROM silver.sites;

CREATE OR REPLACE TABLE gold.dim_customer AS
SELECT account_id, account_name, account_type, state, price_tier
FROM silver.accounts;

CREATE OR REPLACE TABLE gold.dim_project AS
SELECT p.project_id, p.project_name, p.segment, p.state, p.stage,
       a.account_name AS builder_name,
       p.est_m2, p.est_value, p.created_date, p.won_date
FROM silver.projects p
LEFT JOIN silver.accounts a ON a.account_id = p.builder_account_id
UNION ALL
SELECT 'UNASSIGNED', 'Unassigned or unmatched', 'Unknown', 'Unknown', 'Unknown',
       NULL, NULL, NULL, NULL, NULL;

CREATE OR REPLACE TABLE gold.dim_supplier AS
SELECT supplier_id, supplier_name, origin, material_code FROM silver.suppliers;

CREATE OR REPLACE TABLE gold.dim_material AS
SELECT material_code, material_name, uom FROM silver.raw_materials;

-- ---------------------------------------------------------- fact_sales_order
CREATE OR REPLACE TABLE gold.fact_sales_order AS
WITH order_value AS (
    SELECT order_id, sum(qty * unit_price) AS order_value
    FROM silver.sales_order_lines GROUP BY order_id
)
SELECT o.order_id,
       o.order_date, o.requested_date, o.promised_date, o.dispatch_date,
       o.customer_account_id                          AS account_id,
       coalesce(m.project_id, 'UNASSIGNED')           AS project_id,
       m.match_method                                 AS project_match_method,
       o.ship_from_site                               AS site_code,
       coalesce(p.state, c.state)                     AS delivery_state,
       o.order_status,
       ov.order_value,
       o.freight_cost,
       o.fuel_levy,
       (o.order_status = 'Dispatched' AND o.dispatch_date IS NOT NULL) AS is_valid_for_delivery_kpi,
       CASE WHEN o.order_status = 'Dispatched' AND o.dispatch_date IS NOT NULL
            THEN CAST(o.dispatch_date <= o.promised_date AS INTEGER) END  AS on_time_promise,
       CASE WHEN o.order_status = 'Dispatched' AND o.dispatch_date IS NOT NULL
            THEN CAST(o.dispatch_date <= o.requested_date AS INTEGER) END AS request_met,
       CASE WHEN o.dispatch_date IS NOT NULL
            THEN date_diff('day', o.order_date, o.dispatch_date) END       AS days_order_to_dispatch,
       CASE WHEN o.dispatch_date IS NOT NULL
            THEN greatest(date_diff('day', o.promised_date, o.dispatch_date), 0) END AS days_late_vs_promise
FROM silver.sales_orders o
LEFT JOIN silver.order_project_match m USING (order_id)
LEFT JOIN silver.projects p ON p.project_id = m.project_id
LEFT JOIN silver.accounts c ON c.account_id = o.customer_account_id
LEFT JOIN order_value ov USING (order_id);

-- ---------------------------------------------------------- fact_sales_line
CREATE OR REPLACE TABLE gold.fact_sales_line AS
SELECT l.line_id,
       l.order_id,
       o.order_date,
       o.customer_account_id                          AS account_id,
       coalesce(m.project_id, 'UNASSIGNED')           AS project_id,
       o.ship_from_site                               AS site_code,
       l.sku,
       l.qty,
       l.unit_price,
       pc.list_price,
       l.qty * l.unit_price                           AS net_revenue,
       l.qty * pc.list_price * pr.std_cost_ratio      AS std_cost,
       l.qty * l.unit_price - l.qty * pc.list_price * pr.std_cost_ratio AS gross_margin,
       pc.is_exception                                AS is_price_exception
FROM silver.sales_order_lines l
JOIN silver.sales_orders o USING (order_id)
LEFT JOIN silver.order_project_match m USING (order_id)
LEFT JOIN dq.line_price_check pc USING (line_id)
LEFT JOIN silver.products pr ON pr.sku = l.sku
WHERE o.order_status <> 'Cancelled';

-- ---------------------------------------------------------- operations facts
CREATE OR REPLACE TABLE gold.fact_production AS
SELECT production_date, site_code, sku, m2_produced, m2_scrapped, downtime_reason
FROM silver.production;

CREATE OR REPLACE TABLE gold.fact_inventory_weekly AS
SELECT week_ending, site_code, sku, qty_on_hand, qty_received, qty_shipped
FROM silver.inventory_weekly;

CREATE OR REPLACE TABLE gold.fact_purchase_order AS
SELECT po_number, po_date, expected_date, received_date,
       supplier_id, material_code, qty, unit_cost,
       qty * unit_cost                                         AS po_value,
       date_diff('day', po_date, expected_date)                AS quoted_lead_days,
       date_diff('day', po_date, received_date)                AS actual_lead_days,
       CASE WHEN received_date IS NOT NULL
            THEN greatest(date_diff('day', expected_date, received_date), 0) END AS days_late,
       (received_date IS NOT NULL)                             AS is_received,
       CASE WHEN received_date IS NOT NULL
            THEN CAST(received_date <= expected_date AS INTEGER) END AS is_on_time
FROM silver.purchase_orders;

-- ---------------------------------------------------------- governance tables for reporting
CREATE OR REPLACE TABLE gold.dq_results    AS SELECT * FROM dq.results;
CREATE OR REPLACE TABLE gold.dq_exceptions AS SELECT * FROM dq.exceptions;
CREATE OR REPLACE TABLE gold.metric_definitions AS SELECT * FROM bronze.ref_metric_definitions;
