# Servers

This project provides three MCP servers built on a shared authenticated base class.

## Greet Server (`mcp_examples/server.py`)

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

## Contact Server (`mcp_examples/contacts.py`)

A Salesforce-style CRM server backed by a SQLite contacts database, auto-seeded with 20 Warner Bros. cartoon characters.

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

`contacts.db` is auto-seeded with 20 Warner Bros. characters across five accounts:

| Account | Characters |
|---------|-----------|
| ACME Corporation | Bugs Bunny, Daffy Duck, Porky Pig, Elmer Fudd |
| WB Studios | Tweety Bird, Sylvester Cat, Lola Bunny, Tasmanian Devil, Granny Webster, Michigan J. Frog |
| ACME Products | Wile E. Coyote, Road Runner |
| Toontown Inc | Yosemite Sam, Foghorn Leghorn, Pepe Le Pew, Speedy Gonzales, Penelope Pussycat |
| Mars Technologies | Marvin Martian, Gossamer Monster, Witch Hazel |

Each record includes fields: `Id`, `FirstName`, `LastName`, `Email`, `Phone`, `MobilePhone`, `Title`, `Department`, `AccountId`, `AccountName`, `MailingStreet`, `MailingCity`, `MailingState`, `MailingPostalCode`, `MailingCountry`, and more.

## Weather Server (`mcp_examples/weather.py`)

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
| `get_forecast` | `location: str, days: int = 7, units: str = "metric"` | Daily forecast summaries for up to 8 days: min/max temp, description, humidity, wind (days clamped 1–8) |
| `get_air_quality` | `location: str` | Current AQI (1=Good … 5=Very Poor) and pollutant levels: CO, NO₂, O₃, PM2.5, PM10 |

### Running

```bash
# stdio transport (default)
OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather

# HTTP transport
OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather --transport streamable-http --port 8001

# Custom database path
MCP_DB_PATH=/var/data/keys.db OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather
```

---

## Wikipedia Server (`mcp_examples/wikipedia.py`)

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
uv run -m mcp_examples.wikipedia

# HTTP transport
uv run -m mcp_examples.wikipedia --transport streamable-http --port 8001

# Custom database path
MCP_DB_PATH=/var/data/keys.db uv run -m mcp_examples.wikipedia
```

---

## Twilio / SendGrid Server (`mcp_examples/twilio_server.py`)

Sends SMS via the [Twilio REST API](https://www.twilio.com/docs/messaging/api) and email via the [SendGrid v3 Mail Send API](https://docs.sendgrid.com/api-reference/mail-send/mail-send). Supports plain-text and HTML email in a single tool call.

- **TwilioMCPServer** (`twilio_server.py`): Subclass of `AuthenticatedMCPServer` with an `httpx.Client` for outbound Twilio and SendGrid requests
- **API key auth**: Same middleware-based authentication as the other servers

### Required environment variables

| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID (starts with `AC`) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_FROM_NUMBER` | Default sending number in E.164 format (e.g. `+15551234567`) |
| `SENDGRID_API_KEY` | SendGrid API key (starts with `SG.`) |
| `SENDGRID_FROM_EMAIL` | Verified sender email address |
| `SENDGRID_FROM_NAME` | *(optional)* Display name shown in the From field |

### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `send_sms` | `to: str, body: str, from_number: str = None` | Send an SMS via Twilio. `to` must be E.164 format (e.g. `+15551234567`). Returns the Twilio message `sid` and delivery `status`. |
| `send_email` | `to: str, subject: str, plain_text: str, html: str = None, to_name: str = None, from_email: str = None, from_name: str = None` | Send an email via SendGrid. If `html` is provided the message is sent as multipart/alternative so mail clients can choose the best format. Returns SendGrid `message_id`. |

### Running

```bash
# stdio transport (default)
TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_FROM_NUMBER=<number> \
SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_examples.twilio_server

# HTTP transport
TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_FROM_NUMBER=<number> \
SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_examples.twilio_server --transport streamable-http --port 8003

# Custom database path
MCP_DB_PATH=/var/data/keys.db TWILIO_ACCOUNT_SID=<sid> ... uv run -m mcp_examples.twilio_server
```

