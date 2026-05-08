# MCP Example

A production-ready implementation of Model Context Protocol (MCP) server and client using FastMCP with SQLite-backed API key authentication.

**Author:** David Gwartney (david.gwartney@gmail.com)

## Prerequisites

Before you can run this project you need a terminal, Git, and `uv`. You do **not** need to install Python separately — `uv` will download and manage the correct Python version for you.

### 1. Open a terminal

A terminal (also called a shell or command prompt) is where you type commands to run software.

- **macOS**: Press `Cmd + Space`, type `Terminal`, press Enter
- **Windows**: Search for **PowerShell** in the Start menu and open it. Use PowerShell for all commands in this guide.

### 2. Install Git

Git is the tool used to download (clone) this project from GitHub.

**macOS** — Git is usually pre-installed. Confirm by running:
```bash
git --version
```
If it is not found, install the Xcode Command Line Tools:
```bash
xcode-select --install
```

**Windows** — Download and run the installer from [git-scm.com/download/win](https://git-scm.com/download/win). Accept the defaults. After installation, close and reopen PowerShell, then confirm:
```powershell
git --version
```

### 3. Install uv

`uv` is the package and Python manager used by this project. It installs all dependencies and the correct version of Python automatically.

**macOS** (Terminal):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** (PowerShell):
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, close and reopen your terminal, then confirm:

**macOS:**
```bash
uv --version
```
**Windows:**
```powershell
uv --version
```

> `uv` will automatically download Python 3.12 the first time you run `uv sync` — no separate Python installation needed.

## Overview

This project demonstrates how to build secure MCP servers and clients with:

- **SQLite-backed Authentication**: API keys stored and validated against a SQLite database
- **Middleware-based Security**: Clean separation of concerns with reusable authentication middleware
- **Case-insensitive Headers**: RFC 7230-compliant header handling
- **Class-based Architecture**: Modular, testable, and maintainable code structure
- **Cryptographic Key Generation**: Secure random API keys using Python's `secrets` module
- **Comprehensive Testing**: 62 unit tests with >90% code coverage

## Features

### Server (`mcp_examples/server.py`)

- **DatabaseManager** (`database.py`): Handles SQLite operations for API key storage and validation
- **ApiKeyMiddleware** (`middleware.py`): Validates incoming requests against stored API keys
- **MCPServer** (`server.py`): Encapsulates server setup, tool registration, and lifecycle management
- **Multiple Transport Support**: Runs via stdio (default) or HTTP transport
- **Automatic Database Initialization**: Creates schema and generates default API key on first run

### Contact Server (`mcp_examples/contacts.py`)

- **ContactDatabaseManager** (`contact_database.py`): SQLite-backed storage for mock Salesforce-style contact profiles, auto-seeded with 20 Warner Bros. cartoon character records
- **ContactMCPServer** (`contacts.py`): Subclass of `AuthenticatedMCPServer` exposing contact search and authentication tools

**Available Tools:**

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_by_last_name` | `last_name: str` | Case-insensitive partial match on last name |
| `search_by_email` | `email: str` | Case-insensitive exact match on email |
| `search_by_account_id` | `account_id: str` | Exact match on Salesforce-style account ID |
| `authenticate` | `email: str, password: str` | Verify credentials; returns contact profile (without password) or raises `ToolError` |

**Running the Contact Server:**

```bash
# stdio transport (default)
uv run -m mcp_examples.contacts

# HTTP transport
uv run -m mcp_examples.contacts --transport streamable-http --port 8000
```

**Database:** Auto-seeded `contacts.db` with 20 Warner Bros. character contacts including fields like `Id`, `FirstName`, `LastName`, `Email`, `Phone`, `Title`, `Department`, `AccountId`, `AccountName`, and more.

**Example `curl` Calls (Streamable HTTP transport):**

Start the contact server with HTTP transport:

```bash
uv run -m mcp_examples.contacts --transport streamable-http --port 8000
```

The MCP Streamable HTTP transport requires session initialization before calling tools.
Replace `YOUR_API_KEY` with the key printed on first server run.

**Step 1 — Initialize the session** (capture the `Mcp-Session-Id` header):

```bash
curl -s -D /tmp/mcp_headers -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "curl-client", "version": "1.0"}
    }
  }'

