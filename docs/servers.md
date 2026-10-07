# Servers

This project provides seven MCP servers built on a shared authenticated base class.

## Greet Server (`mcp_server_kit/server.py`)

A minimal demonstration server.

- **DatabaseManager** (`database.py`): Handles SQLite operations for API key storage and validation
- **ApiKeyMiddleware** (`middleware.py`): Validates incoming requests against stored API keys
- **GreetMCPServer** (`server.py`): Encapsulates server setup, tool registration, and lifecycle management
- **Multiple Transport Support**: Runs via stdio (default) or HTTP transport
- **Automatic Database Initialization**: Creates schema and generates default API key on first run

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `greet` | `name: str` | Returns `"Hello, {name}!"` |

## Contact Server (`mcp_server_kit/contacts.py`)

A Salesforce-style CRM server backed by a SQLite contacts database, auto-seeded with 20 fictional customer contacts.

- **ContactDatabaseManager** (`contact_database.py`): SQLite-backed storage for mock contact profiles
- **ContactMCPServer** (`contacts.py`): Subclass of `AuthenticatedMCPServer` exposing contact search and authentication tools

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_by_last_name` | `last_name: str` | Case-insensitive partial match on last name |
| `search_by_email` | `email: str` | Case-insensitive exact match on email |
| `search_by_account_id` | `account_id: str` | Exact match on Salesforce-style account ID |
| `authenticate` | `email: str, password: str` | Verify credentials; returns contact profile (without password) or raises `ToolError` |

### Seed data

`contacts.db` is auto-seeded with 20 fictional customer contacts across five accounts:

| Account | Contacts |
|---------|-----------|
| Meridian Corporation | James Whitfield, Daniel Reyes, Robert Chen, Frank Douglas |
| Cascade Media Group | Rachel Adams, Victor Alvarez, Nicole Sanders, Marcus Webb, Eleanor Webster, Gregory Fontaine |
| Apex Industrial Supply | Gary Mitchell, Ethan Park |
| Riverside Holdings | Walter Briggs, Harold Jennings, Philippe Moreau, Mateo Fernandez, Camille Dupont |
| Nova Technologies | Oliver Grant, Bruce Sullivan, Diane Coleman |

Each record includes fields: `Id`, `FirstName`, `LastName`, `Email`, `Phone`, `MobilePhone`, `Title`, `Department`, `AccountId`, `AccountName`, `MailingStreet`, `MailingCity`, `MailingState`, `MailingPostalCode`, `MailingCountry`, and more.

## Weather Server (`mcp_server_kit/weather.py`)

Queries the [OpenWeatherMap API](https://openweathermap.org/api) to provide current conditions, multi-day forecasts, and air quality data. Requires a free OpenWeatherMap API key — sign up at https://openweathermap.org/api and set the `OPENWEATHER_API_KEY` environment variable before starting.

- **WeatherMCPServer** (`weather.py`): Subclass of `AuthenticatedMCPServer` with an `httpx.Client` for outbound OpenWeatherMap requests
- **API key auth**: Same middleware-based authentication as the other servers
- **Geocoding**: All three tools automatically geocode the location name to lat/lon using the OpenWeatherMap Geocoding API before fetching data

### Location format

All tools accept a `location` string in any of these forms:

| Format | Example | Use when |
|--------|---------|----------|
| City name only | `London` | Unambiguous city names |
| City + country code | `Paris,FR` | Disambiguate cities that appear in multiple countries |
| City + state + country | `San Jose,CA,US` | US cities — state code required to avoid matching other countries |

> **Note:** Spaces around commas are ignored (`"San Jose, CA, US"` and `"San Jose,CA,US"` both work). Country and state codes follow [ISO 3166](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) two-letter codes.

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_current_weather` | `location: str, units: str = "metric"` | Current conditions: temperature, humidity, pressure, wind, visibility, sunrise/sunset. `units`: `metric` (°C), `imperial` (°F), `standard` (K) |
| `get_forecast` | `location: str, days: int = 5, units: str = "metric"` | Daily forecast summaries for up to 5 days (aggregated from 3-hour interval data): min/max temp, description, humidity, wind (days clamped 1–5) |
| `get_air_quality` | `location: str` | Current AQI (1=Good … 5=Very Poor) and pollutant levels: CO, NO₂, O₃, PM2.5, PM10 |

### Running

