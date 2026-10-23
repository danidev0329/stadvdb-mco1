# STADVDB MCO1: Query Processing in a Data Warehouse

## Team Members
| Name | Contribution |
|---|---|
| Daniel Rebudiao | Created the ETL Script |
| Jandeil Dural | ... |
| Lance Dimalanta | ... |
| Dion Cubarrubias | Created OLAP Application |

---

## Project Architecture

```
stadvdb-mco1/
├── README.md                  setup steps, architecture, team roles
├── .gitignore                 ignores .env, run artifacts, benchmark CSVs
├── .env.example               DB host/port/user + ETL tunables template
├── requirements.txt           Python dependencies (mysql-connector, dotenv, pytest)
│
├── schema/                    (Member 1)
│   ├── 001_create_warehouse.sql   data_warehouse: 6 dimension + 1 fact table, PKs/FKs
│   └── 002_indexes.sql            indexes on foreign keys (kept separate so
│                                  baseline vs. optimized stays reproducible)
│
├── etl/                       (Member 2)
│   ├── config.py              env-driven tunables (DB creds, chunk/batch size, date range)
│   ├── db.py                  connections to source_db and data_warehouse
│   ├── extract.py             chunked reads from source_db (flat memory on large tables)
│   ├── transform.py           one small, pure, unit-testable function per wrangling rule
│   ├── mapping.py             source -> warehouse jobs (dimensions first, then facts)
│   ├── load.py                batched, idempotent upserts + surrogate key maps
│   ├── pipeline.py            orchestration: per-job read->transform->load, reject log, run stats
│   ├── validate.py            source-vs-warehouse reconciliation + zero-count integrity checks
│   ├── profile.py             source profiling (row counts, null %, distinct counts)
│   └── run_etl.py             CLI entry point (--only / --full-refresh / --dry-run)
│
├── data/                      local source dumps (never committed)
│
├── docs/
│   └── source-profile.md      generated source data profile (row counts, null %, distincts)
│
├── olap/                      (Member 3)  
│   ├── queries.py             parameterized SQL (roll-up, drill-down, slice, dice, pivot)
│   ├── app.py                 web backend exposing the queries as endpoints
│   └── templates/index.html   dashboard with filters and granularity controls
│
├── tests/                     (Member 3, plus Member 2 for ETL checks)
│   ├── conftest.py                shared fixtures (skip DB tests when MySQL is down)
│   ├── test_transform.py          unit tests for the wrangling rules
│   ├── test_mapping.py            row transforms + job/schema consistency
│   ├── test_etl_validation.py     source vs. warehouse reconciliation
│   └── test_olap_queries.py       correct results for different parameters  -- not yet implemented
│
├── pytest.ini                 pytest config (pythonpath, testpaths, markers)
│
└── benchmarks/                (Member 4)  -- not yet implemented
    ├── run_benchmarks.py      runs each query N times, saves timings + EXPLAIN
    └── results/               baseline vs. optimized outputs
```

---

## Data Model

**Source** (`source_db`, MySQL 8.0) — 6 operational tables:

| Table | Rows | Grain |
|---|---|---|
| `users` | 100,000 | one row per user |
| `products` | 10,000 | one row per product |
| `couriers` | 3 | one row per courier company |
| `riders` | 100 | one row per rider |
| `orders` | 1,000,000 | one row per order header |
| `orderitems` | 1,999,824 | one row per product line in an order |

**Warehouse** (`data_warehouse`, star schema) — 6 dimensions + 1 fact:

| Table | Natural key | Notes |
|---|---|---|
| `Dim_Date` | `date_key` (YYYYMMDD) | generated, no source table |
| `Dim_Users` | `user_id` | |
| `Dim_Products` | `product_id` | |
| `Dim_Couriers` | `courier_id` | |
| `Dim_Riders` | `rider_id` | FK -> `Dim_Couriers` |
| `Dim_Orders` | `order_id` | FKs -> `Dim_Users`, `Dim_Riders`, `Dim_Date` |
| `Fact_OrderItems` | `UNIQUE(order_key, product_key)` | FKs -> `Dim_Orders`, `Dim_Products`, `Dim_Date` |

---

## Setup (local MySQL, no Docker required)

The ETL only needs a reachable MySQL server; the defaults match a local MySQL 8.0.

1. **Install and start MySQL 8.0** (the `MySQL80` Windows service is enough) and make sure `source_db` is loaded with the six source tables.
2. **Install Python dependencies:**
   ```
   pip install -r requirements.txt
   ```
