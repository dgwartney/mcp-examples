# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP (Model Context Protocol) examples using the FastMCP Python library. The project demonstrates building MCP servers with tools and middleware-based authentication, plus a client for calling those tools remotely.

## Setup & Commands

This project uses `uv` for Python package management and supports Python 3.10+ (`requires-python = ">=3.10"`).

> **uv only — never pip.** Do not use `pip`, `pip3`, or `python -m venv` anywhere in this
> project (code, tests, docs, deploy configs, or ad-hoc commands). Use `uv` exclusively:
> `uv venv`, `uv sync`, `uv add`, `uv pip install`, `uv run`, `uv build`, `uv tool install`.
> To bootstrap uv on a platform that lacks it, use the official installer
> (`curl -LsSf https://astral.sh/uv/install.sh | sh`), not `pip install uv`.

```bash
# Install dependencies
uv sync

# Run the MCP server
uv run -m mcp_server_kit.server

# Run the MCP client
uv run -m mcp_server_kit.cli

# Run tests
uv run pytest
```

## Architecture

The project is organized as a `mcp_server_kit` Python package:

- **mcp_server_kit/database.py** — `DatabaseManager` class for SQLite-backed API key storage and validation.
- **mcp_server_kit/middleware.py** — `ApiKeyMiddleware` class that checks for an `X-API-Key` header on incoming HTTP requests.
- **mcp_server_kit/base.py** — `AuthenticatedMCPServer` abstract base class with API key auth infrastructure (database, middleware). Subclass and implement `_register_tools()` to create new servers.
- **mcp_server_kit/server.py** — `GreetMCPServer` derived class demonstrating tool registration. Exposes module-level `server` and `mcp` instances.
- **mcp_server_kit/contact_database.py** — `ContactDatabaseManager` class for SQLite-backed contact storage, auto-seeded with mock CRM data.
- **mcp_server_kit/contacts.py** — `ContactMCPServer` derived class exposing contact search and authentication tools.
- **mcp_server_kit/weather.py** — `WeatherMCPServer` derived class wrapping the OpenWeatherMap API (current weather, forecast, air quality).
- **mcp_server_kit/wikipedia.py** — `WikipediaMCPServer` derived class wrapping the Wikipedia API (search, summaries, related pages).
- **mcp_server_kit/messaging.py** — `MessagingMCPServer` derived class exposing SMS (Twilio, including Content API templates) and email (SendGrid, including dynamic templates) tools.
- **mcp_server_kit/combined.py** — Mounts all servers above into a single Starlette app, each at its own URL path (`/greet/mcp`, `/contacts/mcp`, `/wikipedia/mcp`, `/weather/mcp`, `/messaging/mcp`). Entry point used for deployment.
- **mcp_server_kit/client.py** — `MCPClient` class that connects to a remote MCP endpoint and calls tools.
- **mcp_server_kit/cli.py** — `MCPClientApp` CLI application and `main()` entry point.
- **mcp_server_kit/__init__.py** — Re-exports all public classes.

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
   longer exists after the `mcp_server_kit` package refactor (run commands, Dockerfile,
   Procfile all point at it). Rewrite every example to use `uv run -m mcp_server_kit.<server>`
   or `mcp_server_kit.combined`, matching the current layout.
2. **Add a minimal starter template** — a bare-bones server module (e.g.
   `mcp_server_kit/_template.py` or `templates/new_server.py.tmpl`) with one dummy tool and
   no domain logic (no SQLite CRM, no external API), so a beginner can copy one small file
   and understand the whole shape before looking at `contacts.py`/`weather.py`/`messaging.py`.
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

## TODO — cleanup

- **Move contact seed data out of Python** — `_SEED_CONTACTS` in
  `mcp_server_kit/contact_database.py` is currently a large in-code list of dicts. Replace
  it with a `.sql` seed file (e.g. `mcp_server_kit/seed_contacts.sql`) that `seed_contacts()`
  loads and executes, so the seed data isn't mixed in with application code.
- **Migrate the database from SQLite to PostgreSQL** — `DatabaseManager`,
  `ContactDatabaseManager`, and the PTO/onboarding managers are all SQLite-backed
  (`sqlite3` module, file-based `.db` paths). Moving to PostgreSQL would need a new
  connection/config story (host/port/credentials via env vars instead of a file path),
  updated SQL (SQLite and Postgres diverge on things like `AUTOINCREMENT` vs `SERIAL`),
  and updated docs/deployment guides that currently assume a portable SQLite file.
- **Add data-management tools/API for every database-backed server** — right now the
  only supported way to add/update/delete rows in `contacts.db` is raw `sqlite3` DDL/DML
  (see `docs/managing-contacts.md`); the Contact server exposes only read tools
  (`search_by_*`, `authenticate`) with no `create_contact`/`update_contact`/
  `delete_contact` tools or REST endpoints. Same gap applies to any other
  database-backed server where the current MCP tools are read/create-only and lack full
  CRUD (e.g. PTO and Onboarding have `create_case`/`request_pto` and status-update tools,
  but no delete/deactivate path). Add either MCP tools or a small REST API per server so
  data can be managed without hand-writing SQL against the underlying `.db` file.
- **Require a separate API key for the admin/data-management tools from the item above**
  — today `DatabaseManager`/`ApiKeyMiddleware` treat every key in `api_keys` as equally
  privileged (see `mcp_server_kit/database.py`, `mcp_server_kit/middleware.py`), so any
  caller with a normal key could invoke `create_contact`/`delete_contact`-style tools
  once they exist. Add a key tier/scope (e.g. an `is_admin` column or a distinct admin
  key table) and gate the new CRUD tools/endpoints on it, separate from the read-only
  key used for `search_by_*` and similar tools.
