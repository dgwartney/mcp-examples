# MCP Example

A production-ready implementation of Model Context Protocol (MCP) servers and client using [FastMCP](https://github.com/jlowin/fastmcp) with SQLite-backed API key authentication.

**Author:** David Gwartney (david.gwartney@gmail.com)

---

## Servers

| Server | Module | Tools |
|--------|--------|-------|
| **Greet** | `mcp_examples/server.py` | `greet(name)` |
| **Contact** | `mcp_examples/contacts.py` | `search_by_email`, `search_by_last_name`, `search_by_account_id`, `authenticate` |
| **Wikipedia** | `mcp_examples/wikipedia.py` | `search_pages`, `search_titles`, `get_page_summary`, `get_related_pages` |
| **Weather** | `mcp_examples/weather.py` | `get_current_weather`, `get_forecast`, `get_air_quality` |
| **Twilio** | `mcp_examples/twilio_server.py` | `send_sms`, `send_email` |
| **Combined** | `mcp_examples/combined.py` | All of the above, each at its own path (`/greet/mcp`, `/contacts/mcp`, `/wikipedia/mcp`, `/weather/mcp`, `/twilio/mcp`) |

All servers use API key authentication over HTTP and run locally via stdio. See [docs/servers.md](docs/servers.md) for full details, architecture, and project structure.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/dgwartney/mcp-example.git
cd mcp-example
uv sync

# 2. Start all servers combined (HTTP transport, port 8000)
OPENWEATHER_API_KEY=<your_key> TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> \
TWILIO_MESSAGING_SERVICE_SID=<mg_sid> SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_examples.combined --port 8000
# → prints: Generated default API key: <YOUR_KEY>
# → /greet/mcp, /contacts/mcp, /wikipedia/mcp, /weather/mcp, /twilio/mcp all live

# 3. Test the greet server
uv run -m mcp_examples.cli --api-key YOUR_KEY --url http://localhost:8000/greet/mcp --name Alice
# → Hello, Alice!

# 4. Or run a single server on its own
uv run -m mcp_examples.server --transport streamable-http --port 8000

# 5. Or open the interactive browser UI (no API key needed)
uv run fastmcp dev mcp_examples/server.py
```

> **New to the command line?** Start with [docs/prerequisites.md](docs/prerequisites.md) for macOS and Windows setup instructions.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/prerequisites.md](docs/prerequisites.md) | Install terminal, Git, and uv on macOS or Windows |
| [docs/installation.md](docs/installation.md) | Clone the repo, install dependencies, configure environment variables |
| [docs/servers.md](docs/servers.md) | Server descriptions, tools, architecture diagram, project structure |
| [docs/authentication.md](docs/authentication.md) | How API key auth works, getting your key, managing keys |
| [docs/running.md](docs/running.md) | All ways to run: stdio, HTTP transport, FastMCP CLI |
| [docs/clients.md](docs/clients.md) | Built-in mcp-client and curl examples for both servers |
| [docs/managing-contacts.md](docs/managing-contacts.md) | View, add, update, and delete contacts in the SQLite database |
| [docs/deployment.md](docs/deployment.md) | Deployment overview and quick links to all provider guides |
| [docs/deployment/index.md](docs/deployment/index.md) | Provider comparison table with cost, persistence, and availability details |
| [docs/deployment/local.md](docs/deployment/local.md) | Run the server locally on your own machine |
| [docs/deployment/ngrok.md](docs/deployment/ngrok.md) | Expose a local server publicly via ngrok tunnel |
| [docs/deployment/render.md](docs/deployment/render.md) | Deploy to Render (free tier + $1/mo persistent disk) |
| [docs/deployment/flyio.md](docs/deployment/flyio.md) | Deploy to Fly.io (free tier, persistent volumes, always-on option) |
| [docs/deployment/railway.md](docs/deployment/railway.md) | Deploy to Railway ($5 credit/mo, ephemeral filesystem) |
| [docs/deployment/docker.md](docs/deployment/docker.md) | Self-host with Docker on any VPS (~$4–5/mo, full persistence) |
| [docs/testing.md](docs/testing.md) | Running the test suite and coverage reports |
| [docs/security.md](docs/security.md) | API key management, database security, header handling |
| [docs/extending.md](docs/extending.md) | Adding tools, custom auth, serving multiple servers |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common errors and fixes |
| [docs/agent-prompts.md](docs/agent-prompts.md) | Ready-to-use agent system prompt for the Contact server |

---

## Deployment options

| Platform | Cost | SQLite persists | Always on |
|----------|------|-----------------|-----------|
| [Local](docs/deployment/local.md) | Free | Yes | Requires laptop |
| [ngrok](docs/deployment/ngrok.md) | Free / $10/mo fixed URL | Yes | Requires laptop |
| [Fly.io](docs/deployment/flyio.md) | Free tier | Yes | Yes |
| [Render](docs/deployment/render.md) | Free + $1/mo disk | Yes | No (sleeps) |
| [Railway](docs/deployment/railway.md) | $5 credit/mo | No | Yes |
| [Docker + VPS](docs/deployment/docker.md) | ~$4/mo | Yes | Yes |

See [docs/deployment/index.md](docs/deployment/index.md) for a full comparison and step-by-step guides for each platform.

---

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [uv Package Manager](https://github.com/astral-sh/uv)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Kore AI Integration Guide](KORE_AI_INTEGRATION.md)

## Contributing

Contributions are welcome. Please follow PEP 8, use Google-style docstrings, add type hints, and ensure all tests pass before submitting a PR.

## License

This project is provided as-is for educational and demonstration purposes.

## Support

For issues, questions, or contributions, please open an issue on the project repository.
