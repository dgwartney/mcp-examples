# Extending the Project

## Adding New Tools

Subclass `AuthenticatedMCPServer` and implement `_register_tools()`. Edit `mcp_examples/server.py`:

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
