-- ============================================================
-- INDEXES on foreign keys (speeds up joins / OLAP queries)
-- ============================================================
CREATE INDEX idx_riders_courier   ON Dim_Riders (courier_key);
CREATE INDEX idx_orders_user      ON Dim_Orders (user_key);
CREATE INDEX idx_orders_rider     ON Dim_Orders (rider_key);
CREATE INDEX idx_orders_date      ON Dim_Orders (date_key);
CREATE INDEX idx_items_order      ON Fact_OrderItems (order_key);
CREATE INDEX idx_items_product    ON Fact_OrderItems (product_key);
CREATE INDEX idx_items_date       ON Fact_OrderItems (date_key);