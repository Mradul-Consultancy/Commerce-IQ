import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

REGIONS = ["North", "South", "East", "West", "Central"]


def create_database():
    if config.DB_ENGINE == "duckdb":
        import duckdb
        db_path = config.DATABASE_URL.replace("duckdb:///", "")
        con = duckdb.connect(db_path)
        con.close()
        print(f"Database '{db_path}' initialized.")
        return

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        user=config.DB_USER, password=config.DB_PASSWORD,
        dbname="postgres",
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (config.DB_NAME,))
    if cur.fetchone():
        print(f"Database '{config.DB_NAME}' already exists.")
    else:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(config.DB_NAME)))
        print(f"Database '{config.DB_NAME}' created.")
    conn.close()


def create_tables():
    if config.DB_ENGINE == "duckdb":
        import duckdb
        db_path = config.DATABASE_URL.replace("duckdb:///", "")
        con = duckdb.connect(db_path)
        con.execute("CREATE TABLE IF NOT EXISTS regions (region_id INTEGER, region_name VARCHAR);")
        con.execute("DELETE FROM regions;")
        for i, name in enumerate(REGIONS, start=1):
            con.execute("INSERT INTO regions VALUES (?, ?);", [i, name])
        con.close()
        print("Tables created and regions seeded.")
        return

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        user=config.DB_USER, password=config.DB_PASSWORD,
        dbname=config.DB_NAME,
    )
    cur = conn.cursor()
    cur.execute(SCHEMA_FILE.read_text())
    for name in REGIONS:
        cur.execute("INSERT INTO regions (region_name) VALUES (%s);", (name,))
    conn.commit()
    conn.close()
    print("Tables created and regions seeded.")


if __name__ == "__main__":
    create_database()
    create_tables()

