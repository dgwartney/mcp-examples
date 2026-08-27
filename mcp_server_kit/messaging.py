"""
FastMCP Server with Twilio SMS and SendGrid email tools.

Exposes four tools:
- send_sms: Send an SMS message via the Twilio REST API.
- send_sms_template: Send an SMS from a pre-approved Twilio Content API
  template via the Twilio REST API.
- send_email: Send a plain-text or HTML email via the SendGrid v3 API.
- send_email_template: Send an email from a pre-approved SendGrid dynamic
  template via the SendGrid v3 API.

Required environment variables:
    TWILIO_ACCOUNT_SID          — Twilio account SID (starts with "AC")
    TWILIO_AUTH_TOKEN           — Twilio auth token
    TWILIO_MESSAGING_SERVICE_SID — Twilio Messaging Service SID (starts with "MG")
    SENDGRID_API_KEY            — SendGrid API key (starts with "SG.")
    SENDGRID_FROM_EMAIL         — Verified sender email address
    SENDGRID_FROM_NAME          — (optional) Display name for the sender

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_server_kit.messaging

    Run as HTTP server:
        $ uv run -m mcp_server_kit.messaging --transport streamable-http --port 8002
"""

import json
import os
from typing import Optional

import httpx
from fastmcp.exceptions import ToolError

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances

_TWILIO_BASE = "https://api.twilio.com/2010-04-01"
_SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"


