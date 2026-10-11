import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import config

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        kwargs = {"pool_pre_ping": True}
        if config.DB_ENGINE == "duckdb":
            kwargs["connect_args"] = {"read_only": True}
        _engine = create_engine(config.DATABASE_URL, **kwargs)
    return _engine


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Postgres NUMERIC arrives as Decimal; convert to float. Parse date columns."""
    for col in df.columns:
        if df[col].dtype == object:
            first = df[col].dropna().head(1)
            if len(first) and isinstance(first.iloc[0], Decimal):
                df[col] = df[col].astype(float)
    for col in ("month", "order_date", "last_order_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


def run_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return _clean(pd.read_sql(text(sql), conn, params=params))


def read_view(name: str) -> pd.DataFrame:
    return run_sql(f"SELECT * FROM {name}")


# ---------- Core analytics ----------

def kpis() -> dict:
    row = read_view("v_kpi_summary").iloc[0]
    return {k: (float(v) if isinstance(v, (float, np.floating)) else int(v))
            for k, v in row.items()}


def monthly_revenue() -> pd.DataFrame:
    return read_view("v_monthly_revenue").sort_values("month").reset_index(drop=True)


def monthly_growth() -> pd.DataFrame:
    return read_view("v_monthly_growth").sort_values("month").reset_index(drop=True)


def daily_revenue() -> pd.DataFrame:
    df = read_view("v_daily_revenue").sort_values("order_date")
    full = pd.date_range(df["order_date"].min(), df["order_date"].max(), freq="D")
    df = df.set_index("order_date").reindex(full).fillna(0.0)
    df.index.name = "order_date"
    return df.reset_index()


def top_products(n: int = 10, by: str = "units_sold") -> pd.DataFrame:
    if by not in ("units_sold", "revenue", "profit"):
        raise ValueError("by must be units_sold, revenue or profit")
    return read_view("v_top_products").nlargest(n, by).reset_index(drop=True)


def top_customers(n: int = 10) -> pd.DataFrame:
    return read_view("v_top_customers").nlargest(n, "lifetime_value").reset_index(drop=True)


def region_revenue() -> pd.DataFrame:
    return read_view("v_region_revenue").sort_values("revenue", ascending=False).reset_index(drop=True)


def category_performance() -> pd.DataFrame:
    return read_view("v_category_performance").sort_values("revenue", ascending=False).reset_index(drop=True)


# ---------- Anomaly detection ----------

def detect_revenue_anomalies(daily: pd.DataFrame, window: int = 30,
                             z_threshold: float = 3.0) -> pd.DataFrame:
    """Flag days whose revenue is far from the previous `window` days' average."""
    df = daily.sort_values("order_date").reset_index(drop=True).copy()
    prior = df["revenue"].shift(1)  # exclude today from its own baseline
    df["rolling_mean"] = prior.rolling(window, min_periods=14).mean()
    df["rolling_std"] = prior.rolling(window, min_periods=14).std()
    df["z_score"] = (df["revenue"] - df["rolling_mean"]) / df["rolling_std"].replace(0, np.nan)
    flagged = df[df["z_score"].abs() >= z_threshold].copy()
    flagged["type"] = np.where(flagged["z_score"] > 0, "SPIKE", "DROP")
    return flagged[["order_date", "revenue", "rolling_mean", "z_score", "type"]].reset_index(drop=True)


def detect_unusual_orders(iqr_multiplier: float = 3.0, limit: int = 20) -> pd.DataFrame:
    """Completed orders above Q3 + k*IQR, with thresholds computed in SQL."""
    sql = """
    WITH q AS (
        SELECT
            percentile_cont(0.25) WITHIN GROUP (ORDER BY total_amount) AS q1,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY total_amount) AS q3
        FROM orders WHERE status = 'COMPLETED'
    )
    SELECT o.order_id, o.customer_id, o.order_date, o.total_amount,
           ROUND((q.q3 + :k * (q.q3 - q.q1))::numeric, 2) AS threshold
    FROM orders o CROSS JOIN q
    WHERE o.status = 'COMPLETED'
      AND o.total_amount > q.q3 + :k * (q.q3 - q.q1)
    ORDER BY o.total_amount DESC
    LIMIT :lim
    """
    return run_sql(sql, {"k": iqr_multiplier, "lim": limit})


