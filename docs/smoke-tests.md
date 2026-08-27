# Smoke Tests

A short, manual checklist to confirm each server actually works after a change —
faster than [manual-testing.md](manual-testing.md) (which validates the
scaffolding/packaging machinery) and a stand-in for the automated
[end-to-end tests](testing.md) this project doesn't have yet. Run this after any
change to `mcp_server_kit/`, before a release, or after a deploy.

Each check has three parts: **setup**, **command**, **expected result**. Work
top to bottom; skip a server's section if you don't have its credentials, but
say so in your notes rather than silently passing over it.

> **uv only.** Every command below uses `uv run`. Install `uv` first if needed:
> `curl -LsSf https://astral.sh/uv/install.sh | sh`.

---

## 0. Before you start

```bash
uv sync --extra test
```

Start every server with a scratch key database so you know exactly which API
key to send:

```bash
export MCP_DB_PATH="$PWD/smoke_keys.db"
rm -f "$MCP_DB_PATH"
```

There are two ways to get a key into `$MCP_DB_PATH`: let the server generate
one on first run (simple, but the value is random each time you `rm` the
file), or insert a known key yourself before starting anything (repeatable —
better for scripting). Pick one.

### Option A — insert a known key yourself (recommended for scripting)

`DatabaseManager.init_db()` only *generates* a key if the `api_keys` table is
empty when a server first starts — so if you create the table and insert
your own key first, every server that starts against this `$MCP_DB_PATH`
will use it instead:

```bash
export API_KEY="smoke-test-$(uv run python -c 'import secrets; print(secrets.token_urlsafe(16))')"

sqlite3 "$MCP_DB_PATH" \
  "CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL);
   INSERT INTO api_keys (key) VALUES ('$API_KEY');"

echo "$API_KEY"
```

Every `API_KEY=$(sqlite3 ...)` line in the sections below becomes unnecessary
if you do this first — `$API_KEY` is already set and stable for the rest of
your shell session. (See [docs/authentication.md](authentication.md#managing-api-keys)
for the same pattern applied to a running deployment.)

### Option B — let the server generate one, then read it back

`$MCP_DB_PATH` doesn't exist yet — there's no key to fetch until a server
actually starts and initializes it. Each section below starts its server
*first*, which creates the database and generates a key on that first run
(reused by every later section, since they share `$MCP_DB_PATH`), and only
*then* fetches it — that's what the `API_KEY=$(sqlite3 ...)` lines in each
section do. Skip this if you already did Option A.

### Wait-for-ready helper (needed either way)

Every section below starts a server in the background and then immediately
needs it to be listening — whether to call a tool (Option A) or to read back
its generated key (Option B). **Don't use a fixed `sleep`** for this — under
`uv run`, first startup commonly takes 2–4+ seconds (resolving the venv,
importing `fastmcp`), so a short `sleep 1` can run before the server, or even
its database table, exists yet. Define this poll-until-ready helper once per
shell session instead — it succeeds the moment the server responds to any
request, which by then is also the moment its API key exists in the database:

```bash
wait_for_server() {
  # usage: wait_for_server <url>   (defined once per shell session)
  local url="$1"
  for _ in $(seq 1 40); do
    if curl -s -o /dev/null "$url" -X POST \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'; then
      return 0
    fi
    sleep 0.5
  done
  echo "ERROR: server at $url did not respond within 20s" >&2
  return 1
}
```

Example call, in isolation — after defining the function above, start any
server and wait for it:

```bash
uv run -m mcp_server_kit.server --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp && echo "server is up"
kill %1
```

Every section from here on calls it the same way, right after starting that
section's server and before doing anything else with it (fetching a key,
calling a tool, sending a `curl` request).

Confirm the whole flow works before continuing (this example uses Option B —
if you already set `$API_KEY` via Option A, skip the `API_KEY=$(sqlite3 ...)`
line and everything else still applies):

```bash
uv run -m mcp_server_kit.server --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
echo "$API_KEY"
kill %1
```

The snippets below use this helper to list tools and call one, via the fastmcp
client (it does the initialize/session handshake for you):

```bash
call_tool() {
  # usage: call_tool <url> <tool_name> <json_args>
  local url="$1" tool="$2" args="$3"
  API_KEY="$API_KEY" URL="$url" TOOL="$tool" ARGS="$args" uv run python - <<'PY'
import asyncio, json, os
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def main():
    transport = StreamableHttpTransport(
        os.environ["URL"], headers={"X-API-Key": os.environ["API_KEY"]}
    )
    async with Client(transport) as client:
        result = await client.call_tool(os.environ["TOOL"], json.loads(os.environ["ARGS"]))
        print(result.data)

asyncio.run(main())
PY
}
```

---

## 1. Auth guard (run once, on any server)

Start any server (e.g. greet) and confirm unauthenticated requests are rejected:

```bash
uv run -m mcp_server_kit.server --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp

curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

**Expected:** `401`. If you get `200`, auth is broken — stop and investigate
before testing anything else.

```bash
kill %1
```

---

## 2. Greet server

```bash
uv run -m mcp_server_kit.server --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")

