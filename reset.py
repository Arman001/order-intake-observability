"""Back to a clean state between takes.

    uv run python reset.py         re-seed the database, empty outbox/
    uv run python reset.py --all   also delete the MLflow store (once per session)
"""

import argparse
import shutil
from pathlib import Path

from app.config import DB_PATH, MLFLOW_DB, MLFLOW_DIRS, OUTBOX_DIR
from data.seed import seed


def reset(
    db_path: Path = DB_PATH,
    outbox_dir: Path = OUTBOX_DIR,
    mlflow_db: Path = MLFLOW_DB,
    mlflow_dirs: tuple[Path, ...] = MLFLOW_DIRS,
    clear_mlflow: bool = False,
) -> None:
    seed(db_path)

    outbox_dir.mkdir(exist_ok=True)
    for path in outbox_dir.iterdir():
        if path.name != ".gitkeep":
            path.unlink()

    if clear_mlflow:
        mlflow_db.unlink(missing_ok=True)
        for path in mlflow_dirs:
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true",
                        help="also delete the MLflow store")
    args = parser.parse_args()

    reset(clear_mlflow=args.all)
    cleared = "database, outbox and MLflow store" if args.all else "database and outbox"
    print(f"Reset: {cleared}")
