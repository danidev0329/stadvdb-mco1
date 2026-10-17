"""Tests for etl/mapping.py: row transforms and job/schema consistency (no database needed)."""
import re
from pathlib import Path

import pytest

from etl import mapping
from etl import transform as t

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "schema" / "001_create_warehouse.sql"


# ---- Dim_Users ------------------------------------------------------------
class TestUserRow:
    def test_happy_path(self):
        row = mapping._user_row({
            "id": 1, "username": "jdoe", "firstName": "John", "lastName": "Doe",
            "city": "manila", "country": "philippines", "gender": "F",
        }, {})
        assert row == {
            "user_id": 1, "username": "jdoe", "full_name": "John Doe",
            "city": "Manila", "country": "Philippines", "gender": "Female",
        }

    def test_missing_id_rejects(self):
        with pytest.raises(t.Reject):
            mapping._user_row({"id": None, "firstName": "A", "lastName": "B"}, {})


# ---- Dim_Riders -----------------------------------------------------------
class TestRiderRow:
    def test_resolves_courier_key(self):
        row = mapping._rider_row({
            "id": 5, "firstName": "Rye", "lastName": "Torres",
            "vehicleType": "Motorbike", "age": 40, "gender": "M", "courierId": 2,
        }, {"couriers": {2: 20}})
        assert row["rider_id"] == 5
        assert row["vehicle_type"] == "Motorcycle"
        assert row["age_group"] == "Middle"
        assert row["gender"] == "Male"
        assert row["courier_key"] == 20

    def test_unknown_courier_is_null(self):
        row = mapping._rider_row({
            "id": 6, "firstName": "A", "lastName": "B",
            "vehicleType": "Bike", "age": 22, "gender": "F", "courierId": 99,
        }, {"couriers": {2: 20}})
        assert row["courier_key"] is None


# ---- Dim_Orders -----------------------------------------------------------
class TestOrderRow:
    def test_happy_path(self):
        row = mapping._order_row({
            "id": 10, "orderNumber": "ABC", "userId": 1,
            "deliveryRiderId": 5, "deliveryDate": "06/25/2025",
        }, {"users": {1: 100}, "riders": {5: 500}})
        assert row == {
            "order_id": 10, "order_number": "ABC",
            "user_key": 100, "rider_key": 500, "date_key": 20250625,
        }

    def test_missing_rider_is_null(self):
        row = mapping._order_row({
            "id": 10, "orderNumber": "ABC", "userId": 1,
            "deliveryRiderId": None, "deliveryDate": "2025-05-24",
        }, {"users": {1: 100}, "riders": {}})
        assert row["rider_key"] is None

    def test_unknown_user_rejects(self):
        with pytest.raises(t.Reject):
            mapping._order_row({
                "id": 10, "orderNumber": "ABC", "userId": 999,
                "deliveryRiderId": None, "deliveryDate": "2025-05-24",
            }, {"users": {1: 100}, "riders": {}})

    def test_missing_date_rejects(self):
        with pytest.raises(t.Reject):
            mapping._order_row({
                "id": 10, "orderNumber": "ABC", "userId": 1,
                "deliveryRiderId": None, "deliveryDate": None,
            }, {"users": {1: 100}, "riders": {}})


# ---- Fact_OrderItems ------------------------------------------------------
class TestOrderItemRow:
    def test_resolves_keys_and_defaults(self):
        row = mapping._order_item_row({
            "OrderId": 10, "ProductId": 7, "deliveryDate": "2025-05-24",
            "notes": None, "quantity": 3,
        }, {"orders": {10: 1000}, "products": {7: 700}})
        assert row == {
            "order_key": 1000, "product_key": 700,
            "date_key": 20250524, "notes": None, "quantity": 3,
        }

    def test_null_quantity_defaults_zero(self):
        row = mapping._order_item_row({
            "OrderId": 10, "ProductId": 7, "deliveryDate": "2025-05-24",
            "notes": "ok", "quantity": None,
        }, {"orders": {10: 1000}, "products": {7: 700}})
        assert row["quantity"] == 0
        assert row["notes"] == "ok"

    def test_unknown_product_rejects(self):
        with pytest.raises(t.Reject):
            mapping._order_item_row({
                "OrderId": 10, "ProductId": 7, "deliveryDate": "2025-05-24",
                "notes": None, "quantity": 1,
            }, {"orders": {10: 1000}, "products": {}})


# ---- Job / schema consistency (regression: column + casing bugs) ----------
def _schema_columns() -> dict[str, list[str]]:
    sql = SCHEMA_SQL.read_text()
    out = {}
    for m in re.finditer(r"CREATE TABLE\s+(\w+)\s*\((.*?)\n\);", sql, re.S):
        table, body = m.group(1), m.group(2)
        cols = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.upper().startswith(("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN")):
                continue
            c = re.match(r"(\w+)\s+\w", stripped)
            if c:
                cols.append(c.group(1))
        out[table] = cols
    return out


class TestJobSchemaConsistency:
    def test_schema_parsed(self):
        cols = _schema_columns()
        assert "Dim_Date" in cols and "Fact_OrderItems" in cols

    def test_every_job_column_exists_in_target_table(self):
        cols = _schema_columns()
        for job in mapping.JOBS:
            assert job.target in cols, f"target table missing from schema: {job.target}"
            missing = [c for c in job.columns if c not in cols[job.target]]
            assert not missing, f"{job.name}: columns absent from {job.target}: {missing}"

    def test_dim_date_columns_exact(self):
        assert set(mapping.DIM_DATE.columns) == {
            "date_key", "full_date", "year", "quarter", "month",
            "month_name", "day_of_month", "day_of_week", "is_weekend",
        }

    def test_fact_is_last_and_dims_first(self):
        names = [j.target for j in mapping.JOBS]
        assert names[-1] == "Fact_OrderItems"
        assert names.count("Fact_OrderItems") == 1
