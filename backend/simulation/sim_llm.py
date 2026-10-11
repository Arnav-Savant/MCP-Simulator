from dataclasses import dataclass

from scenarios.models import Step


@dataclass
class Decision:
    tool: str
    arguments: dict
    rationale: str
    input_payload: dict
    output_payload: dict


class SimulatedLLM:
    """Deterministic scripted stand-in for a model. It sees the REAL discovered tool metadata."""

    def propose(self, user_message: str, step: Step, tools: list[dict]) -> Decision:
        catalog = [{"name": t["name"], "description": t.get("description"), "inputSchema": t.get("inputSchema")}
                   for t in tools]
        in_catalog = step.tool in {t["name"] for t in tools}
        arguments = step.arguments or {}
        return Decision(
            tool=step.tool or "",
            arguments=arguments,
            rationale=(f"Scripted by the scenario: call '{step.tool}'. "
                       f"That tool {'is' if in_catalog else 'is NOT'} in the catalog the host supplied."),
            input_payload={"user_message": user_message, "available_tools": catalog},
            output_payload={"type": "tool_use", "name": step.tool, "arguments": arguments},
        )

    def interpret(self, summary: str) -> dict:
        return {"input": {"tool_result_summary": summary},
                "output": {"type": "text", "text": f"Noted the tool outcome: {summary}"}}

    def final(self, template: str | None, summary: str) -> dict:
        text = (template or "{summary}").replace("{summary}", summary)
        return {"input": {"last_outcome": summary}, "output": {"type": "text", "text": text}}
