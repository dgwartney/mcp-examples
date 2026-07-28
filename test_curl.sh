#!/usr/bin/env bash
#
# Test the MCP contact server using curl.
# Requires the server to be running:
#   uv run -m mcp_server_kit.contacts --transport streamable-http --port 8000
#
# Usage:
#   API_KEY=<your-api-key> ./test_curl.sh

set -euo pipefail

BASE_URL="http://localhost:8000/mcp"

if [ -z "${API_KEY:-}" ]; then
  echo "Error: API_KEY environment variable is not set." >&2
  echo "Usage: API_KEY=<your-api-key> $0" >&2
  exit 1
fi

echo "=== Step 1: Initialize session ==="
curl -s -D /tmp/mcp_headers -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "curl-client", "version": "1.0"}
    }
  }' | sed -n 's/^data: //p' | jq .
echo ""

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers | awk '{print $2}' | tr -d '\r')
echo "Session ID: $SESSION_ID"
echo ""

echo "=== Step 2: Send initialized notification ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: $API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc": "2.0", "method": "notifications/initialized"}' | sed -n 's/^data: //p' | jq .
echo ""

echo "=== Step 3a: Search by email ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: $API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_by_email",
      "arguments": {
        "email": "bugs.bunny@acme.com"
      }
    }
  }' | sed -n 's/^data: //p' | jq .
echo ""

echo "=== Step 3b: Search by last name ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: $API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "search_by_last_name",
      "arguments": {
        "last_name": "Bunny"
      }
    }
  }' | sed -n 's/^data: //p' | jq .
echo ""

echo "=== Step 3c: Search by account ID ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: $API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search_by_account_id",
      "arguments": {
        "account_id": "0011A00001xAC001"
      }
    }
  }' | sed -n 's/^data: //p' | jq .
echo ""

echo "=== Step 3d: Authenticate a contact ==="
curl -s -X POST "$BASE_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: $API_KEY" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "authenticate",
      "arguments": {
        "email": "bugs.bunny@acme.com",
        "password": "bugs2022!"
      }
    }
  }' | sed -n 's/^data: //p' | jq .
echo ""

echo "=== All tests complete ==="
