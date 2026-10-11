import pandas as pd
import plotly.express as px
from datetime import date

import streamlit as st

import api_client as api


def inr(v: float) -> str:
    """Indian-style compact currency."""
    if v >= 1e7:
        return f"₹{v / 1e7:,.2f} Cr"
    if v >= 1e5:
        return f"₹{v / 1e5:,.2f} L"
    return f"₹{v:,.0f}"


def pct_delta(cur: float, prev: float):
    if not prev:
        return None
    return f"{(cur - prev) / prev * 100:+.1f}%"


st.set_page_config(
    page_title="CommerceIQ Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Sidebar ----------
st.sidebar.title("📊 CommerceIQ")

status = api.health()
if status:
    st.sidebar.success(f"API connected · {status['orders_in_db']:,} orders")
else:
    st.sidebar.error("API offline")
    st.error(
        "The dashboard cannot reach the API.\n\n"
        "Start it in another terminal from the `commerceiq/` folder:\n\n"
        "`uvicorn api.main:app --reload`"
    )
    if st.button("🔄 Retry Connection"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

page = st.sidebar.radio("Page", ["Overview", "Data Quality & Anomalies"])

st.sidebar.divider()
st.sidebar.subheader("Filters")

# Date bounds come from the data itself
daily = api.get("/api/revenue", (("granularity", "day"),))["data"]
min_date = date.fromisoformat(daily[0]["order_date"])
max_date = date.fromisoformat(daily[-1]["order_date"])

picked = st.sidebar.date_input(
    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
# While the user is mid-selection, date_input returns a single date
if isinstance(picked, (tuple, list)) and len(picked) == 2:
    start_date, end_date = picked
else:
    start_date, end_date = min_date, max_date

regions = [r["region_name"] for r in api.get("/api/regions")]
selected_regions = st.sidebar.multiselect("Regions", regions, default=regions)

st.session_state["filters"] = {
    "start": start_date.isoformat(),
    "end": end_date.isoformat(),
    "regions": selected_regions,
}

if st.sidebar.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption(f"API: {api.config.API_URL}")

# ---------- Main area ----------
st.title("CommerceIQ Analytics")
st.caption("E-commerce performance dashboard · data served by FastAPI from PostgreSQL views")

f = st.session_state["filters"]

if page == "Overview":
    if not f["regions"]:
        st.warning("Select at least one region in the sidebar.")
        st.stop()

    params = [("start", f["start"]), ("end", f["end"])]
    if len(f["regions"]) < len(regions):
        params.append(("regions", ",".join(f["regions"])))
    summary = api.get("/api/summary", tuple(params))
    cur, prev = summary["current"], summary["previous"]
    has_prev = prev["total_orders"] > 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Revenue", inr(cur["total_revenue"]),
        delta=pct_delta(cur["total_revenue"], prev["total_revenue"]) if has_prev else None,
        help=f"₹{cur['total_revenue']:,.0f} from completed orders",
    )
    c2.metric(
        "Orders", f"{cur['total_orders']:,}",
        delta=pct_delta(cur["total_orders"], prev["total_orders"]) if has_prev else None,
        help=f"{cur['completed_orders']:,} completed",
    )
    c3.metric(
        "Active customers", f"{cur['active_customers']:,}",
        delta=pct_delta(cur["active_customers"], prev["active_customers"]) if has_prev else None,
        help="Customers with at least one completed order",
    )
    c4.metric(
        "Avg order value", f"₹{cur['avg_order_value']:,.0f}",
        delta=pct_delta(cur["avg_order_value"], prev["avg_order_value"]) if has_prev else None,
    )
    c5.metric(
        "Cancellation rate", f"{cur['cancellation_rate_pct']:.2f}%",
        delta=(f"{cur['cancellation_rate_pct'] - prev['cancellation_rate_pct']:+.2f} pts"
               if has_prev else None),
        delta_color="inverse",
        help="Lower is better",
    )

    p = summary["previous_period"]
    if has_prev:
        st.caption(f"Change vs previous {summary['period']['days']} days ({p['start']} to {p['end']}).")
    else:
        st.caption("No earlier data to compare against for this range, so change indicators are hidden.")

    st.divider()
    base = tuple(params)

    def chart_data(path, extra=()):
        return pd.DataFrame(api.get(path, base + tuple(extra)))

    # --- Revenue trend ---
    gran_label = st.radio("Revenue trend", ["Monthly", "Daily"], horizontal=True)
    gran = "month" if gran_label == "Monthly" else "day"
    trend = chart_data("/api/charts/revenue-trend", (("granularity", gran),))
    if trend.empty:
        st.info("No completed orders in this selection.")
    else:
        fig = px.line(trend, x="period", y="revenue", markers=(gran == "month"),
                      labels={"period": "", "revenue": "Revenue (₹)"})
        fig.update_traces(hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>")
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=340)
        st.plotly_chart(fig, use_container_width=True)

    # --- Top products and revenue by region ---
    left, right = st.columns(2)
    with left:
        by_label = st.radio("Top 10 products by", ["Units sold", "Revenue"], horizontal=True)
        by = "units_sold" if by_label == "Units sold" else "revenue"
        tp = chart_data("/api/charts/top-products", (("n", 10), ("by", by)))
        if tp.empty:
            st.info("No product sales in this selection.")
        else:
            fig = px.bar(tp, x=by, y="product_name", orientation="h", color="category",
                         labels={"product_name": "", by: by_label})
            fig.update_layout(yaxis=dict(autorange="reversed"), height=400,
                              margin=dict(l=0, r=0, t=10, b=0), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown("**Revenue by region**")
        rg = chart_data("/api/charts/regions")
        if rg.empty:
            st.info("No revenue in this selection.")
        else:
            fig = px.bar(rg, x="region_name", y="revenue",
                         labels={"region_name": "", "revenue": "Revenue (₹)"})
            fig.update_traces(hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

    # --- Categories and order status ---
    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("**Revenue by category**")
        cat = chart_data("/api/charts/categories")
        if not cat.empty:
            fig = px.pie(cat, names="category", values="revenue", hole=0.45)
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
    with c_right:
        st.markdown("**Order status**")
        stt = chart_data("/api/charts/status")
        if not stt.empty:
            fig = px.pie(stt, names="status", values="orders", hole=0.45)
            fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

else:
    st.subheader("Data Quality & Anomalies")
    tab_q, tab_a = st.tabs(["Data quality", "Anomalies"])

    # ---------- Data quality ----------
    with tab_q:
        q = api.get("/api/quality")
        db = pd.DataFrame(q["database_checks"])

        m1, m2, m3 = st.columns(3)
        m1.metric("Checks run", len(db))
        m2.metric("Checks passing", int((db["status"] == "PASS").sum()))
        m3.metric("Failing rows", f"{int(db['failed_rows'].sum()):,}")

        st.markdown("**Live database checks**")
        st.dataframe(db, use_container_width=True, hide_index=True)
        if (db["status"] == "FAIL").any():
            st.warning("Some checks are failing. Investigate the tables listed above.")
        else:
            st.success("All database checks pass.")

        st.markdown("**Last CSV validation run** (from `src/validate_data.py`)")
        fv = q["file_validation"]
        if fv is None:
            st.info("No report yet. Run `python src/validate_data.py` from the commerceiq folder.")
        else:
            st.caption(f"Generated {fv['generated']}. Re-run the script to refresh it.")
            fdf = pd.DataFrame(fv["data"])
            st.dataframe(fdf, use_container_width=True, hide_index=True)
            if (fdf["status"] == "FAIL").any():
                st.warning("The last validation run found problems in the source CSVs.")

    # ---------- Anomalies ----------
    with tab_a:
        st.caption("Anomaly detection covers all dates and regions; the sidebar filters do not apply here.")
        s1, s2 = st.columns(2)
        z = s1.slider("Revenue sensitivity (z-score threshold)", 2.0, 6.0, 3.0, 0.5,
                      help="Lower = more days flagged")
        iqr = s2.slider("Large-order threshold (IQR multiplier)", 1.5, 6.0, 3.0, 0.5,
                        help="Lower = more orders flagged")

        an = api.get("/api/anomalies", (("z", z), ("iqr", iqr)))
        rev_an = pd.DataFrame(an["revenue_anomalies"]["data"])
        big = pd.DataFrame(an["unusual_orders"]["data"])

        k1, k2 = st.columns(2)
        k1.metric("Unusual revenue days", an["revenue_anomalies"]["count"])
        k2.metric("Unusually large orders", f"{an['unusual_orders']['count']:,}")

        daily_df = pd.DataFrame(api.get("/api/revenue", (("granularity", "day"),))["data"])
        fig = px.line(daily_df, x="order_date", y="revenue",
                      labels={"order_date": "", "revenue": "Daily revenue (₹)"})
        if not rev_an.empty:
            fig.add_scatter(x=rev_an["order_date"], y=rev_an["revenue"], mode="markers",
                            marker=dict(color="red", size=9), name="Anomaly")
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Flagged revenue days**")
        if rev_an.empty:
            st.info("No unusual days at this sensitivity. Generated data is fairly uniform, so this is expected.")
        else:
            st.dataframe(rev_an.round(2), use_container_width=True, hide_index=True)

        st.markdown("**Largest unusual orders** (top 20)")
        if big.empty:
            st.info("No unusually large orders at this threshold.")
        else:
            st.dataframe(big, use_container_width=True, hide_index=True)
