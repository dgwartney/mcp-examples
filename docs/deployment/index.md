# Deployment Options

Choose the deployment option that best fits your cost and availability requirements.

## Comparison

| Provider | Monthly cost | SQLite persists | Always on | Cold start | Best for |
|----------|-------------|-----------------|-----------|------------|----------|
| [Local](local.md) | Free | ✅ local disk | Requires laptop on | None | Development and local testing |
| [ngrok](ngrok.md) | Free (random URL) / $10 (fixed URL) | ✅ local disk | Requires laptop on | None | Demos and temporary sharing — no cloud account needed |
| [Render](render.md) | Free + $1/mo disk | ✅ | ❌ spins down 15 min idle | 30–60s | Low-traffic APIs where occasional slow startup is acceptable |
| [Fly.io](flyio.md) | Free tier | ✅ volume | ✅ (configurable) | ~5s in auto-stop mode | Best free option: persistent, always-available, full CLI management |
| [Railway](railway.md) | $5 credit then usage | ❌ ephemeral | ✅ | None | Projects without data persistence needs, or willing to pay for volumes |
| [Docker / VPS](docker.md) | ~$4–5/mo | ✅ volume mount | ✅ | None | Production: full control, no cold starts, no platform constraints |

## Key trade-off summary

- **Zero cost + persistence + always-on**: Fly.io free tier with `min_machines_running = 1` in `fly.toml`
- **Zero cost + persistence, accept cold starts**: Fly.io with auto-stop, or Render free + $1/mo disk
- **Zero cost, no persistence**: Railway free credit (databases reset on every restart)
- **Minimal cost, full control**: Hetzner CX11 at €3.79/mo or DigitalOcean Droplet at $4/mo — own VPS, SQLite on disk, no cold starts

## Provider guides

- [Local Development](local.md) — run on your machine, no cloud account needed
- [ngrok](ngrok.md) — expose a locally-running server publicly via a tunnel
- [Render](render.md) — deploy from GitHub, free tier with persistent disk add-on
- [Fly.io](flyio.md) — deploy via Docker, free persistent volumes, full lifecycle management
- [Railway](railway.md) — deploy from GitHub via Procfile, $5/mo free credit
- [Docker / VPS](docker.md) — self-hosted on any VPS, or Docker + ngrok locally
