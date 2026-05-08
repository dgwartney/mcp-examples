# ngrok

**Trade-offs:** Free with random URL on each restart; $10/mo for a fixed URL. Full SQLite persistence on local disk. Requires your machine to stay on. No cloud account needed — the fastest way to share a locally-running server publicly.

---

## Prerequisites

Complete [local.md](local.md) first — the server must run locally before ngrok can tunnel to it.

## Install ngrok

**macOS:**
```bash
brew install ngrok
```

**Windows:** Download the installer from [ngrok.com/download](https://ngrok.com/download), run it, and follow the prompts. After installation, open a new PowerShell window.

## Getting started

1. Clone and set up the project (see [../installation.md](../installation.md)):
   ```bash
   git clone https://github.com/dgwartney/mcp-example.git
   cd mcp-example
   uv sync
   ```

2. Start the server you want to expose:

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

3. In a second terminal, create the ngrok tunnel:
   ```bash
   ngrok http 8000
   ```

   ngrok will display a forwarding URL like `https://abc123.ngrok.app`.

4. Use the ngrok URL with the built-in client:

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
