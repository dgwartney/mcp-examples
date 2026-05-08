# Deployment

## Local Development

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

---

## Production Deployment with ngrok

For exposing your local server to the internet (useful for development and demos):

1. Clone and set up the project (see [installation.md](installation.md)):
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

---

## Render (Free Tier)

[Render](https://render.com) offers a free web service tier with a $1/month persistent disk, which keeps `api_keys.db` and `contacts.db` intact across deploys and restarts.

**Official guides:**
- [Render Python getting started](https://render.com/docs/deploy-python)
- [Render persistent disks](https://render.com/docs/disks)
- [Render environment variables](https://render.com/docs/configure-environment-variables)
- [Render free tier limits](https://render.com/docs/free#free-web-services)

> **What you need:** A [GitHub](https://github.com) account with this repo pushed to it, and a free [Render](https://render.com) account.

### Step 1 — Push the repo to GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/mcp-example.git
git push -u origin main
```

### Step 2 — Create a Render Web Service

1. Log in to [render.com](https://render.com) and click **New > Web Service**
2. Connect your GitHub account and select your `mcp-example` repository
3. Configure the service:

   | Setting | Value |
   |---------|-------|
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install uv && uv sync --frozen` |
   | **Start Command** | `uv run -m mcp_examples.server --transport streamable-http --port $PORT --host 0.0.0.0` |
   | **Instance Type** | Free |

4. Click **Advanced** and add these environment variables:

   | Key | Value |
   |-----|-------|
   | `MCP_DB_PATH` | `/data/api_keys.db` |
   | `CONTACTS_DB_PATH` | `/data/contacts.db` |

5. Click **Create Web Service**. Render will build and deploy automatically.

### Step 3 — Add a persistent disk

Without a disk, `api_keys.db` is wiped on every deploy. To persist it:

1. In your Render service dashboard, click **Disks** in the left menu
2. Click **Add Disk**:

   | Setting | Value |
   |---------|-------|
   | **Name** | `mcp-data` |
   | **Mount Path** | `/data` |
   | **Size** | 1 GB |

3. Click **Save**. Render will redeploy the service automatically.

### Step 4 — Retrieve your API key

Once the deploy finishes, click **Logs** in the Render dashboard. On first deploy you will see:

```
Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
```

Copy and save this key. It will not be printed again.

### Step 5 — Connect a client

Your server is now live at `https://YOUR-SERVICE-NAME.onrender.com/mcp`.

```bash
uv run -m mcp_examples.cli \
  --api-key YOUR_API_KEY \
  --url https://YOUR-SERVICE-NAME.onrender.com/mcp
```

> **Note:** Free tier Render services spin down after 15 minutes of inactivity. The first request after a period of inactivity may take 30–60 seconds while the service wakes up. Upgrade to a paid instance ($7/mo) to keep it always on.

### Deploying the contact server

To run `ContactMCPServer` instead of `GreetMCPServer`, change the Start Command in Render to:

```
uv run -m mcp_examples.contacts --transport streamable-http --port $PORT --host 0.0.0.0
```

Both database files will be stored on the persistent `/data` disk using the environment variables already set above.

---

## Fly.io (Free Tier)

[Fly.io](https://fly.io) offers a free tier with shared VMs and free persistent volumes — the best zero-cost option for always-on deployment with SQLite persistence.

**Official guides:**
- [Fly.io getting started](https://fly.io/docs/getting-started/)
- [Install flyctl](https://fly.io/docs/flyctl/install/)
- [Fly.io persistent volumes](https://fly.io/docs/volumes/overview/)
- [Fly.io free tier allowances](https://fly.io/docs/about/pricing/#free-allowances)
- [Deploying with a Dockerfile on Fly.io](https://fly.io/docs/languages-and-frameworks/dockerfile/)

> **What you need:** The `flyctl` CLI and a free [Fly.io](https://fly.io) account. The `fly.toml` and `Dockerfile` are already included in this repo.

### Step 1 — Install flyctl

**macOS:**
```bash
brew install flyctl
```

**Windows (PowerShell):**
```powershell
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

Confirm:
```bash
fly version
```

### Step 2 — Create a Fly.io account and log in

```bash
fly auth signup
```

Or if you already have an account:
```bash
fly auth login
```

### Step 3 — Create the app

From inside the project directory:

```bash
fly apps create mcp-example
```

> If `mcp-example` is already taken, choose a unique name and update the `app` field in `fly.toml` to match.

### Step 4 — Deploy

```bash
fly deploy
```

Fly.io builds the Docker image, pushes it to its registry, and starts the server. The persistent volume defined in `fly.toml` is created automatically on first deploy.

> **Expected warning during first deploy:** You will see:
> ```
> WARNING The app is not listening on the expected address and will not be reachable by fly-proxy.
> ```
> This is normal. Fly.io's health check runs ~2 seconds after machine start, but the server takes ~5 seconds to initialise the database before binding to port 8000. Confirm with `fly status` after the deploy completes.

### Step 5 — Retrieve your API key from the logs

```bash
fly logs | grep "API key"
```

You will see:
```
Generated default API key: or8hEScfF8RBf1GQnWjrmqZvH9qVTFWfd1cdvEQZXKU
```

If `fly logs` has already scrolled past it, retrieve it from the database on the volume:

```bash
fly ssh console -C "sqlite3 /data/api_keys.db 'SELECT key FROM api_keys;'"
```

### Step 6 — Confirm the server is running

```bash
fly status
```

Look for `started` in the Machines table. Your server is live at `https://mcp-example.fly.dev/mcp`.

### Step 7 — Connect a client

```bash
uv run -m mcp_examples.cli \
  --api-key YOUR_API_KEY \
  --url https://mcp-example.fly.dev/mcp
```

### Deploying the contact server

`fly.toml` already sets both `MCP_DB_PATH` and `CONTACTS_DB_PATH` pointing to the `/data` persistent volume. To run the contact server, update the `Dockerfile` CMD:

```dockerfile
CMD ["uv", "run", "-m", "mcp_examples.contacts", "--transport", "streamable-http", "--port", "8000", "--host", "0.0.0.0"]
```

Then redeploy:
```bash
fly deploy
```

### Useful Fly.io commands

```bash
# View live logs (API key appears here on first deploy)
fly logs

# Grep logs for the API key specifically
fly logs | grep "API key"

# Retrieve API key directly from the database if logs have scrolled past it
fly ssh console -C "sqlite3 /data/api_keys.db 'SELECT key FROM api_keys;'"

# Check app status and confirm the server is running
fly status

# List persistent volumes
fly volumes list

# Open an interactive shell inside the running container
fly ssh console

# Stop the server (scales to zero machines — volume and databases are preserved)
fly scale count 0

# Redeploy after a code change (rebuilds the Docker image and replaces the machine)
fly deploy

# Restart the running machine without rebuilding (faster — no new image build)
fly machines restart

# Note: API key is NOT regenerated on redeploy as long as the volume still contains api_keys.db
```

---

## Railway

[Railway](https://railway.app) provides $5 of free credit per month and deploys directly from GitHub using your `Procfile` — no Docker configuration needed.

**Official guides:**
- [Railway getting started](https://docs.railway.app/getting-started)
- [Railway Procfile deployments](https://docs.railway.app/deploy/config-as-code)
- [Railway environment variables](https://docs.railway.app/guides/variables)
- [Railway volumes (persistent storage)](https://docs.railway.app/guides/volumes)
- [Railway pricing and free tier](https://railway.app/pricing)

> **SQLite limitation:** Railway uses an ephemeral filesystem. `api_keys.db` is wiped on every deploy and restart. Railway offers persistent volumes as a paid add-on. If you need SQLite persistence without paying, use Render or Fly.io instead.

### Getting started

1. Push the repo to GitHub (see Render Step 1 above)
2. Log in to [railway.app](https://railway.app) and click **New Project > Deploy from GitHub repo**
3. Select your `mcp-example` repository
4. Railway detects the `Procfile` automatically and starts the deploy
5. In the service settings, add these environment variables:
   - `MCP_DB_PATH` = `/data/api_keys.db`
   - `CONTACTS_DB_PATH` = `/data/contacts.db`
6. Click **Deploy**
7. Open **Logs** to find the generated API key on first deploy

Your public URL is shown in the Railway dashboard under **Settings > Domains**.

---

## Docker / VPS Deployment

Use Docker when deploying to a VPS (Hetzner, DigitalOcean, etc.) or any environment where you manage the host directly. The `Dockerfile` is included in the repo.

**Official guides:**
- [Docker getting started](https://docs.docker.com/get-started/)
- [Docker install](https://docs.docker.com/engine/install/)
- [Docker volumes](https://docs.docker.com/storage/volumes/)
- [Hetzner Cloud (from €3.79/mo)](https://www.hetzner.com/cloud)
- [DigitalOcean Droplets (from $4/mo)](https://www.digitalocean.com/products/droplets)

### Build and run locally

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

### Run the contact server

```bash
docker run -p 8000:8000 \
  -e MCP_DB_PATH=/data/api_keys.db \
  -e CONTACTS_DB_PATH=/data/contacts.db \
  -v $(pwd)/data:/data \
  mcp-server \
  uv run -m mcp_examples.contacts --transport streamable-http --port 8000 --host 0.0.0.0
```

### Expose a local Docker container via ngrok

This runs the server in Docker locally and uses ngrok to give it a public HTTPS URL.

> **What you need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and ngrok installed (see ngrok section above).

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

### Deploy to a VPS

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
