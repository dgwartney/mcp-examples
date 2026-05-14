# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-11

### Added

- **MCP Server** (`mcp_examples/server.py`)
  - FastMCP server implementation with SQLite-backed API key authentication
  - `DatabaseManager` class for API key storage and validation
  - `ApiKeyMiddleware` for request authentication with case-insensitive header handling (RFC 7230 compliant)
  - `GreetMCPServer` class encapsulating server setup and tool registration
  - Cryptographically secure API key generation using `secrets.token_urlsafe()`
  - Automatic database initialization with default key generation on first run
  - Support for both stdio and HTTP transports
  - Parameterized SQL queries for SQL injection protection
  - `greet` tool for demonstration purposes

- **MCP Client** (`mcp_examples/client.py`)
  - FastMCP client implementation with API key authentication
  - `MCPClient` class for connecting to remote MCP servers
  - `MCPClientApp` class providing CLI interface with argparse
  - `StreamableHttpTransport` integration for custom header passing
  - Command-line arguments: `--api-key`, `--name`, `--url`
  - Error handling and user-friendly error messages

- **Documentation**
  - Comprehensive README.md with:
    - Architecture diagram
    - Installation instructions using uv
    - Usage examples for server and client
    - API key management guide
    - Deployment options (local, ngrok, Docker, cloud)
    - Security considerations and best practices
    - Troubleshooting guide
    - Extension examples
  - Complete Python docstrings (Google style) for all modules, classes, and methods
  - Type hints throughout codebase
  - Author attribution in all source files
  - Project metadata in `pyproject.toml`

- **Project Structure**
  - Python 3.12+ requirement
  - `uv` package manager configuration
  - FastMCP 2.14.5+ dependency
  - SQLite database for API key storage
  - Git repository with structured commit history

### Security

- Case-insensitive HTTP header matching per RFC 7230
- Parameterized SQL queries to prevent SQL injection
- Cryptographically secure random key generation
- API key validation middleware for all requests

### Author

David Gwartney <david.gwartney@gmail.com>

---

[0.1.0]: https://github.com/yourusername/mcp-examples/releases/tag/v0.1.0
