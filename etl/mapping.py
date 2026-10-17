"""Source -> warehouse mapping. THE file to edit when the schema changes.
JOBS run in order: dimensions first, then facts (FK dependencies)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from etl import config, extract, load, transform as t

@dataclass
class Job:
    name: str
    target: str                                   # warehouse table
    columns: list[str]                            # target columns, in the order produced by transform
    extract: Callable[[], Iterable[list[dict]]]   # returns chunks of source row dicts
    transform: Callable[[dict, dict], Optional[dict]]  # (row, ctx) -> target row | None (skip); raise Reject to reject
    prepare: Optional[Callable] = None            # (warehouse_conn) -> ctx dict (e.g. surrogate key maps)


def _req_int(v, what: str) -> int:
    """Required integer key: null -> Reject (used for NOT NULL business keys)."""
    n = t.to_int(v)
    if n is None:
        raise t.Reject(f"missing {what}")
    return n


# ---- dim_date: generated, no source needed (columns must match schema/001 Dim_Date) ----
DIM_DATE = Job(
    name="dim_date",
    target="Dim_Date",
    columns=["date_key", "full_date", "year", "quarter", "month",
             "month_name", "day_of_month", "day_of_week", "is_weekend"],
    extract=lambda: extract.chunked(t.generate_dates(config.DATE_START, config.DATE_END)),
    transform=lambda row, ctx: row,
)


# ---- Dim_Users ------------------------------------------------------------
def _user_row(r, ctx):
    return {
        "user_id": _req_int(r["id"], "id"),
        "username": t.clean_text(r["username"], default=None, max_len=100),
        "full_name": t.merge_name(r["firstName"], r["lastName"]),
        "city": t.clean_text(r["city"], title=True, max_len=100),
        "country": t.clean_text(r["country"], title=True, max_len=100),
        "gender": t.standardize_gender(r["gender"]),
    }

DIM_USERS = Job(
    name="dim_users",
    target="Dim_Users",
    columns=["user_id", "username", "full_name", "city", "country", "gender"],
    extract=lambda: extract.stream(
        "SELECT id, username, firstName, lastName, city, country, gender FROM users"),
    transform=_user_row,
)


# ---- Dim_Products ---------------------------------------------------------
def _product_row(r, ctx):
    return {
        "product_id": _req_int(r["id"], "id"),
        "product_name": t.clean_text(r["name"], max_len=255),
    }

DIM_PRODUCTS = Job(
    name="dim_products",
    target="Dim_Products",
    columns=["product_id", "product_name"],
    extract=lambda: extract.stream("SELECT id, name FROM products"),
    transform=_product_row,
)


# ---- Dim_Couriers ---------------------------------------------------------
def _courier_row(r, ctx):
    return {
        "courier_id": _req_int(r["id"], "id"),
        "courier_name": t.clean_text(r["name"], max_len=150),
    }

DIM_COURIERS = Job(
    name="dim_couriers",
    target="Dim_Couriers",
    columns=["courier_id", "courier_name"],
    extract=lambda: extract.stream("SELECT id, name FROM couriers"),
    transform=_courier_row,
)


# ---- Dim_Riders (resolves courier surrogate key) --------------------------
def _rider_row(r, ctx):
    return {
        "rider_id": _req_int(r["id"], "id"),
        "first_name": t.clean_text(r["firstName"], default=None, max_len=100),
        "last_name": t.clean_text(r["lastName"], default=None, max_len=100),
        "vehicle_type": t.standardize_vehicle(r["vehicleType"]),
        "age_group": t.age_group(r["age"]),
        "gender": t.standardize_gender(r["gender"]),
        "courier_key": ctx["couriers"].get(t.to_int(r["courierId"])),
    }

DIM_RIDERS = Job(
    name="dim_riders",
    target="Dim_Riders",
    columns=["rider_id", "first_name", "last_name", "vehicle_type",
             "age_group", "gender", "courier_key"],
    extract=lambda: extract.stream(
        "SELECT id, firstName, lastName, vehicleType, age, gender, courierId FROM riders"),
    prepare=lambda conn: {"couriers": load.key_map(conn, "Dim_Couriers", "courier_id", "courier_key")},
    transform=_rider_row,
)


# ---- Dim_Orders (resolves user + rider surrogate keys and delivery date) --
def _order_row(r, ctx):
    d = t.parse_date(r["deliveryDate"])
    if d is None:
        raise t.Reject("missing delivery date")
    user_key = ctx["users"].get(t.to_int(r["userId"]))
    if user_key is None:
        raise t.Reject(f"unknown user {r['userId']!r}")
    return {
        "order_id": _req_int(r["id"], "id"),
        "order_number": t.clean_text(r["orderNumber"], default=None, max_len=50),
        "user_key": user_key,
        "rider_key": ctx["riders"].get(t.to_int(r["deliveryRiderId"])),
        "date_key": t.date_row(d)["date_key"],
    }

DIM_ORDERS = Job(
    name="dim_orders",
    target="Dim_Orders",
    columns=["order_id", "order_number", "user_key", "rider_key", "date_key"],
    extract=lambda: extract.stream(
        "SELECT id, orderNumber, userId, deliveryRiderId, deliveryDate FROM orders"),
    prepare=lambda conn: {
        "users": load.key_map(conn, "Dim_Users", "user_id", "user_key"),
        "riders": load.key_map(conn, "Dim_Riders", "rider_id", "rider_key"),
    },
    transform=_order_row,
)


# ---- Fact_OrderItems (grain: one product line per order) ------------------
def _order_item_row(r, ctx):
    order_key = ctx["orders"].get(t.to_int(r["OrderId"]))
    product_key = ctx["products"].get(t.to_int(r["ProductId"]))
    if order_key is None or product_key is None:
        raise t.Reject("unknown order/product")
    d = t.parse_date(r["deliveryDate"])
    if d is None:
        raise t.Reject("missing delivery date")
    return {
        "order_key": order_key,
        "product_key": product_key,
        "date_key": t.date_row(d)["date_key"],
        "notes": t.clean_text(r["notes"], default=None, max_len=500),
        "quantity": t.to_int(r["quantity"], 0),
    }

FACT_ORDER_ITEMS = Job(
    name="fact_order_items",
    target="Fact_OrderItems",
    columns=["order_key", "product_key", "date_key", "notes", "quantity"],
    extract=lambda: extract.stream(
        "SELECT oi.OrderId, oi.ProductId, oi.quantity, oi.notes, o.deliveryDate "
        "FROM orderitems oi JOIN orders o ON o.id = oi.OrderId"),
    prepare=lambda conn: {
        "orders": load.key_map(conn, "Dim_Orders", "order_id", "order_key"),
        "products": load.key_map(conn, "Dim_Products", "product_id", "product_key"),
    },
    transform=_order_item_row,
)


JOBS: list[Job] = [
    DIM_DATE,
    DIM_USERS,
    DIM_PRODUCTS,
    DIM_COURIERS,
    DIM_RIDERS,
    DIM_ORDERS,
    FACT_ORDER_ITEMS,
]
