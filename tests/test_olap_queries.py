from __future__ import annotations
import pytest
from olap import queries


@pytest.fixture(scope="module")
def conn(warehouse_conn):
    return warehouse_conn


@pytest.fixture(scope="module")
def known_couriers(conn):
    return queries.distinct_values(conn, "courier")


@pytest.fixture(scope="module")
def known_years(conn):
    return queries.distinct_values(conn, "year")


@pytest.fixture(scope="module")
def fact_years(conn):
    rows = queries._fetchall(
        conn,
        "SELECT DISTINCT d.year AS v FROM Fact_OrderItems f "
        "JOIN Dim_Date d ON f.date_key = d.date_key ORDER BY v"
    )
    return [r["v"] for r in rows]


@pytest.fixture(scope="module")
def known_genders(conn):
    return queries.distinct_values(conn, "gender")


class TestRollup:

    @pytest.mark.db
    @pytest.mark.parametrize("gran", ["year", "quarter", "month"])
    def test_granularity_levels(self, conn, gran):
        rows = queries.rollup(conn, granularity=gran)
        assert len(rows) > 0, f"rollup({gran}) returned no rows"
        totals = [r for r in rows if r["year"] is None]
        assert len(totals) >= 1, "rollup should produce at least one grand-total row"
        assert totals[0]["total_qty"] is not None

    @pytest.mark.db
    def test_with_year_filter(self, conn, known_years):
        yr = known_years[0]
        rows = queries.rollup(conn, granularity="quarter", year=yr)
        data_rows = [r for r in rows if r["year"] is not None]
        assert all(r["year"] == yr for r in data_rows), \
            f"rollup year filter: expected all rows to be {yr}"

    @pytest.mark.db
    def test_with_courier_filter(self, conn, known_couriers):
        all_rows  = queries.rollup(conn, granularity="year")
        filt_rows = queries.rollup(conn, granularity="year",
                                   courier=known_couriers[0])
        gt_all  = [r for r in all_rows  if r["year"] is None][0]["total_qty"]
        gt_filt = [r for r in filt_rows if r["year"] is None][0]["total_qty"]
        assert gt_filt < gt_all, "courier-filtered total should be less than grand total"

    @pytest.mark.db
    def test_total_qty_positive(self, conn):
        rows = queries.rollup(conn, granularity="year")
        for r in rows:
            if r["total_qty"] is not None:
                assert r["total_qty"] >= 0


class TestDrilldown:

    @pytest.mark.db
    def test_year_to_quarters(self, conn, fact_years):
        yr = fact_years[-1]
        rows = queries.drilldown(conn, year=yr)
        assert len(rows) > 0
        assert "quarter" in rows[0]
        assert all(r["year"] == yr for r in rows)

    @pytest.mark.db
    def test_quarter_to_months(self, conn, fact_years):
        yr = fact_years[-1]
        rows = queries.drilldown(conn, year=yr, quarter=1)
        assert len(rows) > 0
        assert "month" in rows[0]
        months = {r["month"] for r in rows}
        assert months.issubset({1, 2, 3}), "Q1 should only have months 1-3"

    @pytest.mark.db
    def test_month_to_days(self, conn, fact_years):
        yr = fact_years[-1]
        rows = queries.drilldown(conn, year=yr, quarter=1, month=1)
        assert len(rows) > 0
        assert "day_of_month" in rows[0]
        assert all(1 <= r["day_of_month"] <= 31 for r in rows)

    @pytest.mark.db
    @pytest.mark.parametrize("yr_idx", [0, -1])
    def test_different_years(self, conn, fact_years, yr_idx):
        yr = fact_years[yr_idx]
        rows = queries.drilldown(conn, year=yr)
        assert len(rows) > 0


