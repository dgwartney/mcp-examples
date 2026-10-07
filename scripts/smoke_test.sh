#!/usr/bin/env bash
#
# Interactive smoke-test walkthrough for mcp-server-kit.
#
# Walks through the same checks as docs/smoke-tests.md, one step at a time:
# each step prints what it's about to do and what result to expect, runs it,
# shows the output, and then asks whether to continue, skip, or quit. No
# step runs without you seeing what it's about to do first.
#
# Two modes:
#   Local (default)  — starts each server itself against localhost, seeding
#                       a scratch API key database. No deployment needed.
#   Remote            — points at an already-deployed instance instead of
#                       starting anything locally. Assumes the combined
#                       server layout (mcp_server_kit.combined), i.e. every
#                       server mounted at its own path under one base URL
#                       (see docs/tutorial.md). Requires an API key for that
#                       deployment since this script has no way to read or
#                       seed its key database remotely.
#
# Usage:
#   ./scripts/smoke_test.sh
#   ./scripts/smoke_test.sh --port 8100        # local mode, different port
#   ./scripts/smoke_test.sh --yes               # auto-confirm every prompt (for CI/dry-run)
#   ./scripts/smoke_test.sh --base-url https://your-app.fly.dev --api-key YOUR_KEY
#                                                # remote mode: test a live deployment
#
# Requires: uv, sqlite3 (local mode only), curl. Local mode uses a scratch
# temp directory for all databases — nothing in this repo checkout is
# touched, and everything is removed on exit.

set -uo pipefail

# ---------------------------------------------------------------------------
# Config & globals
# ---------------------------------------------------------------------------

PORT=8000
AUTO_YES=0
BASE_URL=""
REMOTE=0
API_KEY="${API_KEY:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR=""
SERVER_PID=""
declare -a RESULTS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --base-url) BASE_URL="${2%/}"; REMOTE=1; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    --yes|-y) AUTO_YES=1; shift ;;
    --help|-h)
      sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

if [ -t 1 ]; then
  C_BOLD=$'\033[1m'; C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_YELLOW=$'\033[33m'; C_RESET=$'\033[0m'
else
  C_BOLD=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_RESET=""
fi

section() {
  echo
  echo "${C_BOLD}== $1 ==${C_RESET}"
}

step() {
  echo
  echo "${C_BOLD}[$1] $2${C_RESET}"
  [ -n "${3:-}" ] && echo "Expected: $3"
}

info()  { echo "  $*"; }
ok()    { echo "${C_GREEN}  OK: $*${C_RESET}"; }
warn()  { echo "${C_YELLOW}  WARN: $*${C_RESET}"; }
fail()  { echo "${C_RED}  FAIL: $*${C_RESET}"; }

# tri_confirm PROMPT [DEFAULT]
# Sets CONFIRM_RESULT to "y", "n", or "q". DEFAULT (default: y) is what a
# bare Enter selects. Honors --yes by always answering DEFAULT.
CONFIRM_RESULT=""
tri_confirm() {
  local prompt="$1" default="${2:-y}" reply
  if [ "$AUTO_YES" = "1" ]; then
    CONFIRM_RESULT="$default"
    return 0
  fi
  local hint="Y/n/q"
  [ "$default" = "n" ] && hint="y/N/q"
  while true; do
    read -r -p "$prompt [$hint] " reply
    reply="${reply:-$default}"
    case "$reply" in
      [Yy]*) CONFIRM_RESULT="y"; return 0 ;;
      [Nn]*) CONFIRM_RESULT="n"; return 0 ;;
      [Qq]*) CONFIRM_RESULT="q"; return 0 ;;
      *) echo "Please answer y, n, or q." ;;
    esac
  done
}

quit_now() {
  echo
  warn "Stopped by user."
  print_summary
  cleanup
  exit 1
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "'$1' is required but not on PATH. $2"
    exit 1
  fi
}

