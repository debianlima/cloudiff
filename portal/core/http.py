"""HTTP request/response contracts shared by migrated Portal v2 modules.

These are transport-agnostic value objects. The legacy adapter and any future
server translate their native request into ``Request`` and translate ``Response``
back. Modules never touch ``BaseHTTPRequestHandler`` directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from portal.core.auth import Identity


@dataclass(frozen=True, slots=True)
class Request:
    path: str
    method: str
    identity: Identity
    query: dict[str, str] = field(default_factory=dict)
    form: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    client_ip: str = ""

    def q(self, key: str, default: str = "") -> str:
        return self.query.get(key, default)

    def f(self, key: str, default: str = "") -> str:
        return self.form.get(key, default)


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: bytes
    content_type: str = "text/html; charset=utf-8"
    headers: tuple[tuple[str, str], ...] = ()

    @classmethod
    def html(cls, markup: str, status: int = 200) -> "Response":
        return cls(status, markup.encode("utf-8"), "text/html; charset=utf-8")

    @classmethod
    def json_body(cls, payload: bytes, status: int = 200) -> "Response":
        return cls(status, payload, "application/json")

    @classmethod
    def redirect(cls, location: str, status: int = 303) -> "Response":
        return cls(status, b"", "text/html; charset=utf-8", (("Location", location),))
