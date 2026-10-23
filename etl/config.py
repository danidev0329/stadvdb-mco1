"""All tunables live here (env-driven) so the ETL is reusable on any teammate's machine."""
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MYSQL = dict(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    port=int(os.getenv("MYSQL_PORT", 3307)),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", ""),
)

# Cloud MySQL providers such as Aiven require TLS. Leave MYSQL_SSL_CA unset for
# local MySQL; set it to the provider's CA certificate path when deploying.
if os.getenv("MYSQL_SSL_CA"):
    MYSQL["ssl_ca"] = os.getenv("MYSQL_SSL_CA")
    MYSQL["ssl_verify_cert"] = True
SOURCE_DB = os.getenv("SOURCE_DB", "source_db")
WAREHOUSE_DB = os.getenv("WAREHOUSE_DB", "data_warehouse")

CHUNK_SIZE = int(os.getenv("ETL_CHUNK_SIZE", 10_000))   # rows read per fetch (memory control)
BATCH_SIZE = int(os.getenv("ETL_BATCH_SIZE", 5_000))    # rows per INSERT batch

DATE_START = date.fromisoformat(os.getenv("DATE_START", "2015-01-01"))
DATE_END = date.fromisoformat(os.getenv("DATE_END", "2026-12-31"))

ROOT = Path(__file__).resolve().parent
REJECT_DIR = ROOT / "rejects"   # rows that failed transformation + reason (data-quality evidence)
RUN_DIR = ROOT / "runs"         # per-run JSON summaries (counts, timings) for the report