require_cmd uv "Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
require_cmd curl "Install it via your OS package manager."
if [ "$REMOTE" != "1" ]; then
  require_cmd sqlite3 "Install it (e.g. 'brew install sqlite3' on macOS)."
fi

# ---------------------------------------------------------------------------
# Scratch workspace & cleanup (local mode only)
# ---------------------------------------------------------------------------

if [ "$REMOTE" != "1" ]; then
  WORKDIR="$(mktemp -d)"
  export MCP_DB_PATH="$WORKDIR/api_keys.db"
  export CONTACTS_DB_PATH="$WORKDIR/contacts.db"
  export PTO_DB_PATH="$WORKDIR/pto.db"
  export ONBOARDING_DB_PATH="$WORKDIR/onboarding.db"
  export ACME_DB_PATH="$WORKDIR/acme.db"
  export CVS_HR_DB_PATH="$WORKDIR/cvs_hr.db"
  LOGFILE="$WORKDIR/server.log"
fi

stop_server() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" 2>/dev/null || true
    SERVER_PID=""
  fi
}

cleanup() {
  stop_server
  [ -n "$WORKDIR" ] && rm -rf "$WORKDIR"
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Server / tool-call helpers
# ---------------------------------------------------------------------------

# wait_for_server URL
wait_for_server() {
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
  return 1
}

# server_url PREFIX
# Local mode: every server runs standalone on localhost:$PORT, unprefixed.
# Remote mode: every server is mounted under its own path on $BASE_URL (the
# combined-server layout — see docs/tutorial.md), so PREFIX picks it out.
server_url() {
  local prefix="$1"
  if [ "$REMOTE" = "1" ]; then
    echo "$BASE_URL/$prefix/mcp"
  else
    echo "http://localhost:$PORT/mcp"
  fi
}

# start_server MODULE [ARGS...]
# Starts `uv run -m MODULE ARGS...` in the background and waits for it to
# accept requests on $PORT. Stops any previously started server first.
# Standalone server modules need "--transport streamable-http --port $PORT";
# mcp_server_kit.combined only accepts "--port" (it's always HTTP) — pass
# whichever ARGS the module actually supports at the call site.
start_server() {
  local module="$1"; shift
  stop_server
  : > "$LOGFILE"
  uv run -m "$module" "$@" >> "$LOGFILE" 2>&1 &
  SERVER_PID=$!
  if ! wait_for_server "http://localhost:$PORT/mcp"; then
    fail "$module did not respond on port $PORT within 20s. Log:"
    sed 's/^/    /' "$LOGFILE"
    return 1
  fi
}

# ensure_server PREFIX MODULE [ARGS...]
# Local mode: starts MODULE (as start_server would). Remote mode: MODULE/ARGS
# are ignored — everything is already running — this just confirms PREFIX's
# path on $BASE_URL is reachable.
ensure_server() {
  local prefix="$1"; shift
  if [ "$REMOTE" = "1" ]; then
    if ! wait_for_server "$(server_url "$prefix")"; then
      fail "$(server_url "$prefix") is not reachable."
      return 1
    fi
    return 0
  fi
  start_server "$@"
}

# call_tool URL TOOL_NAME JSON_ARGS
# Calls a tool via the fastmcp client and prints either "RESULT: <data>" or
# "TOOL_ERROR: <message>" — both are valid outcomes; which one is expected
# depends on the check (see each step's "Expected" line).
call_tool() {
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
        try:
            result = await client.call_tool(os.environ["TOOL"], json.loads(os.environ["ARGS"]))
            # result.data reconstructs list/scalar results into unnamed
            # dataclasses with no visible fields (prints as "Root()").
            # result.content[0].text is always the tool's actual serialized
            # output (raw text for strings, JSON for dicts/lists) — reliable
            # regardless of the tool's return type.
            text = result.content[0].text if result.content else ""
            print("RESULT:", text)
        except Exception as exc:
            print("TOOL_ERROR:", exc)

asyncio.run(main())
PY
}

# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------

# run_check ID DESC EXPECTED CMD...
# Prints the step, runs CMD, shows its output, then asks whether to continue.
# Records ID's outcome in RESULTS. A non-zero exit from CMD is not itself a
# failure — many expected results *are* errors (see EXPECTED).
run_check() {
  local id="$1" desc="$2" expected="$3"; shift 3
  step "$id" "$desc" "$expected"
  info "\$ $*"
  local output status
  output="$("$@" 2>&1)"
  status=$?
  echo "$output" | sed 's/^/  /'
  tri_confirm "Did that match what you expected? Continue to the next step?"
  case "$CONFIRM_RESULT" in
    y) RESULTS+=("$id: PASS - $desc") ;;
    n) RESULTS+=("$id: FLAGGED - $desc"); warn "Marked for follow-up (exit status was $status)." ;;
    q) RESULTS+=("$id: FLAGGED (stopped here) - $desc"); quit_now ;;
  esac
}

