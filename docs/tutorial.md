# Tutorial: Using a Deployed MCP Server Kit Service

This tutorial is for someone who has been handed a **running** instance of this
service — a base URL and an API key — and wants to actually use it: call tools,
connect an AI agent, and understand what each server can do. It assumes someone
has already deployed the service (see [docs/deployment.md](deployment.md)); if
you're the one deploying it, start there instead.

If you just want a quick pass/fail checklist, see
[docs/smoke-tests.md](smoke-tests.md). This document is a walkthrough.

---

## What you need before starting

| Item | Where it comes from |
|------|----------------------|
| **Base URL** | Whoever deployed the service. It looks like `https://your-app.fly.dev` (Fly.io), `https://your-app.onrender.com` (Render), or an `ngrok` URL for local dev. |
| **API key** | Printed to the deploy logs the first time the service started (`Generated default API key: ...`), or fetched from the key database — see [docs/authentication.md](authentication.md). |

Every tool call needs the API key sent as an `X-API-Key` HTTP header. Without
it, every request gets `401 Unauthorized` — that's expected, not a bug.

Throughout this tutorial:

```bash
export BASE_URL="https://your-app.fly.dev"   # no trailing slash
export API_KEY="YOUR_API_KEY_HERE"
```

### Is it the combined server or a standalone one?

Most deployments run `mcp_server_kit.combined`, which mounts every server under
its own path on one base URL:

| Path | Server |
|------|--------|
| `/greet/mcp` | Greet |
| `/contacts/mcp` | Contacts (mock CRM) |
| `/wikipedia/mcp` | Wikipedia |
| `/weather/mcp` | Weather |
| `/messaging/mcp` | Messaging (Twilio SMS + SendGrid email) |
| `/pto/mcp` | PTO |
| `/onboarding/mcp` | Onboarding |

If instead you were given a single URL with no path prefix (e.g. just
`https://your-app.fly.dev/mcp`), you're talking to one standalone server —
skip ahead to whichever section matches it.

---

## Step 1 — Confirm you're connected

The fastest sanity check is listing tools on one path. This uses the bundled
`fastmcp` Python client, which handles the MCP session handshake for you:

```bash
uv run python - <<'PY'
import asyncio, os
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        f"{os.environ['BASE_URL']}/greet/mcp",
        headers={"X-API-Key": os.environ["API_KEY"]},
    )
    async with Client(transport) as client:
        print([t.name for t in await client.list_tools()])

asyncio.run(main())
PY
```

**Expected:** `['greet']`. If you instead see a connection error, double-check
`BASE_URL`. If you see `401`, double-check `API_KEY`.

Don't have `fastmcp` installed as a standalone tool? Any HTTP client works —
see the raw `curl` handshake in [docs/clients.md](clients.md).

---

## Step 2 — Pick a way to call tools

You have three options, roughly in order of convenience:

1. **An AI agent platform** (recommended for real use) — point Kore.ai Agent
   Platform (Artemis), Claude, or another MCP-aware agent at the URL and let
   it decide when to call which tool based on a conversation. See
   [KORE_AI_INTEGRATION.md](../KORE_AI_INTEGRATION.md) for Kore.ai-specific
   setup.
2. **The bundled Python client** — good for the `greet` tool specifically:
   ```bash
   uv run -m mcp_server_kit.cli --api-key "$API_KEY" --url "$BASE_URL/greet/mcp" --name Ada
   ```
3. **A short Python snippet with `fastmcp.Client`** — good for calling *any*
   tool on *any* server, which is what the rest of this tutorial uses:
   ```bash
   uv run python - <<'PY'
   import asyncio, os
   from fastmcp import Client
   from fastmcp.client.transports import StreamableHttpTransport

   async def main():
       transport = StreamableHttpTransport(
           f"{os.environ['BASE_URL']}/contacts/mcp",
           headers={"X-API-Key": os.environ["API_KEY"]},
       )
       async with Client(transport) as client:
           result = await client.call_tool(
               "search_by_last_name", {"last_name": "Webb"}
           )
           print(result.data)

   asyncio.run(main())
   PY
   ```