---

## Combined Server (`mcp_examples/combined.py`) {#combined-server}

Mounts all five servers into a single process, each at its own URL path. This is the entry point used by the Fly.io deployment — one `fly deploy` starts everything.

### URL paths

| Path | Server |
|------|--------|
| `/greet/mcp` | Greet server |
| `/contacts/mcp` | Contact server |
| `/wikipedia/mcp` | Wikipedia server |
| `/weather/mcp` | Weather server |
| `/twilio/mcp` | Twilio SMS + SendGrid email server |

### How it works

`combined.py` maintains a central registry of `(url_prefix, ServerClass)` pairs. At startup it instantiates each server, creates a Starlette sub-app via `mcp.http_app()` with that server's `ApiKeyMiddleware`, and mounts it at the corresponding path. A custom lifespan explicitly composes all sub-app lifespans so FastMCP's background workers start and stop correctly (Starlette's `Mount` does not propagate sub-app lifespans automatically).

All servers share the same `api_keys.db` via the `MCP_DB_PATH` environment variable, so one API key authenticates to every path.

### Adding a new server

Open `mcp_examples/combined.py` and append one line to `SERVER_REGISTRY`:

```python
SERVER_REGISTRY: list[tuple[str, type]] = [
    ("greet",     GreetMCPServer),
    ("contacts",  ContactMCPServer),
    ("wikipedia", WikipediaMCPServer),
    ("weather",   WeatherMCPServer),
    ("twilio",    TwilioMCPServer),
    ("myserver",  MyNewServer),   # ← add this
]
```

Then redeploy with `fly deploy`. No other files need to change.

### Running locally

```bash
OPENWEATHER_API_KEY=<key> \
TWILIO_ACCOUNT_SID=<sid> TWILIO_AUTH_TOKEN=<token> TWILIO_FROM_NUMBER=<number> \
SENDGRID_API_KEY=<key> SENDGRID_FROM_EMAIL=<email> \
  uv run -m mcp_examples.combined --port 8000
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
├── mcp_examples/             # Main Python package
│   ├── __init__.py           # Re-exports all public classes
│   ├── database.py           # DatabaseManager (SQLite API key storage)
│   ├── middleware.py          # ApiKeyMiddleware (request authentication)
│   ├── contact_database.py    # ContactDatabaseManager (mock contacts)
│   ├── contacts.py            # ContactMCPServer + module-level mcp instance
│   ├── server.py              # GreetMCPServer + module-level mcp instance
│   ├── twilio_server.py       # TwilioMCPServer + module-level mcp instance
│   ├── weather.py             # WeatherMCPServer + module-level mcp instance
│   ├── wikipedia.py           # WikipediaMCPServer + module-level mcp instance
│   ├── client.py              # MCPClient (remote tool invocation)
│   └── cli.py                 # MCPClientApp CLI + main() entry point
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_contact_database.py  # ContactDatabaseManager tests
│   ├── test_contacts.py       # ContactMCPServer + integration tests
│   ├── test_database.py       # DatabaseManager tests
│   ├── test_middleware.py     # ApiKeyMiddleware tests
│   ├── test_server.py        # GreetMCPServer + integration tests
│   ├── test_client.py        # MCPClient + edge case tests
│   ├── test_cli.py           # MCPClientApp + integration tests
│   └── test_weather.py       # WeatherMCPServer tests
├── auth.py                   # Standalone middleware example (reference)
├── api_keys.db               # SQLite database (generated on first run)
├── Dockerfile                # Container image for Fly.io and VPS deployment
├── fly.toml                  # Fly.io deployment configuration
├── Procfile                  # Start command for Render and Railway
├── pyproject.toml            # Project dependencies (uv)
├── uv.lock                   # Dependency lock file
├── pytest.ini                # Pytest configuration
└── README.md                 # Project overview and quick start
```
