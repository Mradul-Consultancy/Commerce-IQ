import pandas as pd

from src.analytics import detect_revenue_anomalies


def test_detect_revenue_anomalies_finds_controlled_spike_and_drop():
    daily = pd.DataFrame({
        "order_date": pd.date_range("2026-01-01", periods=100),
        "revenue": [100 + (i % 7) * 3 for i in range(100)],
    })
    daily.loc[50, "revenue"] = 250
    daily.loc[90, "revenue"] = 0

    found = detect_revenue_anomalies(daily)
    found_dates = set(found["order_date"])

    assert daily.loc[50, "order_date"] in found_dates
    assert daily.loc[90, "order_date"] in found_dates
    assert set(found["type"]) == {"SPIKE", "DROP"}
