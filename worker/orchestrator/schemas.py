from pydantic import BaseModel, Field
from typing import List, Dict


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
