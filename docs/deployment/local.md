# Local Development

**Trade-offs:** Free, full SQLite persistence, no cold starts. Requires your machine to stay on — not accessible from outside your network without a tunnel (see [ngrok.md](ngrok.md)).

---

1. Start the server with HTTP transport:
   ```bash
   uv run -m mcp_examples.server --transport streamable-http --port 8000
   ```

2. (Optional) Use a custom database location:

   **macOS:**
   ```bash
   MCP_DB_PATH=/tmp/dev_keys.db uv run -m mcp_examples.server --transport streamable-http --port 8000
   ```

   **Windows (PowerShell):**
   ```powershell
   $env:MCP_DB_PATH = "C:\tmp\dev_keys.db"
   uv run -m mcp_examples.server --transport streamable-http --port 8000
   ```

3. Test with the client:
   ```bash
   uv run -m mcp_examples.cli --api-key YOUR_API_KEY --url http://localhost:8000/mcp
   ```
