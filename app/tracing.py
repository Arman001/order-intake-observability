import logging
import os

# MLflow prints a startup hint on import unless this is set first.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import mlflow  # noqa: E402

from app.config import MLFLOW_DB, MLFLOW_EXPERIMENT, MODEL  # noqa: E402


def setup_tracing() -> None:
    # Keep MLflow's own INFO lines out of the terminal.
    logging.getLogger("mlflow").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)

    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB}")
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    mlflow.langchain.autolog()


def tag_last_trace(state: dict) -> str | None:
    """Tag the trace of the run that just finished and return its ID."""
    trace_id = mlflow.get_last_active_trace_id()
    if trace_id is None:
        return None

    tags = {
        "email_id": state["email"]["id"],
        "customer_id": state["customer_id"],
        "prompt_version": f"extractor-{state['version']}",
        "model": MODEL,
        "status": state["status"],
    }
    # Only completed runs have an order.
    if state.get("order_id"):
        tags["order_id"] = state["order_id"]

    # Traces are written in the background. Wait for this one to be stored,
    # or tagging it fails on a fresh database.
    mlflow.flush_trace_async_logging()
    for key, value in tags.items():
        mlflow.set_trace_tag(trace_id, key, value)
    return trace_id
