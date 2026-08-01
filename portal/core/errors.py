"""User-facing empty and error states."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserMessage:
    title: str
    detail: str
    next_action: str | None = None