# skip_check ID DESC REASON
skip_check() {
  local id="$1" desc="$2" reason="$3"
  step "$id" "$desc"
  warn "Skipped: $reason"
  RESULTS+=("$id: SKIPPED - $desc ($reason)")
}

# gate PROMPT — ask before entering an optional/risky section.
# Returns 0 (proceed) or 1 (skip). Quits the whole script on 'q'.
gate() {
  tri_confirm "$1" "${2:-y}"
  case "$CONFIRM_RESULT" in
    y) return 0 ;;
    n) return 1 ;;
    q) quit_now ;;
  esac
}

# have_or_set_env VAR PROMPT [secret]
# If VAR is already set (non-empty), returns 0 immediately. Otherwise asks
# whether to enter it now; returns 1 if the user declines or leaves it blank.
have_or_set_env() {
  local var="$1" prompt="$2" secret="${3:-}" val
  if [ -n "${!var:-}" ]; then
    return 0
  fi
  gate "$var is not set. Enter it now for this session?" n || return 1
  if [ "$secret" = "secret" ]; then
    read -r -s -p "  $prompt: " val; echo
  else
    read -r -p "  $prompt: " val
  fi
  if [ -z "$val" ]; then
    warn "Empty value — skipping."
    return 1
  fi
  export "$var"="$val"
  return 0
}

print_summary() {
  section "Summary"
  if [ "${#RESULTS[@]}" -eq 0 ]; then
    info "No checks were run."
    return
  fi
  local r
  for r in "${RESULTS[@]}"; do
    case "$r" in
      *": PASS"*) echo "${C_GREEN}  ✓ $r${C_RESET}" ;;
      *": SKIPPED"*) echo "${C_YELLOW}  - $r${C_RESET}" ;;
      *) echo "${C_RED}  ✗ $r${C_RESET}" ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# 0. Setup
# ---------------------------------------------------------------------------

section "0. Setup"
gate "Run 'uv sync --extra test' now?" && (cd "$REPO_ROOT" && uv sync --extra test)

if [ "$REMOTE" = "1" ]; then
  info "Remote mode: testing $BASE_URL (assumed to be mcp_server_kit.combined)."
  if [ -z "$API_KEY" ]; then
    read -r -s -p "  API key for $BASE_URL: " API_KEY; echo
  fi
  if [ -z "$API_KEY" ]; then
    fail "No API key provided. Pass --api-key, set API_KEY, or enter it when prompted."
    exit 1
  fi
  ok "Using the provided API key against $BASE_URL."
else
  info "Scratch workspace: $WORKDIR (removed automatically on exit)"
  API_KEY="smoke-test-$(uv run --project "$REPO_ROOT" python -c 'import secrets; print(secrets.token_urlsafe(16))')"
  sqlite3 "$MCP_DB_PATH" \
    "CREATE TABLE IF NOT EXISTS api_keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL);
     INSERT INTO api_keys (key) VALUES ('$API_KEY');"
  ok "Inserted a known API key into the scratch key database."
  info "Every server started below shares this same key database, so this one key works everywhere."
