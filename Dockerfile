FROM python:3.12-slim

WORKDIR /app

# Ensure Python stdout/stderr is unbuffered so logs appear immediately in docker logs
ENV PYTHONUNBUFFERED=1

# Install sqlite3 CLI and uv
RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
COPY mcp_examples/ mcp_examples/

# Install dependencies
RUN uv sync --frozen --no-dev

# Data directory for SQLite databases (override with a volume mount in production)
RUN mkdir -p /data

EXPOSE 8000

CMD ["uv", "run", "-m", "mcp_examples.combined", "--port", "8000", "--host", "0.0.0.0"]
