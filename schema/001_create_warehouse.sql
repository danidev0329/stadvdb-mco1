-- ============================================================
-- data_warehouse.sql
-- Star schema based on MCO1-Schema.pdf
-- Dialect: MySQL 8+
-- ============================================================

DROP DATABASE IF EXISTS data_warehouse;
CREATE DATABASE data_warehouse;
USE data_warehouse;

-- ------------------------------------------------------------
-- Drop tables (children first) so the script can be re-run
-- ------------------------------------------------------------
DROP TABLE IF EXISTS Fact_OrderItems;
DROP TABLE IF EXISTS Dim_Orders;
DROP TABLE IF EXISTS Dim_Riders;
DROP TABLE IF EXISTS Dim_Couriers;
DROP TABLE IF EXISTS Dim_Products;
DROP TABLE IF EXISTS Dim_Users;
DROP TABLE IF EXISTS Dim_Date;

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

-- ------------------------------------------------------------
-- Dim_Date
-- date_key uses the YYYYMMDD convention (e.g. 20240131)
-- ------------------------------------------------------------
CREATE TABLE Dim_Date (
    date_key      INT          NOT NULL,
    full_date     DATE         NOT NULL,
    year          INT          NOT NULL,
    quarter       INT          NOT NULL,
    month         INT          NOT NULL,
    month_name    VARCHAR(20)  NOT NULL,
    day_of_month  INT          NOT NULL,
    day_of_week   VARCHAR(20)  NOT NULL,
    is_weekend    BOOLEAN      NOT NULL,
    CONSTRAINT pk_dim_date PRIMARY KEY (date_key),
    CONSTRAINT uq_dim_date_full_date UNIQUE (full_date)
);

-- ------------------------------------------------------------
-- Dim_Users
-- ------------------------------------------------------------
CREATE TABLE Dim_Users (
    user_key   INT           NOT NULL AUTO_INCREMENT,
    user_id    INT           NOT NULL,   -- natural/business key from source
    username   VARCHAR(100),
    full_name  VARCHAR(150),
    city       VARCHAR(100),
    country    VARCHAR(100),
    gender     VARCHAR(20),
    CONSTRAINT pk_dim_users PRIMARY KEY (user_key),
    CONSTRAINT uq_dim_users_user_id UNIQUE (user_id)
);

-- ------------------------------------------------------------
-- Dim_Products
-- ------------------------------------------------------------
CREATE TABLE Dim_Products (
    product_key   INT           NOT NULL AUTO_INCREMENT,
    product_id    INT           NOT NULL,   -- natural/business key from source
    product_name  VARCHAR(255),
    CONSTRAINT pk_dim_products PRIMARY KEY (product_key),
    CONSTRAINT uq_dim_products_product_id UNIQUE (product_id)
);

-- ------------------------------------------------------------
-- Dim_Couriers
-- ------------------------------------------------------------
CREATE TABLE Dim_Couriers (
    courier_key   INT           NOT NULL AUTO_INCREMENT,
    courier_id    INT           NOT NULL,   -- natural/business key from source
    courier_name  VARCHAR(150),
    CONSTRAINT pk_dim_couriers PRIMARY KEY (courier_key),
    CONSTRAINT uq_dim_couriers_courier_id UNIQUE (courier_id)
);

-- ------------------------------------------------------------
-- Dim_Riders  (each rider belongs to a courier)
-- ------------------------------------------------------------
CREATE TABLE Dim_Riders (
    rider_key     INT           NOT NULL AUTO_INCREMENT,
    rider_id      INT           NOT NULL,   -- natural/business key from source
    first_name    VARCHAR(100),
    last_name     VARCHAR(100),
    vehicle_type  VARCHAR(50),
    age_group     VARCHAR(50),
    gender        VARCHAR(20),
    courier_key   INT,
    CONSTRAINT pk_dim_riders PRIMARY KEY (rider_key),
    CONSTRAINT uq_dim_riders_rider_id UNIQUE (rider_id),
    CONSTRAINT fk_riders_courier
        FOREIGN KEY (courier_key) REFERENCES Dim_Couriers (courier_key)
);

-- ------------------------------------------------------------
-- Dim_Orders  (order header; links user, rider and date)
-- ------------------------------------------------------------
CREATE TABLE Dim_Orders (
    order_key     INT           NOT NULL AUTO_INCREMENT,
    order_id      INT           NOT NULL,   -- natural/business key from source
    order_number  VARCHAR(50),
    user_key      INT           NOT NULL,
    rider_key     INT,
    date_key      INT           NOT NULL,
    CONSTRAINT pk_dim_orders PRIMARY KEY (order_key),
    CONSTRAINT uq_dim_orders_order_id UNIQUE (order_id),
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_key)  REFERENCES Dim_Users (user_key),
    CONSTRAINT fk_orders_rider
        FOREIGN KEY (rider_key) REFERENCES Dim_Riders (rider_key),
    CONSTRAINT fk_orders_date
        FOREIGN KEY (date_key)  REFERENCES Dim_Date (date_key)
);

-- ============================================================
-- FACT TABLE
-- ============================================================

-- ------------------------------------------------------------
-- Fact_OrderItems  (grain: one row per product line in an order)
-- ------------------------------------------------------------
CREATE TABLE Fact_OrderItems (
    order_item_key  INT           NOT NULL AUTO_INCREMENT,
    order_key       INT           NOT NULL,
    product_key     INT           NOT NULL,
    date_key        INT           NOT NULL,
    notes           VARCHAR(500),
    quantity        INT           NOT NULL,
    CONSTRAINT pk_fact_orderitems PRIMARY KEY (order_item_key),
    CONSTRAINT fk_items_order
        FOREIGN KEY (order_key)   REFERENCES Dim_Orders (order_key),
    CONSTRAINT fk_items_product
        FOREIGN KEY (product_key) REFERENCES Dim_Products (product_key),
    CONSTRAINT fk_items_date
        FOREIGN KEY (date_key)    REFERENCES Dim_Date (date_key)
);

-- ============================================================
-- NOTES
-- * Relationships (all one-to-many):
--     Dim_Date     -> Dim_Orders, Fact_OrderItems
--     Dim_Users    -> Dim_Orders
--     Dim_Riders   -> Dim_Orders
--     Dim_Couriers -> Dim_Riders
--     Dim_Orders   -> Fact_OrderItems
--     Dim_Products -> Fact_OrderItems
-- * For SQL Server: use "INT IDENTITY(1,1)" and BIT instead of BOOLEAN.
-- ============================================================