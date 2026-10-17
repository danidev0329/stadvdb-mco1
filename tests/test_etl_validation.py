"""ETL validation tests.

DB-backed checks (marked `db`) reconcile source_db against data_warehouse and
skip cleanly when the databases are not available. Structural checks run always.
"""
import logging

import pytest

from etl import validate
from etl.validate import RECONCILIATIONS, ZERO_CHECKS, run_checks


def _one(conn, sql):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return cur.fetchone()[0]
    finally:
        cur.close()


# ---- structural checks (no database) --------------------------------------
class TestCheckDefinitions:
    def test_lists_not_empty(self):
        assert RECONCILIATIONS
        assert ZERO_CHECKS

    def test_reconciliation_shape(self):
        for name, src_sql, dw_sql in RECONCILIATIONS:
            assert name
            assert src_sql.strip().upper().startswith("SELECT")
            assert dw_sql.strip().upper().startswith("SELECT")

    def test_zero_check_shape(self):
        for name, sql in ZERO_CHECKS:
            assert name
            assert sql.strip().upper().startswith("SELECT")


# ---- integration checks (need source_db + data_warehouse) -----------------
@pytest.mark.db
class TestReconciliation:
    def test_source_matches_warehouse(self, source_conn, warehouse_conn):
        for name, src_sql, dw_sql in RECONCILIATIONS:
            s = _one(source_conn, src_sql)
            w = _one(warehouse_conn, dw_sql)
            assert s == w, f"{name}: source={s} warehouse={w}"

    def test_total_quantity(self, source_conn, warehouse_conn):
        s = _one(source_conn, "SELECT COALESCE(SUM(quantity),0) FROM orderitems")
        w = _one(warehouse_conn, "SELECT COALESCE(SUM(quantity),0) FROM Fact_OrderItems")
        assert s == w


@pytest.mark.db
class TestZeroChecks:
    def test_all_zero(self, warehouse_conn):
        for name, sql in ZERO_CHECKS:
            assert _one(warehouse_conn, sql) == 0, name


@pytest.mark.db
def test_run_checks_passes(source_conn, warehouse_conn):
    assert run_checks(logging.getLogger("test")) is True
