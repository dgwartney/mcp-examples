"""
Unit tests for mcp_examples.twilio_server

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import tempfile
from unittest.mock import MagicMock

import httpx
import pytest
from fastmcp.exceptions import ToolError

from mcp_examples.database import DatabaseManager
from mcp_examples.twilio_server import TwilioMCPServer


def _tool_fn(server, name):
    """Extract the raw callable from a registered FastMCP tool."""
    return server.mcp._tool_manager._tools[name].fn


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "authtoken")
    monkeypatch.setenv("TWILIO_MESSAGING_SERVICE_SID", "MGtest")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "from@example.com")
    monkeypatch.delenv("SENDGRID_FROM_NAME", raising=False)
    db = str(tmp_path / "keys.db")
    s = TwilioMCPServer(db_path=db)
    s._http = MagicMock()
    return s


@pytest.fixture
def server_no_creds(tmp_path, monkeypatch):
    for var in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_MESSAGING_SERVICE_SID",
        "SENDGRID_API_KEY",
        "SENDGRID_FROM_EMAIL",
        "SENDGRID_FROM_NAME",
    ):
        monkeypatch.delenv(var, raising=False)
    db = str(tmp_path / "keys.db")
    s = TwilioMCPServer(db_path=db)
    s._http = MagicMock()
    return s


def _resp(data, status=200, headers=None):
    """Build a mock httpx response."""
    r = MagicMock()
    r.status_code = status
    r.is_success = 200 <= status < 300
    r.json.return_value = data
    r.text = str(data)
    r.headers = headers or {}
    return r


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestTwilioMCPServerInit:

    def test_server_name(self, server):
        assert server.mcp.name == "TwilioMCP"

    def test_two_tools_registered(self, server):
        assert len(server.mcp._tool_manager._tools) == 2

    def test_tool_names(self, server):
        assert set(server.mcp._tool_manager._tools) == {"send_sms", "send_email"}

    def test_db_manager_created(self, server):
        assert isinstance(server.db_manager, DatabaseManager)

    def test_creds_read_from_env(self, server):
        assert server._twilio_sid == "ACtest"
        assert server._twilio_token == "authtoken"
        assert server._twilio_messaging_service_sid == "MGtest"
        assert server._sendgrid_key == "SG.test"
        assert server._sendgrid_from_email == "from@example.com"

    def test_module_level_server_instance(self):
        import mcp_examples.twilio_server as m
        assert isinstance(m.server, TwilioMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_examples.twilio_server as m
        assert m.mcp is m.server.mcp


# ---------------------------------------------------------------------------
# send_sms
# ---------------------------------------------------------------------------


class TestSendSms:

    def test_success_returns_sid_and_status(self, server):
        server._http.post.return_value = _resp(
            {"sid": "SM123", "status": "queued", "to": "+15551234567", "body": "hi"}
        )
        result = _tool_fn(server, "send_sms")(to="+15551234567", body="hi")
        assert result == {
            "sid": "SM123",
            "status": "queued",
            "to": "+15551234567",
            "body": "hi",
        }

    def test_uses_messaging_service_sid(self, server):
        server._http.post.return_value = _resp({"sid": "SM1", "status": "queued"})
        _tool_fn(server, "send_sms")(to="+15551234567", body="hi")
        kwargs = server._http.post.call_args[1]
        assert kwargs["data"]["MessagingServiceSid"] == "MGtest"
        assert kwargs["auth"] == ("ACtest", "authtoken")

    def test_non_e164_number_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="E.164"):
            _tool_fn(server, "send_sms")(to="5551234567", body="hi")

    def test_empty_body_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="must not be empty"):
            _tool_fn(server, "send_sms")(to="+15551234567", body="")

    def test_missing_credentials_raises_tool_error(self, server_no_creds):
        with pytest.raises(ToolError, match="Missing Twilio credentials"):
            _tool_fn(server_no_creds, "send_sms")(to="+15551234567", body="hi")

    def test_twilio_error_response_raises_tool_error(self, server):
        server._http.post.return_value = _resp(
            {"message": "Invalid number", "code": 21211}, status=400
        )
        with pytest.raises(ToolError, match="Twilio error 21211"):
            _tool_fn(server, "send_sms")(to="+15551234567", body="hi")

    def test_twilio_error_without_code(self, server):
        server._http.post.return_value = _resp({"message": "boom"}, status=500)
        with pytest.raises(ToolError, match="Twilio error: boom"):
            _tool_fn(server, "send_sms")(to="+15551234567", body="hi")

    def test_twilio_error_unparsable_body(self, server):
        resp = _resp({}, status=503)
        resp.json.side_effect = ValueError("bad json")
        server._http.post.return_value = resp
        with pytest.raises(ToolError, match="HTTP 503"):
            _tool_fn(server, "send_sms")(to="+15551234567", body="hi")

    def test_request_error_raises_tool_error(self, server):
        server._http.post.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="Twilio request error"):
            _tool_fn(server, "send_sms")(to="+15551234567", body="hi")


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


class TestSendEmail:

    def test_success_plain_text_only(self, server):
        server._http.post.return_value = _resp(
            {}, status=202, headers={"X-Message-Id": "msg123"}
        )
        result = _tool_fn(server, "send_email")(
            to="alice@example.com", subject="Hi", plain_text="hello"
        )
        assert result == {"message_id": "msg123", "status_code": 202}

    def test_plain_only_payload_has_one_content_entry(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email")(
            to="alice@example.com", subject="Hi", plain_text="hello"
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["content"] == [{"type": "text/plain", "value": "hello"}]

    def test_html_adds_multipart_alternative(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email")(
            to="alice@example.com",
            subject="Hi",
            plain_text="hello",
            html="<p>hello</p>",
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["content"] == [
            {"type": "text/plain", "value": "hello"},
            {"type": "text/html", "value": "<p>hello</p>"},
        ]

    def test_to_name_included_when_provided(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email")(
            to="alice@example.com",
            subject="Hi",
            plain_text="hello",
            to_name="Alice",
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["personalizations"][0]["to"][0] == {
            "email": "alice@example.com",
            "name": "Alice",
        }

    def test_from_email_override(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email")(
            to="alice@example.com",
            subject="Hi",
            plain_text="hello",
            from_email="override@example.com",
            from_name="Override",
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["from"] == {
            "email": "override@example.com",
            "name": "Override",
        }

    def test_missing_sendgrid_key_raises_tool_error(self, server_no_creds):
        with pytest.raises(ToolError, match="Missing SendGrid credentials"):
            _tool_fn(server_no_creds, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )

    def test_no_sender_email_raises_tool_error(self, server, monkeypatch):
        server._sendgrid_from_email = ""
        with pytest.raises(ToolError, match="No sender email"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )

    def test_empty_recipient_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="Recipient email"):
            _tool_fn(server, "send_email")(to="", subject="Hi", plain_text="hello")

    def test_empty_subject_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="subject must not be empty"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="", plain_text="hello"
            )

    def test_empty_plain_text_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="plain_text body must not be empty"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text=""
            )

    def test_sendgrid_error_with_errors_list(self, server):
        server._http.post.return_value = _resp(
            {"errors": [{"message": "bad email"}]}, status=400
        )
        with pytest.raises(ToolError, match="SendGrid error: bad email"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )

    def test_sendgrid_error_without_errors_list(self, server):
        server._http.post.return_value = _resp({}, status=500)
        with pytest.raises(ToolError, match="HTTP 500"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )

    def test_sendgrid_error_unparsable_body(self, server):
        resp = _resp({}, status=503)
        resp.json.side_effect = ValueError("bad json")
        server._http.post.return_value = resp
        with pytest.raises(ToolError, match="HTTP 503"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )

    def test_request_error_raises_tool_error(self, server):
        server._http.post.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="SendGrid request error"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )
