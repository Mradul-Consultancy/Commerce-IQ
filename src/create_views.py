import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import config

VIEWS_FILE = ROOT / "sql" / "views.sql"


def main():
    engine = create_engine(config.DATABASE_URL)

    with engine.begin() as conn:
        conn.exec_driver_sql(VIEWS_FILE.read_text(encoding="utf-8"))
    print("Views created.\n")

    pd.set_option("display.width", 140)
    pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

    schema_condition = "WHERE table_schema = 'public'" if config.DB_ENGINE != "duckdb" else "WHERE table_schema = 'main'"
    with engine.connect() as conn:
        views = pd.read_sql(text(
            f"SELECT table_name FROM information_schema.views {schema_condition} ORDER BY table_name"), conn)
        print(f"{len(views)} views in database:")
        for name in views["table_name"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            print(f"  {name:<26} {n:>6} rows")

        print("\nv_kpi_summary:")
        print(pd.read_sql(text("SELECT * FROM v_kpi_summary"), conn).T.to_string(header=False))


if __name__ == "__main__":
    main()

