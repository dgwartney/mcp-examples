# Extending the Project

## Two ways to build a server

- **Start your own project (installed users):** `uv tool install mcp-server-kit`, then
  `mcp-server-kit new <project-dir>` generates a standalone project in your own
  directory. Use `--standalone` to vendor the base classes (no runtime dependency on
  mcp-server-kit), and choose which bundled example servers to include when prompted (or
  with `--with-examples`, `--all-examples`, `--no-examples`). Nothing below applies — the
  generated project is self-contained.
- **Extend *this* repo (contributors):** follow the checklist below, or run
  `mcp-server-kit add-server <Name>` (equivalently `uv run python scripts/new_server.py <Name>`)
  from a clone to automate steps 1–4.

## Adding a New Server

Follow this checklist when creating an entirely new server in this repo (as opposed to
adding a tool to an existing one — see [Adding New Tools](#adding-new-tools) below). The
step most often missed by hand is registering the new server in `combined.py` — that's
the step that actually exposes it to Artemis/Kore AI, so don't skip it.

1. **Create the module.** Copy `mcp_server_kit/_template.py` to `mcp_server_kit/<name>.py`
   and rename the class, or run the scaffold to automate steps 1-4:
   ```bash
   mcp-server-kit add-server <Name>
   # or, equivalently, from a clone without installing:
   uv run python scripts/new_server.py <Name>
   ```
2. **Implement your tools** in the new class's `_register_tools()` method (see
   [Adding New Tools](#adding-new-tools) below for the pattern).
3. **Register the server in `mcp_server_kit/combined.py`** — import the class and append
   `("<name>", <Name>MCPServer)` to `SERVER_REGISTRY`. **This is the step most often
   forgotten when done by hand** — without it, the server never gets mounted or exposed
   to Artemis. (The scaffold script does this automatically.)
4. **Register it in `mcp_server_kit/__init__.py`'s `__all__` and `_LAZY_IMPORTS`** so
   `from mcp_server_kit import <Name>MCPServer` works, matching every other server. Not
   required for the server to run — `combined.py` imports submodules directly — but
   skipping it leaves your server inconsistent with the rest of the package's public API.
   (Also automated by the scaffold script.)
5. **Add a section to `docs/servers.md`** documenting the new server's tools, required
   env vars, and any seed data — follow the existing per-server sections as a model.
6. **Write/extend tests** in `tests/test_<name>.py` (the scaffold script generates a
   skeleton to fill in). Model a bare server on `tests/test_server.py`, one with an
   external HTTP dependency on `tests/test_weather.py`, or one with a domain SQLite store
   on `tests/test_contacts.py`/`tests/test_contact_database.py`.
7. **Run the test suite**: `uv run pytest` — confirm everything passes and coverage holds.
8. **Curl the new endpoint locally** to sanity-check it end-to-end before touching Kore
   AI:
   ```bash
   uv run -m mcp_server_kit.combined --port 8000
   ```
   then follow the curl recipe in [Serving Multiple Servers on One Port](#serving-multiple-servers-on-one-port)
   below, substituting your new server's `/<name>/mcp` path.
9. **Register the new server as an MCP Tool in Kore AI** (Test → Import) — see
   [KORE_AI_INTEGRATION.md](../KORE_AI_INTEGRATION.md#configuring-in-kore-ai) for the
   full walkthrough.
10. **Remember to manually refresh in Kore AI** after any later change to the server's
    tools — Kore AI does not auto-detect server changes (see
    [KORE_AI_INTEGRATION.md](../KORE_AI_INTEGRATION.md#best-practices)).

## Adding New Tools

Subclass `AuthenticatedMCPServer` and implement `_register_tools()`. Edit `mcp_server_kit/server.py`:

```python
def _register_tools(self) -> None:
    @self.mcp.tool(description="A tool that greets a user by name")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    @self.mcp.tool(description="Add two numbers")
    def add(a: int, b: int) -> int:
        return a + b

    @self.mcp.tool(description="Get current timestamp")
    def timestamp() -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat()
```

## Custom Authentication

To implement a different authentication scheme, create a new middleware class:

```python
class BearerTokenMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        headers = get_http_headers()
        headers_lower = {k.lower(): v for k, v in headers.items()}
        auth_header = headers_lower.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            raise ToolError("Unauthorized: Missing or invalid token")

        token = auth_header[7:]  # Remove "Bearer " prefix
        # Validate token...

        return await call_next(context)
```

## Serving Multiple Servers on One Port

FastMCP supports **mounting** multiple servers into a single parent, letting you serve them all on one port with namespaced tools:

```python
from fastmcp import FastMCP

main = FastMCP("Main")
users = FastMCP("Users")
orders = FastMCP("Orders")

@users.tool
def get_user(id: int): ...

@orders.tool
def get_order(id: int): ...

main.mount("users", users)
main.mount("orders", orders)

main.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

Tools are automatically namespaced (e.g., `users_get_user`, `orders_get_order`). Use `as_proxy=True` to run a mounted server as a separate proxied process:

```python
main.mount("users", users, as_proxy=True)
```

See the [FastMCP composition docs](https://gofastmcp.com/servers/composition) for more details.

### curl example with mounted servers

**Step 1 — Initialize the session:**
```bash
curl -s -D /tmp/mcp_headers -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "curl-client", "version": "1.0"}
    }
  }'

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | awk '{print $2}' | tr -d '\r')
```

**Step 2 — Send the initialized notification:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
```

**Step 3 — List available tools:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'
```

**Step 4 — Call a namespaced tool:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {"name": "users_get_user", "arguments": {"id": 42}}
  }'
```

## Adding Resources

FastMCP also supports resources (read-only data sources):

```python
@self.mcp.resource("config://settings")
def get_settings() -> str:
    return json.dumps({"version": "1.0", "env": "production"})
```
