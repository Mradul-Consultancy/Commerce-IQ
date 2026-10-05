# CommerceIQ: interview talking points

Fill in the bracketed numbers from your own full-dataset run before an interview.

## 30-second pitch

"CommerceIQ is an analytics platform I built for an e-commerce scenario. I generated about a million orders, validated them with Python and Pandas, loaded them into PostgreSQL, and built 12 SQL views for the analytics. A FastAPI backend serves the results to a Streamlit dashboard with Plotly charts, and the system also generates Excel and CSV reports automatically."

## Be upfront about

- The data is synthetic. Say so, then explain why: it let me control volume and plant known errors to prove the validation works.
- Revenue counts completed orders only.

## Likely questions and answers

**Why PostgreSQL, and how did you load 1M rows?**
Relational data with foreign keys fits Postgres. I used `COPY` instead of row-by-row inserts, and loaded parent tables before children to satisfy foreign keys. Full load took [__ seconds].

**What does your validation check?**
Five rules: non-negative amounts, customer IDs that exist, non-empty emails, quantity above zero, and no duplicate order IDs. I proved it works by injecting a known number of each error and confirming the validator found exactly that many.

**Why validate before loading rather than just rely on constraints?**
Constraints reject the whole load on the first bad row. A validation step reports every problem, writes a rejected-records file, and lets automation stop a bad load (it exits with a non-zero code).

**What are SQL views for, and which ones did you build?**
They hold the business logic in one place so the API, dashboard and reports all agree. Examples: monthly revenue, category profit margin, customer segments, and month-over-month growth using `LAG`.

**How does anomaly detection work?**
Daily revenue is compared against the previous 30 days using a z-score, flagging days beyond a threshold. Unusually large orders use the IQR method (Q3 + k x IQR), computed in SQL. I tested it by planting a spike and a drop and confirming both were caught. Because the generated data is uniform, real anomalies are rare, and I say that openly.

**Why put an API between the database and the dashboard?**
It separates concerns: the dashboard has no database credentials, other clients (like a different front end) can reuse the same endpoints, and validation of query parameters happens in one place.

**How did you handle performance?**
Indexes on join and filter columns, `ANALYZE` after load, Streamlit caching (60 seconds), and queries pushed into SQL rather than pulling raw rows into Pandas. The slowest query on the full dataset is [__], taking [__ seconds].

**What would you improve?**
Automated tests, Docker Compose, authentication on the API, scheduled report runs, and materialized views for the heaviest aggregations.

## Numbers to record from your full run

| Item | Your value |
|---|---|
| Orders / customers / products | 1,000,000 / 100,000 / 10,000 |
| Load time | |
| Total revenue | |
| Cancellation rate | |
| Slowest query and its time | |
| Dashboard filter response time | |
