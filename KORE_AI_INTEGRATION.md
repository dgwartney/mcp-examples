# Integrating with Kore AI Agent Platform

This guide explains how to configure and deploy the servers in this repository as tools
in the Kore AI Agent Platform (Artemis).

**Author:** David Gwartney (david.gwartney@gmail.com)

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment Options](#deployment-options)
  - [Option 1: Local Development with ngrok](#option-1-local-development-with-ngrok)
  - [Option 2: Docker Deployment](#option-2-docker-deployment)
  - [Option 3: Cloud Platform Deployment](#option-3-cloud-platform-deployment)
- [Configuring in Kore AI](#configuring-in-kore-ai)
- [Testing the Integration](#testing-the-integration)
- [Managing API Keys](#managing-api-keys)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Adding More Tools](#adding-more-tools)

---

## Overview

The Kore AI Agent Platform uses the Model Context Protocol (MCP) to integrate with
external tools and services. This repository ships seven MCP servers, all built on the
same `AuthenticatedMCPServer` base class:

| Server | Module | Tools |
|--------|--------|-------|
| Greet | `mcp_server_kit/server.py` | `greet` |
| Contact | `mcp_server_kit/contacts.py` | `search_by_last_name`, `search_by_email`, `search_by_account_id`, `authenticate` |
| Wikipedia | `mcp_server_kit/wikipedia.py` | `search_pages`, `search_titles`, `get_page_summary`, `get_related_pages` |
| Weather | `mcp_server_kit/weather.py` | `get_current_weather`, `get_forecast`, `get_air_quality` |
| Messaging | `mcp_server_kit/messaging.py` | `send_sms`, `send_sms_template`, `send_email`, `send_email_template` |
| PTO | `mcp_server_kit/pto.py` | `get_balance`, `get_balance_by_email`, `request_pto`, `list_requests` |
| Onboarding | `mcp_server_kit/onboarding.py` | `create_case`, `get_case`, `update_case_status`, `list_cases` |

`mcp_server_kit/combined.py` mounts all seven into a single deployable Starlette app, each
at its own URL path (`/greet/mcp`, `/contacts/mcp`, `/wikipedia/mcp`, `/weather/mcp`,
`/messaging/mcp`, `/pto/mcp`, `/onboarding/mcp`) sharing one API key store — this is the
recommended way to deploy to Kore AI, since it exposes every tool under one base URL with
one API key. You can also run any single server standalone on its own port if you only
need one.

- **Authentication**: SQLite-backed API key validation (`X-API-Key` header)
- **Transport**: HTTP-based MCP protocol (required for Kore AI — the default stdio
  transport is local-only and not reachable from the platform)

### How It Works with Kore AI

1. **Tool Discovery**: Kore AI connects to your MCP server and discovers available tools
2. **Intent Detection**: The LLM identifies when to use your tools based on user queries
3. **Invocation**: Kore AI sends structured requests with tool name and parameters
4. **Execution**: Your MCP server executes the tool logic and returns results
5. **Response**: The agent formulates a natural language response using the tool output

---

## Prerequisites

Before integrating with Kore AI, ensure you have:

- ✅ Python 3.10+ (see `pyproject.toml`'s `requires-python`)
- ✅ `uv` package manager installed
- ✅ This repository cloned and dependencies installed (`uv sync`)
- ✅ A publicly accessible URL for your server (via ngrok, cloud deployment, etc.)
- ✅ Access to a Kore AI Agent Platform account

---

## Quick Start

For the impatient, here's the fastest path to integration using the combined server
(all five servers, one API key):

```bash
# 1. Install dependencies
uv sync

# 2. Start the combined server (mounts all five servers on one port)
uv run -m mcp_server_kit.combined --port 8000

# 3. Note the API key printed on first run
# Output: Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80

# 4. In another terminal, expose via ngrok
ngrok http 8000

# 5. Use <ngrok_url>/greet/mcp, <ngrok_url>/contacts/mcp, etc. in Kore AI configuration
```

If you only need one server, run it standalone instead:

```bash
uv run -m mcp_server_kit.server --transport streamable-http --port 8000
```

Continue reading for detailed deployment options and configuration steps.

---

## Deployment Options

Choose the deployment option that best fits your needs:

| Option | Best For | Complexity | Production Ready |
|--------|----------|------------|------------------|
| **ngrok** | Quick testing, demos | Low | ⚠️ Development only |
| **Docker** | Consistent environments | Medium | ✅ Yes |
| **Cloud Platform** | Scalable production | Medium | ✅ Yes |

### Option 1: Local Development with ngrok

**Best for**: Quick testing, development, and proof-of-concept.

#### Step 1: Install ngrok

```bash
# macOS
brew install ngrok

# Or download from https://ngrok.com/download
```

#### Step 2: Start the Combined Server

```bash
uv run -m mcp_server_kit.combined --port 8000
```

**On first run**, the server will generate and print an API key:

```
Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
```

**⚠️ IMPORTANT**: Save this API key! You'll need it for Kore AI configuration.

#### Step 3: Create ngrok Tunnel

In a **new terminal window**:

```bash
ngrok http 8000
```

You'll see output like:

```
Forwarding   https://abc123.ngrok.app -> http://localhost:8000
```

**Note the HTTPS URL** — this is your public base URL. Each server is reachable at
`<base_url>/<prefix>/mcp` (e.g. `https://abc123.ngrok.app/greet/mcp`).

#### Step 4: Test an Endpoint

Verify your server is accessible:

```bash
curl -X POST https://abc123.ngrok.app/greet/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
```

Expected response should list the `greet` tool.

### Option 2: Docker Deployment

**Best for**: Production deployments, consistent environments, easy scaling.

This repository already includes a working `Dockerfile` at the project root that runs
the combined server — use it directly rather than hand-rolling one:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY mcp_server_kit/ mcp_server_kit/
RUN uv sync --frozen
EXPOSE 8000
CMD ["uv", "run", "-m", "mcp_server_kit.combined", "--port", "8000", "--host", "0.0.0.0"]
```

(See the actual `Dockerfile` in the repo root — it may have evolved since this guide was
written; treat that file as the source of truth.)

#### Step 1: Build and Run Container

```bash
# Build the Docker image
docker build -t mcp-server .

# Run with persistent database
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e MCP_DB_PATH=/app/data/api_keys.db \
  --name mcp-server \
  mcp-server
```

#### Step 2: Get the API Key

```bash
# Check container logs for the generated API key
docker logs mcp-server
```

Look for the line:
```
Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
```

#### Step 3: Deploy to Cloud

Deploy your Docker container to a cloud provider:

- **AWS ECS/Fargate**: Use AWS Container Service
- **Google Cloud Run**: Automatic HTTPS and scaling
- **Azure Container Instances**: Simple container deployment
- **DigitalOcean App Platform**: Git-based deployment

Make note of the public URL provided by your cloud platform.

### Option 3: Cloud Platform Deployment

**Best for**: Production use without Docker complexity.

#### Railway / Render Deployment

This repository already includes a working `Procfile` at the project root, which deploys
the single Greet server as a simple starting point:

```
web: uv run -m mcp_server_kit.server --transport streamable-http --port $PORT --host 0.0.0.0
```

If you want the combined server (all five, one API key) on Railway/Render instead, edit
the `Procfile` to `web: uv run -m mcp_server_kit.combined --port $PORT --host 0.0.0.0`, or
use the Docker deployment option above, which already runs the combined server by default.

1. **Deploy (Railway)**:
   ```bash
   npm install -g @railway/cli
   railway login
   railway init
   railway up
   ```

2. **Configure Environment**:
   - Set `MCP_DB_PATH` if needed (Railway provides persistent volumes)
   - Note the Railway-provided public URL

3. **Get API Key**:
   ```bash
   railway logs
   ```

For Render or Fly.io, see [docs/deployment/render.md](docs/deployment/render.md) and
[docs/deployment/flyio.md](docs/deployment/flyio.md) for full provider-specific guides,
including secrets configuration for the Weather and Twilio servers.

---

## Configuring in Kore AI

Once your combined server is deployed and accessible via HTTPS, configure each server you
need as a separate MCP Tool in Kore AI. Every entry in `mcp_server_kit/combined.py`'s
`SERVER_REGISTRY` gets its own `/<prefix>/mcp` URL and its own set of tools — repeat the
steps below once per server you want to expose.

### Step 1: Access Tools Section

1. Log in to your Kore AI Agent Platform account
2. Navigate to your Agentic App
3. Go to the **Tools** section
4. Click **Add Tool** → **+New Tool** → **MCP Tool**

### Step 2: Select Transport

Choose **HTTP** (Streamable HTTP) as the transport method — this repository does not use
SSE.

### Step 3: Enter Server Details

Fill in the configuration form, one server at a time. For example, for the Contact server:

| Field | Value | Example |
|-------|-------|---------|
| **Name** | `mcp-server-kit-contacts` | Unique identifier for this server's tools |
| **Description** | `Mock CRM contact search and auth tools` | Brief description of capabilities |
| **Server URL** | Your deployment base URL + the server's prefix + `/mcp` | `https://abc123.ngrok.app/contacts/mcp` |

**⚠️ IMPORTANT**: Each server has its own path — see the table in [Overview](#overview)
and [docs/servers.md](docs/servers.md) for the full list of prefixes and tools.

### Step 4: Configure Authentication

1. Click the **Configure** button next to "Request Definition"
2. Navigate to the **Headers** section
3. Add a new header:
   - **Name**: `X-API-Key`
   - **Value**: Your API key (from server startup logs)

The combined server shares one API key across every mounted path, so you only need to do
this once and reuse the same key for every server you register.

### Step 5: Test Connection

1. Click the **Test** button at the bottom of the configuration page
2. Kore AI will attempt to connect to your server
3. Verify you see a success message and the expected tools listed (see
   [docs/servers.md](docs/servers.md) for each server's tool list)

### Step 6: Select Tools

Check the tools you want and click **Add Selected**. Kore AI automatically prefixes tool
names with the server name you chose in Step 3 (e.g. `mcp-server-kit-contacts__search_by_last_name`).

### Step 7: Save Configuration

Review your configuration and click **Save**/**Add Tool** to finalize. Repeat Steps 1-7
for each additional server you want to expose.

---

## Testing the Integration

### In Kore AI Platform

1. Open your agent in **Preview** mode
2. Navigate to the **Tools** section
3. Find one of your registered tools (e.g. `mcp-server-kit-greet__greet`)
4. Click **Run Sample Execution**

#### Sample Test Input (greet)

```json
{
  "name": "Alice"
}
```

Expected response:

```json
{
  "content": [
    {"type": "text", "text": "Hello, Alice!"}
  ]
}
```

#### Sample Test Input (contacts — search_by_last_name)

```json
{
  "last_name": "Webb"
}
```

Expected response includes a list of matching contact records (e.g. Marcus Webb, Eleanor Webster).

### Via Conversational Interface

**User**: "Can you greet someone named Bob?"

**Agent**: Recognizes the intent, invokes `greet` with `name: "Bob"`, and responds:
"Hello, Bob!"

### Direct API Testing

Test any mounted server directly (outside Kore AI) to isolate issues — substitute the
path for the server you're testing:

```bash
# Test tool discovery on the greet server
curl -s -X POST https://your-server.com/greet/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'

# Test greet tool invocation
curl -s -X POST https://your-server.com/greet/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "greet", "arguments": {"name": "Charlie"}},
    "id": 2
  }'
```

Note that a real MCP session over Streamable HTTP requires an `initialize` handshake
before `tools/call` — see [docs/extending.md](docs/extending.md)'s curl recipe for the
full three-step sequence (initialize → notify initialized → call).

---

## Managing API Keys

### Viewing Existing Keys

```bash
sqlite3 api_keys.db "SELECT * FROM api_keys;"
```

### Adding Additional Keys

```bash
# Generate a cryptographically secure key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to database
sqlite3 api_keys.db "INSERT INTO api_keys (key) VALUES ('NEW_KEY_HERE');"
```

### Rotating Keys

1. **Add a new key** (don't remove the old one yet)
2. **Update Kore AI** configuration with the new key
3. **Test** the integration thoroughly
4. **Remove the old key**:
   ```bash
   sqlite3 api_keys.db "DELETE FROM api_keys WHERE key = 'OLD_KEY';"
   ```

### Revoking Keys

```bash
sqlite3 api_keys.db "DELETE FROM api_keys WHERE key = 'COMPROMISED_KEY';"
```

**⚠️ WARNING**: Revoking a key immediately breaks any integrations using it.

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "Connection Failed" in Kore AI

**Possible Causes**:
- Server not running or not accessible
- Incorrect URL (missing the server's `/<prefix>/mcp` path)
- Firewall blocking external access
- ngrok tunnel expired (free tier has a time limit)

**Solutions**:
```bash
# Verify the server is running and check logs
docker logs mcp-server   # For Docker
railway logs             # For Railway

# Restart ngrok (if using)
ngrok http 8000
```

#### 2. "Unauthorized: Invalid or missing API Key"

**Solutions**:
1. Verify the API key in Kore AI configuration matches the database:
   ```bash
   sqlite3 api_keys.db "SELECT * FROM api_keys;"
   ```
2. Check header configuration — header name must be exactly `X-API-Key` (case-insensitive)
3. Regenerate if lost:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   sqlite3 api_keys.db "INSERT INTO api_keys (key) VALUES ('NEW_KEY');"
   ```

#### 3. "No Tools Discovered"

**Solutions**:
```bash
# Verify tools are registered on the server/path you configured
curl -s -X POST https://your-server.com/<prefix>/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
```
- Double-check you used the right `/<prefix>/mcp` path for the server whose tools you want.

#### 4. "Tool Invocation Failed"

**Solutions**:
1. Test the tool directly with curl (see [Direct API Testing](#direct-api-testing))
2. Check parameter format matches the tool's schema
3. Review server logs for errors

#### 5. ngrok Tunnel Issues

```bash
# Restart ngrok
pkill ngrok
ngrok http 8000
```

#### 6. Database File Not Found

```bash
echo $MCP_DB_PATH
export MCP_DB_PATH=/app/data/api_keys.db
# For Docker, verify the volume mount:
docker run -v $(pwd)/data:/app/data ...
```

---

## Best Practices

### Security

1. **Use HTTPS Only** in production
2. **Rotate Keys Regularly**
3. **Monitor Access** via logs
4. **Separate Keys by Environment**
5. **Backup the database**:
   ```bash
   cp api_keys.db api_keys.db.backup-$(date +%Y%m%d)
   ```

### Deployment

1. **Use Environment Variables**: `MCP_DB_PATH` and any server-specific secrets
   (`OPENWEATHER_API_KEY`, `TWILIO_*`, `SENDGRID_*`) belong in environment/secret
   configuration, not code
2. **Persistent Storage**: Ensure the database survives container restarts
3. **Logging**: Enable comprehensive logging for troubleshooting

### Kore AI Integration

1. **Descriptive Naming**: Use clear names per server/tool-group in Kore AI
2. **Document Tools**: Keep [docs/servers.md](docs/servers.md) current for each server
3. **Test Thoroughly**: Always test in Preview mode before production
4. **Manual Refresh**: Kore AI does not auto-detect server changes — remember to click the
   refresh icon on the MCP server configuration after adding/changing tools
5. **Enable Artifacts**: Turn on "Include Tool Response in Artifacts" for debugging

### Scaling

1. **Horizontal Scaling**: Deploy multiple instances behind a load balancer
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Monitoring**: Use application performance monitoring (APM) tools

---

## Adding More Tools

Every server in this repo follows the same pattern: subclass `AuthenticatedMCPServer` and
register tools in `_register_tools()` (see [docs/extending.md](docs/extending.md) for the
full walkthrough, including a checklist for adding an entirely new server).

For a minimal example to copy from, see `mcp_server_kit/_template.py` — the smallest
possible server, with a single placeholder tool and no domain logic.

To add a tool to an existing server, edit its `_register_tools()` method, e.g. in
`mcp_server_kit/server.py`:

```python
def _register_tools(self) -> None:
    @self.mcp.tool(description="A tool that greets a user by name")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    @self.mcp.tool(description="Get the current server time")
    def get_time() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
```

Restart the server, then in Kore AI click the refresh icon on that server's MCP Tool
configuration and re-select any new tools.

---

## Additional Resources

- **MCP Specification**: [https://spec.modelcontextprotocol.io/](https://spec.modelcontextprotocol.io/)
- **FastMCP Documentation**: [https://github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)
- **Kore AI Documentation**: [https://docs.kore.ai](https://docs.kore.ai)
- **Project README**: See `README.md` for detailed server documentation

---

## Support

For issues with:
- **This MCP Server**: Open an issue in the project repository
- **Kore AI Platform**: Contact Kore AI support
- **FastMCP Library**: Visit the FastMCP GitHub repository