```bash
# stdio transport (default)
OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.weather

# HTTP transport
OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.weather --transport streamable-http --port 8001

# Custom database path
MCP_DB_PATH=/var/data/keys.db OPENWEATHER_API_KEY=<key> uv run -m mcp_server_kit.weather
```

---

## Wikipedia Server (`mcp_server_kit/wikipedia.py`)

Queries the Wikipedia REST API and MediaWiki Action API to search and retrieve article content. Demonstrates how to build a tool-rich MCP server that calls an external HTTP API.

- **WikipediaMCPServer** (`wikipedia.py`): Subclass of `AuthenticatedMCPServer` with an `httpx.Client` for outbound Wikipedia requests
- **API key auth**: Same middleware-based authentication as the other servers
- **HTML stripping**: Strips HTML tags from Wikipedia excerpts before returning them to the caller

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `search_pages` | `query: str, limit: int = 10` | Full-text search; returns title, excerpt, description, and thumbnail URL for each result (limit: 1–100) |
| `search_titles` | `query: str, limit: int = 10` | Autocomplete-style title search; best for finding the exact page title to use with `get_page_summary` (limit: 1–100) |
| `get_page_summary` | `title: str` | Fetch a page's plain-text extract, short description, canonical URL, and thumbnail. Accepts spaces or underscores in the title |
| `get_related_pages` | `title: str, limit: int = 10` | Semantically related articles via the MediaWiki `morelike:` operator (limit: 1–50) |

### Running

```bash
# stdio transport (default)
uv run -m mcp_server_kit.wikipedia

# HTTP transport
uv run -m mcp_server_kit.wikipedia --transport streamable-http --port 8001

# Custom database path
MCP_DB_PATH=/var/data/keys.db uv run -m mcp_server_kit.wikipedia
```

---

## Messaging Server (`mcp_server_kit/messaging.py`)

