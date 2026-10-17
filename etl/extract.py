"""EXTRACT: stream rows from the source in chunks so memory stays flat on large tables."""
from itertools import islice
from typing import Iterable, Iterator
from etl import config
from etl.db import source

def stream(query: str, params=None, chunk_size: int | None = None) -> Iterator[list[dict]]:
    """Yield lists of row dicts. Uses a dedicated connection, closed when exhausted."""
    size = chunk_size or config.CHUNK_SIZE
    conn = source()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(query, params or ())
        while rows := cur.fetchmany(size):
            yield rows
    finally:
        cur.close()
        conn.close()

def chunked(rows: Iterable[dict], size: int | None = None) -> Iterator[list[dict]]:
    """Chunk any in-memory/generated iterable (e.g. the generated date dimension)."""
    size = size or config.CHUNK_SIZE
    it = iter(rows)
    while batch := list(islice(it, size)):
        yield batch
