"""
Unit tests for mcp_server_kit.messaging

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import json
import os
import tempfile
from unittest.mock import MagicMock

import httpx
import pytest
from fastmcp.exceptions import ToolError

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.messaging import MessagingMCPServer, _is_valid_email


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
    s = MessagingMCPServer(db_path=db)
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
    s = MessagingMCPServer(db_path=db)
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


class TestIsValidEmail:

    @pytest.mark.parametrize(
        "email",
        [
            "alice@example.com",
            "alice.bob+tag@example.co.uk",
            "a@b.co",
        ],
    )
    def test_accepts_plausible_addresses(self, email):
        assert _is_valid_email(email) is True

    @pytest.mark.parametrize(
        "email",
        [
            "",
            "not-an-email",
            "missing-domain-dot@example",
            "no-at-sign.example.com",
            "spaces in@example.com",
            "@example.com",
            "alice@",
        ],
    )
    def test_rejects_malformed_addresses(self, email):
        assert _is_valid_email(email) is False


class TestMessagingMCPServerInit:

    def test_server_name(self, server):
        assert server.mcp.name == "MessagingMCP"

    def test_four_tools_registered(self, server):
        assert len(server.mcp._tool_manager._tools) == 4

    def test_tool_names(self, server):
        assert set(server.mcp._tool_manager._tools) == {
            "send_sms",
            "send_sms_template",
            "send_email",
            "send_email_template",
        }

    def test_close_closes_http_client(self, server):
        server.close()
        server._http.close.assert_called_once()

    def test_db_manager_created(self, server):
        assert isinstance(server.db_manager, DatabaseManager)

    def test_creds_read_from_env(self, server):
        assert server._twilio_sid == "ACtest"
        assert server._twilio_token == "authtoken"
        assert server._twilio_messaging_service_sid == "MGtest"
        assert server._sendgrid_key == "SG.test"
        assert server._sendgrid_from_email == "from@example.com"

    def test_module_level_server_instance(self):
        import mcp_server_kit.messaging as m
        assert isinstance(m.server, MessagingMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_server_kit.messaging as m
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

    def test_invalid_json_response_raises_tool_error(self, server):
        import json as _json
        resp = _resp({"sid": "SM1"})
        resp.json.side_effect = _json.JSONDecodeError("bad", "doc", 0)
        server._http.post.return_value = resp
        with pytest.raises(ToolError, match="invalid response"):
            _tool_fn(server, "send_sms")(to="+15551234567", body="hi")

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
# send_sms_template
# ---------------------------------------------------------------------------


class TestSendSmsTemplate:

    def test_success_returns_sid_status_to_body(self, server):
        server._http.post.return_value = _resp(
            {
                "sid": "SM123",
                "status": "queued",
                "to": "+15551234567",
                "body": "Hi Alice",
            }
        )
        result = _tool_fn(server, "send_sms_template")(
            to="+15551234567", content_sid="HX123", content_variables={"1": "Alice"}
        )
        assert result == {
            "sid": "SM123",
            "status": "queued",
            "to": "+15551234567",
            "body": "Hi Alice",
        }

    def test_content_variables_json_encoded_in_form_data(self, server):
        server._http.post.return_value = _resp({"sid": "SM1", "status": "queued"})
        _tool_fn(server, "send_sms_template")(
            to="+15551234567",
            content_sid="HX123",
            content_variables={"1": "Alice", "2": "Tue"},
        )
        kwargs = server._http.post.call_args[1]
        assert kwargs["data"]["ContentSid"] == "HX123"
        assert json.loads(kwargs["data"]["ContentVariables"]) == {
            "1": "Alice",
            "2": "Tue",
        }
        assert kwargs["data"]["MessagingServiceSid"] == "MGtest"

    def test_no_content_variables_defaults_to_empty_json_object(self, server):
        server._http.post.return_value = _resp({"sid": "SM1", "status": "queued"})
        _tool_fn(server, "send_sms_template")(to="+15551234567", content_sid="HX123")
        kwargs = server._http.post.call_args[1]
        assert kwargs["data"]["ContentVariables"] == "{}"


    def test_non_e164_number_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="E.164"):
            _tool_fn(server, "send_sms_template")(to="5551234567", content_sid="HX123")

    def test_empty_content_sid_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="must not be empty"):
            _tool_fn(server, "send_sms_template")(to="+15551234567", content_sid="")

    def test_invalid_content_sid_prefix_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="must be a Twilio Content template SID"):
            _tool_fn(server, "send_sms_template")(
                to="+15551234567", content_sid="XYZ123"
            )

    def test_non_dict_content_variables_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="content_variables must be a dict"):
            _tool_fn(server, "send_sms_template")(
                to="+15551234567", content_sid="HX123", content_variables="not-a-dict"
            )

    def test_non_serializable_content_variables_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="JSON-serializable"):
            _tool_fn(server, "send_sms_template")(
                to="+15551234567",
                content_sid="HX123",
                content_variables={"1": object()},
            )

    def test_missing_credentials_raises_tool_error(self, server_no_creds):
        with pytest.raises(ToolError, match="Missing Twilio credentials"):
            _tool_fn(server_no_creds, "send_sms_template")(
                to="+15551234567", content_sid="HX123"
            )

    def test_twilio_error_response_raises_tool_error(self, server):
        server._http.post.return_value = _resp(
            {"message": "Invalid content sid", "code": 63016}, status=400
        )
        with pytest.raises(ToolError, match="Twilio error 63016"):
            _tool_fn(server, "send_sms_template")(
                to="+15551234567", content_sid="HX123"
            )

    def test_request_error_raises_tool_error(self, server):
        server._http.post.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="Twilio request error"):
            _tool_fn(server, "send_sms_template")(
                to="+15551234567", content_sid="HX123"
            )


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

    def test_no_sender_email_not_masked_by_recipient_error(self, server):
        """A missing sender must be reported even if `to` is also invalid."""
        server._sendgrid_from_email = ""
        with pytest.raises(ToolError, match="No sender email"):
            _tool_fn(server, "send_email")(to="", subject="Hi", plain_text="hello")

    def test_empty_recipient_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="Recipient email"):
            _tool_fn(server, "send_email")(to="", subject="Hi", plain_text="hello")

    def test_malformed_recipient_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="not a valid email address"):
            _tool_fn(server, "send_email")(
                to="not-an-email", subject="Hi", plain_text="hello"
            )

    def test_malformed_sender_raises_tool_error(self, server):
        server._sendgrid_from_email = "not-an-email"
        with pytest.raises(ToolError, match="not a valid email address"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="Hi", plain_text="hello"
            )

    def test_empty_subject_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="subject must not be empty"):
            _tool_fn(server, "send_email")(
                to="alice@example.com", subject="", plain_text="hello"
            )

    def test_missing_plain_text_and_html_raises_tool_error(self, server):
        with pytest.raises(
            ToolError, match="At least one of plain_text or html must be provided"
        ):
            _tool_fn(server, "send_email")(to="alice@example.com", subject="Hi")

    def test_success_html_only(self, server):
        server._http.post.return_value = _resp(
            {}, status=202, headers={"X-Message-Id": "msg123"}
        )
        result = _tool_fn(server, "send_email")(
            to="alice@example.com", subject="Hi", html="<p>hello</p>"
        )
        assert result == {"message_id": "msg123", "status_code": 202}

    def test_html_only_payload_has_one_content_entry(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email")(
            to="alice@example.com", subject="Hi", html="<p>hello</p>"
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["content"] == [
            {"type": "text/html", "value": "<p>hello</p>"}
        ]

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


# ---------------------------------------------------------------------------
# send_email_template
# ---------------------------------------------------------------------------


class TestSendEmailTemplate:

    def test_success_returns_message_id_and_status(self, server):
        server._http.post.return_value = _resp(
            {}, status=202, headers={"X-Message-Id": "msg123"}
        )
        result = _tool_fn(server, "send_email_template")(
            to="alice@example.com",
            template_id="d-1aec03a56a6b4940b6eecaf1d0315de3",
            dynamic_template_data={"first_name": "Alice"},
        )
        assert result == {"message_id": "msg123", "status_code": 202}

    def test_payload_has_template_id_and_dynamic_data_no_content(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email_template")(
            to="alice@example.com",
            template_id="d-abc123",
            dynamic_template_data={"first_name": "Alice"},
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["template_id"] == "d-abc123"
        assert payload["personalizations"][0]["dynamic_template_data"] == {
            "first_name": "Alice"
        }
        assert "content" not in payload

    def test_no_dynamic_template_data_defaults_to_empty_dict(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email_template")(
            to="alice@example.com", template_id="d-abc123"
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["personalizations"][0]["dynamic_template_data"] == {}

    def test_subject_override_included_when_provided(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email_template")(
            to="alice@example.com", template_id="d-abc123", subject="Override"
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["subject"] == "Override"

    def test_no_subject_omits_subject_field(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email_template")(
            to="alice@example.com", template_id="d-abc123"
        )
        payload = server._http.post.call_args[1]["json"]
        assert "subject" not in payload

    def test_to_name_included_when_provided(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email_template")(
            to="alice@example.com", template_id="d-abc123", to_name="Alice"
        )
        payload = server._http.post.call_args[1]["json"]
        assert payload["personalizations"][0]["to"][0] == {
            "email": "alice@example.com",
            "name": "Alice",
        }

    def test_from_email_override(self, server):
        server._http.post.return_value = _resp({}, status=202)
        _tool_fn(server, "send_email_template")(
            to="alice@example.com",
            template_id="d-abc123",
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
            _tool_fn(server_no_creds, "send_email_template")(
                to="alice@example.com", template_id="d-abc123"
            )

    def test_no_sender_email_raises_tool_error(self, server):
        server._sendgrid_from_email = ""
        with pytest.raises(ToolError, match="No sender email"):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com", template_id="d-abc123"
            )

    def test_no_sender_email_not_masked_by_recipient_error(self, server):
        """A missing sender must be reported even if `to` is also invalid."""
        server._sendgrid_from_email = ""
        with pytest.raises(ToolError, match="No sender email"):
            _tool_fn(server, "send_email_template")(to="", template_id="d-abc123")

    def test_empty_recipient_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="Recipient email"):
            _tool_fn(server, "send_email_template")(to="", template_id="d-abc123")

    def test_malformed_recipient_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="not a valid email address"):
            _tool_fn(server, "send_email_template")(
                to="not-an-email", template_id="d-abc123"
            )

    def test_malformed_sender_raises_tool_error(self, server):
        server._sendgrid_from_email = "not-an-email"
        with pytest.raises(ToolError, match="not a valid email address"):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com", template_id="d-abc123"
            )

    def test_empty_template_id_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="must not be empty"):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com", template_id=""
            )

    def test_invalid_template_id_prefix_raises_tool_error(self, server):
        with pytest.raises(
            ToolError, match="must be a SendGrid dynamic template ID"
        ):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com", template_id="abc123"
            )

    def test_non_dict_dynamic_template_data_raises_tool_error(self, server):
        with pytest.raises(
            ToolError, match="dynamic_template_data must be a dict"
        ):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com",
                template_id="d-abc123",
                dynamic_template_data="not-a-dict",
            )

    def test_non_serializable_dynamic_template_data_raises_tool_error(self, server):
        with pytest.raises(ToolError, match="JSON-serializable"):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com",
                template_id="d-abc123",
                dynamic_template_data={"first_name": object()},
            )

    def test_sendgrid_error_with_errors_list(self, server):
        server._http.post.return_value = _resp(
            {"errors": [{"message": "bad template"}]}, status=400
        )
        with pytest.raises(ToolError, match="SendGrid error: bad template"):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com", template_id="d-abc123"
            )

    def test_request_error_raises_tool_error(self, server):
        server._http.post.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="SendGrid request error"):
            _tool_fn(server, "send_email_template")(
                to="alice@example.com", template_id="d-abc123"
            )
