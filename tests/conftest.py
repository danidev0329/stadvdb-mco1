"""Shared fixtures. DB-backed tests skip cleanly when MySQL / source data is unavailable."""
import pytest
import mysql.connector

from etl.db import source, warehouse


def _connect(conn_fn, label: str):
    try:
        return conn_fn()
    except mysql.connector.Error as e:
        pytest.skip(f"{label} unavailable: {e}")


@pytest.fixture(scope="session")
def source_conn():
    conn = _connect(source, "source_db")
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def warehouse_conn():
    conn = _connect(warehouse, "data_warehouse")
    yield conn
    conn.close()
