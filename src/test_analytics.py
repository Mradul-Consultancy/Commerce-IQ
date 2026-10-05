import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import analytics as a

pd.set_option("display.width", 140)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")


def section(title):
    print(f"\n=== {title} ===")


section("KPIs")
for k, v in a.kpis().items():
    print(f"  {k:<24} {v:,.2f}" if isinstance(v, float) else f"  {k:<24} {v:,}")

section("Monthly revenue (last 6)")
print(a.monthly_revenue().tail(6).to_string(index=False))

section("Month-over-month growth (last 6)")
print(a.monthly_growth().tail(6).to_string(index=False))

section("Top 5 products by revenue")
print(a.top_products(5, by="revenue")[["product_name", "category", "units_sold", "revenue", "profit"]]
      .to_string(index=False))

section("Top 5 customers")
print(a.top_customers(5)[["customer_name", "city", "orders", "lifetime_value"]].to_string(index=False))

section("Revenue by region")
print(a.region_revenue().to_string(index=False))

section("Category performance")
print(a.category_performance().to_string(index=False))

daily = a.daily_revenue()
section(f"Daily revenue anomalies on real data (z >= 3, {len(daily)} days)")
real = a.detect_revenue_anomalies(daily)
print(real.to_string(index=False) if len(real) else "  none found (expected: generated data is fairly uniform)")

section("Self-test with planted anomalies")
test = pd.DataFrame({
    "order_date": pd.date_range("2026-01-01", periods=100),
    "revenue": [100 + (i % 7) * 3 for i in range(100)],
})
spike_i, drop_i = 50, 90
test.loc[spike_i, "revenue"] = 250
test.loc[drop_i, "revenue"] = 0
found = a.detect_revenue_anomalies(test)
print(found.to_string(index=False))
got = set(found["order_date"])
ok = test.loc[spike_i, "order_date"] in got and test.loc[drop_i, "order_date"] in got
print("  planted spike and drop both detected:", ok)
if not ok:
    sys.exit(1)

section("Unusual orders (Q3 + 3*IQR)")
print("  total flagged:", f"{a.count_unusual_orders():,}")
u = a.detect_unusual_orders(limit=5)
print(u.to_string(index=False) if len(u) else "  none")
