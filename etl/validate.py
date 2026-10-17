"""Post-load validation: this is the evidence for 'ETL data validation' in the report."""
from etl.db import source, warehouse

def scalar(conn_fn, sql):
    c = conn_fn(); cur = c.cursor(); cur.execute(sql); v = cur.fetchone()[0]
    cur.close(); c.close()
    return v

# (name, source_sql, warehouse_sql): both must return ONE number; they must match.
# Row counts and SUM() of key measures are the classic reconciliations.
RECONCILIATIONS: list[tuple[str, str, str]] = [
    ("user count",     "SELECT COUNT(DISTINCT id) FROM users",        "SELECT COUNT(*) FROM Dim_Users"),
    ("product count",  "SELECT COUNT(DISTINCT id) FROM products",     "SELECT COUNT(*) FROM Dim_Products"),
    ("courier count",  "SELECT COUNT(DISTINCT id) FROM couriers",     "SELECT COUNT(*) FROM Dim_Couriers"),
    ("rider count",    "SELECT COUNT(DISTINCT id) FROM riders",       "SELECT COUNT(*) FROM Dim_Riders"),
    ("order count",    "SELECT COUNT(DISTINCT id) FROM orders",       "SELECT COUNT(*) FROM Dim_Orders"),
    ("order item count", "SELECT COUNT(*) FROM orderitems",           "SELECT COUNT(*) FROM Fact_OrderItems"),
    ("total quantity", "SELECT COALESCE(SUM(quantity),0) FROM orderitems", "SELECT COALESCE(SUM(quantity),0) FROM Fact_OrderItems"),
]

# (name, sql returning a count that must be 0)
ZERO_CHECKS: list[tuple[str, str]] = [
    ("orphan fact->order",   "SELECT COUNT(*) FROM Fact_OrderItems f LEFT JOIN Dim_Orders d ON f.order_key=d.order_key WHERE d.order_key IS NULL"),
    ("orphan fact->product", "SELECT COUNT(*) FROM Fact_OrderItems f LEFT JOIN Dim_Products d ON f.product_key=d.product_key WHERE d.product_key IS NULL"),
    ("orphan fact->date",    "SELECT COUNT(*) FROM Fact_OrderItems f LEFT JOIN Dim_Date d ON f.date_key=d.date_key WHERE d.date_key IS NULL"),
    ("orphan order->user",   "SELECT COUNT(*) FROM Dim_Orders o LEFT JOIN Dim_Users u ON o.user_key=u.user_key WHERE u.user_key IS NULL"),
    ("orphan order->date",   "SELECT COUNT(*) FROM Dim_Orders o LEFT JOIN Dim_Date d ON o.date_key=d.date_key WHERE d.date_key IS NULL"),
    ("orphan rider->courier","SELECT COUNT(*) FROM Dim_Riders r LEFT JOIN Dim_Couriers c ON r.courier_key=c.courier_key WHERE r.courier_key IS NOT NULL AND c.courier_key IS NULL"),
    ("null fact quantity",   "SELECT COUNT(*) FROM Fact_OrderItems WHERE quantity IS NULL"),
    ("null order user_key",  "SELECT COUNT(*) FROM Dim_Orders WHERE user_key IS NULL"),
]

def run_checks(log) -> bool:
    ok = True
    for name, src_sql, dw_sql in RECONCILIATIONS:
        s, w = scalar(source, src_sql), scalar(warehouse, dw_sql)
        passed = s == w
        ok &= passed
        log.info("[%s] reconcile %s: source=%s warehouse=%s", "PASS" if passed else "FAIL", name, s, w)
    for name, sql in ZERO_CHECKS:
        n = scalar(warehouse, sql)
        ok &= n == 0
        log.info("[%s] %s: %s", "PASS" if n == 0 else "FAIL", name, n)
    if not (RECONCILIATIONS or ZERO_CHECKS):
        log.warning("no validation checks defined yet (etl/validate.py)")
    return ok
