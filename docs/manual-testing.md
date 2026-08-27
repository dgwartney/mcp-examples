# Manual Testing Guide

This guide walks you through **manually** creating and exercising MCP servers built
with `mcp-server-kit`, end to end. It is meant to complement the automated suite
([docs/testing.md](testing.md)) — here you actually start a server, retrieve its
API key, and call tools over HTTP the way [Kore.ai Agent Platform (Artemis)] or any
other MCP client would.

You will test three things:

1. A **standalone server** — a single `AuthenticatedMCPServer` subclass exposed at
   one `/mcp` endpoint.
2. A **combined server** — several servers mounted under one process, each at its
   own URL prefix (`/greet/mcp`, `/contacts/mcp`, …).
3. **Scaffold-generated projects** — brand-new projects produced by
   `mcp-server-kit new`, to confirm the package works for a downstream user.

> **uv only — never pip.** Every command below uses `uv`. If `uv` is missing,
> install it with the official installer:
> `curl -LsSf https://astral.sh/uv/install.sh | sh`.

---

## 0. Prerequisites

```bash
# From a clone of this repo
uv sync --extra test
```

Two helpers are used throughout:

- **`jq`** — pretty-prints the JSON-RPC responses (`brew install jq` on macOS).
- **`sqlite3`** — reads the generated API key out of the key database (ships with macOS).

Every HTTP request to a server requires an `X-API-Key` header. The kit generates a
random key the first time a server initializes its SQLite key store, and logs it at
`INFO` on the `mcp_server_kit.database` logger. The most reliable way to retrieve it
is to read it straight from the database (shown below).

---

## 1. Standalone server

A standalone server is a single subclass run directly. We'll use the bundled
`ContactMCPServer` (it seeds mock CRM data, so tool calls return real results with no
external API keys).

### 1.1 Start the server

In terminal **A**, from the repo root:

```bash
# Use a dedicated key DB so we know exactly which key to send.
MCP_DB_PATH="$PWD/standalone_keys.db" \
  uv run -m mcp_server_kit.contacts --transport streamable-http --port 8000
```

The server is now listening at `http://localhost:8000/mcp`.

### 1.2 Retrieve the API key

In terminal **B**:

```bash
API_KEY=$(sqlite3 "$PWD/standalone_keys.db" "SELECT key FROM api_keys LIMIT 1;")
echo "$API_KEY"
```

### 1.3 Verify auth is enforced

A request with **no** key must be rejected with `401`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
# expect: 401
```

### 1.4 Exercise the tools with curl

The repo ships a ready-made script that runs the full MCP handshake (initialize →
initialized → tool calls) against the contact server:

```bash
API_KEY="$API_KEY" ./test_curl.sh
```

Expected: a session ID is printed, then four tool calls
(`search_by_email`, `search_by_last_name`, `search_by_account_id`, `authenticate`)
each return contact data as pretty-printed JSON, ending with `=== All tests complete ===`.

### 1.5 Exercise the tools with the Python client

The kit also ships an MCP client. Point it at the standalone endpoint:

```bash
uv run -m mcp_server_kit.cli \
  --api-key "$API_KEY" \
  --url http://localhost:8000/mcp \
  --name Ada
```

> The bundled CLI (`mcp_server_kit.cli`) calls the `greet` tool, which lives on the
> **greet** server, not the contact server. To hit the contact server here, run the
> greet server standalone instead:
> `MCP_DB_PATH="$PWD/standalone_keys.db" uv run -m mcp_server_kit.server --transport streamable-http --port 8000`
> then re-run the CLI above — you should see a greeting for `Ada`.

For calling arbitrary tools programmatically, use `MCPClient` directly:

```bash
uv run python - <<'PY'
import asyncio, os
from mcp_server_kit.client import MCPClient

async def main():
    client = MCPClient("http://localhost:8000/mcp", os.environ["API_KEY"])
    result = await client.call_tool("search_by_last_name", {"last_name": "Webb"})
    print(result.data)

