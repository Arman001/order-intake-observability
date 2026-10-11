from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from app.config import DB_PATH, OUTBOX_DIR
from app.nodes.classifier import classifier
from app.nodes.executor import executor
from app.nodes.extractor import extractor
from app.nodes.validator import validator
from app.state import State


def after_classifier(state: State) -> str:
    return "extractor" if state["is_order"] else END


def after_validator(state: State) -> str:
    return "executor" if state["status"] == "valid" else END


def build_graph(llm, db_path: Path = DB_PATH, outbox_dir: Path = OUTBOX_DIR):
    graph = StateGraph(State)

    graph.add_node("classifier", partial(classifier, llm=llm))
    graph.add_node("extractor", extractor)
    graph.add_node("validator", partial(validator, db_path=db_path))
    graph.add_node(
        "executor", partial(executor, db_path=db_path, outbox_dir=outbox_dir)
    )

    graph.add_edge(START, "classifier")
    graph.add_conditional_edges("classifier", after_classifier, ["extractor", END])
    graph.add_edge("extractor", "validator")
    graph.add_conditional_edges("validator", after_validator, ["executor", END])
    graph.add_edge("executor", END)

    return graph.compile()
