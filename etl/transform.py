"""TRANSFORM: one small, pure, unit-tested function per rule.
For the report (Section 3), keep a one-line 'why' in each docstring."""
from __future__ import annotations
import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterator

class Reject(Exception):
    """Raise inside a transform to send the row to the reject log with a reason."""

NULL_TOKENS = {"", "na", "n/a", "null", "none", "nan", "-"}

def is_null(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in NULL_TOKENS)

def clean_text(v, default="Unknown", title=False, max_len=None) -> str:
    """Trim, collapse whitespace, map null-like tokens to a default (avoids NULL dimension attributes)."""
    if is_null(v):
        return default
    s = re.sub(r"\s+", " ", str(v)).strip()
    if title:
        s = s.title()
    return s[:max_len] if max_len else s

def to_int(v, default=None):
    """Cast to int; null-like -> default; garbage/inf -> Reject."""
    if is_null(v):
        return default
    try:
        f = float(str(v).replace(",", ""))
    except ValueError:
        raise Reject(f"not an integer: {v!r}")
    if not math.isfinite(f):
        raise Reject(f"not an integer: {v!r}")
    return int(f)

def to_decimal(v, places=2, default=None):
    """Cast money/measure strings ('$1,234.5') to Decimal with fixed scale."""
    if is_null(v):
        return default
    try:
        d = Decimal(str(v).replace(",", "").replace("$", "").strip())
        if not d.is_finite():
            raise InvalidOperation
        return d.quantize(Decimal(1).scaleb(-places))
    except (InvalidOperation, ValueError):
        raise Reject(f"not a number: {v!r}")

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y")

def parse_date(v, formats=DATE_FORMATS) -> date | None:
    """Normalise assorted date formats to date; null-like -> None; unparseable -> Reject."""
    if is_null(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for f in formats:
        try:
            return datetime.strptime(str(v).strip(), f).date()
        except ValueError:
            continue
    raise Reject(f"unparseable date: {v!r}")

def date_row(d: date) -> dict:
    """Build one dim_date row. Hierarchy: year > quarter > month > day (enables roll-up/drill-down)."""
    return {"date_key": int(d.strftime("%Y%m%d")), "full_date": d,
            "year": d.year, "quarter": (d.month - 1) // 3 + 1, "month": d.month,
            "month_name": d.strftime("%B"), "day_of_month": d.day,
            "day_of_week": d.strftime("%A"), "is_weekend": d.weekday() >= 5}

def generate_dates(start: date, end: date) -> Iterator[dict]:
    d = start
    while d <= end:
        yield date_row(d)
        d += timedelta(days=1)

# ---- dataset-specific rules (source_db -> data_warehouse) ----

def merge_name(first, last, default="Unknown") -> str:
    """Merge split source name columns (firstName + lastName) into one full_name attribute."""
    parts = [clean_text(p, default="") for p in (first, last)]
    name = " ".join(p for p in parts if p)
    return name or default

def standardize_gender(v) -> str:
    """Collapse gender variants (F/M/Female/Male) into one domain ('Female'/'Male')."""
    if is_null(v):
        return "Unknown"
    s = str(v).strip().lower()
    if s in {"f", "female"}:
        return "Female"
    if s in {"m", "male"}:
        return "Male"
    return clean_text(v, title=True)

VEHICLE_MAP = {"motorcycle": "Motorcycle", "motorbike": "Motorcycle",
               "bicycle": "Bicycle", "bike": "Bicycle",
               "trike": "Trike", "car": "Car"}

def standardize_vehicle(v) -> str:
    """Unify vehicle synonyms (Motorbike -> Motorcycle, Bike -> Bicycle) for clean slicing."""
    if is_null(v):
        return "Unknown"
    return VEHICLE_MAP.get(str(v).strip().lower(), clean_text(v, title=True))

def age_group(v) -> str:
    """Bucket rider age into Teen/Young/Middle/Senior for drill-down on the rider dimension."""
    a = to_int(v)
    if a is None:
        return "Unknown"
    if a <= 19:
        return "Teen"
    if a <= 35:
        return "Young"
    if a <= 50:
        return "Middle"
    return "Senior"