fi

cd "$REPO_ROOT" || exit 1

# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

section "1. Auth guard"
if ensure_server greet mcp_server_kit.server --transport streamable-http --port "$PORT"; then
  GREET_URL="$(server_url greet)"
  run_check "1" "Request with no API key" "401 Unauthorized" \
    curl -s -o /dev/null -w "%{http_code}" -X POST "$GREET_URL" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
else
  skip_check "1" "Auth guard" "greet server not reachable"
fi

# ---------------------------------------------------------------------------
# 2. Greet server
# ---------------------------------------------------------------------------

section "2. Greet server"
if ensure_server greet mcp_server_kit.server --transport streamable-http --port "$PORT"; then
  GREET_URL="$(server_url greet)"
  run_check "2" "greet tool" 'RESULT: Hello, Ada!' \
    call_tool "$GREET_URL" greet '{"name": "Ada"}'
else
  skip_check "2" "Greet server" "server not reachable"
fi

# ---------------------------------------------------------------------------
# 3. Contact server
# ---------------------------------------------------------------------------

section "3. Contact server"
if ensure_server contacts mcp_server_kit.contacts --transport streamable-http --port "$PORT"; then
  CONTACTS_URL="$(server_url contacts)"
  run_check "3.1" "search_by_last_name (Webb)" "Two contacts (Marcus Webb, Eleanor Webster); no Password field" \
    call_tool "$CONTACTS_URL" search_by_last_name '{"last_name": "Webb"}'

  run_check "3.2" "search_by_last_name (empty string)" "TOOL_ERROR: last_name must not be empty" \
    call_tool "$CONTACTS_URL" search_by_last_name '{"last_name": ""}'

  run_check "3.3" "authenticate (correct password)" "James Whitfield's profile, no Password field" \
    call_tool "$CONTACTS_URL" authenticate '{"email": "james.whitfield@meridiancorp.com", "password": "password123"}'

  run_check "3.4" "authenticate (wrong password)" "TOOL_ERROR: Authentication failed" \
    call_tool "$CONTACTS_URL" authenticate '{"email": "james.whitfield@meridiancorp.com", "password": "wrong"}'
else
  skip_check "3" "Contact server" "server not reachable"
fi

# ---------------------------------------------------------------------------
# 4. Weather server
# ---------------------------------------------------------------------------

section "4. Weather server"
# In remote mode OPENWEATHER_API_KEY configures the deployed server, not this
# script, so there's nothing to check locally — just try reaching it.
if [ "$REMOTE" = "1" ] || have_or_set_env OPENWEATHER_API_KEY "OpenWeatherMap API key" secret; then
  if ensure_server weather mcp_server_kit.weather --transport streamable-http --port "$PORT"; then
    WEATHER_URL="$(server_url weather)"
    run_check "4.1" "get_current_weather (London)" "temperature, humidity, description, etc." \
      call_tool "$WEATHER_URL" get_current_weather '{"location": "London"}'

    run_check "4.2" "get_forecast (Tokyo,JP, 3 days)" "3 daily summaries" \
      call_tool "$WEATHER_URL" get_forecast '{"location": "Tokyo,JP", "days": 3}'

    run_check "4.3" "get_air_quality (Beijing)" "aqi 1-5 with a matching aqi_label" \
      call_tool "$WEATHER_URL" get_air_quality '{"location": "Beijing"}'

    run_check "4.4" "get_current_weather (bogus location)" "TOOL_ERROR: Location not found" \
      call_tool "$WEATHER_URL" get_current_weather '{"location": "Nowhereville,ZZ"}'
  else
    skip_check "4" "Weather server" "server not reachable"
  fi
else
  skip_check "4" "Weather server" "no OPENWEATHER_API_KEY"
fi

# ---------------------------------------------------------------------------
# 5. Wikipedia server
# ---------------------------------------------------------------------------

