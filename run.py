"""Run one email through the pipeline.

    uv run python run.py --email 03 --version v1
"""

import argparse
import sys
from contextlib import closing
from pathlib import Path

from app import console
from app.config import DB_PATH, EMAILS_DIR, OUTBOX_DIR
from app.db import UnknownSenderError, connect, load_email, resolve_customer
from app.graph import build_graph
from data.seed import seed


def run_email(
    email_id: str,
    version: str,
    *,
    llm,
    db_path: Path = DB_PATH,
    outbox_dir: Path = OUTBOX_DIR,
    emails_dir: Path = EMAILS_DIR,
) -> dict:
    email = load_email(email_id, emails_dir)

    # Re-seed before every run, so one run's order never becomes the next
    # run's "last month's order".
    seed(db_path)
    with closing(connect(db_path)) as conn:
        customer_id = resolve_customer(conn, email["from"])

    state = {"email": email, "customer_id": customer_id, "version": version}
    print(console.header(email, customer_id, version))

    graph = build_graph(llm, db_path, outbox_dir)
    for step in graph.stream(state, stream_mode="updates"):
        for name, update in step.items():
            state.update(update)
            print(console.node_line(name, update))
    return state


def order_lines(order_id: str, db_path: Path = DB_PATH) -> list[tuple]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT sku, qty FROM order_lines WHERE order_id = ? ORDER BY rowid",
            (order_id,),
        ).fetchall()
    return [tuple(row) for row in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True, help="email id, 01 to 05")
    parser.add_argument("--version", choices=["v1", "v2"], default="v1",
                        help="extractor version")
    args = parser.parse_args(argv)

    from app.llm import get_llm
    from app.tracing import setup_tracing, tag_last_trace

    setup_tracing()

    try:
        state = run_email(args.email, args.version, llm=get_llm())
    except (UnknownSenderError, FileNotFoundError) as error:
        print(f"{console.RED}Error: {error}{console.RESET}", file=sys.stderr)
        return 1

    trace_id = tag_last_trace(state)
    lines = order_lines(state["order_id"]) if state.get("order_id") else []
    print("\n".join(console.summary_lines(state, lines, trace_id)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
