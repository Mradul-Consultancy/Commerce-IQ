import re
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import config

QUERY_FILE = ROOT / "sql" / "queries.sql"


def load_queries(path: Path) -> dict:
    """Split the SQL file into {name: query} using '-- name: xxx' markers."""
    queries = {}
    name, lines = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"--\s*name:\s*(\w+)", line)
        if m:
            if name:
                queries[name] = "\n".join(lines).strip().rstrip(";")
            name, lines = m.group(1), []
        else:
            lines.append(line)
    if name:
        queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    queries = load_queries(QUERY_FILE)
    if only and only not in queries:
        print(f"Unknown query '{only}'. Available: {', '.join(queries)}")
        sys.exit(1)

    engine = create_engine(config.DATABASE_URL)
    pd.set_option("display.width", 140)
    pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

    with engine.connect() as conn:
        for name, sql in queries.items():
            if only and name != only:
                continue
            start = time.time()
            df = pd.read_sql(text(sql), conn)
            print(f"\n=== {name}  ({len(df)} rows, {time.time() - start:.2f}s) ===")
            print(df.to_string(index=False))


if __name__ == "__main__":
    main()