section "5. Wikipedia server"
if ensure_server wikipedia mcp_server_kit.wikipedia --transport streamable-http --port "$PORT"; then
  WIKIPEDIA_URL="$(server_url wikipedia)"
  run_check "5.1" "search_pages" "Results with title/excerpt, no HTML tags" \
    call_tool "$WIKIPEDIA_URL" search_pages '{"query": "Python programming language"}'

  run_check "5.2" "get_page_summary" "A plain-text extract and a url" \
    call_tool "$WIKIPEDIA_URL" get_page_summary '{"title": "Python (programming language)"}'

  run_check "5.3" "get_related_pages" "A non-empty list of related titles" \
    call_tool "$WIKIPEDIA_URL" get_related_pages '{"title": "Python (programming language)"}'
else
  skip_check "5" "Wikipedia server" "server not reachable"
fi

# ---------------------------------------------------------------------------
# 6. Messaging server (real SMS + email!)
# ---------------------------------------------------------------------------

# have_messaging_creds — in remote mode the Twilio/SendGrid credentials
# configure the deployed server, not this script, so there's nothing to
# collect locally; in local mode, gather them so the local server can start.
have_messaging_creds() {
  [ "$REMOTE" = "1" ] && return 0
  have_or_set_env TWILIO_ACCOUNT_SID "Twilio Account SID" \
    && have_or_set_env TWILIO_AUTH_TOKEN "Twilio Auth Token" secret \
    && have_or_set_env TWILIO_MESSAGING_SERVICE_SID "Twilio Messaging Service SID" \
    && have_or_set_env SENDGRID_API_KEY "SendGrid API key" secret \
    && have_or_set_env SENDGRID_FROM_EMAIL "SendGrid verified sender email"
}

section "6. Messaging server"
warn "This section can send a REAL SMS and a REAL email and may incur cost."
if gate "Configure and test the messaging server?" n && have_messaging_creds
then
  if ensure_server messaging mcp_server_kit.messaging --transport streamable-http --port "$PORT"; then
    MESSAGING_URL="$(server_url messaging)"
    read -r -p "  Phone number to send a real test SMS to (E.164, e.g. +15551234567; blank to skip real sends): " SMOKE_PHONE
    read -r -p "  Email address to send a real test email to (blank to skip): " SMOKE_EMAIL

    if [ -n "$SMOKE_PHONE" ]; then
      gate "Send a real SMS to $SMOKE_PHONE now?" n && run_check "6.1" "send_sms" "sid + status: queued; SMS arrives" \
        call_tool "$MESSAGING_URL" send_sms "{\"to\": \"$SMOKE_PHONE\", \"body\": \"mcp-server-kit smoke test\"}"
    else
      skip_check "6.1" "send_sms" "no phone number provided"
    fi

    if [ -n "$SMOKE_EMAIL" ]; then
      gate "Send a real email to $SMOKE_EMAIL now?" n && run_check "6.2" "send_email" "message_id; email arrives with Reply-To set" \
        call_tool "$MESSAGING_URL" send_email "{\"to\": \"$SMOKE_EMAIL\", \"subject\": \"mcp-server-kit smoke test\", \"plain_text\": \"hello\", \"reply_to\": \"$SMOKE_EMAIL\", \"reply_to_name\": \"Smoke Test\"}"
    else
      skip_check "6.2" "send_email" "no email address provided"
    fi

    if [ -n "$SMOKE_EMAIL" ] && [ -n "${SENDGRID_TEST_TEMPLATE_ID:-}" ]; then
      gate "Send a real templated email to $SMOKE_EMAIL using $SENDGRID_TEST_TEMPLATE_ID now?" n && run_check "6.5" "send_email_template" "message_id; templated email arrives rendered" \
        call_tool "$MESSAGING_URL" send_email_template "{\"to\": \"$SMOKE_EMAIL\", \"template_id\": \"$SENDGRID_TEST_TEMPLATE_ID\", \"dynamic_template_data\": {\"first_name\": \"Ada\"}}"
    else
      skip_check "6.5" "send_email_template" "no SENDGRID_TEST_TEMPLATE_ID set (or no email address provided)"
    fi

    run_check "6.3" "send_sms (invalid E.164 number)" "TOOL_ERROR: E.164 format required, no SMS sent" \
      call_tool "$MESSAGING_URL" send_sms '{"to": "5551234567", "body": "x"}'

    run_check "6.6" "send_sms_template (validation only)" "TOOL_ERROR unless a real approved content_sid is supplied" \
      call_tool "$MESSAGING_URL" send_sms_template '{"to": "+15551234567", "content_sid": "HXabc", "content_variables": {"1": "ok"}}'
  else
    skip_check "6" "Messaging server" "server not reachable"
  fi
