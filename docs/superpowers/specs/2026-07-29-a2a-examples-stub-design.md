# a2a-examples stub repo — design

Date: 2026-07-29
Status: approved

## Purpose

Create a new, separate repository `a2a-examples` (sibling to `mcp-examples` at
`/Users/dgwartney/git/a2a-examples`) that provides a reusable framework for building
future A2A (Agent2Agent protocol) agents, the same way `mcp-examples`/`mcp_server_kit`
provides a reusable framework for building MCP servers. This is a stub/template: one
base class, one trivial example agent, tests, docs, and deployment scaffolding — not a
production agent.

## Stack

- **Microsoft Agent Framework** (`agent-framework`, `agent-framework-a2a`) on top of the
  official `a2a-sdk` — the same combination already proven in the local
  `~/git/microsoft-a2a-agent` repo. `agent-framework-a2a` wraps `a2a-sdk`'s
  `AgentExecutor` / `A2AStarletteApplication` / `DefaultRequestHandler` machinery.
- `uv`-managed, Python `>=3.10`, matching `mcp-examples` tooling conventions exactly:
  `uv sync`, `uv run`, `uv build`, `pytest` via `uv run pytest` — never `pip`.
- Build backend: `hatchling`, same as `mcp-examples/pyproject.toml`.

## Repository layout

```
a2a-examples/
  a2a_agent_kit/
    __init__.py          # re-exports public classes; __version__
    database.py          # DatabaseManager — ported verbatim from mcp_server_kit
    middleware.py         # ApiKeyMiddleware — ported verbatim from mcp_server_kit
    base.py               # AuthenticatedA2AAgent abstract base class
    greet_agent.py        # GreetA2AAgent — the one example agent
    client.py             # A2AClientWrapper
    cli.py                # A2AClientApp + main()
  tests/
    test_database.py
    test_middleware.py
    test_greet_agent.py
    test_client.py
  docs/
    agents.md             # per-agent reference, parallel to mcp-examples/docs/servers.md
    extending.md           # "Adding a New Agent" checklist, parallel to mcp-examples' TODO item 4
  scripts/                 # placeholder, empty for now (no scaffold generator yet — YAGNI)
  Dockerfile
  fly.toml
  pyproject.toml
  pytest.ini               # copied/adapted from mcp-examples, source=a2a_agent_kit
  README.md
  LICENSE                  # MIT, same as mcp-examples
  CLAUDE.md
  .gitignore
```

No `combined.py` / multi-agent mount. A2A's deployment unit is one `AgentCard` at one
base URL (agent discovery is via `GET /.well-known/agent-card.json`), unlike MCP where
several independent tool servers can be multiplexed under one Starlette app at different
sub-paths. Mounting multiple A2A agents behind one process would require each to publish
its own agent-card route and is not idiomatic — future agents each get their own module
and their own deployment, following the pattern this stub establishes with one agent.

## Component design

### `database.py` — `DatabaseManager`

Ported verbatim from `mcp_server_kit/database.py`. It's already generic (SQLite-backed
API key CRUD/validation with no MCP dependency): `init_db()` creates the `api_keys`
table and seeds a random default key (logged via `logging`, never printed), and
`validate_key(api_key)` checks membership. Only docstring authorship/module path
references change.

### `middleware.py` — `ApiKeyMiddleware`

Ported verbatim from `mcp_server_kit/middleware.py`. Pure Starlette
`BaseHTTPMiddleware` reading the `X-API-Key` header and returning 401 JSON on
failure — no MCP dependency, so it plugs directly onto the Starlette app that
`A2AStarletteApplication.build()` returns (that build() has no native auth hook, so
`app.add_middleware(...)` after `build()` is how auth gets wired in, mirroring how
`mcp_server_kit.base` passes `_http_middleware` into `FastMCP.run()`).

### `base.py` — `AuthenticatedA2AAgent`

Abstract base class, structurally parallel to `AuthenticatedMCPServer`:

- `__init__(self, name, db_path=None)`: resolves `db_path` from an `A2A_DB_PATH` env var
  (mirrors `MCP_DB_PATH`) defaulting to `api_keys.db` in cwd; constructs
  `DatabaseManager`, calls `init_db()`; builds the `ChatAgent` via the abstract
  `_create_chat_agent()` hook; wraps it in an internal `AgentExecutor` subclass that
  bridges A2A `RequestContext`/`EventQueue` to `ChatAgent.run()` (same bridging logic as
  `microsoft-a2a-agent/src/msaf_a2a_agent/server.py::A2AAgentExecutor`, generalized to
  take any `ChatAgent`); builds the `AgentCard` via the abstract `_agent_card_info()`
  hook (returns name/description/skills; url/version/capabilities are filled in by the
  base class).
- `_create_chat_agent(self) -> ChatAgent` (abstract): subclasses provide the chat
  client, instructions, and tools.
- `_agent_card_info(self) -> dict` (abstract): subclasses provide `description` and a
  list of `AgentSkill`.
- `build_app(self, host, port, url=None) -> Starlette`: builds `InMemoryTaskStore`,
  `DefaultRequestHandler`, `A2AStarletteApplication`, calls `.build()`, then
  `app.add_middleware(ApiKeyMiddleware, db_manager=self.db_manager)`.
