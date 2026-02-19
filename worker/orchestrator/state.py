from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineState:
    job_id: str
    task: str
    owner: str
    repo: str
    stage: str = "preflight"
    status: str = "running"
    trace_id: str = ""
    retries: Dict[str, int] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