asyncio.run(main())
PY
```

Stop the server in terminal **A** with `Ctrl-C` when finished.

---

## 2. Combined server

The combined app mounts every server in `SERVER_REGISTRY` under its own path
(`/greet/mcp`, `/contacts/mcp`, `/wikipedia/mcp`, `/weather/mcp`, `/messaging/mcp`).
This is the entry point used for deployment and for Artemis.

### 2.1 Start the combined app

In terminal **A**:

```bash
MCP_DB_PATH="$PWD/combined_keys.db" \
  uv run -m mcp_server_kit.combined --port 8000
```

> `weather` and `twilio` need external-service env vars (`OPENWEATHER_API_KEY`,
> `TWILIO_ACCOUNT_SID`, …) to *function*, but the app still starts and mounts them
> without those vars — their `/mcp` endpoints answer tool discovery just fine, so you
> can verify mounting/auth without any secrets.

### 2.2 Retrieve the API key

All mounted servers share the one key DB, so a single key works for every prefix:

```bash
API_KEY=$(sqlite3 "$PWD/combined_keys.db" "SELECT key FROM api_keys LIMIT 1;")
```

### 2.3 Verify each endpoint is mounted and auth-guarded

```bash
for prefix in greet contacts wikipedia weather twilio; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "http://localhost:8000/$prefix/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
  echo "$prefix/mcp (no key) -> $code   (expect 401)"
done

# An unmounted path must 404:
curl -s -o /dev/null -w "unknown/mcp -> %{http_code}   (expect 404)\n" -X POST \
  http://localhost:8000/unknown/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### 2.4 List tools on a mounted server (with key)

> **Note:** `streamable-http` is session-based. A bare `tools/list` POST returns
> `Bad Request: Missing session ID` — you must first `initialize` to get an
> `Mcp-Session-Id`, then send `notifications/initialized`, then `tools/list`
> (that is exactly what `test_curl.sh` does). The easiest way to just list tools
> is the fastmcp client, which performs the handshake for you:

```bash
API_KEY="$API_KEY" uv run python - <<'PY'
import asyncio, os
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        "http://localhost:8000/contacts/mcp",
        headers={"X-API-Key": os.environ["API_KEY"]},
    )
    async with Client(transport) as client:
        print([t.name for t in await client.list_tools()])

asyncio.run(main())
PY
```

Expected: the contact server's tool names
(`search_by_email`, `search_by_last_name`, `search_by_account_id`, `authenticate`).

### 2.5 Full handshake against a combined endpoint

`test_curl.sh` targets `http://localhost:8000/mcp`; for the combined app, point it at
a prefixed path by overriding the base URL inline:

```bash
API_KEY="$API_KEY" BASE_URL="http://localhost:8000/contacts/mcp" \
  bash -c 'sed "s#http://localhost:8000/mcp#$BASE_URL#" test_curl.sh | bash'
```

Or drive it with the Python client:

```bash
uv run -m mcp_server_kit.cli \
  --api-key "$API_KEY" \
  --url http://localhost:8000/greet/mcp \
  --name Ada
```

Stop the server with `Ctrl-C` when done.

---

## 3. Scaffold-generated projects

This section proves the *package itself* produces working projects for a
downstream user — the real "from scratch" test. Generate the projects **outside**
the repo tree so nothing leaks into this checkout.

### 3.1 Standalone (single-server) project

`mcp-server-kit new` creates a self-contained project. With `--no-examples` it emits
just `MyServer` (a single `add` tool) mounted at `/my_server/mcp`. With
`--standalone` it vendors the base classes so the project has **no** dependency on
`mcp-server-kit` at all.

```bash
cd /tmp
uv run --project /Users/dgwartney/git/mcp-examples \
  python -m mcp_server_kit.scaffold new my-standalone --standalone --no-examples

cd my-standalone
uv sync --extra test
uv run pytest                       # generated tests must pass
uv run python -m my_standalone.combined --port 8100 &   # serves /my_server/mcp
sleep 2
```

