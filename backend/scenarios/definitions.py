from scenarios.models import PolicyConfig, Scenario, Step


def connect(mode: str = "auto", script: str | None = None) -> Step:
    return Step(type="connect", mode=mode, script=script)


def discover() -> Step:
    return Step(type="discover")


def call(tool: str, arguments: dict | None = None) -> Step:
    return Step(type="propose_and_call", tool=tool, arguments=arguments or {})


def raw(method: str, params: dict | None = None, with_envelope: bool = True) -> Step:
    return Step(type="raw_request", method=method, params=params or {}, with_envelope=with_envelope)


def final(template: str = "Done. {summary}") -> Step:
    return Step(type="final", template=template)


SCENARIOS: list[Scenario] = [
    Scenario(
        id="discover_tools", title="Discover the server's tools", category="discovery",
        description="Connect and list tools; no tool call.",
        user_message="What can this server do?",
        expected="server/discover (modern connect), then tools/list; the host passes the catalog to the simulated LLM context.",
        steps=[connect(), discover(), final("The server exposes the discovered tools listed in the trace.")]),
    Scenario(
        id="calc_success", title="Successful tool call", category="success",
        description="Full happy path: discover, propose, policy, tools/call, result, final answer.",
        user_message="What is 17 plus 25?",
        expected="isError=false with structuredContent {result: 42.0}.",
        steps=[connect(), discover(), call("calculator", {"op": "add", "a": 17, "b": 25}),
               final("The answer is {summary}")]),
    Scenario(
        id="notes_workflow", title="Stateful notes workflow", category="success",
        description="Mutates server state (notes_add) and reads it back. Reset restores the seeded notes.",
        user_message="Save a note about stdio and then list my notes.",
        expected="notes_add returns id 3; notes_list shows three notes. Reset respawns the server and restores two.",
        steps=[connect(), discover(),
               call("notes_add", {"title": "stdio", "body": "Local transport over stdin/stdout."}),
               call("notes_list"), final("Saved and listed: {summary}")]),
    Scenario(
        id="unknown_tool", title="Unknown tool (host lets it through)", category="error",
        description="The simulated LLM proposes a tool that is not in the catalog; the host does not enforce the catalog.",
        user_message="What is the weather in Paris?",
        expected="The request reaches the server; in SDK 2.3.0 the reply is an isError result 'Unknown tool', not a JSON-RPC error.",
        steps=[connect(), discover(), call("weather_lookup", {"city": "Paris"}), final("Outcome: {summary}")]),
    Scenario(
        id="unknown_tool_blocked", title="Unknown tool (host enforces catalog)", category="policy",
        description="Same proposal, but host policy checks the discovered catalog first.",
        user_message="What is the weather in Paris?",
        expected="Host policy rejects; the request is never sent to the server.",
        policy=PolicyConfig(enforce_catalog=True),
        steps=[connect(), discover(), call("weather_lookup", {"city": "Paris"}), final("Outcome: {summary}")]),
    Scenario(
        id="missing_argument", title="Missing required argument", category="validation",
        description="calculator is called without 'b'.",
        user_message="Add 5 to something.",
        expected="Reached the server; isError result with category invalid_arguments (not a JSON-RPC error).",
        steps=[connect(), discover(), call("calculator", {"op": "add", "a": 5}), final("Outcome: {summary}")]),
    Scenario(
        id="wrong_type", title="Argument of the wrong type", category="validation",
        description="calculator is called with a='seven'.",
        user_message="Add seven and three.",
        expected="isError result, category invalid_arguments; handler never ran (no handler events).",
        steps=[connect(), discover(), call("calculator", {"op": "add", "a": "seven", "b": 3}),
               final("Outcome: {summary}")]),
    Scenario(
        id="invalid_value", title="Invalid schema value", category="validation",
        description="op='power' violates the input schema enum; also exercises text_stats max_length.",
        user_message="Raise 2 to the 10th power.",
        expected="isError result, category invalid_arguments; handler never ran.",
        steps=[connect(), discover(), call("calculator", {"op": "power", "a": 2, "b": 10}),
               call("text_stats", {"text": "x" * 201}), final("Outcome: {summary}")]),
    Scenario(
        id="policy_rejection", title="Host policy rejection", category="policy",
        description="Host policy limits numeric arguments to 1000.",
        user_message="What is 1,000,000,000 times 3?",
        expected="Host rejects before the client; no JSON-RPC request is sent for the call.",
        policy=PolicyConfig(max_abs_number=1000),
        steps=[connect(), discover(), call("calculator", {"op": "multiply", "a": 1000000000, "b": 3}),
               final("Outcome: {summary}")]),
    Scenario(
        id="tool_exception", title="Tool execution failure", category="error",
        description="calculator divides by zero, and always_fails raises.",
        user_message="Divide 10 by 0.",
        expected="Handler ran and raised; isError result with category tool_exception.",
        steps=[connect(), discover(), call("calculator", {"op": "divide", "a": 10, "b": 0}),
               call("always_fails"), final("Outcome: {summary}")]),
    Scenario(
        id="business_negative", title="Negative application result", category="success",
        description="notes_get for a missing id returns found=false as a NORMAL result.",
        user_message="Show me note 999.",
        expected="isError=false with structuredContent {found: false}; not an error at any layer.",
        steps=[connect(), discover(), call("notes_get", {"note_id": 999}), final("Outcome: {summary}")]),
    Scenario(
        id="invalid_method", title="Invalid protocol request: unknown method", category="protocol",
        description="Sends a raw JSON-RPC request for a method that does not exist.",
        user_message="(debug) Send a request for 'bogus/method'.",
        expected="A real JSON-RPC error -32601 Method not found; tool-call paths are not involved.",
        steps=[connect(), raw("bogus/method"), final("Outcome: {summary}")]),
    Scenario(
        id="invalid_envelope", title="Invalid protocol request: missing _meta envelope", category="protocol",
        description="Sends tools/call without the modern per-request _meta envelope.",
        user_message="(debug) Send tools/call without protocol metadata.",
        expected="A real JSON-RPC error -32602; modern (2026-07-28) requests must carry _meta.",
        steps=[connect(), raw("tools/call", {"name": "calculator", "arguments": {"op": "add", "a": 1, "b": 2}},
                              with_envelope=False), final("Outcome: {summary}")]),
    Scenario(
        id="transport_failure", title="Transport / server connection failure", category="transport",
        description="The client is pointed at a server script that does not exist.",
        user_message="(debug) Connect to a broken server.",
        expected="Transport-level failure; the request never reached an MCP server (reached_server=false).",
        steps=[connect(script="does_not_exist.py"), final("unreachable")]),
    Scenario(
        id="legacy_handshake", title="Legacy handshake (comparison)", category="legacy",
        description="Forces the legacy initialize handshake instead of server/discover.",
        user_message="What is 2 plus 2? (legacy connection)",
        expected="Wire shows initialize then notifications/initialized, labeled legacy; negotiated version 2025-11-25.",
        steps=[connect("legacy"), discover(), call("calculator", {"op": "add", "a": 2, "b": 2}),
               final("The answer is {summary}")]),
]

_BY_ID = {s.id: s for s in SCENARIOS}


def get_scenario(scenario_id: str) -> Scenario | None:
    return _BY_ID.get(scenario_id)
