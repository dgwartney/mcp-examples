# Docker / VPS Deployment

**Trade-offs:** ~$4–5/mo for a VPS (Hetzner, DigitalOcean). Full SQLite persistence via volume mount. Always on, no cold starts, complete control over the host. Best option for production workloads or when you want no platform constraints.

**Official guides:**
- [Docker getting started](https://docs.docker.com/get-started/)
- [Docker install](https://docs.docker.com/engine/install/)
- [Docker volumes](https://docs.docker.com/storage/volumes/)
- [Hetzner Cloud (from €3.79/mo)](https://www.hetzner.com/cloud)
- [DigitalOcean Droplets (from $4/mo)](https://www.digitalocean.com/products/droplets)

---

## Build and run locally

```bash
docker build -t mcp-server .
```

**macOS:**
```bash
docker run -p 8000:8000 \
  -e MCP_DB_PATH=/data/api_keys.db \
  -e CONTACTS_DB_PATH=/data/contacts.db \
  -v $(pwd)/data:/data \
  mcp-server
```

**Windows (PowerShell):**
```powershell
docker run -p 8000:8000 `
  -e MCP_DB_PATH=/data/api_keys.db `
  -e CONTACTS_DB_PATH=/data/contacts.db `
  -v ${PWD}/data:/data `
  mcp-server
```

## Run the contact server

```bash
docker run -p 8000:8000 \
  -e MCP_DB_PATH=/data/api_keys.db \
  -e CONTACTS_DB_PATH=/data/contacts.db \
  -v $(pwd)/data:/data \
  mcp-server \
  uv run -m mcp_examples.contacts --transport streamable-http --port 8000 --host 0.0.0.0
```

## Expose a local Docker container via ngrok

This runs the server in Docker locally and uses ngrok to give it a public HTTPS URL.

> **What you need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and ngrok installed (see [ngrok.md — Install ngrok](ngrok.md#install-ngrok)).

**Step 1 — Build the image:**
```bash
docker build -t mcp-server .
```

**Step 2 — Create a local data directory:**

**macOS:**
```bash
mkdir -p data
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path data
```

**Step 3 — Start the container:**

**macOS:**
```bash
docker run -p 8000:8000 \
  -e MCP_DB_PATH=/data/api_keys.db \
  -e CONTACTS_DB_PATH=/data/contacts.db \
  -v $(pwd)/data:/data \
  mcp-server
```

**Windows (PowerShell):**
```powershell
docker run -p 8000:8000 `
  -e MCP_DB_PATH=/data/api_keys.db `
  -e CONTACTS_DB_PATH=/data/contacts.db `
  -v ${PWD}/data:/data `
  mcp-server
```

On first run the container prints its API key. If you missed it:
```bash
sqlite3 data/api_keys.db "SELECT key FROM api_keys;"
```

**Step 4 — In a second terminal, start ngrok:**
```bash
ngrok http 8000
```

Your server is now publicly accessible at `https://abc123.ngrok.app/mcp`.

**Step 5 — Connect a client:**

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

> The ngrok URL changes every time you restart ngrok on the free tier. Your databases persist in `data/` between container restarts via the volume mount.

To run the contact server instead, add the command override to Step 3 (macOS):
```bash
docker run -p 8000:8000 \
  -e MCP_DB_PATH=/data/api_keys.db \
  -e CONTACTS_DB_PATH=/data/contacts.db \
  -v $(pwd)/data:/data \
  mcp-server \
  uv run -m mcp_examples.contacts --transport streamable-http --port 8000 --host 0.0.0.0
```

## Deploy to a VPS

1. SSH into your server
2. Install Docker: [docs.docker.com/engine/install](https://docs.docker.com/engine/install/)
3. Clone the repo and run:
   ```bash
   git clone https://github.com/dgwartney/mcp-example.git
   cd mcp-example
   docker build -t mcp-server .
   mkdir -p data
   docker run -d --restart unless-stopped \
     -p 8000:8000 \
     -e MCP_DB_PATH=/data/api_keys.db \
     -e CONTACTS_DB_PATH=/data/contacts.db \
     -v $(pwd)/data:/data \
     mcp-server
   ```
4. Your server is live at `http://YOUR_SERVER_IP:8000/mcp`
