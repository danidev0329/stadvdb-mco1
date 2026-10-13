# STADVDB MCO1: Query Processing in a Data Warehouse

---

## Project Architecture

```
stadvdb-mco1/
├── README.md                  setup steps, team roles, git workflow
├── .gitignore                 ignores .env, data dumps, benchmark CSVs
├── .env.example               DB host/port/user template (real .env stays local)
├── docker-compose.yml         pins mysql:8.0 so everyone has the same version
├── Makefile                   shortcuts: make up, schema, etl, app, test, bench
├── requirements.txt           Python dependencies
│
├── docker/init/
│   └── 00_create_databases.sql    creates source_db and dw on first start
│
├── data/
│   └── README.md              dumps live here locally, never committed
│
├── schema/                    (Member 1)
│   ├── 001_create_warehouse.sql   fact + dimension tables, PKs/FKs
│   └── 002_indexes.sql            optimization changes, kept separate so
│                                  before/after is reproducible
│
├── etl/                       (Member 2)
│   ├── db.py                  connections to source and warehouse
│   ├── extract.py             chunked reads from source_db
│   ├── transform.py           one small function per wrangling rule
│   ├── load.py                batched, idempotent inserts
│   ├── validate.py            row counts, totals, orphan checks
│   └── run_etl.py             entry point (dimensions first, then facts)
│
├── olap/                      (Member 3)
│   ├── queries.py             parameterized SQL (roll-up, drill-down, slice, dice, pivot)
│   ├── app.py                 web backend exposing the queries as endpoints
│   └── templates/index.html   dashboard with filters and granularity controls
│
├── tests/                     (Member 3, plus Member 2 for ETL checks)
│   ├── test_etl_validation.py     source vs. warehouse reconciliation
│   └── test_olap_queries.py       correct results for different parameters
│
├── benchmarks/                (Member 4)
│   ├── run_benchmarks.py      runs each query N times, saves timings + EXPLAIN
│   └── results/               baseline vs. optimized outputs
│
└── scripts/
    └── package_submission.sh  builds STADVDB-MCO1-GroupN.zip with required names
```

---
