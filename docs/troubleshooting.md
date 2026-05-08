# Troubleshooting

## "Error: Invalid request parameters"

**Cause:** Headers not passed correctly to the transport layer.

**Solution:** Ensure you're using `StreamableHttpTransport` with the headers parameter (already implemented in `mcp_examples/client.py`).

## "Error: Unauthorized: Invalid or missing API Key"

**Cause:** API key is incorrect or not in the database.

**Solution:**
1. Check the key printed during server first run
2. Verify the key exists in the database:
   ```bash
   sqlite3 api_keys.db "SELECT * FROM api_keys;"
   ```
3. See [authentication.md](authentication.md) for how to add a new key

## "Server object 'mcp' not found"

**Cause:** FastMCP CLI expects a module-level `mcp` variable.

**Solution:** Already handled in `mcp_examples/server.py` with:
```python
server = MCPServer()
mcp = server.mcp
```

## Connection Refused

**Cause:** Server not running or wrong URL/port.

**Solution:**
1. Verify the server is running and listening on port 8000:
   - **macOS:** `lsof -i :8000`
   - **Windows (PowerShell):** `netstat -ano | findstr :8000`
2. Check the URL matches the server's address
3. Ensure your firewall allows the connection

## Fly.io: "app is not listening on the expected address"

**Cause:** This warning appears during first deploy because Fly.io's health check fires ~2 seconds after machine start, but the server takes ~5 seconds to initialise the database before binding to port 8000.

**Solution:** This is expected and normal. Run `fly status` after the deploy completes to confirm the machine is in `started` state.

## API key not printed in docker logs

**Cause:** Python stdout buffering in Docker containers.

**Solution:** The `Dockerfile` in this repo sets `ENV PYTHONUNBUFFERED=1` which fixes this. If you are using a custom image, add this environment variable.