# Extract the session ID for subsequent requests
SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | awk '{print $2}' | tr -d '\r')
```

**Step 2 — Send the initialized notification:**

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
```

**Step 3 — Call tools** (all examples use the same session):

Search by email:

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
      "arguments": {
        "email": "bugs.bunny@acme.com"
      }
    }
  }'
```

Search by last name:

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
      "arguments": {
        "last_name": "Bunny"
      }
    }
  }'
```

Search by account ID:

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
      "arguments": {
        "account_id": "0011A00001xAC001"
      }
    }
  }'
```

Authenticate a contact:

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
      "arguments": {
        "email": "bugs.bunny@acme.com",
        "password": "bugs2022!"
      }
    }
  }'
```

### Client (`mcp_examples/client.py`)

- **MCPClient** (`client.py`): Manages connections and tool invocation with authentication
- **MCPClientApp** (`cli.py`): CLI application with argument parsing
- **StreamableHttpTransport**: Properly passes API keys via HTTP headers
- **Error Handling**: Graceful error reporting for connection and authentication failures

### Testing (`tests/`)

- **62 Unit Tests**: Comprehensive test coverage for all components
- **96% Coverage**: Database, middleware, server, client, and CLI classes fully tested
- **Async Test Support**: Proper testing of async/await patterns
- **Integration Tests**: End-to-end workflow validation
- **CI/CD Ready**: XML and HTML coverage reports for continuous integration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       MCP Client                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ MCPClientApp (CLI Interface)                           │ │
│  │   ├─ Argument parsing (--api-key, --url, --name)       │ │
│  │   └─ Error handling and user feedback                  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ MCPClient                                              │ │
│  │   ├─ StreamableHttpTransport (X-API-Key header)        │ │
│  │   └─ Tool invocation (greet, etc.)                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/HTTPS
                            │ X-API-Key: <token>
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       MCP Server                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ MCPServer                                              │ │
│  │   ├─ FastMCP instance                                  │ │
│  │   └─ Tool registration                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ApiKeyMiddleware                                       │ │
│  │   ├─ Extract X-API-Key header (case-insensitive)       │ │
│  │   └─ Validate via DatabaseManager                      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ DatabaseManager                                        │ │
│  │   ├─ SQLite connection management                      │ │
│  │   ├─ Schema initialization                             │ │
│  │   ├─ Key generation (secrets.token_urlsafe)            │ │
│  │   └─ Key validation (parameterized queries)            │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                │
│                            ▼                                │
│              ┌──────────────────────────┐                   │
│              │   api_keys.db (SQLite)   │                   │
│              │  ┌────────────────────┐  │                   │
│              │  │ id | key           │  │                   │
│              │  ├────────────────────┤  │                   │
│              │  │ 1  | abc123...     │  │                   │
│              │  │ 2  | xyz789...     │  │                   │
│              │  └────────────────────┘  │                   │
│              └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.12+
- `uv` package manager (handles all dependencies and virtual environments)
- FastMCP 2.14.5+ (installed via uv)

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_DB_PATH` | Path to SQLite database file | `api_keys.db` in project directory | `/var/data/keys.db` |

**macOS:**
```bash
# Set for a single command
MCP_DB_PATH=/tmp/keys.db uv run -m mcp_examples.server

# Or export for the current terminal session
export MCP_DB_PATH=/var/data/api_keys.db
uv run -m mcp_examples.server
```

**Windows (PowerShell):**
```powershell
# Set for the current terminal session
$env:MCP_DB_PATH = "C:\data\api_keys.db"
uv run -m mcp_examples.server
```

## Installation

### Clone and Setup

Open a terminal, then run these commands one at a time:

```bash
# Download the project from GitHub to your machine
git clone https://github.com/dgwartney/mcp-example.git

# Move into the project directory
cd mcp-example

