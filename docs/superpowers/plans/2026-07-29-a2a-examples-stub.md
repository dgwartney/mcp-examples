# a2a-examples Stub Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a new, separate `a2a-examples` repository at `/Users/dgwartney/git/a2a-examples` providing a reusable base-class framework (`a2a_agent_kit`) for building future A2A (Agent2Agent protocol) agents, with one trivial example agent proving the whole shape end-to-end.

**Architecture:** An `AuthenticatedA2AAgent` abstract base class (parallel to `mcp_server_kit.base.AuthenticatedMCPServer`) owns SQLite-backed API-key auth (ported `DatabaseManager` + `ApiKeyMiddleware`), wraps a Microsoft Agent Framework `ChatAgent` in an internal `AgentExecutor` bridge to the A2A protocol, and builds a Starlette app via `A2AStarletteApplication`. Subclasses implement two hooks (`_create_chat_agent()`, `_agent_card_info()`). One concrete subclass, `GreetA2AAgent`, backed by a hand-written no-network `EchoChatClient`, demonstrates the pattern. A thin async client wrapper and CLI mirror `mcp_server_kit.client`/`cli`.

**Tech Stack:** Python >=3.10, `uv` (never `pip`), `agent-framework` + `agent-framework-a2a` + `a2a-sdk[http-server]`, Starlette, uvicorn, httpx, pytest + pytest-asyncio + pytest-cov + pytest-mock, hatchling build backend.

## Global Constraints

- Never use `pip`, `pip3`, or `python -m venv` — use `uv venv`, `uv sync`, `uv add`, `uv run`, `uv build` exclusively.
- Python `>=3.10`.
- Build backend: `hatchling`.
- No `combined.py` / multi-agent Starlette mount — each A2A agent is its own deployable unit (per approved design doc, `docs/superpowers/specs/2026-07-29-a2a-examples-stub-design.md`).
- No scaffold/generator script in this stub — deferred (see design doc "Out of scope").
- Package name: `a2a_agent_kit`. Repo name: `a2a-examples`.
- Every module gets a module docstring with an `Author:` line: `David Gwartney <david.gwartney@gmail.com>` (matches `mcp_server_kit` convention).

---

### Task 1: Repo scaffolding and packaging

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/pyproject.toml`
- Create: `/Users/dgwartney/git/a2a-examples/pytest.ini`
- Create: `/Users/dgwartney/git/a2a-examples/.gitignore`
- Create: `/Users/dgwartney/git/a2a-examples/LICENSE`
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/__init__.py`
- Create: `/Users/dgwartney/git/a2a-examples/tests/__init__.py` (empty)

**Interfaces:**
- Produces: `a2a_agent_kit.__version__` (str), importable package `a2a_agent_kit` with no I/O on import.

- [ ] **Step 1: Create the repo directory and git init**

```bash
mkdir -p /Users/dgwartney/git/a2a-examples
cd /Users/dgwartney/git/a2a-examples
git init
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
*.db
.pytest_cache/
htmlcov/
.coverage
coverage.xml
dist/
*.egg-info/
```

- [ ] **Step 3: Copy the LICENSE**

```bash
cp /Users/dgwartney/git/mcp-examples/LICENSE /Users/dgwartney/git/a2a-examples/LICENSE
```

- [ ] **Step 4: Write `pyproject.toml`**

```toml
[project]
name = "a2a-agent-kit"
description = "Toolkit for building authenticated A2A (Agent2Agent protocol) agents with SQLite-backed API key auth, plus a remote client."
readme = "README.md"
authors = [
    {name = "David Gwartney", email = "david.gwartney@gmail.com"}
]
requires-python = ">=3.10"
license = "MIT"
license-files = ["LICENSE"]
keywords = [
    "a2a",
    "agent2agent",
    "agent-protocol",
    "llm",
    "ai",
    "authentication",
    "api-key",
    "agent",
    "toolkit",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
]
dynamic = ["version"]
dependencies = [
    "agent-framework",
    "agent-framework-a2a",
    "a2a-sdk[http-server]>=0.3.5",
    "httpx>=0.27.0",
    "starlette>=0.37.0",
    "uvicorn>=0.30.0",
]

[project.urls]
Homepage = "https://github.com/dgwartney/a2a-examples"
Repository = "https://github.com/dgwartney/a2a-examples"
Issues = "https://github.com/dgwartney/a2a-examples/issues"

[project.scripts]
a2a-client = "a2a_agent_kit.cli:main"

[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.version]
path = "a2a_agent_kit/__init__.py"

[tool.hatch.build.targets.wheel]
packages = ["a2a_agent_kit"]
```

- [ ] **Step 5: Write `pytest.ini`**

```ini
[pytest]
# Pytest configuration for a2a-examples

python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*

addopts =
    -v
    --showlocals
    --cov=a2a_agent_kit
    --cov-report=html
    --cov-report=term-missing
    --cov-report=xml
    --strict-markers
    -ra

[coverage:run]
source = .
omit =
    .venv/*
    test_*.py
    *_test.py
    setup.py
    */tests/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

markers =
    asyncio: mark test as async test
    integration: mark test as integration test
    unit: mark test as unit test
    slow: mark test as slow running

asyncio_mode = auto

testpaths = tests
```

- [ ] **Step 6: Write `a2a_agent_kit/__init__.py`**

```python
"""
a2a_agent_kit — toolkit for building authenticated A2A agents.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

__version__ = "0.1.0"
```

- [ ] **Step 7: Create empty `tests/__init__.py`**

```bash
touch /Users/dgwartney/git/a2a-examples/tests/__init__.py
```

- [ ] **Step 8: Sync dependencies and verify the package imports with no I/O**

```bash
cd /Users/dgwartney/git/a2a-examples
uv sync --extra test
uv run python -c "import a2a_agent_kit; print(a2a_agent_kit.__version__)"
```

Expected: prints `0.1.0` with no errors, no `.db` files created in the directory.

- [ ] **Step 9: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add pyproject.toml pytest.ini .gitignore LICENSE a2a_agent_kit/__init__.py tests/__init__.py uv.lock
git commit -m "Scaffold a2a-agent-kit package"
```

---

### Task 2: `database.py` — ported `DatabaseManager`

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/database.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_database.py`

**Interfaces:**
- Consumes: nothing (stdlib `sqlite3`, `secrets`, `logging` only).
- Produces: `DatabaseManager(db_path: str)` with `.init_db() -> Optional[str]` and `.validate_key(api_key: Optional[str]) -> bool`, used by `base.py` in Task 4.

