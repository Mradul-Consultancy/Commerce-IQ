import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIRTY_DIR = DATA_DIR / "dirty"

N_NEG, N_ORPHAN, N_EMAIL, N_QTY, N_DUP = 50, 40, 30, 25, 20


def main():
    rng = np.random.default_rng(7)
    DIRTY_DIR.mkdir(exist_ok=True)
    for f in DATA_DIR.glob("*.csv"):
        shutil.copy(f, DIRTY_DIR / f.name)

    orders = pd.read_csv(DIRTY_DIR / "orders.csv")
    customers = pd.read_csv(DIRTY_DIR / "customers.csv")
    items = pd.read_csv(DIRTY_DIR / "order_items.csv")

    # Rule 1: negative order amounts
    idx = rng.choice(orders.index, N_NEG, replace=False)
    orders.loc[idx, "total_amount"] *= -1

    # Rule 2: orders pointing to customers that don't exist
    idx = rng.choice(orders.index, N_ORPHAN, replace=False)
    orders.loc[idx, "customer_id"] = 99_999_999

    # Rule 3: empty emails
    idx = rng.choice(customers.index, N_EMAIL, replace=False)
    customers.loc[idx, "email"] = np.nan

    # Rule 4: zero quantity
    idx = rng.choice(items.index, N_QTY, replace=False)
    items.loc[idx, "quantity"] = 0

    # Rule 5: duplicate order IDs
    dupes = orders.sample(N_DUP, random_state=7)
    orders = pd.concat([orders, dupes], ignore_index=True)

    orders.to_csv(DIRTY_DIR / "orders.csv", index=False)
    customers.to_csv(DIRTY_DIR / "customers.csv", index=False)
    items.to_csv(DIRTY_DIR / "order_items.csv", index=False)

    print(f"Dirty dataset written to {DIRTY_DIR}")
    print(f"  planted: {N_NEG} negative amounts, {N_ORPHAN} orphan customer IDs, "
          f"{N_EMAIL} empty emails, {N_QTY} zero quantities, {N_DUP} duplicate orders")


if __name__ == "__main__":
    main()
