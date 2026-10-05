import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"


def run_rules(src: Path):
    orders = pd.read_csv(src / "orders.csv")
    customers = pd.read_csv(src / "customers.csv")
    items = pd.read_csv(src / "order_items.csv")

    results = []   # summary rows
    rejected = []  # failing record keys

    def record(rule, table, key_col, df, mask):
        failed = df[mask]
        results.append({
            "rule": rule,
            "table": table,
            "total_rows": len(df),
            "failed_rows": int(mask.sum()),
            "pass_rate_pct": round(100 * (1 - mask.sum() / len(df)), 3),
            "status": "PASS" if mask.sum() == 0 else "FAIL",
        })
        if len(failed):
            rejected.append(pd.DataFrame({
                "rule": rule, "table": table,
                "record_key": failed[key_col].values,
            }))

    # Rule 1: order amount cannot be negative
    record("R1 total_amount >= 0", "orders", "order_id",
           orders, orders["total_amount"] < 0)

    # Rule 2: customer_id must exist in customers
    record("R2 customer_id exists", "orders", "order_id",
           orders, ~orders["customer_id"].isin(customers["customer_id"]))

    # Rule 3: email cannot be empty
    email_empty = customers["email"].isna() | (customers["email"].astype(str).str.strip() == "")
    record("R3 email not empty", "customers", "customer_id", customers, email_empty)

    # Rule 4: quantity must be greater than zero
    record("R4 quantity > 0", "order_items", "order_item_id",
           items, items["quantity"] <= 0)

    # Rule 5: no duplicate order IDs (extra copies are flagged)
    record("R5 no duplicate order_id", "orders", "order_id",
           orders, orders["order_id"].duplicated(keep="first"))

    summary = pd.DataFrame(results)
    rej = pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame(
        columns=["rule", "table", "record_key"])
    return summary, rej


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data",
                        help="folder with CSVs (default: data, try: data/dirty)")
    args = parser.parse_args()

    src = (ROOT / args.source).resolve()
    if not (src / "orders.csv").exists():
        print(f"No CSV files found in {src}")
        sys.exit(1)

    print(f"Validating: {src}\n")
    summary, rejected = run_rules(src)

    REPORTS_DIR.mkdir(exist_ok=True)
    summary.to_csv(REPORTS_DIR / "data_quality_report.csv", index=False)
    rejected.to_csv(REPORTS_DIR / "rejected_records.csv", index=False)

    print(summary.to_string(index=False))
    total_failed = int(summary["failed_rows"].sum())
    print(f"\nTotal failing rows: {total_failed:,}")
    print("Wrote reports/data_quality_report.csv and reports/rejected_records.csv")
    sys.exit(0 if total_failed == 0 else 2)


if __name__ == "__main__":
    main()