- [ ] **Step 1: Write the failing tests**

```python
"""
Unit tests for a2a_agent_kit.database

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import sqlite3

import pytest

from a2a_agent_kit.database import DatabaseManager


class TestInitDb:

    def test_creates_table_and_seeds_default_key(self, tmp_path):
        db_path = str(tmp_path / "keys.db")
        manager = DatabaseManager(db_path)

        generated_key = manager.init_db()

        assert generated_key is not None
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT key FROM api_keys").fetchone()
        conn.close()
        assert row[0] == generated_key

    def test_second_call_does_not_reseed(self, tmp_path):
        db_path = str(tmp_path / "keys.db")
        manager = DatabaseManager(db_path)
        manager.init_db()

        second_result = manager.init_db()

        assert second_result is None


class TestValidateKey:

    def test_valid_key_returns_true(self, tmp_path):
        db_path = str(tmp_path / "keys.db")
        manager = DatabaseManager(db_path)
        key = manager.init_db()

        assert manager.validate_key(key) is True

    def test_invalid_key_returns_false(self, tmp_path):
        db_path = str(tmp_path / "keys.db")
        manager = DatabaseManager(db_path)
        manager.init_db()

        assert manager.validate_key("not-a-real-key") is False

    def test_none_key_returns_false(self, tmp_path):
        db_path = str(tmp_path / "keys.db")
        manager = DatabaseManager(db_path)
        manager.init_db()

        assert manager.validate_key(None) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_database.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_agent_kit.database'`.

- [ ] **Step 3: Write `a2a_agent_kit/database.py`**

```python
"""
Database management for API key storage and validation.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import logging
import secrets
import sqlite3
from typing import Optional

_logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for API key storage and validation.

    Attributes:
        db_path (str): Path to the SQLite database file.
    """

    def __init__(self, db_path: str):
        """
        Initialize the DatabaseManager.

        Args:
            db_path (str): Absolute path to the SQLite database file.
        """
        self.db_path = db_path

    def init_db(self) -> Optional[str]:
        """
        Initialize the database schema and create a default API key.

        Creates the api_keys table if it doesn't exist. If the table is empty,
        generates a cryptographically secure random API key using
        ``secrets.token_urlsafe()`` and inserts it as the default key. The
        generated key is emitted via ``logging`` at INFO level, never printed,
        so importing an agent module never leaks a secret.

        Returns:
            Optional[str]: The newly generated default key if the table was
            empty, otherwise ``None``.
        """
        conn = sqlite3.connect(self.db_path)
        generated_key: Optional[str] = None
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS api_keys "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL)"
            )
            row = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()
            if row[0] == 0:
                generated_key = secrets.token_urlsafe(32)
                conn.execute(
                    "INSERT INTO api_keys (key) VALUES (?)", (generated_key,)
                )
                _logger.info("Generated default API key: %s", generated_key)
            conn.commit()
        finally:
            conn.close()
        return generated_key

    def validate_key(self, api_key: Optional[str]) -> bool:
        """
        Validate an API key against the database.

        Args:
            api_key (Optional[str]): The API key to validate. Can be None.

        Returns:
            bool: True if the key exists in the database, False otherwise.
        """
        if api_key is None:
            return False

        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM api_keys WHERE key = ?", (api_key,)
            ).fetchone()
        finally:
            conn.close()
        return row is not None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_database.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/database.py tests/test_database.py
git commit -m "Add DatabaseManager for API key storage"
```

---

### Task 3: `middleware.py` — ported `ApiKeyMiddleware`

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/middleware.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_middleware.py`

**Interfaces:**
- Consumes: `DatabaseManager` from Task 2 (`a2a_agent_kit.database.DatabaseManager`, `.validate_key`).
- Produces: `ApiKeyMiddleware(app, db_manager: DatabaseManager)` (a Starlette `BaseHTTPMiddleware` subclass), used by `base.py` in Task 4.

- [ ] **Step 1: Write the failing tests**

```python
"""
Unit tests for a2a_agent_kit.middleware

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from a2a_agent_kit.database import DatabaseManager
from a2a_agent_kit.middleware import ApiKeyMiddleware


def _build_app(db_manager: DatabaseManager) -> Starlette:
    async def ok(request):
        return PlainTextResponse("ok")

    return Starlette(
        routes=[Route("/ping", ok)],
        middleware=[Middleware(ApiKeyMiddleware, db_manager=db_manager)],
    )


class TestApiKeyMiddleware:

    def test_missing_key_returns_401(self, tmp_path):
        db_manager = DatabaseManager(str(tmp_path / "keys.db"))
        db_manager.init_db()
        app = _build_app(db_manager)

        with TestClient(app) as client:
            resp = client.get("/ping")

        assert resp.status_code == 401
        assert resp.json() == {"error": "Unauthorized: Invalid or missing API Key"}

    def test_invalid_key_returns_401(self, tmp_path):
        db_manager = DatabaseManager(str(tmp_path / "keys.db"))
        db_manager.init_db()
        app = _build_app(db_manager)

        with TestClient(app) as client:
            resp = client.get("/ping", headers={"X-API-Key": "wrong"})

        assert resp.status_code == 401

    def test_valid_key_passes_through(self, tmp_path):
        db_manager = DatabaseManager(str(tmp_path / "keys.db"))
        key = db_manager.init_db()
        app = _build_app(db_manager)

        with TestClient(app) as client:
            resp = client.get("/ping", headers={"X-API-Key": key})

        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_header_match_is_case_insensitive(self, tmp_path):
        db_manager = DatabaseManager(str(tmp_path / "keys.db"))
        key = db_manager.init_db()
        app = _build_app(db_manager)

        with TestClient(app) as client:
            resp = client.get("/ping", headers={"x-api-key": key})

        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_middleware.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_agent_kit.middleware'`.

- [ ] **Step 3: Write `a2a_agent_kit/middleware.py`**

```python
"""
API key authentication middleware for A2A agents.

