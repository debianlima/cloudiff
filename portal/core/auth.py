"""Authentication identity contract; Authentik remains the source of truth."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Identity:
    username: str
    email: str
    groups: frozenset[str]
    subject: str = ""
    issuer: str = ""

    @property
    def principal(self) -> str:
        """Stable authorization/audit principal when the IdP exposes one.

        Existing callers remain compatible because username is the fallback.
        The issuer is included when present so subjects from different IdPs
        cannot alias each other during a future multi-issuer migration.
        """
        subject = str(self.subject or "").strip()
        issuer = str(self.issuer or "").strip().rstrip("/")
        if subject:
            return f"{issuer}|{subject}" if issuer else subject
        return str(self.username or "").strip().lower()
