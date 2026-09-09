"""Idempotent seed of the demo message templates.

Wording here is PLACEHOLDER / demo text only. It is NOT DLT-approved. Real
SMS/WhatsApp wording must be registered with the DLT/provider before
MESSAGE_PROVIDER is switched away from "console".

Re-runnable: a template is inserted only if its unique ``name`` is not
already present, so calling this repeatedly (startup, seed script, tests)
never duplicates or overwrites.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.messaging.models import MessageCategory, MessageChannel, MessageTemplate

# name -> (channel, category, body). Tokens: {{name}} {{date}} {{time}} {{doctor}} {{clinic}}
_DEMO_TEMPLATES: dict[str, tuple[MessageChannel, MessageCategory, str]] = {
    # Patient-facing (would go to the patient's phone once a real provider is wired).
    "appointment_reminder": (
        MessageChannel.SMS,
        MessageCategory.TRANSACTIONAL,
        "Hi {{name}}, this is a reminder of your appointment with {{doctor}} at "
        "{{clinic}} on {{date}} at {{time}}. [DEMO - not a real message]",
    ),
    "report_ready": (
        MessageChannel.SMS,
        MessageCategory.TRANSACTIONAL,
        "Hi {{name}}, your report is ready at {{clinic}}. Please contact the "
        "front desk to collect it. [DEMO - not a real message]",
    ),
    "welcome": (
        MessageChannel.SMS,
        MessageCategory.TRANSACTIONAL,
        "Welcome to {{clinic}}, {{name}}. Your care team will be in touch with "
        "next steps. [DEMO - not a real message]",
    ),
    # Internal hospital notifications (staff only - never sent to a patient).
    "trigger_due": (
        MessageChannel.SMS,
        MessageCategory.TRANSACTIONAL,
        "Trigger injection is due for {{name}} at {{time}} ({{date}}). "
        "Please acknowledge and administer. [Internal - {{clinic}}]",
    ),
    "npo_started": (
        MessageChannel.SMS,
        MessageCategory.TRANSACTIONAL,
        "NPO starts for {{name}} at {{time}} ({{date}}). Reason: {{reason}}. "
        "[Internal - {{clinic}}]",
    ),
}


async def seed_message_templates(session: AsyncSession) -> int:
    """Insert any missing demo templates. Returns how many were created."""
    existing = set(
        (await session.execute(select(MessageTemplate.name))).scalars().all()
    )
    created = 0
    for name, (channel, category, body) in _DEMO_TEMPLATES.items():
        if name in existing:
            continue
        session.add(
            MessageTemplate(name=name, channel=channel, category=category, body=body, is_active=True)
        )
        created += 1
    if created:
        await session.flush()
    return created