Retrieve the key and call the generated `add` tool:

```bash
API_KEY=$(sqlite3 "$PWD/api_keys.db" "SELECT key FROM api_keys LIMIT 1;")

# 401 without a key:
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8100/my_server/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'   # expect 401

# List tools with the key via the fastmcp client (handles the session handshake).
# Expect the generated "add" tool:
API_KEY="$API_KEY" uv run python - <<'PY'
import asyncio, os
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        "http://localhost:8100/my_server/mcp",
        headers={"X-API-Key": os.environ["API_KEY"]},
    )
    async with Client(transport) as client:
        print([t.name for t in await client.list_tools()])

asyncio.run(main())
PY
```

Because `--standalone` was used, confirm the project stands alone (the dependency
line is gone — the string still appears once in the project description, so match the
quoted dependency spec, not a bare substring):

```bash
grep -c '"mcp-server-kit' pyproject.toml   # expect 0
ls my_standalone/_base                     # base.py, database.py, middleware.py vendored
```

Stop the background server: `kill %1`.

### 3.2 Combined project (with bundled examples)

Including bundled servers produces a genuine combined app: your `MyServer` plus each
chosen example, each at its own prefix. (Bundled servers import from
`mcp-server-kit`, so the dependency is kept — expected.)

```bash
cd /tmp
uv run --project /Users/dgwartney/git/mcp-examples \
  python -m mcp_server_kit.scaffold new my-combined --with-examples greet,contacts

cd my-combined
uv sync --extra test
uv run pytest
uv run python -m my_combined.combined --port 8200 &
sleep 2

API_KEY=$(sqlite3 "$PWD/api_keys.db" "SELECT key FROM api_keys LIMIT 1;")
for prefix in my_server greet contacts; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "http://localhost:8200/$prefix/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
  echo "$prefix/mcp (no key) -> $code   (expect 401)"
done
kill %1
```

All three prefixes should return `401` (mounted + auth-guarded).

### 3.3 In-repo contributor mode (`add-server`)

To test adding a server to *this* repo (as a contributor would), from the repo root:

```bash
uv run python -m mcp_server_kit.scaffold add-server Inventory
# or the wrapper:  uv run python scripts/new_server.py Inventory

uv run pytest tests/test_inventory.py     # generated skeleton passes
grep -n "Inventory" mcp_server_kit/combined.py mcp_server_kit/__init__.py
```

Expected: a new `mcp_server_kit/inventory.py`, a `tests/test_inventory.py`, and
`InventoryMCPServer` registered in both `combined.py`'s `SERVER_REGISTRY` and
`__init__.py`. Revert with `git checkout .` / `git clean -fd` when done experimenting.

---

## 4. Cleanup

```bash
# Remove key databases created during manual testing (from the repo root)
rm -f standalone_keys.db combined_keys.db api_keys.db

# Remove scaffold experiments
rm -rf /tmp/my-standalone /tmp/my-combined

# Undo an add-server experiment in the repo
git checkout . && git clean -fd
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `curl` returns `401` even with a key | Wrong key DB. Re-read the key from the same `MCP_DB_PATH`/`api_keys.db` the server used. |
| `curl` returns `406 Not Acceptable` | Missing `Accept: application/json, text/event-stream` header. |
| `jq` shows nothing | Responses are SSE-framed; keep the `sed -n 's/^data: //p'` filter before `jq`. |
| No key printed on startup | The key is only generated on **first** init of a DB, and is logged at `INFO`, not printed. Read it from the DB with `sqlite3`. |
| `weather`/`twilio` tool calls error | Those servers need `OPENWEATHER_API_KEY` / `TWILIO_*` env vars set to actually call their APIs. Discovery/auth still works without them. |
| Port already in use | Pick another `--port`, or stop the previous server. |

[Kore.ai Agent Platform (Artemis)]: https://docs.kore.ai/agent-platform/tools/mcp
