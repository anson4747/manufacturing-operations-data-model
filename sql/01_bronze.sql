-- =====================================================================
-- 01 BRONZE
-- Land every source exactly as exported. Everything stays as text so
-- nothing is silently coerced or lost on the way in. Each row carries
-- its source file and load time for lineage.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.crm_accounts AS
SELECT *, 'crm_accounts_export.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/crm_accounts_export.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.crm_projects AS
SELECT *, 'crm_projects_export.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/crm_projects_export.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_sales_orders AS
SELECT *, 'erp_sales_orders.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_sales_orders.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_sales_order_lines AS
SELECT *, 'erp_sales_order_lines.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_sales_order_lines.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_products AS
SELECT *, 'erp_products.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_products.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_standard_cost AS
SELECT *, 'erp_standard_cost.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_standard_cost.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_price_list AS
SELECT *, 'erp_price_list.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_price_list.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_purchase_orders AS
SELECT *, 'erp_purchase_orders.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_purchase_orders.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_suppliers AS
SELECT *, 'erp_suppliers.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_suppliers.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.erp_raw_materials AS
SELECT *, 'erp_raw_materials.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/erp_raw_materials.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.prod_daily_output AS
SELECT *, 'prod_daily_output.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/prod_daily_output.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.wms_inventory_weekly AS
SELECT *, 'wms_inventory_weekly.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/wms_inventory_weekly.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.sp_sites AS
SELECT *, 'sharepoint_sites.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/sharepoint_sites.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.sp_fuel_levy AS
SELECT *, 'sharepoint_fuel_levy_rates.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/sharepoint_fuel_levy_rates.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.sp_company_calendar AS
SELECT *, 'sharepoint_company_calendar.csv' AS _source_file, current_timestamp AS _loaded_at
FROM read_csv('raw/sharepoint_company_calendar.csv', all_varchar = true, header = true);

-- Reference data maintained by the data team
CREATE OR REPLACE TABLE bronze.ref_state_mapping AS
SELECT * FROM read_csv('ref/state_mapping.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.ref_project_alias_rules AS
SELECT * FROM read_csv('ref/project_alias_rules.csv', all_varchar = true, header = true);

CREATE OR REPLACE TABLE bronze.ref_metric_definitions AS
SELECT * FROM read_csv('ref/metric_definitions.csv', all_varchar = true, header = true);
