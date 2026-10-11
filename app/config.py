import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# Before anything reads the environment: MISTRAL_API_KEY and the optional MISTRAL_MODEL.
load_dotenv(ROOT / ".env")

DB_PATH = ROOT / "orders.db"
EMAILS_DIR = ROOT / "data" / "emails"
OUTBOX_DIR = ROOT / "outbox"

MLFLOW_DB = ROOT / "mlflow.db"
MLFLOW_DIRS = (ROOT / "mlruns", ROOT / "mlartifacts")
MLFLOW_EXPERIMENT = "order-intake"

MODEL = os.environ.get("MISTRAL_MODEL", "ministral-14b-2512")
