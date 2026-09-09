"""Message-template rendering.

One reusable function every messaging path uses (manual sends, appointment
reminders, trigger/NPO notifications) so token substitution behaves
identically everywhere.
"""
from __future__ import annotations

import re
from typing import Any

# Matches {{ token }} with optional inner whitespace; token is a bare identifier.
_TOKEN_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# The tokens the seeded demo templates use. Callers may pass a superset; unknown
# {{tokens}} in a body are left exactly as-is (not blanked), per spec.
SUPPORTED_TOKENS = ("name", "date", "time", "doctor", "clinic")


def render_body(body: str, context: dict[str, Any]) -> str:
    """Replace ``{{token}}`` occurrences in ``body`` with ``context[token]``.

    - A token present in ``context`` is substituted (value stringified;
      ``None`` becomes an empty string).
    - A token absent from ``context`` is left untouched, so an unresolved
      ``{{foo}}`` is visible rather than silently dropped.
    """

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        value = context[key]
        return "" if value is None else str(value)

    return _TOKEN_RE.sub(_sub, body)