# Install dependencies (uv creates a virtual environment automatically)
uv sync
```

> **What is `cd`?** It stands for "change directory" — it moves your terminal session into the project folder. All subsequent commands must be run from inside this folder.

**Note**: `uv sync` installs all required Python packages into an isolated `.venv/` folder inside the project. You do not need to create a virtual environment manually.

To also install test dependencies:
```bash
uv sync --extra test
```

## Usage

### Authentication Setup

Authentication only applies when the server is running with an HTTP transport (`streamable-http` or `sse`). The `dev` and `stdio` transports bypass authentication entirely and are intended for local development only.

#### How it works

When the server starts in HTTP mode, every incoming request must include an `X-API-Key` header containing a valid key. The server looks up that key in a local SQLite database (`api_keys.db`). Requests with a missing or unrecognised key receive an HTTP 401 response and are not processed.

#### Step 1 — Start the server and get your API key

On first run, the server automatically creates `api_keys.db`, generates a secure random API key, and prints it to the terminal:

```bash
uv run -m mcp_examples.server --transport streamable-http --port 8000
```

```
Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
```

**Copy this key and save it somewhere safe.** The server will not print it again on subsequent runs.

#### Step 2 — Recover the key if you missed it

If you did not save the key, look it up directly in the database:

**macOS:**
```bash
sqlite3 api_keys.db "SELECT * FROM api_keys;"
```

**Windows (PowerShell):**
```powershell
sqlite3 api_keys.db "SELECT * FROM api_keys;"
```

> **Windows users**: `sqlite3` is not installed by default. See the [Managing API Keys](#managing-api-keys) section for installation options.

#### Step 3 — Use the key in client requests

Pass the key in the `X-API-Key` header on every request. Examples for the tools in this project:

**Built-in client (`mcp-client`):**
```bash
uv run -m mcp_examples.cli --api-key YOUR_API_KEY --url http://localhost:8000/mcp
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

#### Adding and revoking keys

See [Managing API Keys](#managing-api-keys) below for how to add additional keys or revoke existing ones.

---

### Running the Server

#### Option 1: Direct Python Execution (stdio transport)

```bash
uv run -m mcp_examples.server
```

> **Note**: stdio transport does not require an API key. Use HTTP transport (Option 2) for authenticated remote access.

#### Database Path Configuration

By default, the server creates `api_keys.db` in the project directory. You can customize this using the `MCP_DB_PATH` environment variable:

**macOS:**
```bash
MCP_DB_PATH=/tmp/mcp_keys.db uv run -m mcp_examples.server
```

**Windows (PowerShell):**
```powershell
$env:MCP_DB_PATH = "C:\data\mcp_keys.db"
uv run -m mcp_examples.server
```

#### Option 2: HTTP Transport (for remote clients)

```bash
uv run fastmcp run mcp_examples/server.py --transport streamable-http --port 8000
```

#### Option 3: Using FastMCP CLI Development Server

```bash
uv run fastmcp dev mcp_examples/server.py
```

### Using the FastMCP CLI

The `fastmcp` CLI provides three useful commands for working with the servers in this project.

#### Inspect a server's tools

`fastmcp inspect` shows all registered tools, their parameters, and descriptions without starting the server:

```bash
# Inspect the greet server
uv run fastmcp inspect mcp_examples/server.py

# Inspect the contact server
uv run fastmcp inspect mcp_examples/contacts.py
```

#### Interactively test with MCP Inspector

`fastmcp dev` starts the server and opens the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) UI in your browser, letting you call tools interactively:

```bash
# Develop/test the greet server
uv run fastmcp dev mcp_examples/server.py

# Develop/test the contact server
uv run fastmcp dev mcp_examples/contacts.py
```

The Inspector UI will open at `http://localhost:5173` by default. You can call any tool directly from the browser — no API key is required because `dev` mode uses the stdio transport, bypassing the HTTP middleware.

#### Connect to a running remote server

`fastmcp run <url>` connects to an already-running HTTP server and creates a local proxy. This is useful for inspecting or relaying a live server:

```bash
uv run fastmcp run http://localhost:8000/mcp --transport streamable-http
```

### Running the Built-in Client (`mcp-client`)

The project includes a minimal Python client (`mcp_examples/cli.py`) registered as the `mcp-client` console script. It connects to a running HTTP server and calls the `greet` tool only — it does not support the contact server tools.

> To interact with the contact server tools (`search_by_last_name`, `search_by_email`, `search_by_account_id`, `authenticate`), use `fastmcp dev` (interactive) or `curl` (see the Contact Server section above).

#### Basic Usage

```bash
uv run -m mcp_examples.cli --api-key YOUR_API_KEY_HERE
```

#### Custom Parameters

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

#### Example Output

```bash
$ uv run -m mcp_examples.cli --api-key QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80 --name Alice
Hello, Alice!
```

