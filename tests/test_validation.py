from pathlib import Path

import pandas as pd

from src.validate_data import run_rules


def _write_csv(path: Path, rows: list[dict]):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_validation_rules_report_bad_rows(tmp_path):
    _write_csv(tmp_path / "customers.csv", [
        {"customer_id": 1, "customer_name": "A", "email": "a@example.com"},
        {"customer_id": 2, "customer_name": "B", "email": ""},
    ])
    _write_csv(tmp_path / "orders.csv", [
        {"order_id": 1, "customer_id": 1, "total_amount": 10},
        {"order_id": 2, "customer_id": 99, "total_amount": -5},
        {"order_id": 2, "customer_id": 1, "total_amount": 12},
    ])
    _write_csv(tmp_path / "order_items.csv", [
        {"order_item_id": 1, "order_id": 1, "quantity": 1},
        {"order_item_id": 2, "order_id": 2, "quantity": 0},
    ])

    summary, rejected = run_rules(tmp_path)
    failures = dict(zip(summary["rule"], summary["failed_rows"]))

    assert failures["R1 total_amount >= 0"] == 1
    assert failures["R2 customer_id exists"] == 1
    assert failures["R3 email not empty"] == 1
    assert failures["R4 quantity > 0"] == 1
    assert failures["R5 no duplicate order_id"] == 1
    assert len(rejected) == 5
