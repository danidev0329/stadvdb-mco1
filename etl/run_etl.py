"""Usage:
  python -m etl.run_etl                      # run all jobs, then validate
  python -m etl.run_etl --only dim_customer  # run selected jobs
  python -m etl.run_etl --full-refresh       # truncate targets first (FK checks off during TRUNCATE)
  python -m etl.run_etl --dry-run            # extract + transform only, nothing loaded

Note: --full-refresh cannot be combined with a partial --only (truncating a subset
orphans dependent tables) -- either drop --full-refresh or list every job.
"""
import argparse, logging, sys
from etl import pipeline
from etl.mapping import JOBS
from etl.validate import run_checks

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", metavar="JOB")
    ap.add_argument("--full-refresh", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-validate", action="store_true")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("etl")

    jobs = [j for j in JOBS if not a.only or j.name in a.only]
    unknown = set(a.only or []) - {j.name for j in JOBS}
    if unknown:
        log.error("unknown job(s): %s", ", ".join(sorted(unknown)))
        return 2

    if a.full_refresh and a.only and set(a.only) != {j.name for j in JOBS}:
        log.error("--full-refresh requires a full run; it cannot be combined with a partial "
                  "--only (truncating a subset orphans dependent tables). "
                  "Drop --full-refresh, or list all jobs.")
        return 2

    results = pipeline.run(jobs, full_refresh=a.full_refresh, dry_run=a.dry_run)
    failed = [r.job for r in results if r.error]
    if failed:
        log.error("job(s) failed: %s", ", ".join(failed))
        return 1
    if a.dry_run or a.skip_validate:
        return 0
    return 0 if run_checks(log) else 1

if __name__ == "__main__":
    sys.exit(main())