### Running Tests

The project includes comprehensive unit tests with >90% code coverage for all production code.

#### Test Coverage Summary

| Component | Tests | Coverage | Details |
|-----------|-------|----------|---------|
| **mcp_examples** | 62 | 96.15% | All package modules |

**Test Categories**:
- **Unit Tests**: Individual class and method testing with mocks
- **Integration Tests**: End-to-end workflows and component interactions
- **Edge Cases**: Special inputs, error conditions, unusual scenarios
- **Async Tests**: Proper async/await testing with pytest-asyncio

#### Install Test Dependencies

```bash
uv sync --extra test
```

**Test Dependencies**:
- `pytest>=8.0.0` - Test framework
- `pytest-asyncio>=0.23.0` - Async test support
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Mocking utilities

#### Run All Tests

```bash
uv run pytest
```

#### Run Tests with Coverage Report

```bash
# Terminal report with missing lines (configured via pytest.ini)
uv run pytest
```

Open the HTML coverage report in a browser:

**macOS:**
```bash
open htmlcov/index.html
```
**Windows (PowerShell):**
```powershell
start htmlcov\index.html
```

#### Run Specific Test Files

```bash
# Test database module
uv run pytest tests/test_database.py

# Test client module
uv run pytest tests/test_client.py

# Run specific test class
uv run pytest tests/test_database.py::TestDatabaseManager

# Run specific test method
uv run pytest tests/test_database.py::TestDatabaseManager::test_init_db_creates_table

# Run with verbose output
uv run pytest -v

# Run and stop on first failure
uv run pytest -x
```

#### Test Suite Details

**Database Tests (`tests/test_database.py`)**:
- `TestDatabaseManager` (9 tests): Database initialization, schema, key validation

**Middleware Tests (`tests/test_middleware.py`)**:
- `TestApiKeyMiddleware` (7 tests): Authentication, case-insensitive headers, error handling

**Server Tests (`tests/test_server.py`)**:
- `TestMCPServer` (10 tests): Server initialization, middleware/tool registration
- `TestIntegration` (3 tests): End-to-end authentication workflows

**Client Tests (`tests/test_client.py`)**:
- `TestMCPClient` (9 tests): Client initialization, tool calls, error handling
- `TestEdgeCases` (4 tests): Special characters, unusual inputs, edge cases

**CLI Tests (`tests/test_cli.py`)**:
- `TestMCPClientApp` (14 tests): CLI parsing, argument validation, execution
- `TestIntegration` (2 tests): End-to-end client workflows

#### Example Test Output

```bash
$ uv run pytest

============================= test session starts ==============================
platform darwin -- Python 3.12.12, pytest-9.0.2, pluggy-1.6.0
collected 62 items

tests/test_cli.py ................                                       [ 25%]
tests/test_client.py ..............                                      [ 48%]
tests/test_database.py .........                                         [ 62%]
tests/test_middleware.py .......                                          [ 74%]
tests/test_server.py ................                                     [100%]

Name                         Stmts   Miss   Cover   Missing
-----------------------------------------------------------
mcp_examples/__init__.py         5      0 100.00%
mcp_examples/cli.py             22      2  90.91%   88-89
mcp_examples/client.py          16      0 100.00%
mcp_examples/database.py        25      0 100.00%
mcp_examples/middleware.py      14      0 100.00%
mcp_examples/server.py          22      2  90.91%   93, 102
-----------------------------------------------------------
TOTAL                          104      4  96.15%

======================== 62 passed in 6.96s ================================
```

### Managing API Keys

API keys are stored in `api_keys.db` SQLite database. You can manage keys directly using the `sqlite3` command-line tool.

