# Railway

**Trade-offs:** $5 of free credit per month, then usage-based billing. Deploys directly from GitHub with no Docker setup. **SQLite databases are wiped on every restart** — Railway uses an ephemeral filesystem. Persistent volumes are available as a paid add-on. Best for projects that don't need data persistence, or where you're willing to pay for volumes.

**Official guides:**
- [Railway getting started](https://docs.railway.app/getting-started)
- [Railway Procfile deployments](https://docs.railway.app/deploy/config-as-code)
- [Railway environment variables](https://docs.railway.app/guides/variables)
- [Railway volumes (persistent storage)](https://docs.railway.app/guides/volumes)
- [Railway pricing and free tier](https://railway.app/pricing)

---

## Getting started

1. Push the repo to GitHub (see [render.md — Step 1](render.md#step-1--push-the-repo-to-github)):
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/mcp-example.git
   git push -u origin main
   ```
2. Log in to [railway.app](https://railway.app) and click **New Project > Deploy from GitHub repo**
3. Select your `mcp-example` repository
4. Railway detects the `Procfile` automatically and starts the deploy
5. In the service settings, add these environment variables:
   - `MCP_DB_PATH` = `/data/api_keys.db`
   - `CONTACTS_DB_PATH` = `/data/contacts.db`
6. Click **Deploy**
7. Open **Logs** to find the generated API key on first deploy

Your public URL is shown in the Railway dashboard under **Settings > Domains**.