Uses Starlette's BaseHTTPMiddleware to intercept requests at the HTTP level,
returning a proper 401 status code for invalid or missing API keys.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from a2a_agent_kit.database import DatabaseManager


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for validating API keys on incoming requests.

    Extracts the X-API-Key header from HTTP requests and validates it
    against the database. Header matching is case-insensitive per RFC 7230.
    Requests with invalid or missing API keys receive an HTTP 401 response.

    Attributes:
        db_manager (DatabaseManager): Database manager instance for key validation.
    """

    def __init__(self, app, db_manager: DatabaseManager):
        """
        Initialize the ApiKeyMiddleware.

        Args:
            app: The ASGI application to wrap.
            db_manager (DatabaseManager): Database manager for API key validation.
        """
        super().__init__(app)
        self.db_manager = db_manager

    async def dispatch(self, request: Request, call_next):
        """
        Process incoming requests and validate API keys.

        Args:
            request (Request): The incoming HTTP request.
            call_next: Callable to invoke the next middleware or route handler.

        Returns:
            Response: The response from the next handler if authenticated,
                or a 401 JSON error response if not.
        """
        api_key = request.headers.get("x-api-key")

        if not self.db_manager.validate_key(api_key):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: Invalid or missing API Key"},
            )

        return await call_next(request)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_middleware.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/middleware.py tests/test_middleware.py
git commit -m "Add ApiKeyMiddleware"
```

---

### Task 4: `base.py` — `AuthenticatedA2AAgent` base class

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/base.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_base.py`

**Interfaces:**
- Consumes: `DatabaseManager` (Task 2), `ApiKeyMiddleware` (Task 3); `agent_framework.ChatAgent`, `agent_framework.AgentThread`; `a2a.server.agent_execution.{AgentExecutor, RequestContext}`; `a2a.server.apps.A2AStarletteApplication`; `a2a.server.events.EventQueue`; `a2a.server.request_handlers.DefaultRequestHandler`; `a2a.server.tasks.InMemoryTaskStore`; `a2a.types.{AgentCapabilities, AgentCard, Message, Part, Role, TaskState, TaskStatus, TaskStatusUpdateEvent, TextPart, TransportProtocol}`.
- Produces: abstract class `AuthenticatedA2AAgent` with:
  - `self.db_manager: DatabaseManager`, `self.name: str`
  - abstract `_create_chat_agent(self) -> ChatAgent`
  - abstract `_agent_card_info(self) -> dict` (keys: `description: str`, `skills: list[AgentSkill]`)
  - `build_app(self, host: str = "0.0.0.0", port: int = 8000, url: Optional[str] = None) -> Starlette`
  - `serve(self, host: str = "0.0.0.0", port: int = 8000, url: Optional[str] = None) -> None`
  - `main(self) -> None`
  Used by `greet_agent.py` in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
"""
Unit tests for a2a_agent_kit.base

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from collections.abc import AsyncIterable, MutableSequence

import pytest
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentSkill,
    Message,
    MessageSendParams,
    Part,
    Role,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)
from agent_framework import ChatAgent
from agent_framework._clients import BaseChatClient
from agent_framework._types import ChatMessage, ChatOptions, ChatResponse, ChatResponseUpdate
from starlette.testclient import TestClient

from a2a_agent_kit.base import AuthenticatedA2AAgent


class _StubChatClient(BaseChatClient):
    """A minimal chat client that always replies with a fixed string."""

    async def _inner_get_response(
        self, *, messages: MutableSequence[ChatMessage], chat_options: ChatOptions, **kwargs
    ) -> ChatResponse:
        return ChatResponse(text="STUB-REPLY")

    async def _inner_get_streaming_response(
        self, *, messages: MutableSequence[ChatMessage], chat_options: ChatOptions, **kwargs
    ) -> AsyncIterable[ChatResponseUpdate]:
        yield ChatResponseUpdate(text="STUB-REPLY")


class _StubA2AAgent(AuthenticatedA2AAgent):
    """Test double: a trivial subclass to exercise the base class."""

    def _create_chat_agent(self) -> ChatAgent:
        return ChatAgent(chat_client=_StubChatClient(), instructions="stub")

    def _agent_card_info(self) -> dict:
        return {
            "description": "Stub agent for tests",
            "skills": [
                AgentSkill(
                    id="stub", name="Stub Skill", description="Always replies STUB-REPLY", tags=["stub"]
                )
            ],
        }


def _make_request_context(text: str) -> RequestContext:
    message = Message(
        role=Role.user, message_id="m1", parts=[Part(root=TextPart(text=text))]
    )
    return RequestContext(
        request=MessageSendParams(message=message),
        task_id="task-1",
        context_id="ctx-1",
    )


