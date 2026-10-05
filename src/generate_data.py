import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
DATA_DIR = ROOT / "data"

SCALES = {
    "small": dict(customers=1_000, products=200, stores=10, orders=10_000),
    "full": dict(customers=100_000, products=10_000, stores=50, orders=1_000_000),
}

SEED = 42
START_DATE = np.datetime64("2024-01-01")
END_DATE = np.datetime64("2026-09-30")

LOCATIONS = [
    ("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"), ("Delhi", "Delhi"),
    ("Meerut", "Uttar Pradesh"), ("Lucknow", "Uttar Pradesh"),
    ("Bengaluru", "Karnataka"), ("Mysuru", "Karnataka"),
    ("Chennai", "Tamil Nadu"), ("Coimbatore", "Tamil Nadu"),
    ("Hyderabad", "Telangana"), ("Kolkata", "West Bengal"),
    ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"),
    ("Jaipur", "Rajasthan"), ("Chandigarh", "Chandigarh"),
    ("Bhopal", "Madhya Pradesh"), ("Indore", "Madhya Pradesh"),
    ("Patna", "Bihar"), ("Kochi", "Kerala"), ("Bhubaneswar", "Odisha"),
]

# category -> (min price, max price, product nouns)
CATEGORIES = {
    "Electronics": (999, 59999, ["Headphones", "Speaker", "Smartwatch", "Power Bank", "Camera", "Monitor"]),
    "Fashion": (299, 6999, ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Kurta", "Handbag"]),
    "Home & Kitchen": (199, 14999, ["Mixer Grinder", "Cookware Set", "Bedsheet", "Lamp", "Air Fryer", "Kettle"]),
    "Beauty": (99, 3999, ["Face Wash", "Moisturizer", "Perfume", "Lipstick", "Shampoo", "Serum"]),
    "Sports": (299, 12999, ["Yoga Mat", "Dumbbell Set", "Cricket Bat", "Football", "Fitness Band", "Backpack"]),
    "Books": (99, 1499, ["Novel", "Guide", "Workbook", "Biography", "Cookbook", "Comic"]),
    "Grocery": (49, 1999, ["Basmati Rice", "Olive Oil", "Tea Pack", "Dry Fruits", "Spice Box", "Coffee"]),
}
ADJECTIVES = ["Premium", "Classic", "Smart", "Eco", "Ultra", "Pro", "Essential", "Deluxe", "Compact", "Everyday"]

STATUSES = ["COMPLETED", "CANCELLED", "RETURNED", "PENDING"]
STATUS_P = [0.82, 0.08, 0.04, 0.06]
PAY_METHODS = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING", "COD", "WALLET"]
PAY_METHOD_P = [0.40, 0.20, 0.15, 0.08, 0.12, 0.05]
PAY_STATUS_MAP = {
    "COMPLETED": "PAID",
    "CANCELLED": "REFUNDED",
    "RETURNED": "REFUNDED",
    "PENDING": "PENDING",
}


def gen_stores(rng, n):
    rows = []
    for i in range(1, n + 1):
        city, _ = LOCATIONS[(i - 1) % len(LOCATIONS)]
        rows.append((i, f"CommerceIQ {city} #{i}", city, (i - 1) % 5 + 1))
    return pd.DataFrame(rows, columns=["store_id", "store_name", "city", "region_id"])


def gen_customers(rng, fake, n):
    loc_idx = rng.integers(0, len(LOCATIONS), n)
    reg_days = rng.integers(0, int((np.datetime64("2026-06-01") - np.datetime64("2022-01-01")).astype(int)), n)
    reg_dates = np.datetime64("2022-01-01") + reg_days.astype("timedelta64[D]")
    ids = np.arange(1, n + 1)
    names = [fake.name() for _ in range(n)]
    emails = [f"{nm.lower().replace(' ', '.').replace('..', '.')}{i}@example.com"
              for nm, i in zip(names, ids)]
    return pd.DataFrame({
        "customer_id": ids,
        "customer_name": names,
        "email": emails,
        "city": [LOCATIONS[i][0] for i in loc_idx],
        "state": [LOCATIONS[i][1] for i in loc_idx],
        "registration_date": reg_dates.astype("datetime64[D]").astype(str),
    })


def gen_products(rng, n):
    cats = list(CATEGORIES)
    cat_idx = rng.integers(0, len(cats), n)
    rows = []
    for pid in range(1, n + 1):
        cat = cats[cat_idx[pid - 1]]
        lo, hi, nouns = CATEGORIES[cat]
        price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), 2)
        cost = round(price * float(rng.uniform(0.50, 0.85)), 2)
        name = f"{rng.choice(ADJECTIVES)} {rng.choice(nouns)} {pid}"
        rows.append((pid, name, cat, price, cost))
    return pd.DataFrame(rows, columns=["product_id", "product_name", "category", "price", "cost"])


