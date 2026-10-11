from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = ROOT / "orders.db"
EMAILS_DIR = ROOT / "data" / "emails"
OUTBOX_DIR = ROOT / "outbox"

MLFLOW_DB = ROOT / "mlflow.db"
MLFLOW_DIRS = (ROOT / "mlruns", ROOT / "mlartifacts")