- `serve(self, host="0.0.0.0", port=8000, url=None)`: calls `build_app()` and
  `uvicorn.run(...)`, printing the agent-card URL — parallel to
  `AuthenticatedMCPServer.run()`.
- `main(self)`: argparse with `--host`, `--port`, `--url` (no `--transport` — A2A here is
  HTTP-only, unlike MCP's stdio/sse/streamable-http choice), parallel to
  `AuthenticatedMCPServer.main()`.

No `lazy_module_instances()` equivalent is needed yet — A2A agent construction talks to
Azure OpenAI credentials at chat-agent-build time in the reference implementation, but
the stub's example agent needs no external API key, so building at module import time is
safe. If a future real agent needs lazy construction (e.g. to avoid failing at import
without credentials), it can add its own `__getattr__`, following the documented pattern
in `mcp_server_kit/base.py`, without needing it baked into the base class now.

### `greet_agent.py` — `GreetA2AAgent`

The one concrete example, mirroring `GreetMCPServer`. `_create_chat_agent()` returns a
`ChatAgent` with a single trivial tool (`def greet(name: str) -> str: return f"Hello,
{name}!"`) — no external chat-completion backend call required for the tool path itself,
but `ChatAgent` still needs *some* `chat_client`; use whatever lightweight in-repo/test
double the Microsoft Agent Framework provides for this (checked during implementation —
if no built-in test double exists, the example instructions keep the agent's job trivial
enough that a real but cheap model call is acceptable, same as any first-run demo). The
`_agent_card_info()` returns a `"greet"` skill.

### `client.py` — `A2AClientWrapper`

Thin async wrapper using the modern (non-deprecated) A2A client API: build an
`httpx.AsyncClient` with `X-API-Key` header, resolve the `AgentCard` via
`A2ACardResolver`, build a client via `ClientFactory`, send a message built with
`create_text_message_object(text)`, and return the reply text — parallel to
`MCPClient.call_tool()` / `MCPClient.greet()`.

### `cli.py` — `A2AClientApp` / `main()`

Same shape as `mcp_server_kit/cli.py`: `--api-key` (required), `--name` (default
`"Ford"`), `--url` (default placeholder ngrok-style URL), calls the wrapper's greet
convenience method and prints the result.

## Testing

- `test_database.py`, `test_middleware.py`: ported from the `mcp-examples` equivalents
  (if present) or written fresh against the ported modules — same behavior, so same
  test shape.
- `test_greet_agent.py`: drives the `AgentExecutor.execute()` bridge directly against a
  fake `EventQueue`/`RequestContext` (no live network, no live model call), asserting a
  `TaskStatusUpdateEvent` with `state=working` then `state=completed` and the greeting
  text — analogous in spirit to `tests/test_combined.py`'s use of fakes/monkeypatch to
  avoid real I/O.
- `test_client.py`: unit tests the wrapper against a mocked transport/response, not a
  live agent.
- `pytest.ini`: adapted from `mcp-examples/pytest.ini`, with `--cov=a2a_agent_kit` and
  `testpaths = tests`.

## Docs

- `docs/agents.md`: per-agent reference (tools, required env vars, skills) — parallel to
  `mcp-examples/docs/servers.md`.
- `docs/extending.md`: an explicit "Adding a New Agent" checklist (new module → register
  its own entry point/deployment target → add `docs/agents.md` entry → write tests →
  `curl` the `/.well-known/agent-card.json` and message endpoint directly → register with
  whatever external platform consumes it) — addressing the same gap flagged as TODO item
  4 in `mcp-examples/CLAUDE.md`, but written into this new repo from day one instead of
  retrofitted later.
- `README.md`: adapted from `mcp-examples/README.md`'s structure (setup, run, test
  sections) for the A2A stack.
- `CLAUDE.md`: adapted from this repo's `CLAUDE.md` — project overview, setup/commands
  (`uv sync`, `uv run -m a2a_agent_kit.greet_agent`, `uv run pytest`), architecture
  section listing each module, "uv only" rule carried over verbatim.

## Deployment

- `Dockerfile`: adapted from `mcp-examples/Dockerfile` — same `python:3.12-slim` base,
  `uv sync --frozen --no-dev`, `/data` volume for the SQLite key store, `CMD ["uv",
  "run", "-m", "a2a_agent_kit.greet_agent", "--port", "8000", "--host", "0.0.0.0"]`.
- `fly.toml`: adapted from `mcp-examples/fly.toml` — app name `a2a-agent-kit`,
  `A2A_DB_PATH=/data/api_keys.db`, same `[http_service]`/`[[mounts]]` shape.

## Out of scope (explicitly deferred, not part of this stub)

- Scaffold/generator script (`scripts/new_agent.py`) — mirrors `mcp-examples`'
  `mcp_server_kit/scaffold.py` and its own TODO item 3; worth doing once there's a second
  real agent to prove the generator against, not before.
- Multi-agent combined mount — ruled out above as non-idiomatic for A2A.
- Any real external API integration (weather, contacts, messaging, etc.) — the stub ships
  exactly one trivial example agent.

## Open technical risk to validate during implementation

`ChatAgent` in Microsoft Agent Framework needs a `chat_client`; confirm during
implementation whether a no-network test double / local echo client exists, or whether
the example agent's tool call still routes through a real (if cheap) model call. This
does not change the design — only which concrete `chat_client` `GreetA2AAgent` wires up —
so it's noted here rather than blocking design approval.
