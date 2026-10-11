import json

from client.lab_client import ClientError, LabClient
from events.model import ErrorInfo
from events.recorder import Recorder
from host.policy import Policy


def summarize(outcome: dict) -> str:
    if outcome["outcome"] == "protocol_error":
        return f"Protocol error {outcome['code']}: {outcome['message']}"
    if outcome["outcome"] == "blocked":
        return f"The host blocked the call: {outcome['reason']}"
    if outcome["is_error"]:
        return f"Tool call failed ({outcome['category']}): {outcome['text'][:200]}"
    return json.dumps(outcome["structured"], ensure_ascii=False) if outcome["structured"] else outcome["text"]


class Host:
    """Application-level orchestration. Talks only to the MCP client; never to tool handlers."""

    def __init__(self, client: LabClient, llm, rec: Recorder):
        self.client, self.llm, self.rec = client, llm, rec
        self.tools: list[dict] | None = None

    async def connect(self, mode: str = "auto", script: str | None = None) -> dict:
        self.rec.emit("host", "request_connect", "completed", "host_internal",
                      f"Host asks the MCP client to connect (mode={mode})")
        return await self.client.connect(mode, script)

    async def discover(self) -> list[dict]:
        self.rec.emit("host", "request_discovery", "completed", "host_internal",
                      "Host asks the MCP client to discover the server's tools")
        self.tools = await self.client.list_tools()
        return self.tools

    async def invoke(self, tool: str, arguments: dict, policy: Policy | None = None) -> dict:
        """Apply host policy, then ask the client to execute."""
        policy = policy or Policy()
        names = {t["name"] for t in self.tools or []}
        verdict = policy.check(tool, arguments, names)
        if not verdict.allowed:
            error = ErrorInfo(layer="host", category="policy_rejection", message=verdict.reason, reached_server=False)
            self.rec.emit("host", "policy_check", "failed", "host_internal",
                          f"Host policy rejected the call: {verdict.reason}. The request was never sent to the server.",
                          data={"tool": tool, "arguments": arguments}, error=error)
            return {"outcome": "blocked", "reason": verdict.reason}
        self.rec.emit("host", "policy_check", "completed", "host_internal", "Host policy approved the call",
                      data={"tool": tool, "arguments": arguments})
        self.rec.emit("host", "dispatch_to_client", "started", "host_internal",
                      "Host asks the MCP client to execute the approved call")
        outcome = await self.client.call_tool(tool, arguments)
        failed = outcome["outcome"] == "protocol_error" or outcome.get("is_error")
        self.rec.emit("host", "receive_result", "failed" if failed else "completed", "host_internal",
                      "Host received the client's result: " + summarize(outcome)[:200], data=outcome)
        return outcome

    async def raw_request(self, method: str, params: dict | None = None, with_envelope: bool = True) -> dict:
        self.rec.emit("host", "dispatch_to_client", "started", "host_internal",
                      f"Host asks the client to send a raw '{method}' request (debug path, no LLM involved)")
        outcome = await self.client.send_raw(method, params, with_envelope)
        failed = outcome["outcome"] == "protocol_error"
        self.rec.emit("host", "receive_result", "failed" if failed else "completed", "host_internal",
                      "Host received: " + summarize(outcome)[:200], data=outcome)
        return outcome

    async def run(self, scenario) -> None:
        rec = self.rec
        policy = Policy(scenario.policy)
        summary, final_text = "", None
        rec.emit("user", "user_request", "completed", "host_internal", scenario.user_message,
                 data={"scenario_id": scenario.id, "title": scenario.title})
        rec.emit("host", "receive_request", "completed", "host_internal",
                 "Host received the request and loaded the scenario plan",
                 data={"steps": [s.type for s in scenario.steps], "policy": scenario.policy.model_dump()})
        try:
            for i, step in enumerate(scenario.steps, 1):
                rec.emit("host", "plan_step", "completed", "host_internal",
                         f"Step {i}/{len(scenario.steps)}: {step.type} (decided by the scenario configuration)",
                         data=step.model_dump(exclude_none=True))
                if step.type == "connect":
                    await self.connect(step.mode or "auto", step.script)
                elif step.type == "discover":
                    await self.discover()
                elif step.type == "raw_request":
                    summary = summarize(await self.raw_request(step.method, step.params, step.with_envelope))
                elif step.type == "propose_and_call":
                    if self.tools is None:
                        rec.emit("host", "auto_discover", "completed", "host_internal",
                                 "No catalog yet; the host discovers tools before consulting the LLM")
                        await self.discover()
                    rec.emit("host", "supply_tools_to_llm", "completed", "host_internal",
                             f"Host passes {len(self.tools)} discovered tool definitions to the simulated LLM",
                             data={"tool_names": [t["name"] for t in self.tools]})
                    decision = self.llm.propose(scenario.user_message, step, self.tools)
                    rec.emit("llm", "llm_input", "completed", "simulated",
                             "SIMULATED inference input: user message plus the real discovered tool definitions",
                             direction="request", data=decision.input_payload)
                    rec.emit("llm", "llm_output", "completed", "simulated",
                             "SIMULATED inference output (scripted tool-call proposal). " + decision.rationale,
                             direction="response", data=decision.output_payload)
                    outcome = await self.invoke(decision.tool, decision.arguments, policy)
                    summary = summarize(outcome)
                    interp = self.llm.interpret(summary)
                    rec.emit("llm", "llm_input", "completed", "simulated",
                             "SIMULATED inference input: the host's tool result",
                             direction="request", data=interp["input"])
                    rec.emit("llm", "llm_output", "completed", "simulated",
                             "SIMULATED inference output (scripted)", direction="response", data=interp["output"])
                elif step.type == "final":
                    out = self.llm.final(step.template, summary)
                    rec.emit("llm", "llm_output", "completed", "simulated",
                             "SIMULATED final response (scripted template)", direction="response", data=out["output"])
                    final_text = out["output"]["text"]
                    rec.emit("host", "final_response", "completed", "host_internal",
                             "Host produced the final response", data={"text": final_text})
            rec.emit("host", "run_complete", "completed", "host_internal", "Scenario finished",
                     data={"final_response": final_text})
        except ClientError as exc:
            rec.emit("host", "run_complete", "failed", "host_internal", f"Run aborted: {exc}",
                     error=ErrorInfo(layer="transport", category="run_aborted", message=str(exc), reached_server=False))
        except Exception as exc:  # noqa: BLE001
            rec.emit("host", "run_complete", "failed", "host_internal", f"Run aborted by an unexpected error: {exc}",
                     error=ErrorInfo(layer="host", category="unexpected_error", message=str(exc), reached_server=False))
