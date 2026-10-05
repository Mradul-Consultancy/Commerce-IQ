import importlib
import sys

import psycopg2

import config

PACKAGES = [
    "pandas", "numpy", "faker", "duckdb", "duckdb_engine", "psycopg2", "sqlalchemy",
    "dotenv", "fastapi", "uvicorn", "requests",
    "streamlit", "plotly", "openpyxl",
]


def check_packages():
    print("Checking packages...")
    ok = True
    for name in PACKAGES:
        try:
            importlib.import_module(name)
            print(f"  [OK]   {name}")
        except ImportError:
            print(f"  [FAIL] {name}")
            ok = False
    return ok


def check_database():
    print(f"\nChecking Database ({config.DB_ENGINE.upper()})...")
    if config.DB_ENGINE == "duckdb":
        try:
            import duckdb
            con = duckdb.connect(config.DATABASE_URL.replace("duckdb:///", ""))
            ver = con.execute("SELECT version();").fetchone()[0]
            print(f"  [OK]   Connected to DuckDB engine (version: {ver})")
            con.close()
            return True
        except Exception as e:
            print(f"  [FAIL] Could not initialize DuckDB: {e}")
            return False
    else:
        try:
            conn = psycopg2.connect(
                host=config.DB_HOST, port=config.DB_PORT,
                user=config.DB_USER, password=config.DB_PASSWORD,
                dbname="postgres",
            )
        except Exception as e:
            print(f"  [FAIL] Could not connect: {e}")
            return False

        print("  [OK]   Connected to PostgreSQL server")
        cur = conn.cursor()
        cur.execute("SELECT version();")
        print("  Version:", cur.fetchone()[0][:40])
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (config.DB_NAME,))
        exists = cur.fetchone() is not None
        print(f"  Database '{config.DB_NAME}':",
              "exists" if exists else "not created yet (that's fine, Task 2 creates it)")
        conn.close()
        return True


if __name__ == "__main__":
    pkgs = check_packages()
    db = check_database()
    print("\nResult:", "ALL GOOD" if pkgs and db else "FIX THE FAILURES ABOVE")
    sys.exit(0 if pkgs and db else 1)

