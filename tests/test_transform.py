"""Unit tests for the pure wrangling rules in etl/transform.py (no database needed)."""
from datetime import date, datetime

import pytest

from etl import transform as t


class TestIsNull:
    @pytest.mark.parametrize("v", [None, "", "  ", "na", "N/A", "null", "None", "nan", "-"])
    def test_null_like(self, v):
        assert t.is_null(v) is True

    @pytest.mark.parametrize("v", [0, 0.0, False, "x", "Unknown", "0"])
    def test_not_null(self, v):
        assert t.is_null(v) is False


class TestCleanText:
    def test_collapses_whitespace(self):
        assert t.clean_text("  John   Doe  ") == "John Doe"

    def test_title(self):
        assert t.clean_text("john doe", title=True) == "John Doe"

    def test_max_len(self):
        assert t.clean_text("abcdef", max_len=3) == "abc"

    def test_null_returns_default(self):
        assert t.clean_text(None, default="Unknown") == "Unknown"
        assert t.clean_text("n/a", default="") == ""

    def test_none_default(self):
        assert t.clean_text(None, default=None) is None


class TestToInt:
    def test_basic(self):
        assert t.to_int("123") == 123
        assert t.to_int(42) == 42

    def test_comma_and_float_truncation(self):
        assert t.to_int("1,234.5") == 1234

    def test_null_returns_default(self):
        assert t.to_int("na") is None
        assert t.to_int("na", 0) == 0

    @pytest.mark.parametrize("bad", ["abc", "inf", "-Inf", "INF"])
    def test_rejects(self, bad):
        with pytest.raises(t.Reject):
            t.to_int(bad)


class TestToDecimal:
    def test_currency_and_comma(self):
        assert t.to_decimal("$1,234.5") == t.Decimal("1234.50")

    def test_fixed_scale(self):
        assert t.to_decimal("1000") == t.Decimal("1000.00")

    def test_places_zero(self):
        assert t.to_decimal("12.7", places=0) == t.Decimal("13")

    def test_null_token_returns_default(self):
        assert t.to_decimal("NaN") is None
        assert t.to_decimal("n/a", default=t.Decimal("0")) == t.Decimal("0")

    @pytest.mark.parametrize("bad", ["Infinity", "-inf", "1e999999", "oops"])
    def test_rejects(self, bad):
        with pytest.raises(t.Reject):
            t.to_decimal(bad)


class TestParseDate:
    @pytest.mark.parametrize("v,expected", [
        ("2025-05-24", date(2025, 5, 24)),
        ("06/25/2025", date(2025, 6, 25)),
        ("25/06/2025", date(2025, 6, 25)),
        ("2024/12/31", date(2024, 12, 31)),
        ("31-Dec-2024", date(2024, 12, 31)),
    ])
    def test_formats(self, v, expected):
        assert t.parse_date(v) == expected

    def test_passthrough(self):
        assert t.parse_date(datetime(2024, 1, 2, 3, 4)) == date(2024, 1, 2)
        assert t.parse_date(date(2024, 1, 2)) == date(2024, 1, 2)

    @pytest.mark.parametrize("v", [None, "", "na"])
    def test_null_returns_none(self, v):
        assert t.parse_date(v) is None

    def test_unparseable_rejects(self):
        with pytest.raises(t.Reject):
            t.parse_date("not a date")


class TestDateRow:
    def test_exact(self):
        assert t.date_row(date(2026, 10, 17)) == {
            "date_key": 20261017, "full_date": date(2026, 10, 17), "year": 2026,
            "quarter": 4, "month": 10, "month_name": "October", "day_of_month": 17,
            "day_of_week": "Saturday", "is_weekend": True,
        }

    def test_weekend_flags(self):
        assert t.date_row(date(2026, 10, 18))["is_weekend"] is True   # Sunday
        assert t.date_row(date(2026, 10, 19))["is_weekend"] is False  # Monday
        assert t.date_row(date(2026, 10, 19))["day_of_week"] == "Monday"

    @pytest.mark.parametrize("month,quarter", [(1, 1), (3, 1), (4, 2), (7, 3), (12, 4)])
    def test_quarters(self, month, quarter):
        assert t.date_row(date(2025, month, 1))["quarter"] == quarter


class TestGenerateDates:
    def test_inclusive_and_count(self):
        rows = list(t.generate_dates(date(2024, 1, 1), date(2024, 1, 31)))
        assert len(rows) == 31
        assert rows[0]["full_date"] == date(2024, 1, 1)
        assert rows[-1]["full_date"] == date(2024, 1, 31)

    def test_single_day(self):
        assert len(list(t.generate_dates(date(2024, 2, 29), date(2024, 2, 29)))) == 1


class TestMergeName:
    def test_both(self):
        assert t.merge_name("John", "Doe") == "John Doe"

    def test_one_missing(self):
        assert t.merge_name("John", None) == "John"
        assert t.merge_name(None, "Doe") == "Doe"

    def test_both_missing(self):
        assert t.merge_name(None, None) == "Unknown"
        assert t.merge_name("", "  ") == "Unknown"

    def test_whitespace(self):
        assert t.merge_name("  John ", " Doe ") == "John Doe"


class TestStandardizeGender:
    @pytest.mark.parametrize("v", ["F", "f", "Female", "female", "FEMALE"])
    def test_female(self, v):
        assert t.standardize_gender(v) == "Female"

    @pytest.mark.parametrize("v", ["M", "m", "Male", "male"])
    def test_male(self, v):
        assert t.standardize_gender(v) == "Male"

    def test_unknown(self):
        assert t.standardize_gender(None) == "Unknown"
        assert t.standardize_gender("na") == "Unknown"

    def test_other_value_titlecased(self):
        assert t.standardize_gender("other") == "Other"


class TestStandardizeVehicle:
    @pytest.mark.parametrize("v", ["Motorcycle", "motorbike", "Motorbike"])
    def test_motorcycle(self, v):
        assert t.standardize_vehicle(v) == "Motorcycle"

    @pytest.mark.parametrize("v", ["Bike", "bicycle", "Bicycle"])
    def test_bicycle(self, v):
        assert t.standardize_vehicle(v) == "Bicycle"

    def test_others(self):
        assert t.standardize_vehicle("Trike") == "Trike"
        assert t.standardize_vehicle("car") == "Car"

    def test_unknown(self):
        assert t.standardize_vehicle(None) == "Unknown"

    def test_passthrough_unknown_value(self):
        assert t.standardize_vehicle("scooter") == "Scooter"


class TestAgeGroup:
    @pytest.mark.parametrize("age,expected", [
        (18, "Teen"), (19, "Teen"),
        (20, "Young"), (35, "Young"),
        (36, "Middle"), (50, "Middle"),
        (51, "Senior"), (60, "Senior"),
    ])
    def test_boundaries(self, age, expected):
        assert t.age_group(age) == expected

    def test_unknown(self):
        assert t.age_group(None) == "Unknown"

    def test_garbage_rejects(self):
        with pytest.raises(t.Reject):
            t.age_group("abc")
