from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph


class GraphState(TypedDict, total=False):
    stage: str
    status: str
    error: str


def _advance(stage: str):
    def _fn(state: GraphState) -> GraphState:
        state["stage"] = stage
        state["status"] = "running"
        return state

    return _fn


def _finish(state: GraphState) -> GraphState:
    state["stage"] = "release"
    state["status"] = "done"
    return state


def build_graph():
    """PR1 skeleton only: stage graph and ordering; runtime wiring deferred."""
    g = StateGraph(GraphState)
    g.add_node("preflight", _advance("preflight"))
    g.add_node("spec", _advance("spec"))
    g.add_node("arch", _advance("arch"))
    g.add_node("tickets", _advance("tickets"))
    g.add_node("implement_loop", _advance("implement_loop"))
    g.add_node("integration", _advance("integration"))
    g.add_node("pr_ci_gate", _advance("pr_ci_gate"))
    g.add_node("release", _finish)

    g.set_entry_point("preflight")
    g.add_edge("preflight", "spec")
    g.add_edge("spec", "arch")
    g.add_edge("arch", "tickets")
    g.add_edge("tickets", "implement_loop")
    g.add_edge("implement_loop", "integration")
    g.add_edge("integration", "pr_ci_gate")
    g.add_edge("pr_ci_gate", "release")
    g.add_edge("release", END)
    return g.compile()