def count_unusual_orders(iqr_multiplier: float = 3.0) -> int:
    sql = """
    WITH q AS (
        SELECT
            percentile_cont(0.25) WITHIN GROUP (ORDER BY total_amount) AS q1,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY total_amount) AS q3
        FROM orders WHERE status = 'COMPLETED'
    )
    SELECT COUNT(*) AS n FROM orders o CROSS JOIN q
    WHERE o.status = 'COMPLETED'
      AND o.total_amount > q.q3 + :k * (q.q3 - q.q1)
    """
    return int(run_sql(sql, {"k": iqr_multiplier}).iloc[0]["n"])


def filtered_kpis(start, end, regions: list | None = None) -> dict:
    """KPIs for a date range and optional list of region names (None = all regions)."""
    empty = {"total_revenue": 0.0, "total_orders": 0, "completed_orders": 0,
             "active_customers": 0, "avg_order_value": 0.0, "cancellation_rate_pct": 0.0}
    if regions is not None and len(regions) == 0:
        return empty

    region_clause, reg_params = _region_filter(regions)
    sql = f"""
    SELECT
        COALESCE(SUM(o.total_amount) FILTER (WHERE o.status = 'COMPLETED'), 0) AS total_revenue,
        COUNT(*)                                                               AS total_orders,
        COUNT(*) FILTER (WHERE o.status = 'COMPLETED')                         AS completed_orders,
        COUNT(DISTINCT o.customer_id) FILTER (WHERE o.status = 'COMPLETED')    AS active_customers,
        AVG(o.total_amount) FILTER (WHERE o.status = 'COMPLETED')              AS avg_order_value,
        100.0 * COUNT(*) FILTER (WHERE o.status = 'CANCELLED')
              / NULLIF(COUNT(*), 0)                                            AS cancellation_rate_pct
    FROM orders o
    JOIN stores  s ON s.store_id  = o.store_id
    JOIN regions r ON r.region_id = s.region_id
    WHERE o.order_date BETWEEN :start AND :end
      {region_clause}
    """
    params = {"start": start, "end": end, **reg_params}
    row = run_sql(sql, params).iloc[0]


    out = {}
    for k, v in row.items():
        if pd.isna(v):
            out[k] = empty[k]
        elif k in ("total_orders", "completed_orders", "active_customers"):
            out[k] = int(v)
        else:
            out[k] = round(float(v), 2)
    return out


# ---------- Filtered chart data (date range + optional regions) ----------

_FROM = """
FROM orders o
JOIN stores  s ON s.store_id  = o.store_id
JOIN regions r ON r.region_id = s.region_id
"""


def _region_filter(regions):
    if regions:
        reg_list = list(regions)
        if config.DB_ENGINE == "duckdb":
            placeholders = ", ".join(f":reg_{i}" for i in range(len(reg_list)))
            params = {f"reg_{i}": val for i, val in enumerate(reg_list)}
            return f"AND r.region_name IN ({placeholders})", params
        return "AND r.region_name = ANY(CAST(:regions AS text[]))", {"regions": reg_list}
    return "", {}



def revenue_trend(start, end, regions=None, granularity: str = "month") -> pd.DataFrame:
    unit = "day" if granularity == "day" else "month"
    clause, extra = _region_filter(regions)
    if config.DB_ENGINE == "duckdb":
        period_expr = f"strftime(DATE_TRUNC('{unit}', o.order_date), '%Y-%m-%d')"
    else:
        period_expr = f"TO_CHAR(DATE_TRUNC('{unit}', o.order_date), 'YYYY-MM-DD')"
    sql = f"""
    SELECT {period_expr} AS period,
           SUM(o.total_amount) AS revenue,
           COUNT(*)            AS orders
    {_FROM}
    WHERE o.status = 'COMPLETED' AND o.order_date BETWEEN :start AND :end {clause}
    GROUP BY 1 ORDER BY 1
    """
    return run_sql(sql, {"start": start, "end": end, **extra})


