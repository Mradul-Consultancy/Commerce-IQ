import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "commerceiq")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "").strip()


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return [value.strip() for value in raw.split(",") if value.strip()]


CORS_ORIGINS = _csv_env(
    "CORS_ORIGINS",
    ["http://localhost:8501", "http://127.0.0.1:8501"],
)

DB_ENGINE = os.getenv("DB_ENGINE", "").lower()
if not DB_ENGINE:
    # If DB_PASSWORD or host specified and explicitly non-default, try postgres, otherwise default to duckdb
    if os.getenv("DB_PASSWORD") and os.getenv("DB_PASSWORD") != "your_password_here":
        DB_ENGINE = "postgres"
    else:
        DB_ENGINE = "duckdb"

if DB_ENGINE in ("postgres", "postgresql"):
    DATABASE_URL = (
        f"postgresql+psycopg2://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
else:
    # DuckDB embedded local database
    db_file = os.path.join(os.path.dirname(__file__), "commerceiq.duckdb").replace("\\", "/")
    DATABASE_URL = f"duckdb:///{db_file}"

if ENVIRONMENT == "production" and not API_KEY:
    raise RuntimeError("API_KEY must be set when ENVIRONMENT=production")