3. **Configure credentials:** copy `.env.example` to `.env` and set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` for your machine. (`.env` is gitignored.)
4. **Create the warehouse schema:**
   ```
   mysql -u root -p -e "source schema/001_create_warehouse.sql"
   mysql -u root -p -D data_warehouse -e "source schema/002_indexes.sql"
   ```
   (001 drops and recreates `data_warehouse`; 002 has no `USE`, so pass `-D`.)

---

## Running the ETL

```
python -m etl.run_etl                      # run all jobs, then validate
python -m etl.run_etl --only dim_users     # run selected jobs
python -m etl.run_etl --full-refresh       # truncate all targets first (full run only)
python -m etl.run_etl --dry-run            # extract + transform only, nothing loaded
python -m etl.profile                      # write docs/source-profile.md
```

## Running the OLAP Web Application & Dashboard

The OLAP application provides an interactive decision-support dashboard connected to the dimensional data warehouse (`data_warehouse`), supporting multi-dimensional analysis with responsive Chart.js visualizations.

### 1. Start the Flask backend:
```bash
python -m olap.app
```
*(By default, the server starts on `http://127.0.0.1:5000`)*

### 2. Access the Analytical Dashboard:
Open your browser and navigate to `http://localhost:5000`.

### 3. Supported OLAP Operations:
* **Roll-Up (`/api/rollup`):** Multi-level hierarchical aggregation across temporal granularities (`year`, `quarter`, `month`, `day`) computing super-aggregate subtotals and grand totals in a single database pass via `WITH ROLLUP`.
* **Drill-Down (`/api/drilldown`):** Interactive top-down de-aggregation navigating from fiscal year down to quarters, months, and individual calendar days.
* **Slice (`/api/slice`):** Isolating performance along a single fixed dimension (`courier`, `gender`, `city`, `product`, `vehicle_type`) across time with dynamic join pruning.
* **Dice (`/api/dice`):** Constrained subcube extraction evaluating the intersection of multiple simultaneous filter criteria (Date Range $\times$ Courier $\times$ Gender $\times$ City $\times$ Vehicle Type).
* **Pivot (`/api/pivot`):** Relational cross-tabulation dynamically transposing courier rows into horizontal columns (`SUM(CASE WHEN ...)`), enabling direct side-by-side carrier volume comparisons alongside row-level grand totals.
`--full-refresh` cannot be combined with a partial `--only`: truncating a subset would
orphan dependent tables (and reset their surrogate keys), so the CLI rejects that with exit 2.

The run exits non-zero if any validation check fails.

### Running tests

```
pip install -r requirements.txt
python -m pytest -q                     # full suite
python -m pytest -m "not db" -q         # skip the DB-backed reconciliation tests
python -m pytest tests/test_transform.py -q
```

The pure unit tests (transform rules, mapping rows, schema consistency) need no
database. The reconciliation/zero-check tests connect to `source_db` and
`data_warehouse` and **skip automatically** when MySQL or the data isn't available.

### Design notes (reuse in the report)
- **Volume**: chunked reads (`ETL_CHUNK_SIZE`), batched multi-row inserts (`ETL_BATCH_SIZE`), one commit per chunk.
- **Idempotent**: `INSERT ... ON DUPLICATE KEY UPDATE`; every dimension has a `UNIQUE` natural key and the fact has `UNIQUE(order_key, product_key)`, so re-running never duplicates rows.
- **Data quality**: bad rows raise `Reject` and are written to `etl/rejects/*.jsonl` with a reason; per-run counts go to `etl/runs/*.json`.
- **Error containment**: a non-`Reject` failure (e.g. schema drift) fails only that job — the run stops, the summary is still written, and the CLI exits non-zero (validation is skipped).
- **Validation**: source-vs-warehouse reconciliation (row counts + total quantity) and zero-count integrity checks (orphan FKs, null measures) after every run.
- **Order**: dimensions before facts; fact rows resolve surrogate keys via `load.key_map`.
- **Wrangling rules**: text clean-up, splitting/merging names, gender + vehicle category standardization, age bucketing, mixed-format date parsing, and type casting.

### Current status
- ETL (extract/transform/load), validation, unit/integration tests, and the source data profile are implemented and verified end-to-end.
-  OLAP Application, Parameterized queries, Flask REST API, interactive dashboard

---

## Git Workflow

- Work on `feature/*` branches and open a pull request into `main`.
- `.env`, source dumps, `etl/rejects/`, `etl/runs/`, and benchmark results are never committed.