def gen_orders_items_payments(rng, customers, products, n_stores, n_orders):
    n_customers = len(customers)
    n_products = len(products)

    order_ids = np.arange(1, n_orders + 1, dtype=np.int64)
    customer_ids = rng.integers(1, n_customers + 1, n_orders)
    store_ids = rng.integers(1, n_stores + 1, n_orders)

    # order date: random day in range, but never before the customer registered
    span = int((END_DATE - START_DATE).astype(int))
    raw_dates = START_DATE + rng.integers(0, span + 1, n_orders).astype("timedelta64[D]")
    reg = pd.to_datetime(customers["registration_date"]).values.astype("datetime64[D]")
    order_dates = np.maximum(raw_dates, reg[customer_ids - 1])
    order_dates = np.minimum(order_dates, END_DATE)

    statuses = rng.choice(STATUSES, n_orders, p=STATUS_P)

    # items per order (1-5, weighted toward fewer)
    items_per_order = rng.choice([1, 2, 3, 4, 5], n_orders, p=[0.40, 0.30, 0.15, 0.10, 0.05])
    n_items = int(items_per_order.sum())
    item_order_ids = np.repeat(order_ids, items_per_order)

    # skewed popularity: some products sell far more than others
    weights = 1.0 / np.arange(1, n_products + 1) ** 0.8
    rng.shuffle(weights)
    weights /= weights.sum()
    item_product_ids = rng.choice(np.arange(1, n_products + 1), n_items, p=weights)
    quantities = rng.choice([1, 2, 3, 4, 5], n_items, p=[0.60, 0.20, 0.10, 0.06, 0.04])
    unit_prices = products["price"].values[item_product_ids - 1]

    line_totals = quantities * unit_prices
    totals = np.bincount(item_order_ids, weights=line_totals, minlength=n_orders + 1)[1:]
    totals = np.round(totals, 2)

    orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": customer_ids,
        "store_id": store_ids,
        "order_date": order_dates.astype("datetime64[D]").astype(str),
        "status": statuses,
        "total_amount": totals,
    })
    order_items = pd.DataFrame({
        "order_item_id": np.arange(1, n_items + 1, dtype=np.int64),
        "order_id": item_order_ids,
        "product_id": item_product_ids,
        "quantity": quantities,
        "unit_price": unit_prices,
    })
    payments = pd.DataFrame({
        "payment_id": order_ids,
        "order_id": order_ids,
        "payment_method": rng.choice(PAY_METHODS, n_orders, p=PAY_METHOD_P),
        "payment_status": pd.Series(statuses).map(PAY_STATUS_MAP).values,
        "amount": totals,
    })
    return orders, order_items, payments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=SCALES.keys(), default="small")
    args = parser.parse_args()
    cfg = SCALES[args.scale]

    rng = np.random.default_rng(SEED)
    fake = Faker("en_IN")
    Faker.seed(SEED)
    DATA_DIR.mkdir(exist_ok=True)

    print(f"Generating '{args.scale}' dataset: {cfg}")
    stores = gen_stores(rng, cfg["stores"])
    print("  stores done")
    customers = gen_customers(rng, fake, cfg["customers"])
    print("  customers done")
    products = gen_products(rng, cfg["products"])
    print("  products done")
    orders, items, payments = gen_orders_items_payments(
        rng, customers, products, cfg["stores"], cfg["orders"]
    )
    print("  orders, items, payments done")

    tables = {
        "stores": stores, "customers": customers, "products": products,
        "orders": orders, "order_items": items, "payments": payments,
    }
    for name, df in tables.items():
        df.to_csv(DATA_DIR / f"{name}.csv", index=False)
        print(f"  wrote data/{name}.csv  ({len(df):,} rows)")

    print("\nSanity checks:")
    check = items.assign(line=items.quantity * items.unit_price).groupby("order_id")["line"].sum().round(2)
    match = np.allclose(check.values, orders.sort_values("order_id").total_amount.values)
    print("  order totals match item sums:", match)
    print("  status split:\n", orders.status.value_counts(normalize=True).round(3).to_string())
    print("  date range:", orders.order_date.min(), "to", orders.order_date.max())
    print("  total revenue (COMPLETED): INR {:,.0f}".format(orders.loc[orders.status == "COMPLETED", "total_amount"].sum()))


if __name__ == "__main__":
    main()
