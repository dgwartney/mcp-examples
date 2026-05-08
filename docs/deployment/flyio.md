# Fly.io (Free Tier)

**Trade-offs:** Free tier includes 3 shared VMs and 3 GB of persistent volumes. Full SQLite persistence. Auto-stops when idle (cold start ~5s); set `min_machines_running = 1` in `fly.toml` to keep it always on. Best free option for persistent, always-available deployments manageable entirely from the CLI.

**Official guides:**
- [Fly.io getting started](https://fly.io/docs/getting-started/)
- [Install flyctl](https://fly.io/docs/flyctl/install/)
- [Fly.io persistent volumes](https://fly.io/docs/volumes/overview/)
- [Fly.io free tier allowances](https://fly.io/docs/about/pricing/#free-allowances)
- [Deploying with a Dockerfile on Fly.io](https://fly.io/docs/languages-and-frameworks/dockerfile/)

> **What you need:** The `flyctl` CLI and a free [Fly.io](https://fly.io) account. The `fly.toml` and `Dockerfile` are already included in this repo.

---

## Getting Started

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

### Which server is deployed

The `Dockerfile` in this repo runs the **Contact server** by default:

```dockerfile
CMD ["uv", "run", "-m", "mcp_examples.contacts", "--transport", "streamable-http", "--port", "8000", "--host", "0.0.0.0"]
```

To switch to the Greet server, change that line and redeploy with `fly deploy`.

### Verify the contact server is running

After deploying, confirm the contact server is live and responding:

```bash
# 1. Wake the machine if it has auto-stopped (see Stopping and starting below)
fly machine start

# 2. Check machine state — look for 'started' in the output
fly status

# 3. Test a contact tool call (replace YOUR_API_KEY with your actual key)
curl -s -X POST https://mcp-example.fly.dev/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

A successful response returns a JSON object containing `"name":"ContactMCP"` in the `serverInfo` field, confirming the contact server is running.

---

## Lifecycle Management

### Viewing logs

```bash
# Stream live logs
fly logs

# Find the API key in logs (only appears on first deploy of a fresh volume)
fly logs | grep "API key"

# View recent logs without streaming
fly logs --no-tail
```

### Stopping and starting

The free tier uses `auto_stop_machines = 'stop'` in `fly.toml`, which means Fly.io automatically stops the machine after a period of inactivity to conserve your free allowance. The machine starts again automatically on the next inbound request (cold start takes ~5 seconds).

```bash
# Manually stop the machine (databases on the volume are preserved)
fly scale count 0

# Manually start a stopped machine
fly machine start

# Check current machine state
fly status
```

> **Cold start behaviour:** When `min_machines_running = 0` and the machine is stopped, the first HTTP request will wait ~5 seconds while Fly.io starts the machine and the server initialises. Subsequent requests are fast. To eliminate cold starts, set `min_machines_running = 1` in `fly.toml` and redeploy — this keeps one machine always running but counts against your free allowance.

### Redeploying after code changes

```bash
# Rebuild the Docker image and replace the running machine (rolling deploy)
fly deploy

# Restart the existing machine without rebuilding — faster, no new image
fly machines restart
```

The API key and both databases are preserved on the `/data` volume across all redeploys as long as the volume exists.

### Managing the API key database remotely

The machine must be in `started` state for SSH commands. Run `fly machine start` first if needed.

```bash
# List all API keys
fly ssh console -C "sqlite3 /data/api_keys.db 'SELECT * FROM api_keys;'"

# Add a new API key
fly ssh console -C "sqlite3 /data/api_keys.db \"INSERT INTO api_keys (key) VALUES ('YOUR_NEW_KEY');\""

# Revoke an API key
fly ssh console -C "sqlite3 /data/api_keys.db \"DELETE FROM api_keys WHERE key = 'KEY_TO_REVOKE';\""

# Generate a new random key and add it in one step
fly ssh console -C "python3 -c \"
import secrets, sqlite3
key = secrets.token_urlsafe(32)
sqlite3.connect('/data/api_keys.db').execute('INSERT INTO api_keys (key) VALUES (?)', (key,)).connection.commit()
print('New key:', key)
\""
```

### Managing the contacts database remotely

```bash
# List all contacts (summary view)
fly ssh console -C "sqlite3 /data/contacts.db 'SELECT Id, FirstName, LastName, Email, AccountName FROM contacts;'"

# Search by last name
fly ssh console -C "sqlite3 /data/contacts.db \"SELECT * FROM contacts WHERE LastName LIKE '%Bunny%';\""

# Search by email
fly ssh console -C "sqlite3 /data/contacts.db \"SELECT * FROM contacts WHERE Email = 'bugs.bunny@acme.com' COLLATE NOCASE;\""

# Update a contact's password
fly ssh console -C "sqlite3 /data/contacts.db \"UPDATE contacts SET Password = 'newpassword!' WHERE Email = 'bugs.bunny@acme.com' COLLATE NOCASE;\""

# Count total contacts
fly ssh console -C "sqlite3 /data/contacts.db 'SELECT COUNT(*) FROM contacts;'"
```

### Backing up and restoring databases

Fly.io volumes are not automatically backed up. Use `fly sftp` to copy databases to your local machine.

```bash
# Download api_keys.db to your local machine
fly sftp get /data/api_keys.db ./api_keys_backup.db

# Download contacts.db to your local machine
fly sftp get /data/contacts.db ./contacts_backup.db

# Upload a local backup back to the volume
fly sftp shell
# Then in the sftp shell:
# put ./contacts_backup.db /data/contacts.db
```

### Resetting contacts to seed data

To wipe all contacts and restore the original 20 Warner Bros. characters:

```bash
# Delete the contacts database on the volume
fly ssh console -C "rm /data/contacts.db"

# Restart the machine — the server will recreate and re-seed contacts.db on startup
fly machines restart
```

### Choosing a region

The default region in `fly.toml` is `ord` (Chicago). To deploy closer to your users, update `primary_region` before your first deploy:

```toml
primary_region = 'lhr'   # London
primary_region = 'fra'   # Frankfurt
primary_region = 'syd'   # Sydney
primary_region = 'nrt'   # Tokyo
primary_region = 'sea'   # Seattle
```

List all available regions:
```bash
fly platform regions
```

### Free tier limits

Fly.io's free tier includes:

| Resource | Free allowance |
|----------|---------------|
| Shared CPU VMs | 3 VMs (`shared-cpu-1x`, 256 MB RAM) |
| Outbound bandwidth | 100 GB/month |
| Persistent volumes | 3 GB total |
| Machines stopped when idle | Yes (with `auto_stop_machines = 'stop'`) |

This project uses 1 VM and 1 GB of volume storage, well within the free tier. See [fly.io/docs/about/pricing](https://fly.io/docs/about/pricing/) for current limits.

### Tearing down the app

To completely remove the app and all its data from Fly.io:

```bash
# Delete the app (also deletes machines and releases IP addresses)
fly apps destroy mcp-example

# Separately delete the persistent volume (this destroys all database data permanently)
fly volumes destroy vol_rkg15xy8pdk19z64
```

> **Warning:** Destroying the volume permanently deletes `api_keys.db` and `contacts.db`. Download backups first if you need to preserve the data (see Backing up and restoring above).

To find the volume ID:
```bash
fly volumes list
```
