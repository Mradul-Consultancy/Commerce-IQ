import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent
print("Testing DuckDB engine...")
con = duckdb.connect("commerceiq.duckdb")

# Load tables from CSV
tables = ["regions", "stores", "customers", "products", "orders", "order_items", "payments"]
for t in tables:
    csv_p = ROOT / "data" / f"{t}.csv"
    if csv_p.exists():
        con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM read_csv_auto('{csv_p.as_posix()}');")
        cnt = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"Loaded {t}: {cnt} rows")

# Test views
views_file = ROOT / "sql" / "views.sql"
views_sql = views_file.read_text(encoding="utf-8")
for stmt in views_sql.split(";"):
    s = stmt.strip()
    if s:
        try:
            con.execute(s)
        except Exception as e:
            print(f"Error on view stmt: {s[:50]}... => {e}")

print("Views checked.")
kpi = con.execute("SELECT * FROM v_kpi_summary").fetchdf()
print("v_kpi_summary:")
print(kpi)
con.close()
