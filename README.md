# MCP Lab: an interactive MCP protocol debugger

Status: **design approved, implementation not started.** See the design spec in
`docs/superpowers/specs/2026-10-11-mcp-lab-design.md`.

## Pinned versions
- Python SDK: `mcp==2.3.0`
- MCP spec: `2026-07-28` (modern, `server/discover`). Handshake-era versions
  (`2024-11-05` to `2025-11-25`, `initialize`) are shown only as labeled *legacy*.

## Setup (you run these; nothing is installed for you)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py          # FastAPI on http://localhost:8000  (added during implementation)
```
```bash
cd frontend
npm install
npm run dev            # Vite UI on http://localhost:5173
```

## Layout
- `backend/` host, client, server, tools, schemas, transports, simulation,
  scenarios, events. Run everything from inside `backend/`.
- `frontend/` React + TypeScript + Vite control panel. It owns no tools or scenarios.
- `docs/` design spec and implementation plan.
