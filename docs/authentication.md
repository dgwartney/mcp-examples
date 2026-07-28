# Authentication

Authentication only applies when the server is running with an HTTP transport (`streamable-http` or `sse`). The `dev` and `stdio` transports bypass authentication entirely and are intended for local development only.

## How it works

When the server starts in HTTP mode, every incoming request must include an `X-API-Key` header containing a valid key. The server looks up that key in a local SQLite database (`api_keys.db`). Requests with a missing or unrecognised key receive an HTTP 401 response and are not processed.

## Step 1 — Start the server and get your API key

On first run, the server automatically creates `api_keys.db`, generates a secure random API key, and prints it to the terminal:

```bash
uv run -m mcp_server_kit.server --transport streamable-http --port 8000
```

```
Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
```

**Copy this key and save it somewhere safe.** The server will not print it again on subsequent runs.

## Step 2 — Recover the key if you missed it

If you did not save the key, look it up directly in the database:

**macOS:**
```bash
sqlite3 api_keys.db "SELECT key FROM api_keys;"
```

**Windows (PowerShell):**
```powershell
sqlite3 api_keys.db "SELECT key FROM api_keys;"
```

> **Windows users**: `sqlite3` is not installed by default. Download it from [sqlite.org/download](https://www.sqlite.org/download.html) (look for "sqlite-tools" under "Precompiled Binaries for Windows"), unzip it, and add the folder to your PATH — or use [DB Browser for SQLite](https://sqlitebrowser.org/) for a graphical interface instead.

## Step 3 — Use the key in client requests

Pass the key in the `X-API-Key` header on every request.

**Built-in client:**
```bash
uv run -m mcp_server_kit.cli --api-key YOUR_API_KEY --url http://localhost:8000/mcp
```

**curl:**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

**Any MCP-compatible client**: configure the server URL as `http://localhost:8000/mcp` and add `X-API-Key: YOUR_API_KEY` as a custom header.

## Managing API Keys

API keys are stored in `api_keys.db`. You can manage them directly using `sqlite3`.

### View existing keys

```bash
sqlite3 api_keys.db "SELECT * FROM api_keys;"
```

### Add a new key

```bash
# Generate a secure random key
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"

# Add it to the database
sqlite3 api_keys.db "INSERT INTO api_keys (key) VALUES ('YOUR_NEW_KEY');"
```

### Revoke a key

```bash
sqlite3 api_keys.db "DELETE FROM api_keys WHERE key = 'KEY_TO_REVOKE';"
```