The rest of this tutorial shows what to expect from each server, using that
same pattern — swap the path, tool name, and arguments.

---

## Walking through each server

### Greet — the "hello world" of this kit

The simplest possible tool. Useful for confirming a fresh deployment works
before wiring up anything real.

```python
await client.call_tool("greet", {"name": "Ada"})
# -> "Hello, Ada!"
```

### Contacts — a mock Salesforce-style CRM

Pre-seeded with 20 fictional customer contacts across five mock accounts — good
for demoing a support or sales-assistant agent without touching a real CRM.

```python
# Find contacts by (partial, case-insensitive) last name
await client.call_tool("search_by_last_name", {"last_name": "Webb"})

# Exact match on email
await client.call_tool("search_by_email", {"email": "james.whitfield@meridiancorp.com"})

# Exact match on Salesforce-style account ID
await client.call_tool("search_by_account_id", {"account_id": "MC-001"})

# Verify a login (password checked against a hash, never stored or
# returned in plaintext)
await client.call_tool(
    "authenticate", {"email": "james.whitfield@meridiancorp.com", "password": "password123"}
)
```

Every one of these returns contact dicts *without* a `Password` field —
that's intentional; the field is stripped from every search result, and
`authenticate` verifies a hash rather than exposing it.

An empty search value (e.g. `{"last_name": ""}`) is rejected with a tool
error rather than silently returning every contact.

See [docs/managing-contacts.md](managing-contacts.md) if you need to add,
update, or reset the seed data on the running deployment.

### Weather — live OpenWeatherMap data

Requires the deployer to have set `OPENWEATHER_API_KEY`. If they didn't,
these calls return a tool error telling you so — that's a deployment
configuration issue, not something you fix as a caller.

```python
await client.call_tool("get_current_weather", {"location": "London"})
await client.call_tool("get_forecast", {"location": "Tokyo,JP", "days": 3})
await client.call_tool("get_air_quality", {"location": "Beijing"})
```

`location` accepts a bare city name, `City,CountryCode`, or
`City,State,CountryCode` for disambiguating US cities. `units` defaults to
`metric`; pass `"imperial"` or `"standard"` to change it.

### Wikipedia — search and article lookups

No credentials needed — always available.

```python
await client.call_tool("search_pages", {"query": "Python programming language"})
await client.call_tool("search_titles", {"query": "Pytho"})
await client.call_tool("get_page_summary", {"title": "Python (programming language)"})
await client.call_tool("get_related_pages", {"title": "Python (programming language)"})
```

`get_page_summary` accepts spaces or underscores in the title
interchangeably.

### Messaging — real SMS and email

**This one sends real messages and can incur real cost.** Requires the
deployer to have set Twilio and SendGrid credentials. Use a phone number and
inbox you own for testing.

```python
# Plain SMS
await client.call_tool(
    "send_sms", {"to": "+15551234567", "body": "Hello from the demo!"}
)

# SMS from a pre-approved Twilio Content template
await client.call_tool(
    "send_sms_template",
    {
        "to": "+15551234567",
        "content_sid": "HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "content_variables": {"1": "Ada"},
    },
)

# Plain or HTML email
await client.call_tool(
    "send_email",
    {
        "to": "you@example.com",
        "subject": "Hello from the demo!",
        "plain_text": "This is a test email.",
    },
)

# Email from a pre-approved SendGrid dynamic template
await client.call_tool(
    "send_email_template",
    {
        "to": "you@example.com",
        "template_id": "d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "dynamic_template_data": {"first_name": "Ada"},
    },
)
```

