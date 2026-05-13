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

All servers use API key authentication over HTTP and run locally via stdio. See [docs/servers.md](docs/servers.md) for full details, architecture, and project structure.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/dgwartney/mcp-example.git
cd mcp-example
uv sync

# 2. Start the greet server (HTTP transport)
uv run -m mcp_examples.server --transport streamable-http --port 8000
# → prints: Generated default API key: <YOUR_KEY>

# 3. Test it
uv run -m mcp_examples.cli --api-key YOUR_KEY --name Alice
# → Hello, Alice!

# 4. Or open the interactive browser UI (no API key needed)
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
| [Local](docs/deployment/local.md) | Free | ✅ | Requires laptop |
| [ngrok](docs/deployment/ngrok.md) | Free / $10/mo fixed URL | ✅ | Requires laptop |
| [Fly.io](docs/deployment/flyio.md) | Free tier | ✅ | ✅ |
| [Render](docs/deployment/render.md) | Free + $1/mo disk | ✅ | ❌ (sleeps) |
| [Railway](docs/deployment/railway.md) | $5 credit/mo | ❌ | ✅ |
| [Docker + VPS](docs/deployment/docker.md) | ~$4/mo | ✅ | ✅ |

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
