"""Mail service: provider-agnostic inbox reads and digest sends."""

import asyncio
from datetime import datetime
from typing import Any, Protocol

from hipeac_agents import settings
from hipeac_agents.services.types import MailMessage


class MailClient(Protocol):
    """What nodes may do against email: list inbox messages, send mail."""

    async def list_messages(
        self,
        inbox_id: str,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[MailMessage]:
        """List messages in an inbox, newest first."""
        ...

    async def send(
        self,
        inbox_id: str,
        to: str | list[str],
        subject: str,
        text: str,
        html: str | None = None,
        reply_to: str | list[str] | None = None,
    ) -> str:
        """Send an email from an inbox.

        :returns: The sent message id.
        """
        ...


HTML_TEMPLATE = (
    '<!doctype html><html><body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
    'font-size:15px;line-height:1.55;color:#1a1a1a;max-width:720px;margin:0 auto;padding:16px">'
    "{body}</body></html>"
)


def markdown_to_html(text: str) -> str:
    """Render a markdown body as a standalone HTML email document.

    Mail clients render the ``html`` part when present; the markdown is still
    sent as the ``text`` part, so clients that block HTML stay readable.

    :param text: The markdown body.
    :returns: A complete HTML document.
    """
    import mistune

    return HTML_TEMPLATE.format(body=mistune.html(text))


def _email_str(value: Any) -> str:
    if value is None:
        return ""
    return getattr(value, "email", None) or str(value)


class AgentMailMail:
    """Mail provider backed by the official AgentMail SDK."""

    def __init__(self, agentmail_client: Any) -> None:
        """Wrap an already-constructed AgentMail client.

        :param agentmail_client: An ``agentmail.AgentMail`` instance.
        """
        self._client = agentmail_client

    async def list_messages(
        self,
        inbox_id: str,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[MailMessage]:
        """List messages in an inbox, newest first.

        :param inbox_id: The inbox to read.
        :param after: Only messages after this instant.
        :param before: Only messages before this instant.
        :returns: The messages; empty when the inbox read fails.
        """
        try:
            response = await asyncio.to_thread(
                self._client.inboxes.messages.list,
                inbox_id,
                after=after,
                before=before,
            )
        except Exception:
            return []

        messages = getattr(response, "messages", None) or []

        return [
            MailMessage(
                inbox_id=getattr(item, "inbox_id", "") or inbox_id,
                message_id=getattr(item, "message_id", "") or "",
                from_=_email_str(getattr(item, "from_", None)),
                to=[_email_str(recipient) for recipient in (getattr(item, "to", None) or [])],
                subject=getattr(item, "subject", "") or "",
                preview=getattr(item, "preview", "") or "",
                timestamp=getattr(item, "timestamp", None),
                created_at=getattr(item, "created_at", None),
            )
            for item in messages
        ]

    async def get_message_text(self, inbox_id: str, message_id: str) -> str:
        """Fetch one message's full text body.

        :param inbox_id: The inbox the message is in.
        :param message_id: The message to fetch.
        :returns: The message text; empty when the fetch fails.
        """
        try:
            message = await asyncio.to_thread(self._client.inboxes.messages.get, inbox_id, message_id)
        except Exception:
            return ""

        return getattr(message, "text", "") or ""

    async def send(
        self,
        inbox_id: str,
        to: str | list[str],
        subject: str,
        text: str,
        html: str | None = None,
        reply_to: str | list[str] | None = None,
    ) -> str:
        """Send an email from an inbox.

        :param inbox_id: The sending inbox.
        :param to: Recipient address or addresses.
        :param subject: The email subject.
        :param text: The plain-text email body.
        :param html: The HTML body, sent alongside the text part.
        :param reply_to: Where replies should go, when not the sending inbox.
        :returns: The sent message id.
        """
        response = await asyncio.to_thread(
            self._client.inboxes.messages.send,
            inbox_id,
            to=to,
            subject=subject,
            text=text,
            html=html,
            reply_to=reply_to,
        )

        return getattr(response, "message_id", "")


def load_mail_client() -> MailClient | None:
    """Build the configured mail provider, or ``None`` when unconfigured.

    :returns: A ``MailClient`` if ``AGENTMAIL_API_KEY`` is set, else ``None``.
    """
    if not settings.AGENTMAIL_API_KEY:
        return None

    from agentmail import AgentMail

    return AgentMailMail(AgentMail(api_key=settings.AGENTMAIL_API_KEY))