> **Windows users**: `sqlite3` is not installed by default. Download it from [sqlite.org/download](https://www.sqlite.org/download.html) (look for "sqlite-tools" under "Precompiled Binaries for Windows"), unzip it, and add the folder to your PATH — or use [DB Browser for SQLite](https://sqlitebrowser.org/) for a graphical interface instead.

#### View Existing Keys

```bash
sqlite3 api_keys.db "SELECT * FROM api_keys;"
```

#### Add a New Key

```bash
# Generate a secure random key
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to database
sqlite3 api_keys.db "INSERT INTO api_keys (key) VALUES ('YOUR_NEW_KEY');"
```

#### Revoke a Key

```bash
sqlite3 api_keys.db "DELETE FROM api_keys WHERE key = 'KEY_TO_REVOKE';"
```

### Managing Contacts

Contact records are stored in `contacts.db` and auto-seeded with 20 Warner Bros. characters on first run. You can view, add, update, and delete records directly with `sqlite3` (see the Windows note in [Managing API Keys](#managing-api-keys) if `sqlite3` is not installed).

#### View All Contacts

```bash
sqlite3 contacts.db "SELECT Id, FirstName, LastName, Email, AccountName FROM contacts;"
```

#### Search for a Contact

```bash
# By last name
sqlite3 contacts.db "SELECT * FROM contacts WHERE LastName LIKE '%Bunny%';"

# By email
sqlite3 contacts.db "SELECT * FROM contacts WHERE Email = 'bugs.bunny@acme.com' COLLATE NOCASE;"

# By account ID
sqlite3 contacts.db "SELECT * FROM contacts WHERE AccountId = '0011A00001xAC001';"
```

#### Add a New Contact

```bash
sqlite3 contacts.db "
INSERT INTO contacts (
  Id, FirstName, LastName, Salutation, Name,
  Email, Phone, MobilePhone, Title, Department,
  AccountId, AccountName,
  MailingStreet, MailingCity, MailingState, MailingPostalCode, MailingCountry,
  LeadSource, OwnerId, CreatedDate, LastModifiedDate,
  Description, DoNotCall, HasOptedOutOfEmail, IsDeleted,
  ContactSource, CaseCount, Password
) VALUES (
  '0031A00001aBC021', 'Elmer', 'Sample', 'Mr.', 'Elmer Sample',
  'elmer.sample@example.com', '555-9999', '555-9998', 'Test User', 'Engineering',
  '0011A00001xAC001', 'ACME Corporation',
  '1 Test St', 'Burbank', 'CA', '91505', 'US',
  'Web', '0051A000001owner', '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z',
  'Test contact.', 0, 0, 0,
  'Inbound', 0, 'changeme123'
);"
```

#### Update a Contact's Password

```bash
sqlite3 contacts.db "UPDATE contacts SET Password = 'newpassword!' WHERE Email = 'bugs.bunny@acme.com' COLLATE NOCASE;"
```

#### Delete a Contact

```bash
sqlite3 contacts.db "DELETE FROM contacts WHERE Id = '0031A00001aBC021';"
```

#### Reset to Seed Data

To wipe all contacts and re-seed with the original 20 Warner Bros. characters, delete the database file and restart the server — it will recreate and re-seed automatically:

**macOS:**
```bash
rm contacts.db
uv run -m mcp_examples.contacts
```

**Windows (PowerShell):**
```powershell
del contacts.db
uv run -m mcp_examples.contacts
```

## Deployment

### Local Development

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

### Production Deployment with ngrok

For exposing your local server to the internet (useful for development and demos):

1. Clone and set up the project (if you haven't already — see [Clone and Setup](#clone-and-setup)):
   ```bash
   git clone https://github.com/dgwartney/mcp-example.git
   cd mcp-example
   uv sync
   ```

2. Install ngrok:

   **macOS:**
   ```bash
   brew install ngrok
   ```

   **Windows:** Download the installer from [ngrok.com/download](https://ngrok.com/download), run it, and follow the prompts. After installation, open a new PowerShell window.

3. Start the server you want to expose:

   **Greet server:**
   ```bash
   uv run -m mcp_examples.server --transport streamable-http --port 8000
   ```

   **Contact server:**
   ```bash
   uv run -m mcp_examples.contacts --transport streamable-http --port 8000
   ```

   On first run, the server prints its API key — save it:
   ```
   Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
   ```

4. In a second terminal, create the ngrok tunnel:
   ```bash
   ngrok http 8000
   ```

   ngrok will display a forwarding URL like `https://abc123.ngrok.app`.

5. Use the ngrok URL with the built-in client:

   **macOS:**
   ```bash
   uv run -m mcp_examples.cli \
     --api-key YOUR_API_KEY \
     --url https://YOUR-NGROK-SUBDOMAIN.ngrok.app/mcp
   ```

   **Windows (PowerShell):**
   ```powershell
   uv run -m mcp_examples.cli `
     --api-key YOUR_API_KEY `
     --url https://YOUR-NGROK-SUBDOMAIN.ngrok.app/mcp
   ```

   Or connect any MCP-compatible client to `https://YOUR-NGROK-SUBDOMAIN.ngrok.app/mcp` with the `X-API-Key` header set to your API key.

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY mcp_examples/ mcp_examples/

# Install dependencies
RUN uv sync --frozen

# Expose port
EXPOSE 8000

# Run server
CMD ["uv", "run", "fastmcp", "run", "mcp_examples/server.py", "--transport", "http", "--port", "8000", "--host", "0.0.0.0"]
```

Build and run:

```bash
# Build image
docker build -t mcp-server .

# Run container with volume mount
docker run -p 8000:8000 -v $(pwd)/api_keys.db:/app/api_keys.db mcp-server

# Or run with custom database path via environment variable
docker run -p 8000:8000 \
  -e MCP_DB_PATH=/data/keys.db \
  -v $(pwd)/data:/data \
  mcp-server
```

### Cloud Deployment

The server can be deployed to any cloud platform that supports Python applications:

#### Railway / Render / Fly.io

1. Add a `Procfile`:
   ```
   web: uv run fastmcp run mcp_examples/server.py --transport http --port $PORT --host 0.0.0.0
   ```

2. Set environment variables in your platform:
   - `MCP_DB_PATH` (optional): Custom database path, e.g., `/data/api_keys.db`

3. Push to your platform's git repository or use their CLI tools

#### AWS Lambda / Google Cloud Functions

For serverless deployment, you'll need to adapt the server to use the platform's event model. FastMCP supports custom transports for this purpose.

## Security Considerations

### API Key Management

- **Never commit** `api_keys.db` to version control (already in `.gitignore`)
- **Rotate keys regularly** in production environments
- **Use environment variables** for sensitive configuration in production
- **Implement rate limiting** for production deployments
- **Use HTTPS** for all production traffic (ngrok provides this automatically)

### Database Security

- The SQLite database uses parameterized queries to prevent SQL injection
- Keys are stored as plain text in the database - for high-security applications, consider hashing keys
- Ensure proper file permissions on `api_keys.db` (readable only by the server process)

### Header Handling

- The server implements case-insensitive header matching per RFC 7230
- All variations of `X-API-Key` header casing are supported

## Extending the Project

### Adding New Tools

Edit `mcp_examples/server.py` and add tools in the `_register_tools` method:

```python
def _register_tools(self) -> None:
    @self.mcp.tool(description="A tool that greets a user by name")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    @self.mcp.tool(description="Add two numbers")
    def add(a: int, b: int) -> int:
        return a + b

    @self.mcp.tool(description="Get current timestamp")
    def timestamp() -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat()
```

### Custom Authentication

To implement different authentication schemes, create a new middleware class:

```python
class BearerTokenMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        headers = get_http_headers()
        headers_lower = {k.lower(): v for k, v in headers.items()}
        auth_header = headers_lower.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            raise ToolError("Unauthorized: Missing or invalid token")

        token = auth_header[7:]  # Remove "Bearer " prefix
        # Validate token...

        return await call_next(context)
```

### Serving Multiple Servers on One Port

FastMCP supports **mounting** multiple servers into a single parent, letting you serve them all on one port with namespaced tools:

```python
from fastmcp import FastMCP

main = FastMCP("Main")
users = FastMCP("Users")
orders = FastMCP("Orders")

@users.tool
def get_user(id: int): ...

@orders.tool
def get_order(id: int): ...

# Mount sub-servers onto the main server
main.mount("users", users)
main.mount("orders", orders)

# Serve everything on one port
main.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

Tools are automatically namespaced (e.g., `users_get_user`, `orders_get_order`) to avoid collisions. Use `as_proxy=True` to run a mounted server as a separate proxied process:

```python
main.mount("users", users, as_proxy=True)
```

See the [FastMCP composition docs](https://gofastmcp.com/servers/composition) for more details.

**Example `curl` Calls (Mounted Servers):**

**Step 1 — Initialize the session:**

```bash
curl -s -D /tmp/mcp_headers -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "curl-client", "version": "1.0"}
    }
  }'

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | awk '{print $2}' | tr -d '\r')
```

**Step 2 — Send the initialized notification:**

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "notifications/initialized"}'
```

**Step 3 — List available tools** (verify namespaced tool names):

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

**Step 4 — Call a tool on the mounted `users` server** (note the `users_` prefix):

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "users_get_user",
      "arguments": {
        "id": 42
      }
    }
  }'
```

**Step 5 — Call a tool on the mounted `orders` server** (note the `orders_` prefix):

```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "orders_get_order",
      "arguments": {
        "id": 1001
      }
    }
  }'
```

### Adding Resources

FastMCP also supports resources (read-only data sources):

```python
@self.mcp.resource("config://settings")
def get_settings() -> str:
    return json.dumps({"version": "1.0", "env": "production"})
```

## Troubleshooting

### Client: "Error: Invalid request parameters"

**Cause**: Headers not passed correctly to the transport layer.

**Solution**: Ensure you're using `StreamableHttpTransport` with headers parameter (already implemented in `mcp_examples/client.py`).

### Client: "Error: Unauthorized: Invalid or missing API Key"

**Cause**: API key is incorrect or not in the database.

**Solution**:
1. Check the key printed during server first run
2. Verify the key exists in the database:
   ```bash
   sqlite3 api_keys.db "SELECT * FROM api_keys;"
   ```

### Server: "Server object 'mcp' not found"

**Cause**: FastMCP CLI expects a module-level `mcp` variable.

**Solution**: Already handled in `mcp_examples/server.py` with:
```python
server = MCPServer()
mcp = server.mcp
```

### Connection Refused

**Cause**: Server not running or wrong URL/port.

**Solution**:
1. Verify server is running: `lsof -i :8000` (on Unix)
2. Check the URL matches the server's address
3. Ensure firewall allows the connection

## Project Structure

```
mcp-examples/
├── mcp_examples/             # Main Python package
│   ├── __init__.py           # Re-exports all public classes
│   ├── database.py           # DatabaseManager (SQLite API key storage)
│   ├── middleware.py          # ApiKeyMiddleware (request authentication)
│   ├── contact_database.py    # ContactDatabaseManager (mock contacts)
│   ├── contacts.py            # ContactMCPServer + module-level mcp instance
│   ├── server.py              # GreetMCPServer + module-level mcp instance
│   ├── client.py              # MCPClient (remote tool invocation)
│   └── cli.py                 # MCPClientApp CLI + main() entry point
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_contact_database.py  # ContactDatabaseManager tests
│   ├── test_contacts.py       # ContactMCPServer + integration tests
│   ├── test_database.py       # DatabaseManager tests
│   ├── test_middleware.py     # ApiKeyMiddleware tests
│   ├── test_server.py        # GreetMCPServer + integration tests
│   ├── test_client.py        # MCPClient + edge case tests
│   └── test_cli.py           # MCPClientApp + integration tests
├── auth.py                   # Standalone middleware example (reference)
├── api_keys.db               # SQLite database (generated on first run)
├── pyproject.toml            # Project dependencies (uv)
├── uv.lock                   # Dependency lock file
├── pytest.ini                # Pytest configuration
├── .coveragerc               # Coverage configuration
├── CHANGELOG.md              # Version history and changes
├── CLAUDE.md                 # Instructions for Claude Code
├── KORE_AI_INTEGRATION.md    # Kore AI Agent Platform integration guide
└── README.md                 # This file
```

## Contributing

Contributions are welcome! Please ensure:

- Code follows PEP 8 style guidelines
- All classes and functions have docstrings (Google style)
- Type hints are used throughout
- Changes maintain backward compatibility
- Security best practices are followed

## License

This project is provided as-is for educational and demonstration purposes.

## Platform Integrations

### Kore AI Agent Platform

This MCP server can be integrated with the Kore AI Agent Platform to provide tools for AI agents. See **[KORE_AI_INTEGRATION.md](KORE_AI_INTEGRATION.md)** for a comprehensive guide including:

- Deployment options (ngrok, Docker, cloud platforms)
- Step-by-step Kore AI configuration
- Authentication setup
- Testing procedures
- Troubleshooting and best practices

## Resources

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [uv Package Manager](https://github.com/astral-sh/uv)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Kore AI Documentation](https://docs.kore.ai)

## Support

For issues, questions, or contributions, please open an issue on the project repository.