class MessagingMCPServer(AuthenticatedMCPServer):
    """
    MCP server with Twilio SMS and SendGrid email tools.

    Reads credentials from environment variables on construction.
    All tools raise ``ToolError`` on missing credentials or API errors.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self._twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._twilio_messaging_service_sid = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")
        self._sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
        self._sendgrid_from_email = os.environ.get("SENDGRID_FROM_EMAIL", "")
        self._sendgrid_from_name = os.environ.get("SENDGRID_FROM_NAME", "")
        self._http = httpx.Client(timeout=15.0)
        super().__init__(name="MessagingMCP", db_path=db_path)

    def _register_tools(self) -> None:

        @self.mcp.tool(
            description=(
                "Send an SMS message via Twilio. "
                "to: destination phone number in E.164 format (e.g. +15551234567). "
                "body: text content of the message (max 1600 characters). "
                "Returns the Twilio message SID and delivery status on success."
            )
        )
        def send_sms(
            to: str,
            body: str,
        ) -> dict:
            """
            Send an SMS via the Twilio Messages REST API using a Messaging Service.

            Args:
                to: Destination phone number in E.164 format.
                body: SMS body text (max 1600 characters).

            Returns:
                Dict with keys: sid, status, to, body.

            Raises:
                ToolError: If credentials are missing, the number is invalid,
                           or the Twilio API returns an error.
            """
            self._check_twilio_creds()
            if not to.startswith("+"):
                raise ToolError(
                    f"Phone number '{to}' must be in E.164 format (e.g. +15551234567)."
                )
            if not body:
                raise ToolError("SMS body must not be empty.")

            return self._send_twilio_message({"To": to, "Body": body})

        @self.mcp.tool(
            description=(
                "Send an SMS using a pre-approved Twilio Content API template. "
                "to: destination phone number in E.164 format (e.g. +15551234567). "
                "content_sid: Twilio Content template SID (starts with 'HX'). "
                "content_variables: (optional) dict mapping template variable names "
                "(as strings) to their substitution values, e.g. "
                '{"1": "Alice", "2": "Tuesday"}. '
                "Returns the Twilio message SID and delivery status on success."
            )
        )
        def send_sms_template(
            to: str,
            content_sid: str,
            content_variables: Optional[dict] = None,
        ) -> dict:
            """
            Send a templated SMS via the Twilio Messages REST API using the
            Content API (ContentSid / ContentVariables) instead of a raw Body.

            Args:
                to: Destination phone number in E.164 format.
                content_sid: Twilio Content template SID (starts with "HX").
                content_variables: Optional dict of template variable substitutions.

            Returns:
                Dict with keys: sid, status, to, body.

            Raises:
                ToolError: If credentials are missing, to/content_sid are invalid,
                           content_variables is not a dict, or the Twilio API
                           returns an error.
            """
            self._check_twilio_creds()
            if not to.startswith("+"):
                raise ToolError(
                    f"Phone number '{to}' must be in E.164 format (e.g. +15551234567)."
                )
            if not content_sid:
                raise ToolError("Content SID must not be empty.")
            if not content_sid.startswith("HX"):
                raise ToolError(
                    f"Content SID '{content_sid}' must be a Twilio Content template SID "
                    "(starts with 'HX')."
                )
            if content_variables is not None and not isinstance(content_variables, dict):
                raise ToolError(
                    "content_variables must be a dict of variable name/value pairs."
                )
            try:
                encoded_variables = json.dumps(content_variables or {})
            except TypeError as exc:
                raise ToolError(
                    f"content_variables must be JSON-serializable: {exc}"
                ) from exc

            return self._send_twilio_message(
                {
                    "To": to,
                    "ContentSid": content_sid,
                    "ContentVariables": encoded_variables,
                }
            )

        @self.mcp.tool(
            description=(
                "Send an email via SendGrid. Supports plain-text and HTML content; "
                "at least one of plain_text or html must be provided. "
                "to: recipient email address. "
                "subject: email subject line. "
                "plain_text: (optional) plain-text version of the email body. "
                "html: (optional) HTML version of the email body; if both are "
                "provided the message is sent as multipart/alternative so mail "
                "clients can choose. "
                "to_name: (optional) display name for the recipient. "
                "from_email: (optional) override the default SENDGRID_FROM_EMAIL. "
                "from_name: (optional) override the default SENDGRID_FROM_NAME. "
                "Returns the SendGrid message ID on success."
            )
        )
        def send_email(
            to: str,
            subject: str,
            plain_text: Optional[str] = None,
            html: Optional[str] = None,
            to_name: Optional[str] = None,
            from_email: Optional[str] = None,
            from_name: Optional[str] = None,
        ) -> dict:
            """
            Send an email via the SendGrid v3 Mail Send API.

            At least one of ``plain_text`` or ``html`` must be supplied. If both
            are given the message contains a text/plain and a text/html part
            (multipart/alternative); otherwise only the supplied part is sent.

            Args:
                to: Recipient email address.
                subject: Email subject line.
                plain_text: Optional plain-text body.
                html: Optional HTML body.
                to_name: Optional display name for the recipient.
                from_email: Sender address; falls back to SENDGRID_FROM_EMAIL.
                from_name: Sender display name; falls back to SENDGRID_FROM_NAME.

            Returns:
                Dict with keys: message_id, status_code.

            Raises:
                ToolError: If credentials are missing or the SendGrid API returns
                           an error.
            """
            self._check_sendgrid_creds()
            if not to:
                raise ToolError("Recipient email address must not be empty.")
            if not subject:
                raise ToolError("Email subject must not be empty.")
            if not plain_text and not html:
                raise ToolError(
                    "At least one of plain_text or html must be provided."
                )

            from_entry = self._sendgrid_from_entry(from_email, from_name)
            to_entry = self._sendgrid_to_entry(to, to_name)

            content = []
            if plain_text:
                content.append({"type": "text/plain", "value": plain_text})
            if html:
                content.append({"type": "text/html", "value": html})

            payload = {
                "personalizations": [{"to": [to_entry]}],
                "from": from_entry,
                "subject": subject,
                "content": content,
            }

            return self._send_sendgrid_email(payload)

        @self.mcp.tool(
            description=(
                "Send an email using a pre-approved SendGrid dynamic template. "
                "to: recipient email address. "
                "template_id: SendGrid dynamic template ID (starts with 'd-'). "
                "dynamic_template_data: (optional) dict of template variable "
                "substitutions, e.g. {\"first_name\": \"Alice\"}. "
                "to_name: (optional) display name for the recipient. "
                "from_email: (optional) override the default SENDGRID_FROM_EMAIL. "
                "from_name: (optional) override the default SENDGRID_FROM_NAME. "
                "subject: (optional) override the template's default subject. "
                "Returns the SendGrid message ID on success."
            )
        )
        def send_email_template(
            to: str,
            template_id: str,
            dynamic_template_data: Optional[dict] = None,
            to_name: Optional[str] = None,
            from_email: Optional[str] = None,
            from_name: Optional[str] = None,
            subject: Optional[str] = None,
        ) -> dict:
            """
            Send an email via the SendGrid v3 Mail Send API using a dynamic
            template (template_id / dynamic_template_data) instead of inline
            plain_text/html content.

            Args:
                to: Recipient email address.
                template_id: SendGrid dynamic template ID (starts with "d-").
                dynamic_template_data: Optional dict of template variable
                    substitutions.
                to_name: Optional display name for the recipient.
                from_email: Sender address; falls back to SENDGRID_FROM_EMAIL.
                from_name: Sender display name; falls back to SENDGRID_FROM_NAME.
                subject: Optional subject override; templates usually supply
                    their own subject.

            Returns:
                Dict with keys: message_id, status_code.

            Raises:
                ToolError: If credentials are missing, to/template_id are
                           invalid, dynamic_template_data is not a dict, or
                           the SendGrid API returns an error.
            """
            self._check_sendgrid_creds()
            if not to:
                raise ToolError("Recipient email address must not be empty.")
            if not template_id:
                raise ToolError("Template ID must not be empty.")
            if not template_id.startswith("d-"):
                raise ToolError(
                    f"Template ID '{template_id}' must be a SendGrid dynamic "
                    "template ID (starts with 'd-')."
                )
            if dynamic_template_data is not None and not isinstance(
                dynamic_template_data, dict
            ):
                raise ToolError(
                    "dynamic_template_data must be a dict of variable name/value pairs."
                )

            from_entry = self._sendgrid_from_entry(from_email, from_name)
            to_entry = self._sendgrid_to_entry(to, to_name)

            personalization: dict = {
                "to": [to_entry],
                "dynamic_template_data": dynamic_template_data or {},
            }

            payload = {
                "personalizations": [personalization],
                "from": from_entry,
                "template_id": template_id,
            }
            if subject:
                payload["subject"] = subject

            return self._send_sendgrid_email(payload)

    def close(self) -> None:
        """Close the underlying ``httpx.Client``."""
        self._http.close()

    def _send_twilio_message(self, data: dict) -> dict:
        """
        POST a message to the Twilio Messages API and normalize the response.

        Args:
            data: Form fields for the request, excluding MessagingServiceSid
                (added here) and auth (added via ``_twilio_auth_kwargs``).

        Returns:
            Dict with keys: sid, status, to, body.

        Raises:
            ToolError: If the Twilio API returns an error or the request fails.
        """
        url = f"{_TWILIO_BASE}/Accounts/{self._twilio_sid}/Messages.json"
        data = {"MessagingServiceSid": self._twilio_messaging_service_sid, **data}
        request_kwargs = {**self._twilio_auth_kwargs(), "data": data}
        try:
            resp = self._http.post(url, **request_kwargs)
            _raise_twilio_error(resp)
            d = resp.json()
        except ToolError:
            raise
        except httpx.RequestError as exc:
            raise ToolError(f"Twilio request error: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ToolError(f"Twilio returned an invalid response: {exc}") from exc

        return {
            "sid": d.get("sid"),
            "status": d.get("status"),
            "to": d.get("to"),
            "body": d.get("body"),
        }

    def _sendgrid_from_entry(
        self, from_email: Optional[str], from_name: Optional[str]
    ) -> dict:
        """Build the SendGrid ``from`` object, validating a sender is configured."""
        sender_email = from_email or self._sendgrid_from_email
        if not sender_email:
            raise ToolError(
                "No sender email provided. Pass from_email or set "
                "the SENDGRID_FROM_EMAIL environment variable."
            )
        entry: dict = {"email": sender_email}
        sender_name = from_name or self._sendgrid_from_name
        if sender_name:
            entry["name"] = sender_name
        return entry

    @staticmethod
    def _sendgrid_to_entry(to: str, to_name: Optional[str]) -> dict:
        """Build a SendGrid recipient object."""
        entry: dict = {"email": to}
        if to_name:
            entry["name"] = to_name
        return entry

    def _send_sendgrid_email(self, payload: dict) -> dict:
        """
        POST a payload to the SendGrid Mail Send API and normalize the response.

        Returns:
            Dict with keys: message_id, status_code.

        Raises:
            ToolError: If the SendGrid API returns an error or the request fails.
        """
        try:
            json.dumps(payload)
        except TypeError as exc:
            raise ToolError(f"Email payload is not JSON-serializable: {exc}") from exc

        try:
            resp = self._http.post(
                _SENDGRID_SEND_URL,
                headers={
                    "Authorization": f"Bearer {self._sendgrid_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            _raise_sendgrid_error(resp)
        except ToolError:
            raise
        except httpx.RequestError as exc:
            raise ToolError(f"SendGrid request error: {exc}") from exc

        return {
            "message_id": resp.headers.get("X-Message-Id"),
            "status_code": resp.status_code,
        }

    def _twilio_auth_kwargs(self) -> dict:
        """
        Return the httpx ``auth`` kwarg for the configured Twilio credentials.
        Call ``_check_twilio_creds`` first to guarantee they're set.
        """
        return {"auth": (self._twilio_sid, self._twilio_token)}

    def _check_twilio_creds(self) -> None:
        missing = [
            name
            for name, val in [
                ("TWILIO_ACCOUNT_SID", self._twilio_sid),
                ("TWILIO_AUTH_TOKEN", self._twilio_token),
                ("TWILIO_MESSAGING_SERVICE_SID", self._twilio_messaging_service_sid),
            ]
            if not val
        ]
        if missing:
            raise ToolError(
                f"Missing Twilio credentials: {', '.join(missing)}. "
                "Set the corresponding environment variables."
            )

    def _check_sendgrid_creds(self) -> None:
        if not self._sendgrid_key:
            raise ToolError(
                "Missing SendGrid credentials: SENDGRID_API_KEY. "
                "Set the corresponding environment variable."
            )


def _raise_twilio_error(resp: httpx.Response) -> None:
    """Raise ToolError for non-2xx Twilio responses with API error detail."""
    if resp.is_success:
        return
    try:
        body = resp.json()
        msg = body.get("message", resp.text)
        code = body.get("code", "")
        detail = f"Twilio error {code}: {msg}" if code else f"Twilio error: {msg}"
    except Exception:
        detail = f"Twilio request failed: HTTP {resp.status_code}"
    raise ToolError(detail)


def _raise_sendgrid_error(resp: httpx.Response) -> None:
    """Raise ToolError for non-2xx SendGrid responses with API error detail."""
    if resp.is_success:
        return
    try:
        body = resp.json()
        errors = body.get("errors", [])
        if errors:
            msgs = "; ".join(e.get("message", str(e)) for e in errors)
            detail = f"SendGrid error: {msgs}"
        else:
            detail = f"SendGrid request failed: HTTP {resp.status_code}"
    except Exception:
        detail = f"SendGrid request failed: HTTP {resp.status_code}"
    raise ToolError(detail)


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.messaging`` performs no database I/O.
__getattr__ = lazy_module_instances(MessagingMCPServer)

if __name__ == "__main__":
    MessagingMCPServer().main()
