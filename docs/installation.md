# Installation

## Clone and Setup

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

`uv sync` installs all required Python packages into an isolated `.venv/` folder inside the project. You do not need to create a virtual environment manually.

To also install test dependencies:
```bash
uv sync --extra test
```

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_DB_PATH` | Path to the API key SQLite database | `api_keys.db` in working directory | `/data/api_keys.db` |
| `CONTACTS_DB_PATH` | Path to the contacts SQLite database | `contacts.db` in working directory | `/data/contacts.db` |

**macOS:**
```bash
# Set for a single command
MCP_DB_PATH=/tmp/keys.db uv run -m mcp_server_kit.server

# Or export for the current terminal session
export MCP_DB_PATH=/var/data/api_keys.db
uv run -m mcp_server_kit.server
```

**Windows (PowerShell):**
```powershell
# Set for the current terminal session
$env:MCP_DB_PATH = "C:\data\api_keys.db"
uv run -m mcp_server_kit.server
```
