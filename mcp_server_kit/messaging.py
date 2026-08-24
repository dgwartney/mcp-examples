"""
FastMCP Server with Twilio SMS and SendGrid email tools.

Exposes two tools:
- send_sms: Send an SMS message via the Twilio REST API.
- send_email: Send a plain-text or HTML email via the SendGrid v3 API.

Required environment variables:
    TWILIO_ACCOUNT_SID          — Twilio account SID (starts with "AC")
    TWILIO_AUTH_TOKEN           — Twilio auth token. Mutually exclusive with
                                  TWILIO_BASIC_AUTH — set exactly one.
    TWILIO_BASIC_AUTH           — Pre-encoded "Authorization: Basic <value>"
                                  credential (the base64 string, without the
                                  "Basic " prefix). Mutually exclusive with
                                  TWILIO_AUTH_TOKEN — set exactly one.
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
        self._twilio_basic_auth = os.environ.get("TWILIO_BASIC_AUTH", "").strip()
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

            url = f"{_TWILIO_BASE}/Accounts/{self._twilio_sid}/Messages.json"
            data = {
                "To": to,
                "MessagingServiceSid": self._twilio_messaging_service_sid,
                "Body": body,
            }
            request_kwargs = {**self._twilio_auth_kwargs(), "data": data}
            try:
                resp = self._http.post(url, **request_kwargs)
                _raise_twilio_error(resp)
            except ToolError:
                raise
            except httpx.RequestError as exc:
                raise ToolError(f"Twilio request error: {exc}") from exc

            d = resp.json()
            return {
                "sid": d.get("sid"),
                "status": d.get("status"),
                "to": d.get("to"),
                "body": d.get("body"),
            }

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
            sender_email = from_email or self._sendgrid_from_email
            if not sender_email:
                raise ToolError(
                    "No sender email provided. Pass from_email or set "
                    "the SENDGRID_FROM_EMAIL environment variable."
                )
            if not to:
                raise ToolError("Recipient email address must not be empty.")
            if not subject:
                raise ToolError("Email subject must not be empty.")
            if not plain_text and not html:
                raise ToolError(
                    "At least one of plain_text or html must be provided."
                )

            sender_name = from_name or self._sendgrid_from_name
            to_entry: dict = {"email": to}
            if to_name:
                to_entry["name"] = to_name

            from_entry: dict = {"email": sender_email}
            if sender_name:
                from_entry["name"] = sender_name

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
        Return the httpx request kwargs (``auth`` or ``headers``) for whichever
        Twilio credential is configured. Call ``_check_twilio_creds`` first to
        guarantee exactly one is set.
        """
        if self._twilio_basic_auth:
            return {"headers": {"Authorization": f"Basic {self._twilio_basic_auth}"}}
        return {"auth": (self._twilio_sid, self._twilio_token)}

    def _check_twilio_creds(self) -> None:
        if self._twilio_token and self._twilio_basic_auth:
            raise ToolError(
                "Set only one of TWILIO_AUTH_TOKEN or TWILIO_BASIC_AUTH, not both."
            )
        missing = [
            name
            for name, val in [
                ("TWILIO_ACCOUNT_SID", self._twilio_sid),
                ("TWILIO_MESSAGING_SERVICE_SID", self._twilio_messaging_service_sid),
            ]
            if not val
        ]
        if not self._twilio_token and not self._twilio_basic_auth:
            missing.append("TWILIO_AUTH_TOKEN or TWILIO_BASIC_AUTH")
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
