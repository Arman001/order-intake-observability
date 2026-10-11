"""What the viewer sees in the terminal. Every line stays under 80 characters."""

WIDTH = 79

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

STATUS_COLOR = {
    "completed": GREEN,
    "not_an_order": YELLOW,
    "needs_review": YELLOW,
    "rejected": RED,
}


def _clip(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def _items(items: list[dict], width: int) -> str:
    """As many whole items as fit, then how many were left out."""
    parts = [f"{item['qty']} {item['sku']}" for item in items]
    for shown in range(len(parts), 0, -1):
        more = len(parts) - shown
        text = ", ".join(parts[:shown]) + (f", +{more} more" if more else "")
        if len(text) <= width:
            return text
    return f"{len(parts)} items"


def node_line(name: str, update: dict) -> str:
    """One line for one node: mark, name, result, summary."""
    color, mark, result = GREEN, "✓", "ok"

    if name == "classifier":
        kind = "order" if update["is_order"] else "not an order"
        summary = f"{kind}: {update['classifier_reason']}"
    elif name == "extractor":
        items = update["items"]
        count = f"{len(items)} items: "
        summary = count + _items(items, WIDTH - 22 - len(count)) if items else "no items"
    elif name == "validator":
        summary = update["reason"]
        if update["status"] == "rejected":
            color, mark, result = RED, "✗", "rejected"
        elif update["status"] == "needs_review":
            color, mark, result = YELLOW, "!", "review"
    else:
        summary = f"order {update['order_id']} saved, confirmation in outbox/"

    head = f"{mark} {name:<10} {result:<8} "  # 22 characters
    return f"{color}{head}{_clip(summary, WIDTH - len(head))}{RESET}"


def header(email: dict, customer_id: str, version: str) -> str:
    text = f"Email {email['id']} from {customer_id}, extractor {version}"
    return f"{BOLD}{_clip(text, WIDTH)}{RESET}"


def summary_lines(state: dict, order_lines: list[tuple], trace_id: str | None) -> list[str]:
    """Final status, the order as written to the database, and the trace ID."""
    status = state["status"]
    lines = ["", f"{BOLD}Status:{RESET} {STATUS_COLOR[status]}{status}{RESET}"]
    if state.get("order_id"):
        lines.append(f"{BOLD}Order:{RESET}  {state['order_id']}")
        lines += [f"  {qty:>5} x {sku}" for sku, qty in order_lines]
    if trace_id:
        lines.append(f"{BOLD}Trace:{RESET}  {trace_id}")
    return lines
