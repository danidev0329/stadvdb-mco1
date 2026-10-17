"""Profile the SOURCE DB (Member 2's first task): row counts, null %, distinct counts per column.
  python -m etl.profile                 # all tables
  python -m etl.profile orders customers --no-distinct
Writes docs/source-profile.md; paste findings into the report's data-quality section."""
import argparse
from pathlib import Path
from etl import config
from etl.db import source

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*")
    ap.add_argument("--no-distinct", action="store_true", help="skip COUNT(DISTINCT) (slow on big tables)")
    a = ap.parse_args()

    conn = source(); cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'",
                (config.SOURCE_DB,))
    tables = a.tables or [r[0] for r in cur.fetchall()]
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
    out = Path("docs/source-profile.md"); out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines)); print(f"\nSaved to {out}")

if __name__ == "__main__":
    main()
