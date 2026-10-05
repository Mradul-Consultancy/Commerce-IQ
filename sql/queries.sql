-- name: total_revenue
SELECT
    SUM(total_amount) AS total_revenue,
    COUNT(*)          AS completed_orders
FROM orders
WHERE status = 'COMPLETED';

-- name: revenue_by_month
SELECT
    DATE_TRUNC('month', order_date)::date AS month,
    SUM(total_amount)                     AS revenue,
    COUNT(*)                              AS orders
FROM orders
WHERE status = 'COMPLETED'
GROUP BY 1
ORDER BY 1;

-- name: top_products_by_units
SELECT
    p.product_name,
    p.category,
    SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN orders   o ON o.order_id   = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'COMPLETED'
GROUP BY p.product_name, p.category
ORDER BY units_sold DESC
LIMIT 10;

-- name: revenue_by_region
SELECT
    r.region_name,
    SUM(o.total_amount) AS revenue,
    COUNT(*)            AS orders
FROM orders o
JOIN stores  s ON s.store_id  = o.store_id
JOIN regions r ON r.region_id = s.region_id
WHERE o.status = 'COMPLETED'
GROUP BY r.region_name
ORDER BY revenue DESC;

-- name: top_customers
SELECT
    c.customer_id,
    c.customer_name,
    c.city,
    COUNT(*)            AS orders,
    SUM(o.total_amount) AS lifetime_value
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status = 'COMPLETED'
GROUP BY c.customer_id, c.customer_name, c.city
ORDER BY lifetime_value DESC
LIMIT 10;

-- name: order_status_breakdown
SELECT
    status,
    COUNT(*) AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_orders
FROM orders
GROUP BY status
ORDER BY orders DESC;

-- name: cancellation_rate
SELECT
    COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled_orders,
    COUNT(*)                                     AS total_orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'CANCELLED') / COUNT(*), 2)
                                                 AS cancellation_rate_pct
FROM orders;

-- name: average_order_value
SELECT
    ROUND(AVG(total_amount), 2) AS avg_order_value
FROM orders
WHERE status = 'COMPLETED';
