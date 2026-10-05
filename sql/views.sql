-- Analytical views for CommerceIQ (safe to re-run)

DROP VIEW IF EXISTS v_kpi_summary          CASCADE;
DROP VIEW IF EXISTS v_monthly_revenue      CASCADE;
DROP VIEW IF EXISTS v_daily_revenue        CASCADE;
DROP VIEW IF EXISTS v_top_products         CASCADE;
DROP VIEW IF EXISTS v_category_performance CASCADE;
DROP VIEW IF EXISTS v_region_revenue       CASCADE;
DROP VIEW IF EXISTS v_store_performance    CASCADE;
DROP VIEW IF EXISTS v_top_customers        CASCADE;
DROP VIEW IF EXISTS v_customer_segments    CASCADE;
DROP VIEW IF EXISTS v_order_status         CASCADE;
DROP VIEW IF EXISTS v_payment_methods      CASCADE;
DROP VIEW IF EXISTS v_monthly_growth       CASCADE;

-- 1. Headline KPIs
CREATE VIEW v_kpi_summary AS
SELECT
    COALESCE(SUM(total_amount) FILTER (WHERE status = 'COMPLETED'), 0)   AS total_revenue,
    COUNT(*)                                                             AS total_orders,
    COUNT(*) FILTER (WHERE status = 'COMPLETED')                         AS completed_orders,
    COUNT(DISTINCT customer_id) FILTER (WHERE status = 'COMPLETED')      AS active_customers,
    ROUND(AVG(total_amount) FILTER (WHERE status = 'COMPLETED'), 2)      AS avg_order_value,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'CANCELLED') / COUNT(*), 2)
                                                                         AS cancellation_rate_pct
FROM orders;

-- 2. Revenue by month
CREATE VIEW v_monthly_revenue AS
SELECT
    DATE_TRUNC('month', order_date)::date AS month,
    SUM(total_amount)                     AS revenue,
    COUNT(*)                              AS orders,
    ROUND(AVG(total_amount), 2)           AS avg_order_value
FROM orders
WHERE status = 'COMPLETED'
GROUP BY 1;

-- 3. Revenue by day
CREATE VIEW v_daily_revenue AS
SELECT
    order_date,
    SUM(total_amount) AS revenue,
    COUNT(*)          AS orders
FROM orders
WHERE status = 'COMPLETED'
GROUP BY order_date;

-- 4. Product performance
CREATE VIEW v_top_products AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(oi.quantity)                                  AS units_sold,
    SUM(oi.quantity * oi.unit_price)                  AS revenue,
    SUM(oi.quantity * (oi.unit_price - p.cost))       AS profit
FROM order_items oi
JOIN orders   o ON o.order_id   = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'COMPLETED'
GROUP BY p.product_id, p.product_name, p.category;

-- 5. Category performance with margin
CREATE VIEW v_category_performance AS
SELECT
    p.category,
    SUM(oi.quantity)                              AS units_sold,
    SUM(oi.quantity * oi.unit_price)              AS revenue,
    SUM(oi.quantity * (oi.unit_price - p.cost))   AS profit,
    ROUND(100.0 * SUM(oi.quantity * (oi.unit_price - p.cost))
          / NULLIF(SUM(oi.quantity * oi.unit_price), 0), 2) AS margin_pct
FROM order_items oi
JOIN orders   o ON o.order_id   = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'COMPLETED'
GROUP BY p.category;

-- 6. Revenue by region
CREATE VIEW v_region_revenue AS
SELECT
    r.region_name,
    SUM(o.total_amount)                                        AS revenue,
    COUNT(*)                                                   AS orders,
    ROUND(100.0 * SUM(o.total_amount) / SUM(SUM(o.total_amount)) OVER (), 2)
                                                               AS pct_of_revenue
FROM orders o
JOIN stores  s ON s.store_id  = o.store_id
JOIN regions r ON r.region_id = s.region_id
WHERE o.status = 'COMPLETED'
GROUP BY r.region_name;

-- 7. Store performance
CREATE VIEW v_store_performance AS
SELECT
    s.store_id,
    s.store_name,
    r.region_name,
    SUM(o.total_amount)         AS revenue,
    COUNT(*)                    AS orders,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
JOIN stores  s ON s.store_id  = o.store_id
JOIN regions r ON r.region_id = s.region_id
WHERE o.status = 'COMPLETED'
GROUP BY s.store_id, s.store_name, r.region_name;

-- 8. Customer lifetime value
CREATE VIEW v_top_customers AS
SELECT
    c.customer_id,
    c.customer_name,
    c.city,
    c.state,
    COUNT(*)            AS orders,
    SUM(o.total_amount) AS lifetime_value,
    MAX(o.order_date)   AS last_order_date
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status = 'COMPLETED'
GROUP BY c.customer_id, c.customer_name, c.city, c.state;

-- 9. Customer segments
CREATE VIEW v_customer_segments AS
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS orders, SUM(total_amount) AS spend
    FROM orders
    WHERE status = 'COMPLETED'
    GROUP BY customer_id
)
SELECT
    CASE
        WHEN orders >= 20 THEN 'Loyal (20+ orders)'
        WHEN orders >= 10 THEN 'Regular (10-19 orders)'
        WHEN orders >= 5  THEN 'Occasional (5-9 orders)'
        ELSE 'New / Light (1-4 orders)'
    END                 AS segment,
    COUNT(*)            AS customers,
    SUM(spend)          AS revenue,
    ROUND(AVG(spend), 2) AS avg_spend_per_customer
FROM per_customer
GROUP BY 1;

-- 10. Order status breakdown
CREATE VIEW v_order_status AS
SELECT
    status,
    COUNT(*)                                            AS orders,
    SUM(total_amount)                                   AS order_value,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct_of_orders
FROM orders
GROUP BY status;

-- 11. Payment methods (paid only)
CREATE VIEW v_payment_methods AS
SELECT
    payment_method,
    COUNT(*)                                            AS payments,
    SUM(amount)                                         AS amount,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct_of_payments
FROM payments
WHERE payment_status = 'PAID'
GROUP BY payment_method;

-- 12. Month-over-month growth
CREATE VIEW v_monthly_growth AS
WITH m AS (
    SELECT DATE_TRUNC('month', order_date)::date AS month,
           SUM(total_amount) AS revenue
    FROM orders
    WHERE status = 'COMPLETED'
    GROUP BY 1
)
SELECT
    month,
    revenue,
    LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
          / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS growth_pct
FROM m;
