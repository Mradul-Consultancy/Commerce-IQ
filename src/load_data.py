import sys
import time
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import config

DATA_DIR = ROOT / "data"

# Parents first, then children (order matters for foreign keys)
LOAD_ORDER = [
    ("stores",      ["store_id", "store_name", "city", "region_id"]),
    ("customers",   ["customer_id", "customer_name", "email", "city", "state", "registration_date"]),
    ("products",    ["product_id", "product_name", "category", "price", "cost"]),
    ("orders",      ["order_id", "customer_id", "store_id", "order_date", "status", "total_amount"]),
    ("order_items", ["order_item_id", "order_id", "product_id", "quantity", "unit_price"]),
    ("payments",    ["payment_id", "order_id", "payment_method", "payment_status", "amount"]),
]

# Children first, for clearing tables (regions stays: it was seeded by init_db.py)
CLEAR_ORDER = ["payments", "order_items", "orders", "products", "customers", "stores"]


def main():
    missing = [t for t, _ in LOAD_ORDER if not (DATA_DIR / f"{t}.csv").exists()]
    if missing:
        print("Missing CSV files:", missing)
        print("Run: python src/generate_data.py --scale small")
        sys.exit(1)

    if config.DB_ENGINE == "duckdb":
        import duckdb
        db_path = config.DATABASE_URL.replace("duckdb:///", "")
        con = duckdb.connect(db_path)
        total_start = time.time()
        print("Loading data into DuckDB...")
        for table, cols in LOAD_ORDER:
            start = time.time()
            csv_path = (DATA_DIR / f"{table}.csv").as_posix()
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT {', '.join(cols)} FROM read_csv_auto('{csv_path}');")
            print(f"  loaded {table:<12} in {time.time() - start:5.1f}s")
        print(f"\nAll tables loaded in {time.time() - total_start:.1f}s")
        print("\nRow counts:")
        for table, _ in LOAD_ORDER:
            cnt = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<12} {cnt:>10,}")
        con.close()
        print("Done.")
        return

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        user=config.DB_USER, password=config.DB_PASSWORD,
        dbname=config.DB_NAME,
    )
    cur = conn.cursor()

    try:
        print("Clearing existing data...")
        for table in CLEAR_ORDER:
            cur.execute(f"DELETE FROM {table};")

        total_start = time.time()
        for table, cols in LOAD_ORDER:
            start = time.time()
            copy_sql = f"COPY {table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, HEADER true)"
            with open(DATA_DIR / f"{table}.csv", "r", encoding="utf-8") as f:
                cur.copy_expert(copy_sql, f)
            print(f"  loaded {table:<12} in {time.time() - start:5.1f}s")

        conn.commit()
        print(f"\nAll tables loaded in {time.time() - total_start:.1f}s")

        print("\nRow counts:")
        for table, _ in LOAD_ORDER:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            print(f"  {table:<12} {cur.fetchone()[0]:>10,}")

        print("\nRunning ANALYZE for faster queries...")
    except Exception as e:
        conn.rollback()
        print("Load failed, rolled back. Error:", e)
        sys.exit(1)

    conn.autocommit = True
    cur.execute("ANALYZE;")
    conn.close()
    print("Done.")



if __name__ == "__main__":
    main()
