# ETL skeleton

```
mapping.py   <- edit this: source->warehouse jobs (dimensions first, then facts)
transform.py <- cleaning rules (pure functions, unit-tested)
extract.py   load.py   pipeline.py   run_etl.py   validate.py   profile.py
```

## Workflow
1. `python -m etl.profile` -> docs/source-profile.md (nulls, distincts, row counts)
2. Add cleaning rules to `transform.py` (+ tests in tests/test_transform.py)
3. When the schema is agreed: define jobs in `mapping.py`
4. Add reconciliation / zero checks in `validate.py`
5. `python -m etl.run_etl --dry-run`, then `python -m etl.run_etl`

## Design notes (reuse in the report)
- **Volume**: chunked reads (`ETL_CHUNK_SIZE`), batched multi-row inserts (`ETL_BATCH_SIZE`), commit per chunk.
- **Idempotent**: `INSERT ... ON DUPLICATE KEY UPDATE`; needs UNIQUE keys on natural keys (e.g. `UNIQUE(source_id)`) in dimension tables.
- **Data quality**: bad rows raise `Reject` -> `etl/rejects/*.jsonl` with reason; run counts in `etl/runs/*.json`.
- **Error containment**: a non-`Reject` failure (e.g. schema drift) fails that job only; the run stops and the summary is still written, and the CLI exits non-zero.
- **Validation**: source-vs-warehouse reconciliation + zero-count integrity checks after every run; non-zero exit code on failure.
- **Order**: dimensions before facts; facts resolve surrogate keys via `load.key_map`.
- Add `etl/rejects/` and `etl/runs/` to .gitignore.

## Run it

`pip install -r requirements.txt`
`python -m etl.run_etl`                         # full load + validation
`python -m etl.run_etl --only dim_users`         # subset
`python -m etl.run_etl --dry-run`                # extract+transform only
`python -m etl.profile`                          # source data profile