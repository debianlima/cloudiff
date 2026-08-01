"""Application shell: institutional header, permission-filtered nav, profile
and footer. docs/portal-v2/prototipo.html is the visual reference.

The shell decides nothing about access — it receives the already-filtered set of
navigable modules and the identity, and renders. Colors and spacing come only
from portal/design (no literals here).
"""
from __future__ import annotations

from html import escape

from portal.core.auth import Identity
from portal.ui.icons import icon

# Módulos já portados para a v2 (viram link na nav). Cresce a cada iteração.
PORTED = {"overview"}

# URL de cada módulo portado (a home usa a raiz; os demais definidos ao portar).
_NAV_HREF = {"overview": "/cloudiff/portal"}

_NAV_LABELS = {
    "overview": ("Início", "Painel"),
    "projects": ("Projetos", "Gestão"),
    "data": ("Bancos e Tenants", "Gestão"),
    "delivery": ("Entrega", "Operação"),
    "environments": ("Produção", "Operação"),
    "health": ("Saúde e reparação", "Operação"),
    "admin": ("Administração", "Governança"),
}

_FOOTER = (
    "IFFluminense — Campus Bom Jesus do Itabapoana · "
    "Av. Dário Viêira Borges, 235 - Lia Márcia, "
    "Bom Jesus do Itabapoana - RJ, 28360-000 · (22) 3833-9850"
)


def _primary_group(identity: Identity) -> str:
    groups = {g.strip() for g in identity.groups}
    for candidate in ("CloudIF-Tenants-Admin", "CloudIF-Professor", "CloudIF-Tenants"):
        if candidate in groups:
            return candidate
    return "Usuário"


_NAV_ORDER = ("overview", "projects", "data", "delivery", "environments", "health", "admin")


def _nav(nav_modules: list[str], active: str) -> str:
    """Nav de topo canônica. Só módulos em PORTED viram link; os demais
    aparecem desabilitados com marca 'em breve' (portar antes de linkar)."""
    from collections import OrderedDict

    groups: "OrderedDict[str, list[str]]" = OrderedDict()
    for module in _NAV_ORDER:
        label, section = _NAV_LABELS.get(module, (module.title(), "Outros"))
        groups.setdefault(section, []).append(module)
    out = []
    for section, modules in groups.items():
        items = []
        for module in modules:
            label = _NAV_LABELS.get(module, (module.title(),))[0]
            if module in PORTED:
                href = _NAV_HREF.get(module, f"/cloudiff/portal?tab={escape(module)}")
                current = ' aria-current="page"' if module == active else ""
                items.append(f'<a class="nav-link" href="{href}"{current}>{escape(label)}</a>')
            else:
                items.append(
                    f'<span class="nav-link nav-link-soon" aria-disabled="true" '
                    f'title="Em migração para a nova interface">{escape(label)}'
                    f'<span class="nav-soon">em breve</span></span>')
        out.append(
            f'<div class="nav-group"><p class="nav-group-label">{escape(section)}</p>'
            + "".join(items) + "</div>"
        )
    return "".join(out)


def render(identity: Identity, nav_modules: list[str], active: str, title: str, body: str) -> str:
    initials = escape((identity.username[:2] or "u").upper())
    group = escape(_primary_group(identity))
    return (
        "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{escape(title)} · CloudIFF</title>"
        "<link rel=\"stylesheet\" href=\"/cloudiff/portal/assets/tokens.css\">"
        "<link rel=\"stylesheet\" href=\"/cloudiff/portal/assets/base.css\">"
        "<link rel=\"stylesheet\" href=\"/cloudiff/portal/assets/components.css\">"
        "</head><body><div class=\"app\">"
        "<nav class=\"nav\" aria-label=\"Navegação principal\">"
        "<div class=\"nav-brand\"><span class=\"nav-mark\">C</span>"
        "<span><span class=\"nav-brand-name\">CloudIFF</span>"
        "<span class=\"nav-brand-sub\">Portal acadêmico</span></span></div>"
        f"<div class=\"nav-scroll\">{_nav(nav_modules, active)}</div>"
        f"<div class=\"nav-foot\">{escape(_FOOTER)}</div>"
        "</nav><div class=\"main\">"
        "<header class=\"bar\"><button class=\"bar-toggle\" aria-label=\"Menu\">≡</button>"
        "<span class=\"scope\"><span class=\"scope-dot\"></span>Ambiente acadêmico</span>"
        f"<span class=\"avatar\" title=\"{escape(identity.username)} · {group}\">"
        f"{icon('user-tie') or initials}</span></header>"
        f"<main class=\"page\"><div class=\"page-head\"><p class=\"eyebrow\">{group}</p>"
        f"<h1 class=\"page-title\">{escape(title)}</h1></div>{body}</main>"
        f"<footer class=\"nav-foot\" style=\"padding:16px 24px\">{escape(_FOOTER)}</footer>"
        "</div></div></body></html>"
    )
