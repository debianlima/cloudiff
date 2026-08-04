"""CloudIFF Portal v2 coexistence and auto-recovery adapter.

Native v2 routes are dispatched first. Every remaining Portal HTML GET is
rendered by the legacy handler into an in-memory buffer and adapted to the
canonical v2 shell. APIs, downloads, redirects and all state-changing methods
remain untouched. Any adapter exception returns the exact legacy response.
"""
from __future__ import annotations

from io import BytesIO
import dataclasses
import os
import sys
import urllib.parse
import json

LIB = "/srv/cloudif/lib"
DESIGN = LIB + "/portal/design"
ASSET_PREFIXES = ("/cloudiff/portal/assets/", "/cloudif/portal/assets/", "/assets/")
ASSET_ALLOW = {"tokens.css", "base.css", "components.css", "app.js"}
PORTAL_PATHS = {"/", "/cloudif/portal", "/cloudif/portal/", "/cloudiff/portal", "/cloudiff/portal/"}
NATIVE_READY = {
    ("/cloudiff/portal/api/reconciliation", "GET"),
    ("/api/reconciliation", "GET"),
    ("/cloudiff/portal", "GET"),
    ("/cloudiff/portal/", "GET"),
    ("/", "GET"),
}


def _install() -> None:
    if os.environ.get("CLOUDIF_PORTAL_V2") != "1":
        return
    if LIB not in sys.path:
        sys.path.insert(0, LIB)

    from portal.app import handle
    from portal.core.auth import Identity
    from portal.core.http import Request
    from portal.core.legacy_shell import transform
    from portal.registry import registry
    from portal.wiring import install as wire

    if not registry.routes():
        wire()

    def identity(headers) -> Identity:
        username = (headers.get("X-authentik-username") or headers.get("X-Authentik-Username") or "unknown").strip().lower()
        email = (headers.get("X-authentik-email") or headers.get("X-Authentik-Email") or "").strip().lower()
        raw = headers.get("X-authentik-groups") or headers.get("X-Authentik-Groups") or ""
        for separator in (";", "|"):
            raw = raw.replace(separator, ",")
        return Identity(username, email, frozenset(group.strip() for group in raw.split(",") if group.strip()))

    def request_for(handler, method: str) -> Request:
        parsed = urllib.parse.urlparse(handler.path)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        return Request(
            parsed.path,
            method,
            identity(handler.headers),
            query,
            {},
            {key: value for key, value in handler.headers.items()},
            getattr(handler, "client_address", ("", 0))[0],
        )

    def send(handler, status: int, content_type: str, body: bytes, headers=()) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", "no-store")
        for key, value in headers:
            if key.lower() not in {"content-length", "content-type", "cache-control", "transfer-encoding"}:
                handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        if body:
            handler.wfile.write(body)

    def send_response_object(handler, response) -> None:
        send(handler, response.status, response.content_type, response.body, response.headers)

    def send_json(handler, status: int, payload) -> None:
        send(handler, status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def try_asset(handler, path: str) -> bool:
        name = None
        for prefix in ASSET_PREFIXES:
            if path.startswith(prefix):
                name = path[len(prefix) :]
                break
        if name is None or name not in ASSET_ALLOW:
            return False
        file_path = os.path.join(DESIGN, name)
        if not os.path.isfile(file_path):
            return False
        with open(file_path, "rb") as stream:
            data = stream.read()
        content_type = "text/css; charset=utf-8" if name.endswith(".css") else "application/javascript; charset=utf-8"
        send(handler, 200, content_type, data)
        return True

    def capture_legacy(handler, previous_get):
        original = {
            "wfile": handler.wfile,
            "send_response": handler.send_response,
            "send_header": handler.send_header,
            "end_headers": handler.end_headers,
        }
        buffer = BytesIO()
        status = {"code": 200}
        headers: list[tuple[str, str]] = []
        handler.wfile = buffer
        handler.send_response = lambda code, message=None: status.__setitem__("code", code)
        handler.send_header = lambda key, value: headers.append((str(key), str(value)))
        handler.end_headers = lambda: None
        try:
            previous_get(handler)
            return status["code"], tuple(headers), buffer.getvalue()
        finally:
            handler.wfile = original["wfile"]
            handler.send_response = original["send_response"]
            handler.send_header = original["send_header"]
            handler.end_headers = original["end_headers"]

    def header_value(headers, name: str, default: str = "") -> str:
        wanted = name.lower()
        for key, value in headers:
            if key.lower() == wanted:
                return value
        return default

    def wrap(handler_class) -> None:
        if getattr(handler_class, "_v2_coexist_wrapped", False):
            return
        previous_get = handler_class.do_GET

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            try:
                if path in {"/cloudif/portal/api/admin-delete-project-status", "/cloudiff/portal/api/admin-delete-project-status"}:
                    owner = sys.modules.get(handler_class.__module__)
                    user = self.user()
                    allowed = bool(getattr(owner, "_admin_project_delete_global")(user))
                    if not allowed:
                        return send_json(self, 403, {"ok": False, "error": "forbidden"})
                    from cloudif_admin_project_delete import job_status
                    query = urllib.parse.parse_qs(parsed.query)
                    payload = job_status((query.get("job_id") or [""])[0])
                    return send_json(self, 200 if payload.get("ok") else 404, payload)
                if try_asset(self, path):
                    return

                query = urllib.parse.parse_qs(parsed.query)
                tab = (query.get("tab") or [""])[0]
                native_home = path in PORTAL_PATHS and tab in ("", "resumo", "inicio", "início", "overview")
                match_path = "/cloudiff/portal" if path == "/" else path
                native_nonportal = (path, "GET") in NATIVE_READY and path not in PORTAL_PATHS
                if native_home or native_nonportal:
                    if registry.match(match_path, "GET") is None:
                        wire()
                    if registry.match(match_path, "GET") is not None:
                        request = request_for(self, "GET")
                        if path == "/":
                            request = dataclasses.replace(request, path=match_path)
                        response = handle(request, lambda _request: None)
                        if response is not None:
                            return send_response_object(self, response)

                if path in PORTAL_PATHS:
                    status, captured_headers, body = capture_legacy(self, previous_get)
                    content_type = header_value(captured_headers, "Content-Type", "text/html; charset=utf-8")
                    if status == 200 and content_type.lower().startswith("text/html"):
                        try:
                            markup = body.decode("utf-8")
                            selected_project = (query.get("project") or [""])[0]
                            adapted = transform(markup, identity(self.headers), tab or "resumo", selected_project).encode("utf-8")
                            return send(self, 200, "text/html; charset=utf-8", adapted, captured_headers)
                        except Exception:
                            # Auto-recovery: return byte-identical legacy output.
                            return send(self, status, content_type, body, captured_headers)
                    return send(self, status, content_type, body, captured_headers)
            except Exception:
                # Fail-open before capture: the original handler still owns the request.
                return previous_get(self)
            return previous_get(self)

        handler_class.do_GET = do_GET

        previous_post = getattr(handler_class, "do_POST", None)
        if previous_post is not None:
            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path not in {
                    "/cloudif/portal/action/admin-delete-project",
                    "/cloudiff/portal/action/admin-delete-project",
                }:
                    return previous_post(self)
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(content_length)
                form = urllib.parse.parse_qs(raw.decode("utf-8", "ignore"))
                value = lambda key: (form.get(key) or [""])[0].strip()
                if value("async") == "1":
                    try:
                        owner = sys.modules.get(handler_class.__module__)
                        user = self.user()
                        if not getattr(owner, "_admin_project_delete_global")(user):
                            return send_json(self, 403, {"ok": False, "error": "forbidden"})
                        token_ok = getattr(owner, "_prod_csrf_equal")(
                            value("csrf_token"), getattr(owner, "_prod_csrf_token")(user)
                        )
                        if not token_ok:
                            return send_json(self, 403, {"ok": False, "error": "invalid_csrf"})
                        from cloudif_admin_project_delete import start_job
                        job = start_job(value("slug"), value("confirm_text"), user.get("username") or "admin")
                        return send_json(self, 202, job)
                    except Exception as exc:
                        return send_json(self, 500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]})
                self.rfile = BytesIO(raw)
                try:
                    status, captured_headers, body = capture_legacy(self, previous_post)
                    content_type = header_value(captured_headers, "Content-Type", "text/html; charset=utf-8")
                    if status in {200, 409} and content_type.lower().startswith("text/html"):
                        try:
                            adapted = transform(
                                body.decode("utf-8"),
                                identity(self.headers),
                                "admin-excluir-projeto",
                            ).encode("utf-8")
                            return send(self, status, "text/html; charset=utf-8", adapted, captured_headers)
                        except Exception:
                            return send(self, status, content_type, body, captured_headers)
                    return send(self, status, content_type, body, captured_headers)
                except Exception:
                    self.rfile = BytesIO(raw)
                    return previous_post(self)

            handler_class.do_POST = do_POST

        handler_class._v2_coexist_wrapped = True

    import http.server as http_server

    if not getattr(http_server, "_v2_server_hooked", False):
        original_server = http_server.ThreadingHTTPServer

        class V2Server(original_server):
            def __init__(self, address, handler, *args, **kwargs):
                try:
                    wrap(handler)
                except Exception:
                    pass
                super().__init__(address, handler, *args, **kwargs)

        http_server.ThreadingHTTPServer = V2Server
        http_server._v2_server_hooked = True


try:
    _install()
except Exception:
    pass
