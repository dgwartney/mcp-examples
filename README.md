# mcp-server-kit

A toolkit for building authenticated Model Context Protocol (MCP) servers using [FastMCP](https://github.com/jlowin/fastmcp) with SQLite-backed API key authentication — plus a scaffolding generator (`mcp-server-kit new`) and a remote client. Ships with five example servers you can mount, extend, or generate a fresh project from.

**Author:** David Gwartney (david.gwartney@gmail.com)

---

## Servers

| Server | Module | Tools |
|--------|--------|-------|
| **Greet** | `mcp_server_kit/server.py` | `greet(name)` |
| **Contact** | `mcp_server_kit/contacts.py` | `search_by_email`, `search_by_last_name`, `search_by_account_id`, `authenticate` |
| **Wikipedia** | `mcp_server_kit/wikipedia.py` | `search_pages`, `search_titles`, `get_page_summary`, `get_related_pages` |
| **Weather** | `mcp_server_kit/weather.py` | `get_current_weather`, `get_forecast`, `get_air_quality` |
| **Messaging** | `mcp_server_kit/messaging.py` | `send_sms`, `send_sms_template`, `send_email`, `send_email_template` |
| **Combined** | `mcp_server_kit/combined.py` | All of the above, each at its own path (`/greet/mcp`, `/contacts/mcp`, `/wikipedia/mcp`, `/weather/mcp`, `/messaging/mcp`) |

All servers use API key authentication over HTTP and run locally via stdio. See [docs/servers.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/servers.md) for full details, architecture, and project structure.

---

## Install

This project uses [uv](https://github.com/astral-sh/uv) exclusively — not pip.

```bash
uv tool install mcp-server-kit    # installs the mcp-server-kit / mcp-client CLIs
# or, to add it as a library dependency of your project:
uv add mcp-server-kit
```

Then generate a brand-new standalone MCP server project:

```bash
mcp-server-kit new my-mcp        # interactive: choose which bundled example servers to include
cd my-mcp && uv sync
uv run python -m my_mcp.combined --port 8000
```

Or import the base classes directly in your own project:

```python
from mcp_server_kit import AuthenticatedMCPServer

class MyServer(AuthenticatedMCPServer):
    def _register_tools(self):
        @self.mcp.tool(description="Add two numbers")
        def add(a: int, b: int) -> int:
            return a + b
```

---

## Quick Start (from a clone of this repo)

```bash
# 1. Clone and install
git clone https://github.com/dgwartney/mcp-examples.git
cd mcp-examples
uv sync

# 2. Start all servers combined (HTTP transport, port 8000)
OPENWEATHER_API_KEY=<your_key> TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> \
TWILIO_MESSAGING_SERVICE_SID=<mg_sid> SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_server_kit.combined --port 8000
# → prints: Generated default API key: <YOUR_KEY>
# → /greet/mcp, /contacts/mcp, /wikipedia/mcp, /weather/mcp, /messaging/mcp all live

# 3. Test the greet server
uv run -m mcp_server_kit.cli --api-key YOUR_KEY --url http://localhost:8000/greet/mcp --name Alice
# → Hello, Alice!

# 4. Or run a single server on its own
uv run -m mcp_server_kit.server --transport streamable-http --port 8000

# 5. Or open the interactive browser UI (no API key needed)
uv run fastmcp dev mcp_server_kit/server.py
```

> **New to the command line?** Start with [docs/prerequisites.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/prerequisites.md) for macOS and Windows setup instructions.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/prerequisites.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/prerequisites.md) | Install terminal, Git, and uv on macOS or Windows |
| [docs/installation.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/installation.md) | Clone the repo, install dependencies, configure environment variables |
| [docs/servers.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/servers.md) | Server descriptions, tools, architecture diagram, project structure |
| [docs/authentication.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/authentication.md) | How API key auth works, getting your key, managing keys |
| [docs/running.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/running.md) | All ways to run: stdio, HTTP transport, FastMCP CLI |
| [docs/clients.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/clients.md) | Built-in mcp-client and curl examples for both servers |
| [docs/managing-contacts.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/managing-contacts.md) | View, add, update, and delete contacts in the SQLite database |
| [docs/deployment.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment.md) | Deployment overview and quick links to all provider guides |
| [docs/tutorial.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/tutorial.md) | Walkthrough for using an already-deployed instance: calling tools, connecting an agent |
| [docs/deployment/index.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/index.md) | Provider comparison table with cost, persistence, and availability details |
| [docs/deployment/local.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/local.md) | Run the server locally on your own machine |
| [docs/deployment/ngrok.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/ngrok.md) | Expose a local server publicly via ngrok tunnel |
| [docs/deployment/render.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/render.md) | Deploy to Render (free tier + $1/mo persistent disk) |
| [docs/deployment/flyio.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/flyio.md) | Deploy to Fly.io (free tier, persistent volumes, always-on option) |
| [docs/deployment/railway.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/railway.md) | Deploy to Railway ($5 credit/mo, ephemeral filesystem) |
| [docs/deployment/docker.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/docker.md) | Self-host with Docker on any VPS (~$4–5/mo, full persistence) |
| [docs/testing.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/testing.md) | Running the test suite and coverage reports |
| [docs/smoke-tests.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/smoke-tests.md) | Manual smoke-test checklist to run against a live server before a release |
| [docs/security.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/security.md) | API key management, database security, header handling |
| [docs/extending.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/extending.md) | Adding tools, custom auth, serving multiple servers |
| [docs/troubleshooting.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/troubleshooting.md) | Common errors and fixes |
| [docs/agent-prompts.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/agent-prompts.md) | Ready-to-use agent system prompt for the Contact server |

---

## Deployment options

| Platform | Cost | SQLite persists | Always on |
|----------|------|-----------------|-----------|
| [Local](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/local.md) | Free | Yes | Requires laptop |
| [ngrok](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/ngrok.md) | Free / $10/mo fixed URL | Yes | Requires laptop |
| [Fly.io](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/flyio.md) | Free tier | Yes | Yes |
| [Render](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/render.md) | Free + $1/mo disk | Yes | No (sleeps) |
| [Railway](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/railway.md) | $5 credit/mo | No | Yes |
| [Docker + VPS](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/docker.md) | ~$4/mo | Yes | Yes |

See [docs/deployment/index.md](https://github.com/dgwartney/mcp-examples/blob/main/docs/deployment/index.md) for a full comparison and step-by-step guides for each platform.

---

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [uv Package Manager](https://github.com/astral-sh/uv)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Kore AI Integration Guide](https://github.com/dgwartney/mcp-examples/blob/main/KORE_AI_INTEGRATION.md)

## Contributing

Contributions are welcome. Please follow PEP 8, use Google-style docstrings, add type hints, and ensure all tests pass before submitting a PR.

## License

Released under the [MIT License](https://github.com/dgwartney/mcp-examples/blob/main/LICENSE).

## Support

For issues, questions, or contributions, please open an issue on the project repository.