class TestSlice:

    @pytest.mark.db
    @pytest.mark.parametrize("dim,fixture", [
        ("courier", "known_couriers"),
        ("gender",  "known_genders"),
    ])
    def test_slice_returns_data(self, conn, dim, fixture, request):
        values = request.getfixturevalue(fixture)
        val = values[0]
        rows = queries.slice_query(conn, dimension=dim, value=val,
                                   granularity="year")
        assert len(rows) > 0, f"slice({dim}={val!r}) returned no rows"

    @pytest.mark.db
    def test_slice_different_couriers(self, conn, known_couriers):
        totals = {}
        for c in known_couriers:
            rows = queries.slice_query(conn, dimension="courier", value=c,
                                       granularity="year")
            totals[c] = sum(r["total_qty"] for r in rows if r["total_qty"])
        assert len(set(totals.values())) > 1, "expected different totals per courier"

    @pytest.mark.db
    def test_slice_invalid_dimension(self, conn):
        with pytest.raises(ValueError, match="unsupported"):
            queries.slice_query(conn, dimension="nonexistent", value="x")

    @pytest.mark.db
    @pytest.mark.parametrize("gran", ["year", "quarter", "month"])
    def test_slice_granularity(self, conn, known_couriers, gran):
        rows = queries.slice_query(conn, dimension="courier",
                                   value=known_couriers[0], granularity=gran)
        assert len(rows) > 0


class TestDice:

    @pytest.mark.db
    def test_single_filter(self, conn, known_couriers):
        rows = queries.dice_query(conn, courier=known_couriers[0],
                                  granularity="year")
        assert len(rows) > 0

    @pytest.mark.db
    def test_multiple_filters(self, conn, known_couriers, known_genders, known_years):
        rows = queries.dice_query(
            conn,
            year_start=known_years[0],
            year_end=known_years[0],
            courier=known_couriers[0],
            gender=known_genders[0],
            granularity="month",
        )
        assert isinstance(rows, list)

    @pytest.mark.db
    def test_no_filters_returns_all(self, conn):
        rows = queries.dice_query(conn, granularity="year")
        assert len(rows) > 0

    @pytest.mark.db
    def test_year_range(self, conn, known_years):
        yr = known_years[len(known_years)//2]
        rows = queries.dice_query(conn, year_start=yr, year_end=yr,
                                  granularity="month")
        data_rows = [r for r in rows if r.get("year")]
        assert all(r["year"] == yr for r in data_rows)

    @pytest.mark.db
    @pytest.mark.parametrize("gran", ["year", "quarter", "month"])
    def test_dice_granularities(self, conn, gran):
        rows = queries.dice_query(conn, granularity=gran)
        assert len(rows) > 0


class TestPivot:

    @pytest.mark.db
    def test_pivot_has_courier_columns(self, conn, known_couriers):
        rows = queries.pivot(conn, granularity="year")
        assert len(rows) > 0
        cols = set(rows[0].keys())
        for c in known_couriers:
            assert c in cols, f"expected column {c!r} in pivot"

    @pytest.mark.db
    def test_pivot_grand_total_matches_couriers(self, conn, known_couriers):
        rows = queries.pivot(conn, granularity="year")
        for r in rows:
            if r.get("year") is None:
                continue
            courier_sum = sum(r.get(c, 0) for c in known_couriers)
            assert courier_sum == r["grand_total"], \
                f"year {r['year']}: courier sum {courier_sum} != grand_total {r['grand_total']}"

    @pytest.mark.db
    def test_pivot_year_range(self, conn, known_years):
        all_rows  = queries.pivot(conn, granularity="year")
        yr = known_years[0]
        filt_rows = queries.pivot(conn, granularity="year",
                                  year_start=yr, year_end=yr)
        assert len(filt_rows) <= len(all_rows)
        data_rows = [r for r in filt_rows if r.get("year")]
        assert all(r["year"] == yr for r in data_rows)

    @pytest.mark.db
    @pytest.mark.parametrize("gran", ["year", "quarter"])
    def test_pivot_granularity(self, conn, gran):
        rows = queries.pivot(conn, granularity=gran)
        assert len(rows) > 0


class TestDimensionHelpers:

    @pytest.mark.db
    @pytest.mark.parametrize("dim", ["year","quarter","courier","gender","vehicle_type"])
    def test_distinct_values(self, conn, dim):
        vals = queries.distinct_values(conn, dim)
        assert len(vals) > 0, f"distinct_values({dim!r}) was empty"

    @pytest.mark.db
    def test_invalid_dimension(self, conn):
        with pytest.raises(ValueError):
            queries.distinct_values(conn, "bogus")
