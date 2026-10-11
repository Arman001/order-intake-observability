from contextlib import closing

import pytest

from app.db import connect
from reset import reset


@pytest.fixture
def project(tmp_path, db_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / ".gitkeep").touch()
    (outbox / "ORD-ABC123.txt").write_text("Confirmation")

    with closing(connect(db_path)) as conn:
        conn.execute("INSERT INTO orders VALUES ('ORD-ABC123', 'client-co', '2026-10-08')")
        conn.execute("INSERT INTO order_lines VALUES ('ORD-ABC123', 'BOLT-M8', 50)")
        conn.commit()

    mlflow_db = tmp_path / "mlflow.db"
    mlflow_db.write_text("traces")
    mlruns = tmp_path / "mlruns"
    (mlruns / "0").mkdir(parents=True)

    return {
        "db_path": db_path,
        "outbox_dir": outbox,
        "mlflow_db": mlflow_db,
        "mlflow_dirs": (mlruns, tmp_path / "mlartifacts"),
    }


def order_ids(db_path):
    with closing(connect(db_path)) as conn:
        return {r["order_id"] for r in conn.execute("SELECT order_id FROM orders")}


def test_reset_clears_run_orders_and_outbox_but_keeps_mlflow(project):
    reset(**project)

    assert order_ids(project["db_path"]) == {"ORD-5EED01", "ORD-5EED02"}
    assert [p.name for p in project["outbox_dir"].iterdir()] == [".gitkeep"]
    assert project["mlflow_db"].read_text() == "traces"
    assert project["mlflow_dirs"][0].exists()


def test_reset_all_also_clears_mlflow(project):
    reset(**project, clear_mlflow=True)

    assert order_ids(project["db_path"]) == {"ORD-5EED01", "ORD-5EED02"}
    assert [p.name for p in project["outbox_dir"].iterdir()] == [".gitkeep"]
    assert not project["mlflow_db"].exists()
    assert not project["mlflow_dirs"][0].exists()


def test_reset_works_from_nothing(tmp_path):
    reset(
        db_path=tmp_path / "orders.db",
        outbox_dir=tmp_path / "outbox",
        mlflow_db=tmp_path / "mlflow.db",
        mlflow_dirs=(tmp_path / "mlruns",),
        clear_mlflow=True,
    )

    assert order_ids(tmp_path / "orders.db") == {"ORD-5EED01", "ORD-5EED02"}
    assert (tmp_path / "outbox").is_dir()
