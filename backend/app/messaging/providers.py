"""
Provider abstraction — swap in a real WhatsApp Business API / SMS
gateway client here once one is chosen (NEEDS CLIENT CONFIRMATION, see
models.py docstring) without touching app/messaging/service.py or any
caller. Every provider reads its credentials from environment variables
via app.core.config — never hardcode a credential in this file or
anywhere else, per the source doc's non-negotiable security rule.

Selection is config-driven: ``settings.MESSAGE_PROVIDER`` ("console" by
default, "msg91" later). Callers only ever see the ``MessageProvider``
interface, so switching providers changes nothing outside this file.
"""
import abc
import logging

from app.core.config import get_settings
from app.messaging.models import MessageChannel

logger = logging.getLogger("app.messaging")

# Recorded in MessageLog.provider_message_id for demo sends so nothing in the
# UI or an export can be mistaken for a real gateway delivery receipt.
CONSOLE_PROVIDER_TAG = "console-demo"


class MessageProvider(abc.ABC):
    #: Stable identifier recorded on every MessageLog this provider produces.
    name: str = "abstract"

    @abc.abstractmethod
    async def send(
        self, *, to_phone: str | None, body: str, channel: MessageChannel
    ) -> tuple[bool, str | None, str | None]:
        """Returns (success, provider_message_id, failure_reason)."""
        raise NotImplementedError


class ConsoleProvider(MessageProvider):
    """The only provider wired up today — deliberately a safe no-op, not
    a real send. Messages are fully logged/auditable (MessageLog rows are
    created regardless of provider) without risking an accidental real
    WhatsApp/SMS send before a provider contract and consent process are
    actually in place. Swap via settings.MESSAGE_PROVIDER once that's decided."""

    name = "console"

    async def send(
        self, *, to_phone: str | None, body: str, channel: MessageChannel
    ) -> tuple[bool, str | None, str | None]:
        logger.info(
            "messaging.console_provider: DEMO — would send %s to %s: %s",
            channel.value, to_phone or "(internal/staff)", body,
        )
        # success=True so the workflow completes; the id is a demo tag, never a
        # gateway receipt — callers/UI must not present this as "delivered".
        return True, CONSOLE_PROVIDER_TAG, None


class Msg91Provider(MessageProvider):
    """Skeleton for the future MSG91 SMS/WhatsApp integration. NOT wired up.

    When the MSG91 account exists:
      1. set MESSAGE_PROVIDER=msg91 and the MSG91_* env vars (app.core.config),
      2. implement ``send`` below with an httpx call to the MSG91 API using
         those settings — this is the ONLY place that changes,
      3. everything else (templates, trigger/NPO/appointment workflows, the
         MessageLog, the frontend) already goes through this interface.
    """

    name = "msg91"

    def __init__(self) -> None:
        s = get_settings()
        self._auth_key = s.MSG91_AUTH_KEY
        self._sender_id = s.MSG91_SENDER_ID
        self._sms_template_id = s.MSG91_SMS_TEMPLATE_ID
        self._whatsapp_number = s.MSG91_WHATSAPP_NUMBER
        self._base_url = s.MSG91_BASE_URL

    async def send(
        self, *, to_phone: str | None, body: str, channel: MessageChannel
    ) -> tuple[bool, str | None, str | None]:
        raise NotImplementedError(
            "MSG91 integration is not implemented yet. Keep MESSAGE_PROVIDER=console "
            "until the MSG91 credentials are configured and this method is filled in."
        )


def get_provider() -> MessageProvider:
    if get_settings().MESSAGE_PROVIDER == "msg91":
        return Msg91Provider()
    return ConsoleProvider()