else
  skip_check "6" "Messaging server" "declined or missing credentials"
fi

# ---------------------------------------------------------------------------
# 7. PTO server
# ---------------------------------------------------------------------------

section "7. PTO server"
if ensure_server pto mcp_server_kit.pto --transport streamable-http --port "$PORT"; then
  PTO_URL="$(server_url pto)"
  run_check "7.1" "get_balance (E1001)" "A balance in days" \
    call_tool "$PTO_URL" get_balance '{"employee_id": "E1001"}'

  run_check "7.2" "request_pto (2 days)" "Approved; balance drops by 2" \
    call_tool "$PTO_URL" request_pto '{"employee_id": "E1001", "start_date": "2026-09-01", "end_date": "2026-09-03", "days": 2}'

  run_check "7.3" "request_pto (999 days)" "denied_insufficient_balance; balance unchanged" \
    call_tool "$PTO_URL" request_pto '{"employee_id": "E1001", "start_date": "2026-09-01", "end_date": "2026-09-30", "days": 999}'

  run_check "7.4" "list_requests" "Both requests above, most recent first" \
    call_tool "$PTO_URL" list_requests '{"employee_id": "E1001"}'
else
  skip_check "7" "PTO server" "server not reachable"
fi

# ---------------------------------------------------------------------------
# 8. Onboarding server
# ---------------------------------------------------------------------------

section "8. Onboarding server"
if ensure_server onboarding mcp_server_kit.onboarding --transport streamable-http --port "$PORT"; then
  ONBOARDING_URL="$(server_url onboarding)"
  run_check "8.1" "create_case" "New case with a CaseId, status submitted" \
    call_tool "$ONBOARDING_URL" create_case '{"employee_name": "Ada Lovelace", "employee_email": "ada@example.com", "location": "London", "manager_name": "Grace Hopper", "start_date": "2026-09-01"}'

  run_check "8.2" "get_case (case_id: 1)" "The case from 8.1" \
    call_tool "$ONBOARDING_URL" get_case '{"case_id": 1}'

  run_check "8.3" "update_case_status (completed)" "Status updated to completed" \
    call_tool "$ONBOARDING_URL" update_case_status '{"case_id": 1, "status": "completed"}'

  run_check "8.4" "update_case_status (bogus)" "TOOL_ERROR: invalid status" \
    call_tool "$ONBOARDING_URL" update_case_status '{"case_id": 1, "status": "bogus"}'

  run_check "8.5" "list_cases" "Includes the case from 8.1" \
    call_tool "$ONBOARDING_URL" list_cases '{}'
else
  skip_check "8" "Onboarding server" "server not reachable"
fi

# ---------------------------------------------------------------------------
# 9. Combined server
# ---------------------------------------------------------------------------

# combined_url PREFIX
# Local mode: the combined server mounts every prefix on the same $PORT.
# Remote mode: identical to server_url — every prefix on $BASE_URL.
combined_url() {
  local prefix="$1"
  if [ "$REMOTE" = "1" ]; then
    echo "$BASE_URL/$prefix/mcp"
  else
    echo "http://localhost:$PORT/$prefix/mcp"
  fi
}

