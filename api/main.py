import json
import secrets
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import config  # noqa: E402
from src import analytics  # noqa: E402

app = FastAPI(
    title="CommerceIQ API",
    description="E-commerce analytics API backed by SQL analytics views.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

VALID_STATUSES = "^(COMPLETED|CANCELLED|RETURNED|PENDING)$"
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


def _is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith("/docs/")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if config.API_KEY and not _is_public_path(request.url.path):
        supplied = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(supplied, config.API_KEY):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
    return await call_next(request)


def to_records(df: pd.DataFrame) -> list:
    """DataFrame -> JSON-safe list of dicts (dates as YYYY-MM-DD, NaN as null)."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    return json.loads(df.to_json(orient="records"))


def filter_dates(df: pd.DataFrame, col: str, start: Optional[date], end: Optional[date]):
    if start:
        df = df[df[col] >= pd.Timestamp(start)]
    if end:
        df = df[df[col] <= pd.Timestamp(end)]
    return df


# ---------------- Basics ----------------

@app.get("/")
def root():
    return {
        "service": "CommerceIQ API",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    start = time.time()
    try:
        df = analytics.run_sql("SELECT COUNT(*) AS n FROM orders")
        orders = int(df.iloc[0]["n"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
    return {
        "status": "ok",
        "database": "connected",
        "orders_in_db": orders,
        "response_ms": round((time.time() - start) * 1000, 1),
    }


# ---------------- Analytics endpoints ----------------

@app.get("/api/kpis")
def get_kpis():
    return analytics.kpis()


@app.get("/api/summary")
def get_summary(
    start: date,
    end: date,
    regions: Optional[str] = Query(None, description="Comma-separated region names; omit for all"),
):
    if end < start:
        raise HTTPException(status_code=422, detail="end must be on or after start")
    region_list = [r.strip() for r in regions.split(",") if r.strip()] if regions else None

    span = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)

    return {
        "period": {"start": start, "end": end, "days": span},
        "previous_period": {"start": prev_start, "end": prev_end},
        "current": analytics.filtered_kpis(start, end, region_list),
        "previous": analytics.filtered_kpis(prev_start, prev_end, region_list),
    }


@app.get("/api/revenue")
def get_revenue(
    granularity: str = Query("month", pattern="^(month|day)$"),
    start: Optional[date] = None,
    end: Optional[date] = None,
):
    if granularity == "month":
        df = analytics.monthly_revenue()
        df = filter_dates(df, "month", start, end)
    else:
        df = analytics.daily_revenue()
        df = filter_dates(df, "order_date", start, end)
    return {
        "granularity": granularity,
        "total_revenue": round(float(df["revenue"].sum()), 2),
        "rows": len(df),
        "data": to_records(df),
    }


@app.get("/api/orders")
def get_orders(
    status: Optional[str] = Query(None, pattern=VALID_STATUSES),
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    where, params = [], {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if start:
        where.append("order_date >= :start")
        params["start"] = start
    if end:
        where.append("order_date <= :end")
        params["end"] = end
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = int(analytics.run_sql(
        f"SELECT COUNT(*) AS n FROM orders {clause}", params).iloc[0]["n"])
    df = analytics.run_sql(
        f"""SELECT order_id, customer_id, store_id, order_date, status, total_amount
            FROM orders {clause}
            ORDER BY order_date DESC, order_id DESC
            LIMIT :limit OFFSET :offset""",
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "limit": limit, "offset": offset, "data": to_records(df)}


@app.get("/api/orders/status")
def get_order_status():
    return to_records(analytics.read_view("v_order_status"))


@app.get("/api/products/top")
def get_top_products(
    n: int = Query(10, ge=1, le=100),
    by: str = Query("units_sold", pattern="^(units_sold|revenue|profit)$"),
):
    return to_records(analytics.top_products(n, by))


@app.get("/api/customers/top")
def get_top_customers(n: int = Query(10, ge=1, le=100)):
    return to_records(analytics.top_customers(n))


@app.get("/api/regions")
def get_regions():
    return to_records(analytics.region_revenue())


@app.get("/api/categories")
def get_categories():
    return to_records(analytics.category_performance())


@app.get("/api/anomalies")
def get_anomalies(
    z: float = Query(3.0, ge=1.0, le=10.0),
    window: int = Query(30, ge=14, le=180),
    iqr: float = Query(3.0, ge=1.0, le=10.0),
    limit: int = Query(20, ge=1, le=200),
):
    daily = analytics.daily_revenue()
    revenue_anoms = analytics.detect_revenue_anomalies(daily, window=window, z_threshold=z)
    return {
        "revenue_anomalies": {
            "count": len(revenue_anoms),
            "data": to_records(revenue_anoms),
        },
        "unusual_orders": {
            "count": analytics.count_unusual_orders(iqr),
            "data": to_records(analytics.detect_unusual_orders(iqr, limit)),
        },
    }


# ---------------- Filtered chart endpoints (date range + regions) ----------------

def _parse_regions(regions: Optional[str]):
    return [r.strip() for r in regions.split(",") if r.strip()] if regions else None


@app.get("/api/charts/revenue-trend")
def chart_revenue_trend(start: date, end: date, regions: Optional[str] = None,
                        granularity: str = Query("month", pattern="^(month|day)$")):
    return to_records(analytics.revenue_trend(start, end, _parse_regions(regions), granularity))


@app.get("/api/charts/top-products")
def chart_top_products(start: date, end: date, regions: Optional[str] = None,
                       n: int = Query(10, ge=1, le=50),
                       by: str = Query("units_sold", pattern="^(units_sold|revenue)$")):
    return to_records(analytics.top_products_filtered(start, end, _parse_regions(regions), n, by))


@app.get("/api/charts/regions")
def chart_regions(start: date, end: date, regions: Optional[str] = None):
    return to_records(analytics.region_revenue_filtered(start, end, _parse_regions(regions)))


@app.get("/api/charts/categories")
def chart_categories(start: date, end: date, regions: Optional[str] = None):
    return to_records(analytics.category_revenue_filtered(start, end, _parse_regions(regions)))


@app.get("/api/charts/status")
def chart_status(start: date, end: date, regions: Optional[str] = None):
    return to_records(analytics.status_filtered(start, end, _parse_regions(regions)))


# ---------------- Data quality ----------------

@app.get("/api/quality")
def get_quality():
    report_path = ROOT / "reports" / "data_quality_report.csv"
    file_validation = None
    if report_path.exists():
        file_validation = {
            "generated": datetime.fromtimestamp(report_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "data": to_records(pd.read_csv(report_path)),
        }
    return {
        "file_validation": file_validation,
        "database_checks": to_records(analytics.db_quality_checks()),
    }
