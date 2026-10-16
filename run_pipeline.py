"""
Runs the warehouse build end to end:
  bronze  -> land raw exports as text with lineage
  silver  -> type, deduplicate, standardise, match orders to projects
  dq      -> run and log every data quality check
  gold    -> star schema, exported as CSV for Power BI
"""
import csv
import os
import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
os.makedirs("gold", exist_ok=True)

con = duckdb.connect("warehouse.duckdb")


def run(path):
    with open(path) as f:
        con.execute(f.read())
    print(f"  ran {path}")


def build_alias_macro():
    """Turn the alias rules file into a nested regexp_replace macro."""
    with open("ref/project_alias_rules.csv", newline="") as f:
        rules = sorted(csv.DictReader(f), key=lambda r: int(r["rule_order"]))
    expr = "coalesce(x, '')"
    for r in rules:
        pat = "(?i)" + r["pattern"].replace("'", "''")
        rep = r["replacement"].replace("'", "''")
        expr = f"regexp_replace({expr}, '{pat}', '{rep}', 'g')"
    con.execute(f"CREATE OR REPLACE MACRO expand_alias(x) AS {expr};")
    print(f"  built expand_alias() from {len(rules)} rules")


print("Building warehouse")
run("sql/01_bronze.sql")
build_alias_macro()
run("sql/02_silver.sql")
run("sql/03_quality.sql")
run("sql/04_gold.sql")

print("\nExporting gold tables")
tables = [r[0] for r in con.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'gold' ORDER BY 1").fetchall()]
for t in tables:
    con.execute(f"COPY gold.{t} TO 'gold/{t}.csv' (HEADER, DELIMITER ',')")
    n = con.execute(f"SELECT count(*) FROM gold.{t}").fetchone()[0]
    print(f"  {t:<24}{n:>7} rows")

print("\nData quality summary")
for row in con.execute(
        "SELECT check_id, status, rows_failed, rows_checked, round(value_at_risk), check_name "
        "FROM dq.results ORDER BY check_id").fetchall():
    cid, status, failed, checked, var, name = row
    risk = f"  value at risk ${var:,.0f}" if var else ""
    print(f"  {cid} {status:<5}{failed:>6} of {checked:<6} {name}{risk}")

con.close()
