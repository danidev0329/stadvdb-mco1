
from __future__ import annotations
from typing import Optional


def _fetchall(conn, sql: str, params: dict | None = None) -> list[dict]:
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or {})
    rows = cur.fetchall()
    cur.close()
    return rows


def _granularity_columns(granularity: str) -> str:
    levels = {
        "year":    "d.year",
        "quarter": "d.year, d.quarter",
        "month":   "d.year, d.quarter, d.month, d.month_name",
        "day":     "d.year, d.quarter, d.month, d.month_name, d.day_of_month",
    }
    return levels.get(granularity, levels["month"])



#ROLLUP 
def rollup(conn, *, granularity: str = "month",
           year: Optional[int] = None,
           courier: Optional[str] = None) -> list[dict]:
    
    gcols = _granularity_columns(granularity)

    where_clauses: list[str] = []
    params: dict = {}
    if year:
        where_clauses.append("d.year = %(year)s")
        params["year"] = year
    if courier:
        where_clauses.append("c.courier_name = %(courier)s")
        params["courier"] = courier

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT {gcols},
               SUM(f.quantity) AS total_qty,
               COUNT(*)        AS line_count
        FROM Fact_OrderItems f
        JOIN Dim_Date     d ON f.date_key    = d.date_key
        JOIN Dim_Orders   o ON f.order_key   = o.order_key
        JOIN Dim_Riders   r ON o.rider_key   = r.rider_key
        JOIN Dim_Couriers c ON r.courier_key = c.courier_key
        {where}
        GROUP BY {gcols} WITH ROLLUP
        ORDER BY {gcols}
    """
    return _fetchall(conn, sql, params)



#DRILLDOWN  

def drilldown(conn, *, year: int,
              quarter: Optional[int] = None,
              month: Optional[int] = None,
              courier: Optional[str] = None) -> list[dict]:
    where_parts = ["d.year = %(year)s"]
    params: dict = {"year": year}

    if month and quarter:
        # drill to day level
        where_parts.append("d.quarter = %(quarter)s")
        where_parts.append("d.month = %(month)s")
        params["quarter"] = quarter
        params["month"] = month
        group = "d.year, d.quarter, d.month, d.month_name, d.day_of_month"
    elif quarter:
        # drill to month level
        where_parts.append("d.quarter = %(quarter)s")
        params["quarter"] = quarter
        group = "d.year, d.quarter, d.month, d.month_name"
    else:
        # drill to quarter level
        group = "d.year, d.quarter"

    if courier:
        where_parts.append("c.courier_name = %(courier)s")
        params["courier"] = courier

    where = "WHERE " + " AND ".join(where_parts)

    sql = f"""
        SELECT {group},
               SUM(f.quantity)  AS total_qty,
               COUNT(*)         AS line_count
        FROM Fact_OrderItems f
        JOIN Dim_Date     d ON f.date_key    = d.date_key
        JOIN Dim_Orders   o ON f.order_key   = o.order_key
        JOIN Dim_Riders   r ON o.rider_key   = r.rider_key
        JOIN Dim_Couriers c ON r.courier_key = c.courier_key
        {where}
        GROUP BY {group}
        ORDER BY {group}
    """
    return _fetchall(conn, sql, params)



#SLICE 
def slice_query(conn, *, dimension: str, value,
                granularity: str = "month") -> list[dict]:
    """Fix a single dimension to *value* and aggregate by time.

    *dimension* may be: 'courier', 'gender', 'city', 'product', 'vehicle_type'.
    """
    dim_map = {
        "courier":      ("c.courier_name = %(val)s",
                         "JOIN Dim_Orders o ON f.order_key=o.order_key "
                         "JOIN Dim_Riders r ON o.rider_key=r.rider_key "
                         "JOIN Dim_Couriers c ON r.courier_key=c.courier_key"),
        "gender":       ("u.gender = %(val)s",
                         "JOIN Dim_Orders o ON f.order_key=o.order_key "
                         "JOIN Dim_Users u ON o.user_key=u.user_key"),
        "city":         ("u.city = %(val)s",
                         "JOIN Dim_Orders o ON f.order_key=o.order_key "
                         "JOIN Dim_Users u ON o.user_key=u.user_key"),
        "product":      ("p.product_name = %(val)s",
                         "JOIN Dim_Products p ON f.product_key=p.product_key"),
        "vehicle_type": ("r.vehicle_type = %(val)s",
                         "JOIN Dim_Orders o ON f.order_key=o.order_key "
                         "JOIN Dim_Riders r ON o.rider_key=r.rider_key"),
    }
    if dimension not in dim_map:
        raise ValueError(f"unsupported slice dimension: {dimension!r}")

    cond, joins = dim_map[dimension]
    gcols = _granularity_columns(granularity)

    sql = f"""
        SELECT {gcols},
               SUM(f.quantity) AS total_qty,
               COUNT(*)        AS line_count
        FROM Fact_OrderItems f
        JOIN Dim_Date d ON f.date_key = d.date_key
        {joins}
        WHERE {cond}
        GROUP BY {gcols}
        ORDER BY {gcols}
    """
    return _fetchall(conn, sql, {"val": value})



#DICE  
def dice_query(conn, *,
               year_start: Optional[int] = None,
               year_end: Optional[int] = None,
               courier: Optional[str] = None,
               gender: Optional[str] = None,
               city: Optional[str] = None,
               vehicle_type: Optional[str] = None,
               granularity: str = "month") -> list[dict]:
    joins: list[str] = [
        "JOIN Dim_Date     d ON f.date_key    = d.date_key",
        "JOIN Dim_Orders   o ON f.order_key   = o.order_key",
    ]
    where_parts: list[str] = []
    params: dict = {}

    # date range
    if year_start:
        where_parts.append("d.year >= %(year_start)s")
        params["year_start"] = year_start
    if year_end:
        where_parts.append("d.year <= %(year_end)s")
        params["year_end"] = year_end

    # courier
    if courier:
        joins.append("JOIN Dim_Riders   r ON o.rider_key   = r.rider_key")
        joins.append("JOIN Dim_Couriers c ON r.courier_key = c.courier_key")
        where_parts.append("c.courier_name = %(courier)s")
        params["courier"] = courier

    # gender (user gender)
    if gender:
        if "JOIN Dim_Users" not in " ".join(joins):
            joins.append("JOIN Dim_Users u ON o.user_key = u.user_key")
        where_parts.append("u.gender = %(gender)s")
        params["gender"] = gender

    # city
    if city:
        if "JOIN Dim_Users" not in " ".join(joins):
            joins.append("JOIN Dim_Users u ON o.user_key = u.user_key")
        where_parts.append("u.city = %(city)s")
        params["city"] = city

    # vehicle type
    if vehicle_type:
        if "JOIN Dim_Riders" not in " ".join(joins):
            joins.append("JOIN Dim_Riders r ON o.rider_key = r.rider_key")
        where_parts.append("r.vehicle_type = %(vehicle_type)s")
        params["vehicle_type"] = vehicle_type

    gcols = _granularity_columns(granularity)
    join_block = "\n        ".join(joins)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT {gcols},
               SUM(f.quantity) AS total_qty,
               COUNT(*)        AS line_count
        FROM Fact_OrderItems f
        {join_block}
        {where}
        GROUP BY {gcols}
        ORDER BY {gcols}
    """
    return _fetchall(conn, sql, params)