call_tool http://localhost:8000/mcp greet '{"name": "Ada"}'
```

**Expected:** `Hello, Ada!`

```bash
kill %1
```

---

## 3. Contact server

Seeded with 20 mock CRM contacts — no external credentials needed.

```bash
uv run -m mcp_server_kit.contacts --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
```

| # | Call | Expected |
|---|------|----------|
| 3.1 | `call_tool http://localhost:8000/mcp search_by_last_name '{"last_name": "Webb"}'` | Two contacts (Marcus Webb, Eleanor Webster); **no `Password` field anywhere in the output** |
| 3.2 | `call_tool http://localhost:8000/mcp search_by_last_name '{"last_name": ""}'` | Tool error — empty search is rejected, not a dump of every contact |
| 3.3 | `call_tool http://localhost:8000/mcp authenticate '{"email": "james.whitfield@meridiancorp.com", "password": "password123"}'` | James Whitfield's profile, no `Password` field |
| 3.4 | `call_tool http://localhost:8000/mcp authenticate '{"email": "james.whitfield@meridiancorp.com", "password": "wrong"}'` | Tool error: `Authentication failed` |

```bash
kill %1
```

---

## 4. Weather server

Requires a free key from <https://openweathermap.org/api>.

```bash
export OPENWEATHER_API_KEY=<your_key>
uv run -m mcp_server_kit.weather --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
```

| # | Call | Expected |
|---|------|----------|
| 4.1 | `call_tool http://localhost:8000/mcp get_current_weather '{"location": "London"}'` | Dict with `temperature`, `humidity`, `description`, etc. for London, UK |
| 4.2 | `call_tool http://localhost:8000/mcp get_forecast '{"location": "Tokyo,JP", "days": 3}'` | 3 daily summaries |
| 4.3 | `call_tool http://localhost:8000/mcp get_air_quality '{"location": "Beijing"}'` | `aqi` between 1–5 with a matching `aqi_label` |
| 4.4 | `call_tool http://localhost:8000/mcp get_current_weather '{"location": "Nowhereville,ZZ"}'` | Tool error: `Location not found` |

```bash
kill %1
```

---

## 5. Wikipedia server

No credentials needed.

```bash
uv run -m mcp_server_kit.wikipedia --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
```

| # | Call | Expected |
|---|------|----------|
| 5.1 | `call_tool http://localhost:8000/mcp search_pages '{"query": "Python programming language"}'` | Results list with `title`, `excerpt` (no HTML tags in the excerpt) |
| 5.2 | `call_tool http://localhost:8000/mcp get_page_summary '{"title": "Python (programming language)"}'` | A plain-text `extract` and a `url` |
| 5.3 | `call_tool http://localhost:8000/mcp get_related_pages '{"title": "Python (programming language)"}'` | A non-empty list of related titles |

```bash
kill %1
```

---

## 6. Messaging server (Twilio SMS + SendGrid email)

Requires real Twilio and SendGrid credentials — **these calls send a real SMS
and a real email**, so use a phone number and inbox you own, and expect a
small Twilio cost per SMS.

```bash
export TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_MESSAGING_SERVICE_SID=<mg_sid>
export SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<verified_sender>
# Optional — only needed for check 6.5 (send_email_template); leave unset to skip it.
export SENDGRID_TEST_TEMPLATE_ID=<your approved SendGrid dynamic template ID>
uv run -m mcp_server_kit.messaging --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
```

| # | Call | Expected |
|---|------|----------|
| 6.1 | `call_tool http://localhost:8000/mcp send_sms '{"to": "+1YOURNUMBER", "body": "Smoke test"}'` | Dict with `sid` and `status: queued`; SMS arrives on the phone |
| 6.2 | `call_tool http://localhost:8000/mcp send_email '{"to": "you@example.com", "subject": "Smoke test", "plain_text": "hello", "reply_to": "you@example.com", "reply_to_name": "Smoke Test"}'` | Dict with `message_id`; email arrives with Reply-To set to the given address |
| 6.3 | `call_tool http://localhost:8000/mcp send_sms '{"to": "5551234567", "body": "x"}'` | Tool error: E.164 format required (no SMS sent — confirms validation runs before the Twilio call) |
| 6.4 | *(only if you have an approved Content template)* `call_tool http://localhost:8000/mcp send_sms_template '{"to": "+1YOURNUMBER", "content_sid": "HXxxxxxxxx", "content_variables": {"1": "Ada"}}'` | Dict with `sid`; templated SMS arrives with the variable substituted |
| 6.5 | *(only if you have an approved dynamic template — set `SENDGRID_TEST_TEMPLATE_ID`, or substitute the ID directly)* `call_tool http://localhost:8000/mcp send_email_template "{\"to\": \"you@example.com\", \"template_id\": \"$SENDGRID_TEST_TEMPLATE_ID\", \"dynamic_template_data\": {\"first_name\": \"Ada\"}}"` | Dict with `message_id`; templated email arrives rendered |
| 6.6 | `call_tool http://localhost:8000/mcp send_sms_template '{"to": "+1YOURNUMBER", "content_sid": "HXabc", "content_variables": {"1": "ok"}}'` with `TWILIO_ACCOUNT_SID` unset | Tool error: `Missing Twilio credentials` (no request reaches Twilio) |

