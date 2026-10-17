"""Orchestration: per-job read -> transform -> load, with reject log and run stats."""
from __future__ import annotations
import json, logging, time
from dataclasses import dataclass, asdict
from datetime import datetime
from etl import config, load
from etl.db import warehouse
from etl.mapping import Job
from etl.transform import Reject

log = logging.getLogger("etl")

@dataclass
class JobStats:
    job: str
    read: int = 0
    loaded: int = 0
    rejected: int = 0
    skipped: int = 0
    seconds: float = 0.0

class RejectLog:
    def __init__(self, job: str, enabled: bool = True):
        self.enabled, self.f, self.path = enabled, None, None
        self.job = job
    def __enter__(self):
        if self.enabled:
            config.REJECT_DIR.mkdir(parents=True, exist_ok=True)
            self.path = config.REJECT_DIR / f"{self.job}_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
            self.f = open(self.path, "w", encoding="utf-8")
        return self
    def write(self, row, reason):
        if self.f:
            self.f.write(json.dumps({"reason": reason, "row": row}, default=str) + "\n")
    def __exit__(self, *exc):
        if self.f:
            self.f.close()
            if self.path.stat().st_size == 0:   # no rejects: don't leave empty files
                self.path.unlink()

def run_job(job: Job, full_refresh=False, dry_run=False) -> JobStats:
    stats, t0 = JobStats(job.name), time.perf_counter()
    conn = warehouse()
    try:
        if full_refresh and not dry_run:
            load.truncate(conn, job.target)
        ctx = job.prepare(conn) if job.prepare else {}
        with RejectLog(job.name, enabled=True) as rejects:
            for chunk in job.extract():
                good = []
                for row in chunk:
                    stats.read += 1
                    try:
                        out = job.transform(row, ctx)
                    except Reject as e:
                        stats.rejected += 1
                        rejects.write(row, str(e))
                        continue
                    if out is None:
                        stats.skipped += 1
                    else:
                        good.append(out)
                stats.loaded += len(good) if dry_run else load.upsert(conn, job.target, job.columns, good)
                log.info("%s: read=%d loaded=%d rejected=%d", job.name, stats.read, stats.loaded, stats.rejected)
    finally:
        conn.close()
    stats.seconds = round(time.perf_counter() - t0, 2)
    return stats

def run(jobs: list[Job], full_refresh=False, dry_run=False) -> list[JobStats]:
    results = [run_job(j, full_refresh, dry_run) for j in jobs]
    config.RUN_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RUN_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps([asdict(r) for r in results], indent=2))
    log.info("run summary written to %s", out)
    return results
