"""Tests for etl/pipeline.py error containment (no real database needed)."""
import json

import pytest

from etl import config
from etl import pipeline
from etl.mapping import Job
from etl.pipeline import JobStats, run, run_job
from etl.transform import Reject


class FakeConn:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    """Redirect run artifacts to tmp and stub out DB + load."""
    monkeypatch.setattr(config, "REJECT_DIR", tmp_path / "rejects")
    monkeypatch.setattr(config, "RUN_DIR", tmp_path / "runs")
    monkeypatch.setattr(pipeline, "warehouse", lambda: FakeConn())
    monkeypatch.setattr(
        pipeline.load, "upsert",
        lambda conn, table, columns, rows, batch_size=None: len(rows),
    )
    return tmp_path


def make_job(name="job", transform=None, extract=None):
    return Job(
        name=name,
        target="T",
        columns=["a"],
        extract=extract or (lambda: [[{"a": 1}]]),
        transform=transform or (lambda r, ctx: {"a": r["a"]}),
    )


class TestRunJobContainment:
    def test_success(self):
        stats = run_job(make_job())
        assert stats.error is None
        assert stats.read == 1 and stats.loaded == 1

    def test_transform_error_is_contained(self):
        def boom(r, ctx):
            raise ValueError("schema drift")
        stats = run_job(make_job(transform=boom))
        assert stats.error == "ValueError: schema drift"
        assert stats.loaded == 0

    def test_extract_error_is_contained(self):
        def bad_extract():
            raise RuntimeError("source gone")
        stats = run_job(make_job(extract=bad_extract))
        assert stats.error == "RuntimeError: source gone"

    def test_connect_error_is_contained(self, monkeypatch):
        def bad_warehouse():
            raise OSError("no db")
        monkeypatch.setattr(pipeline, "warehouse", bad_warehouse)
        stats = run_job(make_job())
        assert stats.error == "OSError: no db"

    def test_reject_is_not_an_error(self):
        def rejects(r, ctx):
            raise Reject("bad row")
        stats = run_job(make_job(transform=rejects))
        assert stats.error is None
        assert stats.rejected == 1


class TestRun:
    def test_summary_written_on_failure(self, isolate):
        def boom(r, ctx):
            raise ValueError("x")
        run([make_job(name="bad", transform=boom)])
        files = list((isolate / "runs").glob("run_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data[0]["job"] == "bad"
        assert data[0]["error"] == "ValueError: x"

    def test_fail_fast_stops_remaining_jobs(self):
        def boom(r, ctx):
            raise ValueError("x")
        results = run([
            make_job(name="ok"),
            make_job(name="bad", transform=boom),
            make_job(name="never"),
        ])
        assert [r.job for r in results] == ["ok", "bad"]
        assert results[0].error is None
        assert results[1].error is not None


class TestRunEtlExitCode:
    def test_returns_1_when_job_failed(self, monkeypatch):
        import etl.run_etl as run_etl
        monkeypatch.setattr(
            run_etl.pipeline, "run",
            lambda jobs, full_refresh=False, dry_run=False: [JobStats(job="x", error="boom")],
        )
        assert run_etl.main([]) == 1

    def test_returns_0_when_all_ok(self, monkeypatch):
        import etl.run_etl as run_etl
        monkeypatch.setattr(
            run_etl.pipeline, "run",
            lambda jobs, full_refresh=False, dry_run=False: [JobStats(job="x")],
        )
        monkeypatch.setattr(run_etl, "run_checks", lambda log: True)
        assert run_etl.main([]) == 0


class TestFullRefreshGuard:
    def _stub_run(self, monkeypatch, calls):
        import etl.run_etl as run_etl

        def fake_run(jobs, full_refresh=False, dry_run=False):
            calls.append(([j.name for j in jobs], full_refresh))
            return [JobStats(job=j.name) for j in jobs]

        monkeypatch.setattr(run_etl.pipeline, "run", fake_run)
        monkeypatch.setattr(run_etl, "run_checks", lambda log: True)

    def test_partial_full_refresh_is_refused(self, monkeypatch):
        import etl.run_etl as run_etl
        calls = []
        self._stub_run(monkeypatch, calls)
        assert run_etl.main(["--full-refresh", "--only", "dim_users"]) == 2
        assert calls == []

    def test_full_refresh_allowed(self, monkeypatch):
        import etl.run_etl as run_etl
        calls = []
        self._stub_run(monkeypatch, calls)
        assert run_etl.main(["--full-refresh"]) == 0
        assert calls and calls[0][1] is True

    def test_full_refresh_with_all_jobs_allowed(self, monkeypatch):
        import etl.run_etl as run_etl
        from etl.mapping import JOBS
        calls = []
        self._stub_run(monkeypatch, calls)
        names = [j.name for j in JOBS]
        assert run_etl.main(["--full-refresh", "--only", *names]) == 0
        assert calls and calls[0][1] is True

    def test_only_without_full_refresh_allowed(self, monkeypatch):
        import etl.run_etl as run_etl
        calls = []
        self._stub_run(monkeypatch, calls)
        assert run_etl.main(["--only", "dim_users"]) == 0
        assert calls and calls[0][1] is False