```bash
kill %1
```

---

## 7. PTO server

Seeded with 6 mock employees — no external credentials needed.

```bash
uv run -m mcp_server_kit.pto --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
```

| # | Call | Expected |
|---|------|----------|
| 7.1 | `call_tool http://localhost:8000/mcp get_balance '{"employee_id": "E1001"}'` | A balance in days |
| 7.2 | `call_tool http://localhost:8000/mcp request_pto '{"employee_id": "E1001", "start_date": "2026-09-01", "end_date": "2026-09-03", "days": 2}'` | Approved request; re-run 7.1 and confirm the balance dropped by 2 |
| 7.3 | `call_tool http://localhost:8000/mcp request_pto '{"employee_id": "E1001", "start_date": "2026-09-01", "end_date": "2026-09-30", "days": 999}'` | Request logged as `denied_insufficient_balance`; balance unchanged |
| 7.4 | `call_tool http://localhost:8000/mcp list_requests '{"employee_id": "E1001"}'` | Both requests above, most recent first |

```bash
kill %1
```

---

## 8. Onboarding server

Case table starts empty — no external credentials needed.

```bash
uv run -m mcp_server_kit.onboarding --transport streamable-http --port 8000 &
wait_for_server http://localhost:8000/mcp
API_KEY=$(sqlite3 "$MCP_DB_PATH" "SELECT key FROM api_keys LIMIT 1;")
```

| # | Call | Expected |
|---|------|----------|
| 8.1 | `call_tool http://localhost:8000/mcp create_case '{"employee_name": "Ada Lovelace", "employee_email": "ada@example.com", "location": "London", "manager_name": "Grace Hopper", "start_date": "2026-09-01"}'` | New case with a `CaseId`, status `submitted` |
| 8.2 | `call_tool http://localhost:8000/mcp get_case '{"case_id": 1}'` | The case from 8.1 (adjust the ID if not `1`) |
| 8.3 | `call_tool http://localhost:8000/mcp update_case_status '{"case_id": 1, "status": "completed"}'` | Status updated to `completed` |
| 8.4 | `call_tool http://localhost:8000/mcp update_case_status '{"case_id": 1, "status": "bogus"}'` | Tool error: invalid status |
| 8.5 | `call_tool http://localhost:8000/mcp list_cases '{}'` | Includes the case from 8.1 |

```bash
kill %1
```

---

## 9. Combined server

Confirms every server mounts correctly in one process — the configuration
used for deployment.

```bash
uv run -m mcp_server_kit.combined --port 8000 &
wait_for_server http://localhost:8000/greet/mcp
API_KEY=$(sqlite3 "$PWD/api_keys.db" "SELECT key FROM api_keys LIMIT 1;")

for prefix in greet contacts wikipedia weather messaging pto onboarding; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "http://localhost:8000/$prefix/mcp" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
  echo "$prefix/mcp (no key) -> $code   (expect 401)"
done

curl -s -o /dev/null -w "unknown/mcp -> %{http_code}   (expect 404)\n" -X POST \
  http://localhost:8000/unknown/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

call_tool http://localhost:8000/greet/mcp greet '{"name": "Ada"}'
```

**Expected:** all seven prefixes return `401`, `unknown/mcp` returns `404`,
and the greet call at the end returns `Hello, Ada!`.

```bash
kill %1
rm -f "$MCP_DB_PATH" "$PWD/api_keys.db"
```

---

## Sign-off checklist

Copy this into your PR description or release notes and check off what you ran:

- [ ] §1 Auth guard — unauthenticated request rejected with 401
- [ ] §2 Greet
- [ ] §3 Contacts — including empty-search rejection (3.2) and no password leakage (3.1, 3.3)
- [ ] §4 Weather
- [ ] §5 Wikipedia
- [ ] §6 Messaging — including credential-missing guard (6.6) and, if templates are configured, 6.4/6.5
- [ ] §7 PTO
- [ ] §8 Onboarding
- [ ] §9 Combined server — all seven prefixes mounted and auth-guarded

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `401` even with a key | Wrong key DB — re-read the key from the same `MCP_DB_PATH`/`api_keys.db` the running server used. |
| `call_tool` hangs | The server isn't listening yet — increase the `sleep` after starting it, or check the terminal for a startup error. |
| Weather/messaging tool errors | Missing or invalid `OPENWEATHER_API_KEY` / `TWILIO_*` / `SENDGRID_*` env vars. |
| Port already in use | Pick another `--port`, or `kill %1` a server left running from an earlier section. |
| `sqlite3: command not found` | Install it (`brew install sqlite3` on macOS) or read the key with `python -c "import sqlite3; ..."` instead. |
