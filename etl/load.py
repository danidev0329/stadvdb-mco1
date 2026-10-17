"""LOAD: batched, idempotent upserts (re-running the ETL does not duplicate rows).
Requires a UNIQUE key on each dimension's natural/source key (e.g. UNIQUE(source_id))."""
from etl import config

def upsert(conn, table: str, columns: list[str], rows: list[dict], batch_size: int | None = None) -> int:
    if not rows:
        return 0
    size = batch_size or config.BATCH_SIZE
    cols = ", ".join(f"`{c}`" for c in columns)
    ph = ", ".join(["%s"] * len(columns))
    upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in columns)
    sql = f"INSERT INTO `{table}` ({cols}) VALUES ({ph}) ON DUPLICATE KEY UPDATE {upd}"
    cur = conn.cursor()
    try:
        for i in range(0, len(rows), size):
            cur.executemany(sql, [tuple(r[c] for c in columns) for r in rows[i:i + size]])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
    return len(rows)

def truncate(conn, table: str) -> None:
    """Full refresh helper. FK checks are disabled only for the TRUNCATE."""
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    cur.execute(f"TRUNCATE TABLE `{table}`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.commit()
    cur.close()

def key_map(conn, table: str, natural_col: str, surrogate_col: str) -> dict:
    """Load {natural_key: surrogate_key} into memory for fact-table lookups."""
    cur = conn.cursor()
    cur.execute(f"SELECT `{natural_col}`, `{surrogate_col}` FROM `{table}`")
    out = dict(cur.fetchall())
    cur.close()
    return out
