from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class AcceptanceCriteria(BaseModel):
    items: List[str] = Field(default_factory=list)


class SpecModel(BaseModel):
    scope: str
    non_goals: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    acceptance: AcceptanceCriteria = Field(default_factory=AcceptanceCriteria)
    constraints: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class TicketModel(BaseModel):
    id: str
    goal: str
    files_touched: List[str] = Field(default_factory=list)
    commands_allowed: List[str] = Field(default_factory=list)
    tests_required: List[str] = Field(default_factory=list)
    done_criteria: List[str] = Field(default_factory=list)


class PipelineConfig(BaseModel):
    implement_retries: int = 3
    ci_fix_retries: int = 2
    required_check_context: str = "tests"
    local_test_cmd: str = "make test"
    local_integration_cmd: str = "make integration"


class PipelineCheckpointSchema(BaseModel):
    stage: Literal[
        "preflight",
        "spec",
        "arch",
        "tickets",
        "implement_loop",
        "integration",
        "pr_ci_gate",
        "release",
    ]
    ts: str
    note: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PipelineStateSchema(BaseModel):
    job_id: str
    trace_id: str = ""
    stage: Literal[
        "preflight",
        "spec",
        "arch",
        "tickets",
        "implement_loop",
        "integration",
        "pr_ci_gate",
        "release",
    ] = "preflight"
    status: str = "running"
    retries: Dict[str, int] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    checkpoints: List[PipelineCheckpointSchema] = Field(default_factory=list)
    error: str | None = None