`to` for SMS must be E.164 format (`+` then country code then number) —
anything else is rejected before Twilio is ever called. Template SIDs are
validated by prefix (`HX...` for Twilio, `d-...` for SendGrid) so a typo'd
ID fails fast with a clear error instead of an opaque provider error.

### PTO — a mock time-off system

Pre-seeded with 6 employees (3 India, 3 USA), each with a manager and a
starting balance.

```python
await client.call_tool("get_balance", {"employee_id": "E1001"})
await client.call_tool("get_balance_by_email", {"email": "asha.rao@example.com"})

# Auto-approves if there's enough balance; otherwise denied with no deduction
await client.call_tool(
    "request_pto",
    {"employee_id": "E1001", "start_date": "2026-09-01", "end_date": "2026-09-03", "days": 2},
)

await client.call_tool("list_requests", {"employee_id": "E1001"})
```

### Onboarding — a mock new-hire case tracker

Starts empty; cases are created as you go.

```python
case = await client.call_tool(
    "create_case",
    {
        "employee_name": "Ada Lovelace",
        "employee_email": "ada@example.com",
        "location": "London",
        "manager_name": "Grace Hopper",
        "start_date": "2026-09-01",
    },
)
case_id = case.data["CaseId"]

await client.call_tool("get_case", {"case_id": case_id})
await client.call_tool(
    "update_case_status", {"case_id": case_id, "status": "it_provisioning"}
)
await client.call_tool("list_cases", {"status": "it_provisioning"})
```

`status` must be one of `submitted`, `it_provisioning`, `manager_review`,
`completed`, `cancelled` — anything else is a tool error.

---

## Connecting an AI agent instead of calling tools yourself

Everything above calls tools directly, which is useful for testing but isn't
the point of MCP — the point is letting an LLM-driven agent decide when to
call which tool based on a conversation. To wire that up:

- **Kore.ai Agent Platform (Artemis)** — see
  [KORE_AI_INTEGRATION.md](../KORE_AI_INTEGRATION.md) for the full setup,
  including registering the server, importing tools, and re-syncing after
  changes.
- **Any other MCP-aware agent platform** — configure it with:
  - **Server URL**: `$BASE_URL/<prefix>/mcp` (e.g. `.../contacts/mcp`)
  - **Transport**: Streamable HTTP
  - **Auth header**: `X-API-Key: $API_KEY`

Most platforms need one connection *per server path* if they don't support
mounting sub-paths of a single MCP endpoint — check the platform's docs for
whether it can discover multiple `/mcp` paths under one base URL or needs
one connection per path.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Every call returns `401` | Wrong or missing `X-API-Key` header, or you're using a key from a different deployment/database than the one you're calling. |
| A path returns `404` | That server isn't mounted at that prefix — check the table in "Is it the combined server" above, or ask whoever deployed it. |
| Weather / messaging tools return a credentials error | The deployer hasn't set `OPENWEATHER_API_KEY` / `TWILIO_*` / `SENDGRID_*` — this is a deployment configuration gap, not something you can fix as a caller. |
| `send_sms_template` / `send_email_template` reject a valid-looking ID | Twilio Content SIDs must start with `HX`; SendGrid dynamic template IDs must start with `d-`. Double-check you copied the ID from the right provider console. |
| A contact search with an empty string errors out | Intentional — an empty search would otherwise match every contact in the database. Pass a real search term. |
| Nothing happens / times out | The service may be asleep (some free-tier hosts suspend idle instances) — retry after a few seconds, or check with whoever deployed it. |

---

## Where to go next

- [docs/smoke-tests.md](smoke-tests.md) — a fast pass/fail checklist covering the same tools
- [docs/servers.md](servers.md) — full tool/parameter reference for every server
- [docs/security.md](security.md) — how API keys and passwords are handled
- [docs/extending.md](extending.md) — adding a new tool or server
- [docs/troubleshooting.md](troubleshooting.md) — broader troubleshooting beyond this tutorial's scope
