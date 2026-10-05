-- Run against the commerceiq database

DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS stores CASCADE;
DROP TABLE IF EXISTS regions CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE regions (
    region_id    SERIAL PRIMARY KEY,
    region_name  VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE customers (
    customer_id        INTEGER PRIMARY KEY,
    customer_name      VARCHAR(120) NOT NULL,
    email              VARCHAR(150),
    city               VARCHAR(80),
    state              VARCHAR(80),
    registration_date  DATE NOT NULL
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  VARCHAR(150) NOT NULL,
    category      VARCHAR(60) NOT NULL,
    price         NUMERIC(10,2) NOT NULL,
    cost          NUMERIC(10,2) NOT NULL
);

CREATE TABLE stores (
    store_id    INTEGER PRIMARY KEY,
    store_name  VARCHAR(100) NOT NULL,
    city        VARCHAR(80),
    region_id   INTEGER NOT NULL REFERENCES regions(region_id)
);

CREATE TABLE orders (
    order_id      BIGINT PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    store_id      INTEGER NOT NULL REFERENCES stores(store_id),
    order_date    DATE NOT NULL,
    status        VARCHAR(20) NOT NULL,
    total_amount  NUMERIC(12,2) NOT NULL
);

CREATE TABLE order_items (
    order_item_id  BIGINT PRIMARY KEY,
    order_id       BIGINT NOT NULL REFERENCES orders(order_id),
    product_id     INTEGER NOT NULL REFERENCES products(product_id),
    quantity       INTEGER NOT NULL,
    unit_price     NUMERIC(10,2) NOT NULL
);

CREATE TABLE payments (
    payment_id      BIGINT PRIMARY KEY,
    order_id        BIGINT NOT NULL REFERENCES orders(order_id),
    payment_method  VARCHAR(30) NOT NULL,
    payment_status  VARCHAR(20) NOT NULL,
    amount          NUMERIC(12,2) NOT NULL
);

CREATE INDEX idx_orders_customer   ON orders(customer_id);
CREATE INDEX idx_orders_store      ON orders(store_id);
CREATE INDEX idx_orders_date       ON orders(order_date);
CREATE INDEX idx_orders_status     ON orders(status);
CREATE INDEX idx_items_order       ON order_items(order_id);
CREATE INDEX idx_items_product     ON order_items(product_id);
CREATE INDEX idx_payments_order    ON payments(order_id);
