# Testing

The project includes 62 unit tests with 96% code coverage across all modules.

## Install test dependencies

```bash
uv sync --extra test
```

**Test dependencies:**
- `pytest>=8.0.0` — Test framework
- `pytest-asyncio>=0.23.0` — Async test support
- `pytest-cov>=4.1.0` — Coverage reporting
- `pytest-mock>=3.12.0` — Mocking utilities

## Run all tests

```bash
uv run pytest
```

## Run tests with coverage report

```bash
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

## Run specific tests

```bash
# Single file
uv run pytest tests/test_database.py

# Single class
uv run pytest tests/test_database.py::TestDatabaseManager

# Single method
uv run pytest tests/test_database.py::TestDatabaseManager::test_init_db_creates_table

# Verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x
```

## Test suite

| File | Class | Tests | Coverage |
|------|-------|-------|----------|
| `test_database.py` | `TestDatabaseManager` | 9 | Database initialization, schema, key validation |
| `test_middleware.py` | `TestApiKeyMiddleware` | 7 | Authentication, case-insensitive headers, error handling |
| `test_server.py` | `TestMCPServer` | 10 | Server initialization, middleware/tool registration |
| `test_server.py` | `TestIntegration` | 3 | End-to-end authentication workflows |
| `test_client.py` | `TestMCPClient` | 9 | Client initialization, tool calls, error handling |
| `test_client.py` | `TestEdgeCases` | 4 | Special characters, unusual inputs, edge cases |
| `test_cli.py` | `TestMCPClientApp` | 14 | CLI parsing, argument validation, execution |
| `test_cli.py` | `TestIntegration` | 2 | End-to-end client workflows |

## Example output

```
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
mcp_server_kit/__init__.py         5      0 100.00%
mcp_server_kit/cli.py             22      2  90.91%   88-89
mcp_server_kit/client.py          16      0 100.00%
mcp_server_kit/database.py        25      0 100.00%
mcp_server_kit/middleware.py      14      0 100.00%
mcp_server_kit/server.py          22      2  90.91%   93, 102
-----------------------------------------------------------
TOTAL                          104      4  96.15%

======================== 62 passed in 6.96s ================================
```
