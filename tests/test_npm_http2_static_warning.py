from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "components/proxy/srv/cloudif/proxy/npm/data/nginx/custom/http.conf"


def _server_block_for(host: str, required: str) -> str:
    text = CONF.read_text(encoding="utf-8")
    for match in re.finditer(r"server\s*\{", text):
        depth = 0
        for idx in range(match.start(), len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    block = text[match.start(): idx + 1]
                    if f"server_name {host};" in block and required in block:
                        return block
                    break
    raise AssertionError(f"server block not found for {host}")


def test_admin_https_uses_current_http2_directive_without_semantic_drift():
    block = _server_block_for("admin.cloudiff.duckdns.org", "listen 443")
    assert "listen 443 ssl http2;" not in block
    assert "listen [::]:443 ssl http2;" not in block
    assert "listen 443 ssl;" in block
    assert "listen [::]:443 ssl;" in block
    assert "http2 on;" in block
    assert "ssl_certificate /etc/letsencrypt/live/cloudif-admin/fullchain.pem;" in block
    assert "ssl_certificate_key /etc/letsencrypt/live/cloudif-admin/privkey.pem;" in block
    assert "proxy_pass http://10.62.92.7:8099/cloudiff/portal/?tab=admin;" in block
