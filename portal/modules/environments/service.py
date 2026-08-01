"""environments — dados de produção. Sem HTML, sem decisão de acesso."""
from __future__ import annotations

VALID_INCIDENT = ("assign", "escalate", "mitigate", "close")


def incident_status(action: str) -> str:
    return {"assign": "assigned", "escalate": "escalated",
            "mitigate": "mitigated", "close": "closed"}.get(action, "unknown")


def window_is_valid(duration_seconds: int) -> bool:
    """v1 rule: change window must last between 5 and 30 minutes."""
    return 300 <= duration_seconds <= 1800
