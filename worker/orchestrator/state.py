from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional


class PipelineStage(StrEnum):
    PREFLIGHT = "preflight"           # Stage 0
    SPEC = "spec"                     # Stage 1
    ARCH = "arch"                     # Stage 2
    TICKETS = "tickets"               # Stage 3
    IMPLEMENT_LOOP = "implement_loop" # Stage 4
    INTEGRATION = "integration"       # Stage 5
    PR_CI_GATE = "pr_ci_gate"         # Stage 6
    RELEASE = "release"               # Stage 7


@dataclass
class RetryBudget:
    implement_loop: int = 3
    ci_fix_loop: int = 2


@dataclass
class PipelineCheckpoint:
    stage: PipelineStage
    ts: str
    note: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineState:
    job_id: str
    task: str
    owner: str
    repo: str
    trace_id: str = ""
    stage: PipelineStage = PipelineStage.PREFLIGHT
    status: str = "running"
    retry_budget: RetryBudget = field(default_factory=RetryBudget)
    retries: Dict[str, int] = field(default_factory=dict)
    checkpoints: List[PipelineCheckpoint] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
