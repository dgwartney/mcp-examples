FROM python:3.12-slim

WORKDIR /app

# Ensure Python stdout/stderr is unbuffered so logs appear immediately in docker logs
ENV PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
COPY mcp_examples/ mcp_examples/

# Install dependencies
RUN uv sync --frozen --no-dev

# Data directory for SQLite databases (override with a volume mount in production)
RUN mkdir -p /data

EXPOSE 8000

CMD ["uv", "run", "-m", "mcp_examples.server", "--transport", "streamable-http", "--port", "8000", "--host", "0.0.0.0"]