def top_products_filtered(start, end, regions=None, n: int = 10, by: str = "units_sold") -> pd.DataFrame:
    if by not in ("units_sold", "revenue"):
        raise ValueError("by must be units_sold or revenue")
    clause, extra = _region_filter(regions)
    sql = f"""
    SELECT p.product_name, p.category,
           SUM(oi.quantity)                 AS units_sold,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders   o ON o.order_id   = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    JOIN stores   s ON s.store_id   = o.store_id
    JOIN regions  r ON r.region_id  = s.region_id
    WHERE o.status = 'COMPLETED' AND o.order_date BETWEEN :start AND :end {clause}
    GROUP BY p.product_name, p.category
    ORDER BY {by} DESC
    LIMIT :n
    """
    return run_sql(sql, {"start": start, "end": end, "n": n, **extra})


def region_revenue_filtered(start, end, regions=None) -> pd.DataFrame:
    clause, extra = _region_filter(regions)
    sql = f"""
    SELECT r.region_name, SUM(o.total_amount) AS revenue, COUNT(*) AS orders
    {_FROM}
    WHERE o.status = 'COMPLETED' AND o.order_date BETWEEN :start AND :end {clause}
    GROUP BY r.region_name ORDER BY revenue DESC
    """
    return run_sql(sql, {"start": start, "end": end, **extra})


def category_revenue_filtered(start, end, regions=None) -> pd.DataFrame:
    clause, extra = _region_filter(regions)
    sql = f"""
    SELECT p.category, SUM(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders   o ON o.order_id   = oi.order_id
    JOIN products p ON p.product_id = oi.product_id
    JOIN stores   s ON s.store_id   = o.store_id
    JOIN regions  r ON r.region_id  = s.region_id
    WHERE o.status = 'COMPLETED' AND o.order_date BETWEEN :start AND :end {clause}
    GROUP BY p.category ORDER BY revenue DESC
    """
    return run_sql(sql, {"start": start, "end": end, **extra})


def status_filtered(start, end, regions=None) -> pd.DataFrame:
    clause, extra = _region_filter(regions)
    sql = f"""
    SELECT o.status, COUNT(*) AS orders
    {_FROM}
    WHERE o.order_date BETWEEN :start AND :end {clause}
    GROUP BY o.status ORDER BY orders DESC
    """
    return run_sql(sql, {"start": start, "end": end, **extra})


# ---------- Data quality checks run directly on the database ----------

def db_quality_checks() -> pd.DataFrame:
    checks = [
        ("Order amount >= 0", "orders",
         "SELECT COUNT(*) AS n FROM orders WHERE total_amount < 0"),
        ("Customer email not empty", "customers",
         "SELECT COUNT(*) AS n FROM customers WHERE email IS NULL OR TRIM(email) = ''"),
        ("Item quantity > 0", "order_items",
         "SELECT COUNT(*) AS n FROM order_items WHERE quantity <= 0"),
        ("Order total equals sum of its items", "orders",
         """SELECT COUNT(*) AS n FROM orders o
            JOIN (SELECT order_id, SUM(quantity * unit_price) AS s
                  FROM order_items GROUP BY order_id) i ON i.order_id = o.order_id
            WHERE ABS(o.total_amount - i.s) > 0.01"""),
        ("Every order has at least one item", "orders",
         """SELECT COUNT(*) AS n FROM orders o
            WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)"""),
        ("Payment amount equals order total", "payments",
         """SELECT COUNT(*) AS n FROM payments p
            JOIN orders o ON o.order_id = p.order_id
            WHERE ABS(p.amount - o.total_amount) > 0.01"""),
    ]
    rows = []
    for name, table, sql in checks:
        failed = int(run_sql(sql).iloc[0]["n"])
        total = int(run_sql(f"SELECT COUNT(*) AS n FROM {table}").iloc[0]["n"])
        rows.append({
            "check": name, "table": table, "total_rows": total,
            "failed_rows": failed, "status": "PASS" if failed == 0 else "FAIL",
        })
    return pd.DataFrame(rows)