class TestAgentCard:

    def test_build_app_exposes_agent_card_with_subclass_info(self, tmp_path):
        agent = _StubA2AAgent(name="Stub", db_path=str(tmp_path / "keys.db"))
        key = agent.db_manager.validate_key  # sanity: db_manager exists
        assert callable(key)

        app = agent.build_app(host="127.0.0.1", port=9001)

        # Fetch the seeded key directly from the manager's own db file.
        import sqlite3
        conn = sqlite3.connect(agent.db_manager.db_path)
        api_key = conn.execute("SELECT key FROM api_keys LIMIT 1").fetchone()[0]
        conn.close()

        with TestClient(app) as client:
            resp = client.get(
                "/.well-known/agent-card.json", headers={"X-API-Key": api_key}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "Stub agent for tests"
        assert body["skills"][0]["id"] == "stub"


class TestAuthMiddleware:

    def test_agent_card_requires_api_key(self, tmp_path):
        agent = _StubA2AAgent(name="Stub", db_path=str(tmp_path / "keys.db"))
        app = agent.build_app(host="127.0.0.1", port=9002)

        with TestClient(app) as client:
            resp = client.get("/.well-known/agent-card.json")

        assert resp.status_code == 401


class TestExecutorBridge:

    @pytest.mark.asyncio
    async def test_execute_enqueues_working_then_completed_with_reply_text(self, tmp_path):
        agent = _StubA2AAgent(name="Stub", db_path=str(tmp_path / "keys.db"))
        executor = agent._executor
        queue = EventQueue()
        context = _make_request_context("hello")

        await executor.execute(context, queue)

        first = queue.queue.get_nowait()
        second = queue.queue.get_nowait()

        assert isinstance(first, TaskStatusUpdateEvent)
        assert first.status.state == TaskState.working
        assert first.final is False

        assert isinstance(second, TaskStatusUpdateEvent)
        assert second.status.state == TaskState.completed
        assert second.final is True
        assert second.status.message.parts[0].root.text == "STUB-REPLY"

    @pytest.mark.asyncio
    async def test_cancel_enqueues_canceled_status(self, tmp_path):
        agent = _StubA2AAgent(name="Stub", db_path=str(tmp_path / "keys.db"))
        executor = agent._executor
        queue = EventQueue()
        context = _make_request_context("hello")

        await executor.cancel(context, queue)

        event = queue.queue.get_nowait()
        assert isinstance(event, TaskStatusUpdateEvent)
        assert event.status.state == TaskState.canceled
        assert event.final is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_base.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_agent_kit.base'`.

- [ ] **Step 3: Write `a2a_agent_kit/base.py`**

```python
"""
Abstract base class for authenticated A2A agents.

Provides API key authentication infrastructure and the A2A protocol
plumbing (AgentExecutor bridge, AgentCard, Starlette app) so that
subclasses only need to implement ``_create_chat_agent()`` and
``_agent_card_info()``.

Author:
    David Gwartney <david.gwartney@gmail.com>

Environment Variables:
    A2A_DB_PATH: Optional path to SQLite database file.
                 Defaults to api_keys.db in the current working directory if not set.
"""

import argparse
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    Message,
    Part,
    Role,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
    TransportProtocol,
)
from agent_framework import AgentThread, ChatAgent
from starlette.applications import Starlette

from a2a_agent_kit.database import DatabaseManager
from a2a_agent_kit.middleware import ApiKeyMiddleware


class _ChatAgentExecutor(AgentExecutor):
    """Bridges A2A requests to an ``agent_framework.ChatAgent``."""

    def __init__(self, chat_agent: ChatAgent) -> None:
        self._agent = chat_agent
        self._threads: dict[str, AgentThread] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id or ""

        if context_id not in self._threads:
            self._threads[context_id] = self._agent.get_new_thread()
        thread = self._threads[context_id]

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        response = await self._agent.run(user_text, thread=thread)
        reply_text = response.text or ""

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(
                    state=TaskState.completed,
                    message=Message(
                        role=Role.agent,
                        message_id=str(uuid.uuid4()),
                        parts=[Part(root=TextPart(text=reply_text))],
                    ),
                ),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id or "",
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


class AuthenticatedA2AAgent(ABC):
    """
    Abstract base class for A2A agents with API key authentication.

    Handles database initialization, chat agent construction, the
    AgentExecutor bridge, agent card assembly, and middleware registration.
    Subclasses provide domain behavior via ``_create_chat_agent()`` and
    ``_agent_card_info()``.

    Attributes:
        db_manager (DatabaseManager): Manages API key database operations.
        name (str): Name of the agent, used in its AgentCard.
    """

    def __init__(self, name: str = "MyA2AAgent", db_path: Optional[str] = None):
        """
        Initialize the authenticated A2A agent.

        Args:
            name (str, optional): Name of the agent. Defaults to "MyA2AAgent".
            db_path (Optional[str], optional): Path to the SQLite database.
                If None, checks the A2A_DB_PATH environment variable.
                If not set, defaults to api_keys.db in the current working
                directory. Defaults to None.
        """
        if db_path is None:
            db_path = os.environ.get(
                "A2A_DB_PATH", os.path.join(os.getcwd(), "api_keys.db")
            )

        self.name = name
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.init_db()

        self._chat_agent = self._create_chat_agent()
        self._executor = _ChatAgentExecutor(self._chat_agent)

    @abstractmethod
    def _create_chat_agent(self) -> ChatAgent:
        """Subclasses must implement this to build their ChatAgent (chat client, instructions, tools)."""
        ...

    @abstractmethod
    def _agent_card_info(self) -> dict:
        """Subclasses must implement this to return ``{"description": str, "skills": list[AgentSkill]}``."""
        ...

    def _build_agent_card(self, host: str, port: int, url: Optional[str] = None) -> AgentCard:
        base_url = url.rstrip("/") + "/" if url else f"http://{host}:{port}/"
        info = self._agent_card_info()
        return AgentCard(
            name=self.name,
            description=info["description"],
            url=base_url,
            version="0.1.0",
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            capabilities=AgentCapabilities(streaming=False),
            preferred_transport=TransportProtocol.jsonrpc,
            skills=info["skills"],
        )

    def build_app(
        self, host: str = "0.0.0.0", port: int = 8000, url: Optional[str] = None
    ) -> Starlette:
        """
        Build the Starlette application serving this agent over A2A.

        API key authentication middleware is applied to every route,
        including the agent card discovery endpoint.

        Args:
            host (str, optional): Host used to build the default agent card URL. Defaults to "0.0.0.0".
            port (int, optional): Port used to build the default agent card URL. Defaults to 8000.
            url (Optional[str], optional): Public URL to use instead of host:port. Defaults to None.

        Returns:
            Starlette: The configured application.
        """
        task_store = InMemoryTaskStore()
        request_handler = DefaultRequestHandler(
            agent_executor=self._executor, task_store=task_store
        )
        agent_card = self._build_agent_card(host, port, url)
        app_builder = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )
        app = app_builder.build()
        app.add_middleware(ApiKeyMiddleware, db_manager=self.db_manager)
        return app

    def serve(
        self, host: str = "0.0.0.0", port: int = 8000, url: Optional[str] = None
    ) -> None:
        """
        Start the A2A HTTP server. Blocks until the server is shut down.

        Args:
            host (str, optional): Host to bind. Defaults to "0.0.0.0".
            port (int, optional): Port to bind. Defaults to 8000.
            url (Optional[str], optional): Public URL for the agent card (e.g. an ngrok URL). Defaults to None.
        """
        app = self.build_app(host, port, url)
        display_url = url or f"http://{host}:{port}"
        print(f"A2A agent '{self.name}' serving on http://{host}:{port}/")
        print(f"  Agent card: {display_url.rstrip('/')}/.well-known/agent-card.json")
        uvicorn.run(app, host=host, port=port)

    def main(self) -> None:
        """
        Parse command-line arguments and run the agent.

        Provides ``--host``, ``--port``, and ``--url`` flags so every
        subclass gets HTTP serving without duplicating argument parsing.
        """
        parser = argparse.ArgumentParser(description=f"{self.name} A2A Agent")
        parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
        parser.add_argument(
            "--port", type=int, default=8000, help="Port to bind (default: 8000)"
        )
        parser.add_argument(
            "--url", default=None, help="Public URL for the agent card (e.g. an ngrok URL)"
        )
        args = parser.parse_args()
        self.serve(host=args.host, port=args.port, url=args.url)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_base.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/base.py tests/test_base.py
git commit -m "Add AuthenticatedA2AAgent base class"
```

---

### Task 5: `greet_agent.py` — `EchoChatClient` + `GreetA2AAgent` example

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/greet_agent.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_greet_agent.py`

**Interfaces:**
- Consumes: `AuthenticatedA2AAgent` (Task 4), `agent_framework.ChatAgent`, `agent_framework._clients.BaseChatClient`, `agent_framework._types.{ChatMessage, ChatOptions, ChatResponse, ChatResponseUpdate}`, `a2a.types.AgentSkill`.
- Produces: `EchoChatClient` (a `BaseChatClient` that replies `"Hello, {last user message text}!"` with no network calls), `GreetA2AAgent` (a concrete `AuthenticatedA2AAgent`), module-level `if __name__ == "__main__":` entry point.

- [ ] **Step 1: Write the failing tests**

```python
"""
Unit tests for a2a_agent_kit.greet_agent

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import pytest
from a2a.server.events import EventQueue
from a2a.types import Message, MessageSendParams, Part, Role, TaskState, TaskStatusUpdateEvent, TextPart
from a2a.server.agent_execution import RequestContext

from a2a_agent_kit.greet_agent import EchoChatClient, GreetA2AAgent


def _make_request_context(text: str) -> RequestContext:
    message = Message(role=Role.user, message_id="m1", parts=[Part(root=TextPart(text=text))])
    return RequestContext(
        request=MessageSendParams(message=message), task_id="task-1", context_id="ctx-1"
    )


class TestEchoChatClient:

    @pytest.mark.asyncio
    async def test_get_response_echoes_greeting(self):
        from agent_framework._types import ChatMessage, ChatOptions

        client = EchoChatClient()
        response = await client.get_response("World", chat_options=ChatOptions())

        assert response.text == "Hello, World!"

    @pytest.mark.asyncio
    async def test_streaming_response_yields_same_greeting(self):
        from agent_framework._types import ChatOptions

        client = EchoChatClient()
        updates = [
            update
            async for update in client.get_streaming_response("Ford", chat_options=ChatOptions())
        ]

        assert len(updates) == 1
        assert updates[0].text == "Hello, Ford!"


class TestGreetA2AAgent:

    def test_agent_card_has_greet_skill(self, tmp_path):
        agent = GreetA2AAgent(db_path=str(tmp_path / "keys.db"))
        info = agent._agent_card_info()

        assert info["skills"][0].id == "greet"

    @pytest.mark.asyncio
    async def test_execute_greets_the_supplied_name(self, tmp_path):
        agent = GreetA2AAgent(db_path=str(tmp_path / "keys.db"))
        queue = EventQueue()
        context = _make_request_context("Ford")

        await agent._executor.execute(context, queue)

        queue.queue.get_nowait()  # working status, not asserted here
        completed = queue.queue.get_nowait()

        assert isinstance(completed, TaskStatusUpdateEvent)
        assert completed.status.state == TaskState.completed
        assert completed.status.message.parts[0].root.text == "Hello, Ford!"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_greet_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_agent_kit.greet_agent'`.

- [ ] **Step 3: Write `a2a_agent_kit/greet_agent.py`**

```python
"""
A2A agent with a greet skill, backed by a no-network echo chat client.

Demonstrates how to build an A2A agent by subclassing
``AuthenticatedA2AAgent`` and implementing ``_create_chat_agent()`` and
``_agent_card_info()``. ``EchoChatClient`` always echoes the user's
message back as a greeting — it makes no external model calls, so this
module can be run and tested without any API keys. Swap in a real
``ChatClientProtocol`` implementation (e.g. an Azure OpenAI client) for a
production agent.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the agent directly:
        $ uv run -m a2a_agent_kit.greet_agent --port 8000

    Run with a custom database path:
        $ A2A_DB_PATH=/var/data/keys.db uv run -m a2a_agent_kit.greet_agent
"""

from collections.abc import AsyncIterable, MutableSequence

from a2a.types import AgentSkill
from agent_framework import ChatAgent
from agent_framework._clients import BaseChatClient
from agent_framework._types import ChatMessage, ChatOptions, ChatResponse, ChatResponseUpdate

from a2a_agent_kit.base import AuthenticatedA2AAgent


class EchoChatClient(BaseChatClient):
    """
    A no-network chat client that replies "Hello, {last message text}!".

    Exists purely so the stub example has zero external dependencies.
    Implements the two abstract hooks ``BaseChatClient`` requires;
    everything else (tool handling, streaming aggregation) is provided
    by the base class.
    """

    async def _inner_get_response(
        self,
        *,
        messages: MutableSequence[ChatMessage],
        chat_options: ChatOptions,
        **kwargs,
    ) -> ChatResponse:
        last_text = messages[-1].text if messages else ""
        return ChatResponse(text=f"Hello, {last_text}!")

    async def _inner_get_streaming_response(
        self,
        *,
        messages: MutableSequence[ChatMessage],
        chat_options: ChatOptions,
        **kwargs,
    ) -> AsyncIterable[ChatResponseUpdate]:
        response = await self._inner_get_response(
            messages=messages, chat_options=chat_options, **kwargs
        )
        yield ChatResponseUpdate(text=response.text)


class GreetA2AAgent(AuthenticatedA2AAgent):
    """A2A agent that greets whatever name/text it's sent."""

    def _create_chat_agent(self) -> ChatAgent:
        return ChatAgent(
            chat_client=EchoChatClient(),
            instructions="Greet the user by echoing their message as a greeting.",
        )

    def _agent_card_info(self) -> dict:
        return {
            "description": "An agent that greets you by name.",
            "skills": [
                AgentSkill(
                    id="greet",
                    name="Greet",
                    description="Greets a user by name",
                    tags=["greeting"],
                )
            ],
        }


if __name__ == "__main__":
    GreetA2AAgent(name="Greet A2A Agent").main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_greet_agent.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/greet_agent.py tests/test_greet_agent.py
git commit -m "Add GreetA2AAgent example with EchoChatClient"
```

---

### Task 6: `client.py` — `A2AClientWrapper`

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/client.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_client.py`

**Interfaces:**
- Consumes: `a2a.client.{ClientFactory, ClientConfig}`, `a2a.client.helpers.create_text_message_object`, `a2a.types.{Message, Task, Role}`.
- Produces: `A2AClientWrapper(url: str, api_key: str)` with `async def send_text(self, text: str) -> str` and `async def greet(self, name: str) -> None` (prints the result), used by `cli.py` in Task 7.

- [ ] **Step 1: Write the failing tests**

```python
"""
Unit tests for a2a_agent_kit.client

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from unittest.mock import AsyncMock, patch

import pytest
from a2a.types import Message, Part, Role, TextPart

from a2a_agent_kit.client import A2AClientWrapper


class TestSendText:

    @pytest.mark.asyncio
    async def test_send_text_returns_final_message_text(self):
        reply = Message(
            role=Role.agent, message_id="r1", parts=[Part(root=TextPart(text="Hello, Ford!"))]
        )

        async def fake_send_message(*args, **kwargs):
            yield reply

        fake_client = AsyncMock()
        fake_client.send_message = fake_send_message

        with patch(
            "a2a_agent_kit.client.ClientFactory.connect", new=AsyncMock(return_value=fake_client)
        ):
            wrapper = A2AClientWrapper("http://localhost:8000", "test-key")
            result = await wrapper.send_text("Ford")

        assert result == "Hello, Ford!"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_agent_kit.client'`.

- [ ] **Step 3: Write `a2a_agent_kit/client.py`**

```python
"""
A2A client for calling remote A2A agents with API key authentication.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.client.helpers import create_text_message_object
from a2a.types import Message


class A2AClientWrapper:
    """
    Client for connecting to and messaging a remote A2A agent.

    Attributes:
        url (str): The A2A agent's base URL.
        api_key (str): API key for authentication via X-API-Key header.
    """

    def __init__(self, url: str, api_key: str):
        """
        Initialize the A2A client wrapper.

        Args:
            url (str): The A2A agent's base URL (e.g. "http://localhost:8000").
            api_key (str): API key for authentication.
        """
        self.url = url
        self.api_key = api_key

    async def send_text(self, text: str) -> str:
        """
        Send a text message to the remote agent and return its reply text.

        Args:
            text (str): The message text to send.

        Returns:
            str: The text content of the agent's final reply message.
        """
        httpx_client = httpx.AsyncClient(headers={"X-API-Key": self.api_key})
        config = ClientConfig(streaming=False, httpx_client=httpx_client)
        client = await ClientFactory.connect(self.url, client_config=config)

        message = create_text_message_object(content=text)
        async for event in client.send_message(message):
            if isinstance(event, Message):
                return "".join(
                    part.root.text for part in event.parts if hasattr(part.root, "text")
                )
        return ""

    async def greet(self, name: str) -> None:
        """
        Send ``name`` to the remote agent and print its reply.

        Args:
            name (str): The name to send.
        """
        result = await self.send_text(name)
        print(result)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_client.py -v
```

Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/client.py tests/test_client.py
git commit -m "Add A2AClientWrapper"
```

---

### Task 7: `cli.py` — command-line client app

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/cli.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_cli.py`

**Interfaces:**
- Consumes: `A2AClientWrapper` (Task 6): `A2AClientWrapper(url, api_key)`, `.greet(name) -> None` (async).
- Produces: `A2AClientApp` class with `.run() -> None`, module-level `main() -> None` (referenced by `pyproject.toml`'s `a2a-client` script entry point from Task 1).

- [ ] **Step 1: Write the failing test**

```python
"""
Unit tests for a2a_agent_kit.cli

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import sys
from unittest.mock import AsyncMock, patch

from a2a_agent_kit.cli import A2AClientApp


class TestA2AClientApp:

    def test_run_invokes_greet_with_parsed_args(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["prog", "--api-key", "abc123", "--name", "Alice", "--url", "http://x"]
        )
        app = A2AClientApp()

        with patch("a2a_agent_kit.cli.A2AClientWrapper") as fake_wrapper_cls:
            fake_wrapper = fake_wrapper_cls.return_value
            fake_wrapper.greet = AsyncMock()
            app.run()

        fake_wrapper_cls.assert_called_once_with("http://x", "abc123")
        fake_wrapper.greet.assert_awaited_once_with("Alice")

    def test_run_defaults_name_to_ford(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "--api-key", "abc123"])
        app = A2AClientApp()

        with patch("a2a_agent_kit.cli.A2AClientWrapper") as fake_wrapper_cls:
            fake_wrapper = fake_wrapper_cls.return_value
            fake_wrapper.greet = AsyncMock()
            app.run()

        fake_wrapper.greet.assert_awaited_once_with("Ford")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_cli.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_agent_kit.cli'`.

- [ ] **Step 3: Write `a2a_agent_kit/cli.py`**

```python
"""
Command-line application for the A2A client.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Basic usage with required API key:
        $ uv run -m a2a_agent_kit.cli --api-key YOUR_API_KEY

    Custom name and agent URL:
        $ uv run -m a2a_agent_kit.cli --api-key YOUR_API_KEY --name Alice --url http://localhost:8000
"""

import argparse
import asyncio

from a2a_agent_kit.client import A2AClientWrapper


class A2AClientApp:
    """
    Command-line application for the A2A client.

    Attributes:
        parser (argparse.ArgumentParser): Command-line argument parser.
    """

    def __init__(self):
        """Initialize the CLI application with argument parser."""
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create and configure the argument parser.

        Returns:
            argparse.ArgumentParser: Configured parser with all CLI arguments.
        """
        parser = argparse.ArgumentParser(
            description="A2A client for calling a remote agent",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --api-key abc123xyz
  %(prog)s --api-key abc123xyz --name Alice
  %(prog)s --api-key abc123xyz --url http://localhost:8000 --name Bob
            """,
        )
        parser.add_argument(
            "--api-key", required=True, help="API key for authentication (required)"
        )
        parser.add_argument("--name", default="Ford", help="Name to greet (default: Ford)")
        parser.add_argument(
            "--url",
            default="https://my-agent.ngrok.app",
            help="A2A agent base URL (default: https://my-agent.ngrok.app)",
        )
        return parser

    def run(self) -> None:
        """
        Parse arguments and run the client.

        Parses command-line arguments, creates an A2AClientWrapper instance,
        and calls its greet method. Handles and displays any errors that occur.
        """
        args = self.parser.parse_args()
        client = A2AClientWrapper(args.url, args.api_key)

        try:
            asyncio.run(client.greet(args.name))
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Entry point for the a2a-client console script."""
    app = A2AClientApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_cli.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/cli.py tests/test_cli.py
git commit -m "Add A2A CLI client app"
```

---

### Task 8: Update `a2a_agent_kit/__init__.py` re-exports

**Files:**
- Modify: `/Users/dgwartney/git/a2a-examples/a2a_agent_kit/__init__.py`
- Test: `/Users/dgwartney/git/a2a-examples/tests/test_init.py`

**Interfaces:**
- Consumes: `AuthenticatedA2AAgent` (Task 4), `GreetA2AAgent`, `EchoChatClient` (Task 5), `A2AClientWrapper` (Task 6), `A2AClientApp` (Task 7).
- Produces: all of the above importable directly from `a2a_agent_kit`.

- [ ] **Step 1: Write the failing test**

```python
"""
Unit tests for a2a_agent_kit package-level exports

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import a2a_agent_kit


class TestPublicExports:

    def test_all_public_classes_are_importable_from_package_root(self):
        assert hasattr(a2a_agent_kit, "AuthenticatedA2AAgent")
        assert hasattr(a2a_agent_kit, "GreetA2AAgent")
        assert hasattr(a2a_agent_kit, "EchoChatClient")
        assert hasattr(a2a_agent_kit, "A2AClientWrapper")
        assert hasattr(a2a_agent_kit, "A2AClientApp")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_init.py -v
```

Expected: FAIL with `AttributeError: module 'a2a_agent_kit' has no attribute 'AuthenticatedA2AAgent'`.

- [ ] **Step 3: Update `a2a_agent_kit/__init__.py`**

```python
"""
a2a_agent_kit — toolkit for building authenticated A2A agents.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from a2a_agent_kit.base import AuthenticatedA2AAgent
from a2a_agent_kit.client import A2AClientWrapper
from a2a_agent_kit.cli import A2AClientApp
from a2a_agent_kit.greet_agent import EchoChatClient, GreetA2AAgent

__version__ = "0.1.0"

__all__ = [
    "AuthenticatedA2AAgent",
    "GreetA2AAgent",
    "EchoChatClient",
    "A2AClientWrapper",
    "A2AClientApp",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest tests/test_init.py -v
```

Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add a2a_agent_kit/__init__.py tests/test_init.py
git commit -m "Re-export public classes from a2a_agent_kit package root"
```

---

### Task 9: Docs, README, CLAUDE.md, and deployment scaffolding

**Files:**
- Create: `/Users/dgwartney/git/a2a-examples/docs/agents.md`
- Create: `/Users/dgwartney/git/a2a-examples/docs/extending.md`
- Create: `/Users/dgwartney/git/a2a-examples/README.md`
- Create: `/Users/dgwartney/git/a2a-examples/CLAUDE.md`
- Create: `/Users/dgwartney/git/a2a-examples/Dockerfile`
- Create: `/Users/dgwartney/git/a2a-examples/fly.toml`

**Interfaces:**
- Consumes: nothing new — this task documents and packages what Tasks 1–8 built.
- Produces: nothing consumed by later tasks (this is the final task).

- [ ] **Step 1: Write `docs/agents.md`**

```markdown
# Agents

## GreetA2AAgent (`a2a_agent_kit/greet_agent.py`)

A trivial example agent that greets whatever text it receives.

- **Skill:** `greet` — greets a user by name.
- **Chat client:** `EchoChatClient`, a no-network stand-in that echoes
  `"Hello, {input}!"`. Replace it with a real `ChatClientProtocol`
  implementation (e.g. an Azure OpenAI client) for a production agent.
- **Required env vars:** none.
- **Optional env vars:**
  - `A2A_DB_PATH` — path to the SQLite API-key database. Defaults to
    `api_keys.db` in the current working directory.
- **Run it:**
  ```bash
  uv run -m a2a_agent_kit.greet_agent --port 8000
  ```
- **Auth:** every route — including `/.well-known/agent-card.json` — requires
  an `X-API-Key` header matching a key in the API-key database. The first run
  generates and logs a default key (INFO level, logger
  `a2a_agent_kit.database`).
```

- [ ] **Step 2: Write `docs/extending.md`**

```markdown
# Adding a New Agent

Checklist for building a new agent on top of `a2a_agent_kit`:

1. **Create the module** — `a2a_agent_kit/<name>_agent.py`, subclassing
   `AuthenticatedA2AAgent` and implementing `_create_chat_agent()` and
   `_agent_card_info()`. See `greet_agent.py` for the minimal shape.
2. **Wire up its own deployment target** — each A2A agent is a standalone
   deployable unit (one `AgentCard`, one base URL). Add its own
   `if __name__ == "__main__":` entry point calling `.main()`, and its own
   `CMD`/`Procfile` line if it needs independent deployment from
   `greet_agent.py`.
3. **Add a `docs/agents.md` entry** — skills, required/optional env vars, how
   to run it, following the `GreetA2AAgent` entry's format.
4. **Write tests** — `tests/test_<name>_agent.py`, following
   `tests/test_greet_agent.py`'s pattern of driving the executor bridge
   directly (`agent._executor.execute(context, queue)`) rather than making
   live network/model calls.
5. **Curl the endpoints directly** before wiring up any external platform:
   ```bash
   uv run -m a2a_agent_kit.<name>_agent --port 8000 &
   curl -H "X-API-Key: <key from logs>" http://localhost:8000/.well-known/agent-card.json
   ```
6. **Register with whatever external platform will consume it**, using the
   base URL and the generated API key.
```

- [ ] **Step 3: Write `README.md`**

```markdown
# a2a-examples

A toolkit and stub framework for building authenticated A2A (Agent2Agent
protocol) agents, mirroring the pattern established in
[mcp-examples](https://github.com/dgwartney/mcp-examples) for MCP servers.

## Setup & Commands

This project uses `uv` for Python package management (never `pip`), and
supports Python 3.10+.

```bash
# Install dependencies
uv sync --extra test

# Run the example agent
uv run -m a2a_agent_kit.greet_agent --port 8000

# Run the CLI client against it
uv run -m a2a_agent_kit.cli --api-key <key from server logs> --name Alice --url http://localhost:8000

# Run tests
uv run pytest
```

## Architecture

- `a2a_agent_kit/database.py` — `DatabaseManager`, SQLite-backed API key storage/validation.
- `a2a_agent_kit/middleware.py` — `ApiKeyMiddleware`, Starlette middleware checking `X-API-Key`.
- `a2a_agent_kit/base.py` — `AuthenticatedA2AAgent` abstract base class: owns auth, the AgentExecutor bridge to `agent_framework.ChatAgent`, agent card assembly, and the Starlette app.
- `a2a_agent_kit/greet_agent.py` — `GreetA2AAgent`, the one example agent, backed by the no-network `EchoChatClient`.
- `a2a_agent_kit/client.py` — `A2AClientWrapper`, a thin async client for calling a remote agent.
- `a2a_agent_kit/cli.py` — `A2AClientApp` command-line client.

See [docs/agents.md](docs/agents.md) for per-agent details and
[docs/extending.md](docs/extending.md) for how to add a new agent.

## Key Dependencies

- `agent-framework` / `agent-framework-a2a` — Microsoft Agent Framework's A2A integration.
- `a2a-sdk[http-server]` — the official A2A protocol SDK (Starlette/FastAPI server pieces).
```

- [ ] **Step 4: Write `CLAUDE.md`**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A2A (Agent2Agent protocol) examples built on Microsoft Agent Framework's
A2A integration (`agent-framework-a2a`) over the official `a2a-sdk`. The
project provides a reusable `AuthenticatedA2AAgent` base class with
SQLite-backed API-key auth, plus one example agent and a client for calling
it remotely.

## Setup & Commands

This project uses `uv` for Python package management and supports Python 3.10+.

> **uv only — never pip.** Do not use `pip`, `pip3`, or `python -m venv`
> anywhere in this project. Use `uv` exclusively: `uv venv`, `uv sync`,
> `uv add`, `uv pip install`, `uv run`, `uv build`, `uv tool install`.

```bash
# Install dependencies
uv sync --extra test

# Run the example agent
uv run -m a2a_agent_kit.greet_agent

# Run the CLI client
uv run -m a2a_agent_kit.cli --api-key <key>

# Run tests
uv run pytest
```

## Architecture

- **a2a_agent_kit/database.py** — `DatabaseManager` for SQLite-backed API key storage/validation.
- **a2a_agent_kit/middleware.py** — `ApiKeyMiddleware` checking `X-API-Key`.
- **a2a_agent_kit/base.py** — `AuthenticatedA2AAgent` abstract base class. Subclass and implement `_create_chat_agent()` / `_agent_card_info()` to create a new agent.
- **a2a_agent_kit/greet_agent.py** — `GreetA2AAgent` + `EchoChatClient`, the example agent.
- **a2a_agent_kit/client.py** — `A2AClientWrapper` for calling a remote agent.
- **a2a_agent_kit/cli.py** — `A2AClientApp` CLI and `main()` entry point.

See [docs/agents.md](docs/agents.md) for per-agent details and
[docs/extending.md](docs/extending.md) for the "Adding a New Agent" checklist.

## Key Dependencies

- `agent-framework` / `agent-framework-a2a` — the core libraries for both server and client.
- `a2a-sdk[http-server]>=0.3.5` — official A2A protocol types, server, and client machinery.
```

- [ ] **Step 5: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY a2a_agent_kit/ a2a_agent_kit/

RUN uv sync --frozen --no-dev

RUN mkdir -p /data

EXPOSE 8000

CMD ["uv", "run", "-m", "a2a_agent_kit.greet_agent", "--port", "8000", "--host", "0.0.0.0"]
```

- [ ] **Step 6: Write `fly.toml`**

```toml
app = 'a2a-agent-kit'
primary_region = 'ord'

[build]

[env]
  A2A_DB_PATH = '/data/api_keys.db'

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = 'suspend'
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  size = 'shared-cpu-1x'
  memory = '256mb'

[[mounts]]
  source = 'a2a_data'
  destination = '/data'
```

- [ ] **Step 7: Run the full test suite as a final check**

```bash
cd /Users/dgwartney/git/a2a-examples
uv run pytest
```

Expected: all tests across every module PASS (database, middleware, base, greet_agent, client, cli, init).

- [ ] **Step 8: Smoke-test the running agent end-to-end**

```bash
cd /Users/dgwartney/git/a2a-examples
rm -f api_keys.db
uv run -m a2a_agent_kit.greet_agent --port 8000 &
SERVER_PID=$!
sleep 2
KEY=$(sqlite3 api_keys.db "SELECT key FROM api_keys LIMIT 1;")
curl -s -H "X-API-Key: $KEY" http://localhost:8000/.well-known/agent-card.json
uv run -m a2a_agent_kit.cli --api-key "$KEY" --name Ford --url http://localhost:8000
kill $SERVER_PID
rm -f api_keys.db
```

Expected: the `curl` prints an agent card JSON body with `"name": "Greet A2A Agent"` and a `"greet"` skill; the CLI command prints `Hello, Ford!`.

- [ ] **Step 9: Commit**

```bash
cd /Users/dgwartney/git/a2a-examples
git add docs/agents.md docs/extending.md README.md CLAUDE.md Dockerfile fly.toml
git commit -m "Add docs, README, CLAUDE.md, and deployment scaffolding"
```

---

## Self-Review Notes

- **Spec coverage:** every component in the design doc (`database.py`, `middleware.py`, `base.py`, `greet_agent.py`, `client.py`, `cli.py`, `__init__.py`, tests, `docs/agents.md`, `docs/extending.md`, `README.md`, `CLAUDE.md`, `Dockerfile`, `fly.toml`) has a task. The design's "no `combined.py`" and "no scaffold script" exclusions are respected — no task creates either.
- **Open technical risk resolved:** the design doc flagged uncertainty over `ChatAgent`'s `chat_client` requirement for the trivial example. Resolved during planning — `agent_framework.BaseChatClient` is a two-method ABC (`_inner_get_response`, `_inner_get_streaming_response`), so `EchoChatClient` implements both directly with no network dependency, confirmed against the installed `agent_framework` package source.
- **Type/signature consistency:** `AuthenticatedA2AAgent._create_chat_agent()` and `._agent_card_info()` signatures match between the abstract declaration (Task 4) and both concrete overrides (`_StubA2AAgent` in Task 4's tests, `GreetA2AAgent` in Task 5). `A2AClientWrapper.__init__(url, api_key)` matches every call site (Task 6 tests, Task 7's `cli.py`, Task 9's smoke test).