Sends SMS via the [Twilio REST API](https://www.twilio.com/docs/messaging/api) and email via the [SendGrid v3 Mail Send API](https://docs.sendgrid.com/api-reference/mail-send/mail-send). Supports plain-text and HTML email in a single tool call, plus pre-approved [Twilio Content API templates](https://www.twilio.com/docs/content/send-templates-created-with-the-content-template-builder) for SMS and [SendGrid dynamic templates](https://docs.sendgrid.com/ui/sending-email/how-to-send-an-email-with-dynamic-transactional-templates/) for email.

- **MessagingMCPServer** (`messaging.py`): Subclass of `AuthenticatedMCPServer` with an `httpx.Client` for outbound Twilio and SendGrid requests
- **API key auth**: Same middleware-based authentication as the other servers

### Required environment variables

| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID (starts with `AC`) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_MESSAGING_SERVICE_SID` | Twilio Messaging Service SID (starts with `MG`) |
| `SENDGRID_API_KEY` | SendGrid API key (starts with `SG.`) |
| `SENDGRID_FROM_EMAIL` | Verified sender email address |
| `SENDGRID_FROM_NAME` | *(optional)* Display name shown in the From field |

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `send_sms` | `to: str, body: str` | Send an SMS via Twilio using the configured Messaging Service. `to` must be E.164 format (e.g. `+15551234567`). Returns the Twilio message `sid` and delivery `status`. |
| `send_sms_template` | `to: str, content_sid: str, content_variables: dict = None` | Send an SMS using a pre-approved Twilio Content API template. `content_sid` must start with `HX`; `content_variables` maps template variable names to substitution values. Returns the Twilio message `sid`, `status`, and rendered `body`. |
| `send_email` | `to: str, subject: str, plain_text: str = None, html: str = None, to_name: str = None, from_email: str = None, from_name: str = None, reply_to: str = None, reply_to_name: str = None` | Send an email via SendGrid. At least one of `plain_text` or `html` must be provided; if both are given the message is sent as multipart/alternative so mail clients can choose the best format. `reply_to` sets the Reply-To address if different from the sender. Returns SendGrid `message_id`. |
| `send_email_template` | `to: str, template_id: str, dynamic_template_data: dict = None, to_name: str = None, from_email: str = None, from_name: str = None, subject: str = None, reply_to: str = None, reply_to_name: str = None` | Send an email using a pre-approved SendGrid dynamic template. `template_id` must start with `d-`; `dynamic_template_data` maps template variable names to substitution values. `subject` is optional since templates usually supply their own. `reply_to` sets the Reply-To address if different from the sender. Returns SendGrid `message_id`. |

### Running

```bash
# stdio transport (default)
TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_MESSAGING_SERVICE_SID=<mg_sid> \
SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_server_kit.messaging

# HTTP transport
TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_MESSAGING_SERVICE_SID=<mg_sid> \
SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_server_kit.messaging --transport streamable-http --port 8003

# Custom database path
MCP_DB_PATH=/var/data/keys.db TWILIO_ACCOUNT_SID=<sid> ... uv run -m mcp_server_kit.messaging
```

---

## PTO Server (`mcp_server_kit/pto.py`)

A mock employee PTO (paid time off) server backed by a SQLite database, auto-seeded with a small India/USA workforce (three India employees, three USA employees, each with a manager and a starting PTO balance).

- **PtoDatabaseManager** (`pto_database.py`): SQLite-backed storage for employee PTO balances and a PTO request log
- **PtoMCPServer** (`pto.py`): Subclass of `AuthenticatedMCPServer` exposing balance lookup and PTO request tools

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_balance` | `employee_id: str` | Look up an employee's PTO balance by employee ID. Raises `ToolError` if not found. |
| `get_balance_by_email` | `email: str` | Look up an employee's PTO balance by email (case-insensitive exact match). Raises `ToolError` if not found. |
| `request_pto` | `employee_id: str, start_date: str, end_date: str, days: float` | File a PTO request. Auto-approves and deducts the balance if sufficient days are available; otherwise recorded as `denied_insufficient_balance` with no deduction. Dates are ISO `YYYY-MM-DD`. |
| `list_requests` | `employee_id: str` | List all PTO requests filed by an employee, most recent first. |

### Seed data

`pto.db` is auto-seeded with 6 employees: `E1001`–`E1003` (India, manager chain Asha Rao → Priya Nair → Deepak Menon) and `E2001`–`E2003` (USA, manager chain Jordan Blake → Casey Morgan → Jamie Ellis). Starting balances range 9–22 days.

### Running

```bash
# stdio transport (default)
uv run -m mcp_server_kit.pto

# HTTP transport
uv run -m mcp_server_kit.pto --transport streamable-http --port 8010

# Custom database paths
MCP_DB_PATH=/var/data/keys.db PTO_DB_PATH=/var/data/pto.db uv run -m mcp_server_kit.pto
```

---

## Onboarding Server (`mcp_server_kit/onboarding.py`)

A mock new-hire onboarding case tracker backed by a SQLite database. Unlike PTO, the case table starts empty — cases are created at runtime as new hires are onboarded (India/USA).

- **OnboardingDatabaseManager** (`onboarding_database.py`): SQLite-backed storage for onboarding case records
- **OnboardingMCPServer** (`onboarding.py`): Subclass of `AuthenticatedMCPServer` exposing case create/read/update/list tools

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_case` | `employee_name: str, employee_email: str, location: str, manager_name: str, start_date: str` | Create a new onboarding case in `submitted` status. Returns the created case with its `CaseId`. |
| `get_case` | `case_id: int` | Look up an onboarding case by case ID. Raises `ToolError` if not found. |
| `update_case_status` | `case_id: int, status: str, notes: str = None` | Update a case's status. `status` must be one of `submitted`, `it_provisioning`, `manager_review`, `completed`, `cancelled`. Raises `ToolError` for an unknown case or invalid status. |
| `list_cases` | `status: str = None` | List onboarding cases, optionally filtered by status; omit to list all. |

### Running

```bash
# stdio transport (default)
uv run -m mcp_server_kit.onboarding

# HTTP transport
uv run -m mcp_server_kit.onboarding --transport streamable-http --port 8011

# Custom database paths
MCP_DB_PATH=/var/data/keys.db ONBOARDING_DB_PATH=/var/data/onboarding.db uv run -m mcp_server_kit.onboarding
```

---

## Acme Support Server (`mcp_server_kit/acme.py` + `mcp_server_kit/acme_api.py`)

A mock retail customer-service backend (orders, returns, support tickets) built for the Artemis learning-guide labs. The same SQLite data is exposed **two ways** so labs can compare an HTTP tool with an MCP tool that reach the same backend:

- **AcmeDatabaseManager** (`acme_database.py`): SQLite storage. Six seeded orders cover every lifecycle state; returns and tickets start empty and are created at runtime.
- **AcmeMCPServer** (`acme.py`): Subclass of `AuthenticatedMCPServer`, mounted at `/acme/mcp`.
- **REST API** (`acme_api.py`): A plain Starlette app, mounted at `/acme/api`. Every route except `GET /acme/api/health` requires the shared `X-API-Key`.

### MCP tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_order` | `order_id: str` | Order status and details, including `return_eligible` / `return_deadline`. `ToolError` if not found. |
| `list_orders` | `email: str` | All orders for a customer email, newest first. |
| `create_return` | `order_id: str, reason: str` | Open a return (`RET-<n>`) for a delivered order inside its 30-day window. `ToolError` otherwise. |
| `get_return` | `return_id: str` | Look up a return. |
| `create_ticket` | `customer_email: str, subject: str, description: str, priority: str = "normal"` | Open a support ticket (`TKT-<n>`). Priority is `low`, `normal`, `high` or `urgent`. |
| `get_ticket` | `ticket_id: str` | Look up a ticket. |

### REST routes (under `/acme/api`)

| Method & path | Success | Errors |
|---|---|---|
| `GET /health` (no key) | `200 {"status":"ok","service":"acme"}` | — |
| `GET /orders/{order_id}` | `200` order | `404 order_not_found` |
| `GET /orders?email=` | `200 {"customer_email","count","orders"}` | `400 missing_email` |
| `POST /returns` `{"order_id","reason"}` | `201` return | `400`, `404 order_not_found`, `409 not_eligible` |
| `GET /returns/{return_id}` | `200` return | `404` |
| `POST /tickets` `{"customer_email","subject","description","priority"?}` | `201` ticket | `400` |
| `GET /tickets/{ticket_id}` | `200` ticket | `404` |

Errors use the shape `{"error": "<code>", "message": "<text>"}`.

**Reliability-lab simulations** (REST `GET /orders/{id}` only): `ACM-1099` responds after ~8 s, which exceeds a short tool timeout. `ACM-1098` always returns `503`. `ACM-1097` returns `503` twice and then succeeds; the counter resets 60 s after the first failure.

### Seed data

| Order | Customer | Status | Notes |
|---|---|---|---|
| ACM-1001 | maria.lopez@example.com | processing | not yet shipped |
| ACM-1002 | maria.lopez@example.com | shipped | UPS tracking |
| ACM-1003 | james.chen@example.com | out_for_delivery | 2 items |
| ACM-1004 | james.chen@example.com | delivered 2026-09-25 | returnable until 2026-10-25 |
| ACM-1005 | aisha.patel@example.com | delivered 2026-08-02 | return window closed |
| ACM-1006 | aisha.patel@example.com | cancelled | — |

### Running

```bash
# stdio transport (MCP only)
uv run -m mcp_server_kit.acme

# Both REST and MCP, via the combined server
uv run -m mcp_server_kit.combined --port 8000
curl http://localhost:8000/acme/api/health
```

---

## CVS HR Systems of Record (Savvy demo)

Four mock MCP servers that mirror the systems a CVS Health Colleague Service voice agent ("Savvy") touches, sharing one SQLite file (`CVS_HR_DB_PATH`), plus an admin REST API. Business rules live in `cvs_hr_rules.py` (pure, no I/O); schema, seed, sandboxes and audit in `cvs_hr_database.py`; each server is a thin adapter.

| Prefix | Module | Tools |
|---|---|---|
| `/cvs_identity/mcp` | `cvs_identity.py` | `verify_colleague(colleague_id="", mobile="", attempt=1)`, `revoke_verification(verification_id)` |
| `/workday_hcm/mcp` | `workday_hcm.py` | `get_worker(worker_id, verification_id)`, `get_time_off_balance(worker_id, verification_id)`, `project_time_off(worker_id, target_hours, verification_id)`, `evaluate_pay_correction(worker_id, hours, verification_id)` (read-only; never writes payroll) |
| `/time_attendance/mcp` | `time_attendance.py` | `get_timecard(worker_id, period_end="", verification_id)`, `submit_timecard_correction(worker_id, period_end, dates, remove_auto_deduct="meal", audit_note, consent, exclude_dates, verification_id)`, `cancel_timecard_correction(verification_id, correction_id)` |
| `/cvs_hr_router/mcp` | `cvs_hr_router.py` | `interpret_reply(text, expecting="")`: deterministic keyword rules (English and Spanish, in `cvs_hr_router_rules.py`) that return only strings: `intent`, `pending_intent`, `intents` (comma-separated), `consent`, `target_hours` (`""` if none), `recap_language`, `wants_spanish` (yes/no), `language_name`, `wants_human` (yes/no), `leave_topic` (parental/other/""), `expecting`. Needs no verification; writes only an audit row |
| `/servicenow_hrsd/mcp` | `servicenow_hrsd.py` | `create_hr_case(subject_person, hr_service, contact_type, short_description, description, related_records, state, resolved_by, assignment_group, verification_id, leave_discussed="no", language="en")` (returns `sms_body`, the en/es recap built from what happened in the call; an empty `description` is filled from the same facts), `add_work_note(number, note, verification_id)`, `get_hr_cases(subject_person, state, verification_id)` |

**Rules the servers enforce:**

- `verify_colleague` turns spoken digits into numerals (English zero/oh/one–nine and "double/triple X", Spanish cero–nueve), strips the rest (7 digits = colleague ID, 10 = mobile) and issues a `verification_id`. It is stateless across attempts: a failure with `attempt >= 2` returns `escalate=true`.
- Every other tool returns `{"error": "not_verified"}` unless the `verification_id` is active and covers the worker. The one exception is `create_hr_case(hr_service="Identity verification")` with no `subject_person`, whose text is stored with digits masked.
- **Per-call sandbox:** corrections and cases are keyed by `verification_id`, and reads overlay them on the seed, so concurrent calls never see each other's writes.
- `submit_timecard_correction` requires `consent=true`.
- Every call writes one `audit_events` row tagged with its system.
- **Dates** are relative to the as-of date: today by default, or `CVS_HR_AS_OF`.
  - The last closed week ends on the most recent Saturday on or before it.
  - Payday is period end + 13 days, then every 14 days.
  - Every date, amount, hour count and yes/no flag the agent speaks has a string display field (`*_display`, `*_display_en`, `*_display_es`), so templates never format numbers.
- After a reset, case numbers start at `HR-<year>-0917`.
- `sms_to` comes from `CVS_HR_DEMO_SMS_TO` only while the SMS switch is on (default **off**); otherwise `sms_to=""` and `sms_suppressed=true`.

**Admin REST** (`/cvs_hr/api`, all but `/health` need `X-API-Key`): `GET /health`, `POST /reset`, `GET /audit_events?system=&verification_id=&limit=`, `GET /systems?verification_id=` (what changed; latest sandbox if omitted), `GET|POST /settings` `{"sms_enabled": bool}`.

**Seed colleagues:**

| Colleague | ID | Notes |
|---|---|---|
| Daniel Reyes | 7742318 | Mobile 6025550148. Meal breaks wrongly deducted Mon/Wed/Thu: 1.5 h short, priced at $41.63 OT. PTO 62.5 h, accruing 6.15 h. |
| Ana Ortiz | 5530912 | Prefers Spanish; PTO 40 h |
| Marcus Lee | 8104467 | 5.0 h of missed breaks, so the correction is paid off-cycle |
| Kevin Park | 3329018 | Used for the failed-verification path |
| Jordan Hayes | 9017734 | Parental-leave caller |
| Priya Shah | 6610425 | PTO 88.5 h, already above 80 |
| Elena Ruiz | 7742381 | Daniel's ID with two digits transposed (wrong-person recovery) |

---

## Combined Server (`mcp_server_kit/combined.py`) {#combined-server}

Mounts all thirteen MCP servers (plus the Acme and CVS HR REST APIs) into a single process, each at its own URL path. This is the entry point used by the Fly.io deployment — one `fly deploy` starts everything.

### URL paths

| Path | Server |
|------|--------|
| `/greet/mcp` | Greet server |
| `/contacts/mcp` | Contact server |
| `/wikipedia/mcp` | Wikipedia server |
| `/weather/mcp` | Weather server |
| `/messaging/mcp` | Messaging server (Twilio SMS + SendGrid email) |
| `/pto/mcp` | PTO server |
| `/onboarding/mcp` | Onboarding server |
| `/acme/mcp` | Acme Support server |
| `/acme/api/...` | Acme Support REST API (plain HTTP, mounted first via `REST_REGISTRY`) |

### How it works

`combined.py` maintains a central registry of `(url_prefix, ServerClass)` pairs. At startup it instantiates each server, creates a Starlette sub-app via `mcp.http_app()` with that server's `ApiKeyMiddleware`, and mounts it at the corresponding path. A custom lifespan explicitly composes all sub-app lifespans so FastMCP's background workers start and stop correctly (Starlette's `Mount` does not propagate sub-app lifespans automatically).

All servers share the same `api_keys.db` via the `MCP_DB_PATH` environment variable, so one API key authenticates to every path.

### Adding a new server

Open `mcp_server_kit/combined.py` and append one line to `SERVER_REGISTRY`:

```python
SERVER_REGISTRY: list[tuple[str, type]] = [
    ("greet",     GreetMCPServer),
    ("contacts",  ContactMCPServer),
    ("wikipedia", WikipediaMCPServer),
    ("weather",   WeatherMCPServer),
    ("messaging", MessagingMCPServer),
    ("myserver",  MyNewServer),   # ← add this
]
```

Then redeploy with `fly deploy`. No other files need to change.

### Running locally

```bash
OPENWEATHER_API_KEY=<key> \
TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_MESSAGING_SERVICE_SID=<mg_sid> \
SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_server_kit.combined --port 8000
# → starts all five servers; prints one shared API key
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       MCP Client                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ MCPClientApp (CLI Interface)                           │ │
│  │   ├─ Argument parsing (--api-key, --url, --name)       │ │
│  │   └─ Error handling and user feedback                  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ MCPClient                                              │ │
│  │   ├─ StreamableHttpTransport (X-API-Key header)        │ │
│  │   └─ Tool invocation (greet, etc.)                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP/HTTPS
                            │ X-API-Key: <token>
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       MCP Server                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ MCPServer                                              │ │
│  │   ├─ FastMCP instance                                  │ │
│  │   └─ Tool registration                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ApiKeyMiddleware                                       │ │
│  │   ├─ Extract X-API-Key header (case-insensitive)       │ │
│  │   └─ Validate via DatabaseManager                      │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ DatabaseManager                                        │ │
│  │   ├─ SQLite connection management                      │ │
│  │   ├─ Schema initialization                             │ │
│  │   ├─ Key generation (secrets.token_urlsafe)            │ │
│  │   └─ Key validation (parameterized queries)            │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                │
│                            ▼                                │
│              ┌──────────────────────────┐                   │
│              │   api_keys.db (SQLite)   │                   │
│              │  ┌────────────────────┐  │                   │
│              │  │ id | key           │  │                   │
│              │  ├────────────────────┤  │                   │
│              │  │ 1  | abc123...     │  │                   │
│              │  │ 2  | xyz789...     │  │                   │
│              │  └────────────────────┘  │                   │
│              └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
mcp-example/
├── mcp_server_kit/             # Main Python package
│   ├── __init__.py           # Re-exports all public classes
│   ├── base.py                # AuthenticatedMCPServer abstract base class
│   ├── database.py           # DatabaseManager (SQLite API key storage)
│   ├── middleware.py          # ApiKeyMiddleware (request authentication)
│   ├── contact_database.py    # ContactDatabaseManager (mock contacts)
│   ├── contacts.py            # ContactMCPServer + module-level mcp instance
│   ├── server.py              # GreetMCPServer + module-level mcp instance
│   ├── messaging.py           # MessagingMCPServer + module-level mcp instance
│   ├── weather.py             # WeatherMCPServer + module-level mcp instance
│   ├── wikipedia.py           # WikipediaMCPServer + module-level mcp instance
│   ├── combined.py            # Mounts all servers into one Starlette app
│   ├── client.py              # MCPClient (remote tool invocation)
│   └── cli.py                 # MCPClientApp CLI + main() entry point
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_base.py           # AuthenticatedMCPServer tests
│   ├── test_contact_database.py  # ContactDatabaseManager tests
│   ├── test_contacts.py       # ContactMCPServer + integration tests
│   ├── test_database.py       # DatabaseManager tests
│   ├── test_middleware.py     # ApiKeyMiddleware tests
│   ├── test_server.py        # GreetMCPServer + integration tests
│   ├── test_client.py        # MCPClient + edge case tests
│   ├── test_cli.py           # MCPClientApp + integration tests
│   ├── test_weather.py       # WeatherMCPServer tests
│   ├── test_wikipedia.py     # WikipediaMCPServer tests
│   ├── test_messaging.py     # MessagingMCPServer tests
│   └── test_combined.py      # Combined server mounting/lifespan tests
├── api_keys.db               # SQLite database (generated on first run)
├── Dockerfile                # Container image for Fly.io and VPS deployment
├── fly.toml                  # Fly.io deployment configuration
├── Procfile                  # Start command for Render and Railway
├── pyproject.toml            # Project dependencies (uv)
├── uv.lock                   # Dependency lock file
├── pytest.ini                # Pytest configuration
└── README.md                 # Project overview and quick start
```