#PIVOT
def pivot(conn, *, granularity: str = "year",
          year_start: Optional[int] = None,
          year_end: Optional[int] = None) -> list[dict]:
   
    couriers = _fetchall(conn, "SELECT courier_name FROM Dim_Couriers ORDER BY courier_key")
    if not couriers:
        return []

    cases = []
    for c in couriers:
        name = c["courier_name"]
        alias = name.replace(" ", "_").replace("-", "_").lower()
        cases.append(
            f"SUM(CASE WHEN c.courier_name = '{name}' THEN f.quantity ELSE 0 END) AS `{name}`"
        )
    case_block = ",\n               ".join(cases)

    gcols = _granularity_columns(granularity)
    where_parts: list[str] = []
    params: dict = {}
    if year_start:
        where_parts.append("d.year >= %(year_start)s")
        params["year_start"] = year_start
    if year_end:
        where_parts.append("d.year <= %(year_end)s")
        params["year_end"] = year_end
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sql = f"""
        SELECT {gcols},
               {case_block},
               SUM(f.quantity) AS grand_total
        FROM Fact_OrderItems f
        JOIN Dim_Date     d ON f.date_key    = d.date_key
        JOIN Dim_Orders   o ON f.order_key   = o.order_key
        JOIN Dim_Riders   r ON o.rider_key   = r.rider_key
        JOIN Dim_Couriers c ON r.courier_key = c.courier_key
        {where}
        GROUP BY {gcols}
        ORDER BY {gcols}
    """
    return _fetchall(conn, sql, params)




def distinct_values(conn, column: str) -> list:

    col_map = {
        "year":         "SELECT DISTINCT year         AS v FROM Dim_Date     ORDER BY v",
        "quarter":      "SELECT DISTINCT quarter      AS v FROM Dim_Date     ORDER BY v",
        "courier":      "SELECT DISTINCT courier_name AS v FROM Dim_Couriers ORDER BY v",
        "gender":       "SELECT DISTINCT gender       AS v FROM Dim_Users    WHERE gender IS NOT NULL ORDER BY v",
        "city":         "SELECT DISTINCT city         AS v FROM Dim_Users    WHERE city IS NOT NULL ORDER BY v",
        "country":      "SELECT DISTINCT country      AS v FROM Dim_Users    WHERE country IS NOT NULL ORDER BY v",
        "vehicle_type": "SELECT DISTINCT vehicle_type AS v FROM Dim_Riders   WHERE vehicle_type IS NOT NULL ORDER BY v",
        "product":      "SELECT DISTINCT product_name AS v FROM Dim_Products WHERE product_name IS NOT NULL ORDER BY v",
    }
    if column not in col_map:
        raise ValueError(f"unknown dimension: {column!r}")
    rows = _fetchall(conn, col_map[column])
    return [r["v"] for r in rows]
