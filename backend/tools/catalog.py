from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CalcResult(BaseModel):
    result: float
    expression: str


class TextStats(BaseModel):
    characters: int
    words: int
    lines: int


class Note(BaseModel):
    id: int
    title: str
    body: str


class NoteList(BaseModel):
    notes: list[Note]


class NoteLookup(BaseModel):
    found: bool
    note: Note | None = None


# Deterministic fixture. It lives in the server subprocess, so reset (respawn) restores it.
_notes: list[Note] = [
    Note(id=1, title="MCP basics", body="Hosts own clients; clients talk to servers."),
    Note(id=2, title="Transports", body="stdio for local use, Streamable HTTP for remote."),
]


def calculator(op: Literal["add", "subtract", "multiply", "divide"], a: float, b: float) -> CalcResult:
    """Apply an arithmetic operation to two numbers. Division by zero raises a tool execution error."""
    symbols = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}
    if op == "add":
        value = a + b
    elif op == "subtract":
        value = a - b
    elif op == "multiply":
        value = a * b
    else:
        if b == 0:
            raise ValueError("Division by zero is not defined")
        value = a / b
    return CalcResult(result=value, expression=f"{a} {symbols[op]} {b}")


def text_stats(text: Annotated[str, Field(max_length=200)]) -> TextStats:
    """Count characters, words and lines in a text of at most 200 characters."""
    return TextStats(characters=len(text), words=len(text.split()), lines=len(text.splitlines()) or 1)


def notes_add(
    title: Annotated[str, Field(min_length=1, max_length=60)],
    body: Annotated[str, Field(max_length=200)],
) -> Note:
    """Add a note to the in-memory store and return it. State persists until the session is reset."""
    note = Note(id=max((n.id for n in _notes), default=0) + 1, title=title, body=body)
    _notes.append(note)
    return note


def notes_list() -> NoteList:
    """List all notes in the in-memory store."""
    return NoteList(notes=list(_notes))


def notes_get(note_id: int) -> NoteLookup:
    """Look up a note by id. A missing note is a normal result with found=false, not an error."""
    for note in _notes:
        if note.id == note_id:
            return NoteLookup(found=True, note=note)
    return NoteLookup(found=False)


def always_fails() -> str:
    """Always raises, to demonstrate a tool execution error."""
    raise RuntimeError("This tool always fails on purpose")


TOOL_FUNCTIONS = [calculator, text_stats, notes_add, notes_list, notes_get, always_fails]


def register_tools(mcp, wrap=lambda fn: fn) -> None:
    """Register every handler on the given MCPServer. `wrap` lets the server add tracing."""
    for fn in TOOL_FUNCTIONS:
        mcp.tool()(wrap(fn))
