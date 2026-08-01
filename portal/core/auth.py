"""Authentication identity contract; Authentik remains the source of truth."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Identity:
    username: str
    email: str
    groups: frozenset[str]
