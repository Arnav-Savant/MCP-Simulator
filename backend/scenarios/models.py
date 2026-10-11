from typing import Any, Literal

from pydantic import BaseModel, Field


class PolicyConfig(BaseModel):
    denied_tools: list[str] = []
    max_abs_number: float | None = None
    enforce_catalog: bool = False


class Step(BaseModel):
    type: Literal["connect", "discover", "propose_and_call", "raw_request", "final"]
    mode: str | None = None                 # connect: "auto" (modern) or "legacy"
    script: str | None = None               # connect: override server script (transport failure demo)
    tool: str | None = None                 # propose_and_call
    arguments: dict[str, Any] | None = None
    method: str | None = None               # raw_request
    params: dict[str, Any] | None = None
    with_envelope: bool = True
    template: str | None = None             # final: text with {summary}


class Scenario(BaseModel):
    id: str
    title: str
    category: Literal["discovery", "success", "validation", "error", "policy", "protocol", "transport", "legacy"]
    description: str
    user_message: str
    expected: str                           # what the learner should observe
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    steps: list[Step]