section "9. Combined server"
if ensure_server greet mcp_server_kit.combined --port "$PORT"; then
  step "9.1" "Every prefix is mounted and auth-guarded" "All twelve return 401, unknown path returns 404"
  for prefix in greet contacts wikipedia weather messaging pto onboarding acme \
      cvs_identity workday_hcm time_attendance servicenow_hrsd; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$(combined_url "$prefix")" \
      -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
    info "$prefix/mcp (no key) -> $code (expect 401)"
  done
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$(combined_url unknown)" \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
  info "unknown/mcp (no key) -> $code (expect 404)"
  tri_confirm "Did all of those match? Continue to the next step?"
  case "$CONFIRM_RESULT" in
    y) RESULTS+=("9.1: PASS - combined server mounting") ;;
    n) RESULTS+=("9.1: FLAGGED - combined server mounting") ;;
    q) RESULTS+=("9.1: FLAGGED (stopped here) - combined server mounting"); quit_now ;;
  esac

  run_check "9.2" "greet tool via /greet/mcp" 'RESULT: Hello, Ada!' \
    call_tool "$(combined_url greet)" greet '{"name": "Ada"}'
else
  skip_check "9" "Combined server" "server not reachable"
fi

# ---------------------------------------------------------------------------
# 10. CVS HR systems of record (Savvy demo) — via the combined server
# ---------------------------------------------------------------------------

# rest_base — base URL of the combined server (local or remote).
rest_base() {
  if [ "$REMOTE" = "1" ]; then echo "$BASE_URL"; else echo "http://localhost:$PORT"; fi
}

# cvs_golden_chain — verify Daniel, then read his worker and timecard records
# with the verification_id, printing the fields the agent speaks. Read-only
# apart from one verification row and audit rows; sends no SMS.
cvs_golden_chain() {
  API_KEY="$API_KEY" BASE="$(rest_base)" uv run python - <<'PY'
import asyncio, json, os
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def call(prefix, tool, args):
    t = StreamableHttpTransport(f"{os.environ['BASE']}/{prefix}/mcp",
                                headers={"X-API-Key": os.environ["API_KEY"]})
    async with Client(t) as c:
        r = await c.call_tool(tool, args)
        return json.loads(r.content[0].text)

async def main():
    v = await call("cvs_identity", "verify_colleague", {"colleague_id": "7742318"})
    vid = v["verification_id"]
    w = await call("workday_hcm", "get_worker", {"worker_id": "7742318", "verification_id": vid})
    tc = await call("time_attendance", "get_timecard", {"worker_id": "7742318", "verification_id": vid})
    print("verified:", v["verified"], "| sms_suppressed:", v.get("sms_suppressed"))
    print("worker:", w["display_name"], "|", w["job_title"], "| store", w["location"]["store"])
    print("timecard:", tc["period_end"], "| hours_short", tc["hours_short"], "| amount_usd", tc["amount_usd"])
    locked = await call("time_attendance", "get_timecard", {"worker_id": "7742318"})
    print("without verification_id:", locked.get("error"))

asyncio.run(main())
PY
}

section "10. CVS HR systems (Savvy)"
if ensure_server greet mcp_server_kit.combined --port "$PORT"; then
  run_check "10.1" "CVS HR admin health (no key)" '200 with "service":"cvs_hr" and the as_of date' \
    curl -s -w " -> %{http_code}" "$(rest_base)/cvs_hr/api/health"

  run_check "10.2" "CVS HR admin settings without a key" "401" \
    curl -s -o /dev/null -w "%{http_code}" "$(rest_base)/cvs_hr/api/settings"

  run_check "10.3" "verify -> get_worker -> get_timecard" \
    "verified True; Daniel R. | Pharmacy Technician | store 6218; hours_short 1.5 | amount_usd 41.63; without verification_id: not_verified" \
    cvs_golden_chain
else
  skip_check "10" "CVS HR systems" "combined server not reachable"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

stop_server
print_summary
