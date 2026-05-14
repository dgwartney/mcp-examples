# Clients

## Built-in client (`mcp-client`)

The project includes a minimal Python client (`mcp_examples/cli.py`) that connects to a running HTTP server and calls the `greet` tool. It does **not** support the contact server tools.

> To interact with contact server tools (`search_by_last_name`, `search_by_email`, `search_by_account_id`, `authenticate`), use `fastmcp dev` (interactive browser UI) or `curl` (see below).

### Basic usage

```bash
uv run -m mcp_examples.cli --api-key YOUR_API_KEY_HERE
```

### Parameters

```bash
# Custom name
uv run -m mcp_examples.cli --api-key YOUR_API_KEY --name Alice

# Custom server URL
uv run -m mcp_examples.cli --api-key YOUR_API_KEY --url http://localhost:8000/mcp

# All parameters (macOS)
uv run -m mcp_examples.cli \
  --api-key YOUR_API_KEY \
  --name Bob \
  --url http://localhost:8000/mcp

# All parameters (Windows PowerShell)
uv run -m mcp_examples.cli `
  --api-key YOUR_API_KEY `
  --name Bob `
  --url http://localhost:8000/mcp
```

### Example output

```
$ uv run -m mcp_examples.cli --api-key QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80 --name Alice
Hello, Alice!
```

---

## curl

`curl` is available on macOS and Windows 10/11 (PowerShell and Command Prompt).

The Streamable HTTP transport requires a three-step sequence: initialize the session, confirm it, then call tools. All requests must include your `X-API-Key` header.

The examples below use macOS syntax for multi-line commands — replace `\` with a backtick `` ` `` on Windows PowerShell.

> The `/tmp/mcp_headers` path in Step 1 is macOS-only. On Windows, replace it with a local path such as `C:\tmp\mcp_headers.txt` and adjust the `grep` line accordingly, or use [Postman](https://www.postman.com/) to manage sessions interactively.

### Greet Server

Start the server first:
```bash
uv run -m mcp_examples.server --transport streamable-http --port 8000
```

**Step 1 — Initialize the session:**
```bash
curl -s -D /tmp/mcp_headers -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl-client","version":"1.0"}}}'

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | awk '{print $2}' | tr -d '\r')
```

**Step 2 — Confirm the session:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

**Step 3 — Call the greet tool:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"greet","arguments":{"name":"Alice"}}}'
```

---

### Contact Server

Start the server first:
```bash
uv run -m mcp_examples.contacts --transport streamable-http --port 8000
```

Run Steps 1 and 2 from the Greet Server section above (same commands). Then call any contact tool:

**Search by email:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_by_email",
      "arguments": {"email": "bugs.bunny@acme.com"}
    }
  }'
```

**Search by last name:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "search_by_last_name",
      "arguments": {"last_name": "Bunny"}
    }
  }'
```

**Search by account ID:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search_by_account_id",
      "arguments": {"account_id": "0011A00001xAC001"}
    }
  }'
```

**Authenticate a contact:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "authenticate",
      "arguments": {"email": "bugs.bunny@acme.com", "password": "bugs2022!"}
    }
  }'
```

---

### Weather Server

Start the server first:
```bash
OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather --transport streamable-http --port 8000
```

Run Steps 1 and 2 from the Greet Server section above (same commands). Then call any weather tool:

**Get current weather:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_current_weather",
      "arguments": {"location": "London", "units": "metric"}
    }
  }'
```

**Get 5-day forecast:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_forecast",
      "arguments": {"location": "Tokyo,JP", "days": 5, "units": "metric"}
    }
  }'
```

**Get air quality:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "get_air_quality",
      "arguments": {"location": "Beijing"}
    }
  }'
```
