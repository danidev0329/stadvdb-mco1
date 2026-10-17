"""Profile the SOURCE DB (Member 2's first task): row counts, null %, distinct counts per column.
  python -m etl.profile                 # all tables
  python -m etl.profile orders customers --no-distinct
Writes docs/source-profile.md; paste findings into the report's data-quality section."""
import argparse
import sys
from pathlib import Path
from etl import config
from etl.db import source

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "source-profile.md"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*")
    ap.add_argument("--no-distinct", action="store_true", help="skip COUNT(DISTINCT) (slow on big tables)")
    a = ap.parse_args()

    conn = source(); cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'",
                (config.SOURCE_DB,))
    discovered = [r[0] for r in cur.fetchall()]
    if a.tables:
        unknown = [t for t in a.tables if t not in discovered]
        for u in unknown:
            print(f"warning: skipping unknown table: {u}", file=sys.stderr)
        tables = [t for t in a.tables if t in discovered]
        if not tables:
            print("error: no known tables to profile", file=sys.stderr)
            conn.close()
            return 1
    else:
        tables = discovered
    lines = ["# Source data profile\n"]
    for tb in tables:
        cur.execute(f"SELECT COUNT(*) FROM `{tb}`"); n = cur.fetchone()[0]
        cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (config.SOURCE_DB, tb))
        cols = cur.fetchall()
        lines += [f"## {tb} ({n:,} rows)\n", "| column | type | null % | distinct |", "|---|---|---|---|"]
        for col, typ in cols:
            cur.execute(f"SELECT SUM(`{col}` IS NULL) FROM `{tb}`"); nulls = cur.fetchone()[0] or 0
            if a.no_distinct:
                dist = "-"
            else:
                cur.execute(f"SELECT COUNT(DISTINCT `{col}`) FROM `{tb}`"); dist = f"{cur.fetchone()[0]:,}"
            lines.append(f"| {col} | {typ} | {100 * nulls / n:.1f} | {dist} |" if n else f"| {col} | {typ} | - | - |")
        lines.append("")
    conn.close()
    out = OUT_PATH; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines)); print(f"\nSaved to {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
