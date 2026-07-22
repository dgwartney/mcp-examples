# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP (Model Context Protocol) examples using the FastMCP Python library. The project demonstrates building MCP servers with tools and middleware-based authentication, plus a client for calling those tools remotely.

## Setup & Commands

This project uses `uv` for Python package management with Python 3.12.

```bash
# Install dependencies
uv sync

# Run the MCP server
uv run -m mcp_examples.server

# Run the MCP client
uv run -m mcp_examples.cli

# Run tests
uv run pytest
```

## Architecture

The project is organized as a `mcp_examples` Python package:

- **mcp_examples/database.py** — `DatabaseManager` class for SQLite-backed API key storage and validation.
- **mcp_examples/middleware.py** — `ApiKeyMiddleware` class that checks for an `X-API-Key` header on incoming HTTP requests.
- **mcp_examples/base.py** — `AuthenticatedMCPServer` abstract base class with API key auth infrastructure (database, middleware). Subclass and implement `_register_tools()` to create new servers.
- **mcp_examples/server.py** — `GreetMCPServer` derived class demonstrating tool registration. Exposes module-level `server` and `mcp` instances.
- **mcp_examples/contact_database.py** — `ContactDatabaseManager` class for SQLite-backed contact storage, auto-seeded with mock CRM data.
- **mcp_examples/contacts.py** — `ContactMCPServer` derived class exposing contact search and authentication tools.
- **mcp_examples/weather.py** — `WeatherMCPServer` derived class wrapping the OpenWeatherMap API (current weather, forecast, air quality).
- **mcp_examples/wikipedia.py** — `WikipediaMCPServer` derived class wrapping the Wikipedia API (search, summaries, related pages).
- **mcp_examples/twilio_server.py** — `TwilioMCPServer` derived class exposing SMS (Twilio) and email (SendGrid) tools.
- **mcp_examples/combined.py** — Mounts all servers above into a single Starlette app, each at its own URL path (`/greet/mcp`, `/contacts/mcp`, `/wikipedia/mcp`, `/weather/mcp`, `/twilio/mcp`). Entry point used for deployment.
- **mcp_examples/client.py** — `MCPClient` class that connects to a remote MCP endpoint and calls tools.
- **mcp_examples/cli.py** — `MCPClientApp` CLI application and `main()` entry point.
- **mcp_examples/__init__.py** — Re-exports all public classes.
- **auth.py** — Standalone snippet of the `ApiKeyMiddleware` class (no imports; reference/example code, not directly runnable).

See [docs/servers.md](docs/servers.md) for full per-server details (tools, required env vars, seed data).

## Key Dependencies

- `fastmcp>=2.14.5` — The core library for both server and client. Provides `FastMCP`, `Client`, `Middleware`, `ToolError`, and `get_http_headers`.

## TODO — cookie-cutter experience for beginners building Artemis MCP servers

Goal: a beginning Python programmer should be able to stamp out a new, Artemis-ready MCP
server from this repo with minimal manual file surgery. Evaluated against live Kore.ai
Agent Platform v2 (Artemis) docs (`docs.kore.ai/agent-platform/tools/mcp`), which require
HTTP or SSE transport, header/API-key (or Bearer/Basic/OAuth) auth, and a `/mcp` endpoint
that responds to tool discovery. This repo's `AuthenticatedMCPServer` + `combined.py`
pattern already matches that model well — the gaps below are about lowering the bar for
a first-time contributor, not architecture changes.

1. **Fix `KORE_AI_INTEGRATION.md`** — it still references `my_server.py`, a file that no
   longer exists after the `mcp_examples` package refactor (run commands, Dockerfile,
   Procfile all point at it). Rewrite every example to use `uv run -m mcp_examples.<server>`
   or `mcp_examples.combined`, matching the current layout.
2. **Add a minimal starter template** — a bare-bones server module (e.g.
   `mcp_examples/_template.py` or `templates/new_server.py.tmpl`) with one dummy tool and
   no domain logic (no SQLite CRM, no external API), so a beginner can copy one small file
   and understand the whole shape before looking at `contacts.py`/`weather.py`/`twilio_server.py`.
3. **Add a scaffold script** — e.g. `scripts/new_server.py <Name>` that generates the new
   server module, a matching `tests/test_<name>.py` skeleton, and appends the entry to
   `combined.py`'s `SERVER_REGISTRY` — the multi-file edit (module + tests + registry +
   docs) is currently manual and easy to get partially wrong (forgetting the
   `combined.py` registration is the most likely miss, since that's the step that
   actually exposes the server to Artemis).
4. **Add an explicit "Adding a New Server" checklist to `docs/extending.md`** — today it
   only shows editing tool registration in an existing class, not the full path from zero
   to an Artemis-registered tool: new module → register in `combined.py` → add
   `docs/servers.md` entry → write tests → `curl` the `/mcp` endpoint directly → register
   in Kore AI (Test → Import) → refresh in Kore AI after any tool change.
