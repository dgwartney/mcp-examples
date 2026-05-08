# Render (Free Tier)

**Trade-offs:** Free web service + $1/mo persistent disk. Full SQLite persistence. Spins down after 15 minutes of inactivity — first request after idle takes 30–60 seconds. Good for low-traffic APIs where occasional slow startup is acceptable.

**Official guides:**
- [Render Python getting started](https://render.com/docs/deploy-python)
- [Render persistent disks](https://render.com/docs/disks)
- [Render environment variables](https://render.com/docs/configure-environment-variables)
- [Render free tier limits](https://render.com/docs/free#free-web-services)

> **What you need:** A [GitHub](https://github.com) account with this repo pushed to it, and a free [Render](https://render.com) account.

---

## Step 1 — Push the repo to GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/mcp-example.git
git push -u origin main
```

## Step 2 — Create a Render Web Service

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

## Step 3 — Add a persistent disk

Without a disk, `api_keys.db` is wiped on every deploy. To persist it:

1. In your Render service dashboard, click **Disks** in the left menu
2. Click **Add Disk**:

   | Setting | Value |
   |---------|-------|
   | **Name** | `mcp-data` |
   | **Mount Path** | `/data` |
   | **Size** | 1 GB |

3. Click **Save**. Render will redeploy the service automatically.

## Step 4 — Retrieve your API key

Once the deploy finishes, click **Logs** in the Render dashboard. On first deploy you will see:

```
Generated default API key: QBMDHIqbf_qQV8uW7wJ6sMNDAj2q7VoFS_u9IGVqX80
```

Copy and save this key. It will not be printed again.

## Step 5 — Connect a client

Your server is now live at `https://YOUR-SERVICE-NAME.onrender.com/mcp`.

```bash
uv run -m mcp_examples.cli \
  --api-key YOUR_API_KEY \
  --url https://YOUR-SERVICE-NAME.onrender.com/mcp
```

> **Note:** Free tier Render services spin down after 15 minutes of inactivity. The first request after a period of inactivity may take 30–60 seconds while the service wakes up. Upgrade to a paid instance ($7/mo) to keep it always on.

## Deploying the contact server

To run `ContactMCPServer` instead of `GreetMCPServer`, change the Start Command in Render to:

```
uv run -m mcp_examples.contacts --transport streamable-http --port $PORT --host 0.0.0.0
```

Both database files will be stored on the persistent `/data` disk using the environment variables already set above.
