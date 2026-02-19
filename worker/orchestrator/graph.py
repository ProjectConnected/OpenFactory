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
    state["stage"] = "release_artifacts"
    state["status"] = "done"
    return state


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("preflight", _advance("preflight"))
    g.add_node("spec_freeze", _advance("spec_freeze"))
    g.add_node("architecture", _advance("architecture"))
    g.add_node("ticket_planning", _advance("ticket_planning"))
    g.add_node("implement_loop", _advance("implement_loop"))
    g.add_node("integration", _advance("integration"))
    g.add_node("pr_ci_gate", _advance("pr_ci_gate"))
    g.add_node("release_artifacts", _finish)

    g.set_entry_point("preflight")
    g.add_edge("preflight", "spec_freeze")
    g.add_edge("spec_freeze", "architecture")
    g.add_edge("architecture", "ticket_planning")
    g.add_edge("ticket_planning", "implement_loop")
    g.add_edge("implement_loop", "integration")
    g.add_edge("integration", "pr_ci_gate")
    g.add_edge("pr_ci_gate", "release_artifacts")
    g.add_edge("release_artifacts", END)
    return g.compile()
