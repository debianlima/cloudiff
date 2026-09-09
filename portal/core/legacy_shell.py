"""Adapt legacy GET pages into the canonical Portal v2 shell.

The adapter changes presentation only. Forms, CSRF fields, links, element IDs and
functional scripts remain intact. Failure is explicit to the caller, which must
return the untouched legacy response (auto-recovery/fail-open).
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
import os
from collections import OrderedDict
from html import escape

from portal.core.auth import Identity
from portal.core.html_fragments import article_spans as _card_spans
from portal.core.publication_summary import clean_general_publication_body, individual_publication_body
from portal.core.resource_ownership import load_resource_ownership
from portal.ui.shell import render_legacy


PORTAL_PATHS = frozenset({"/", "/cloudif/portal", "/cloudif/portal/", "/cloudiff/portal", "/cloudiff/portal/"})
_BLOCKED_SCRIPT_IDS = frozenset({"cloudif-enterprise-navigation-js", "cloudif-ui142-script"})


@dataclass(frozen=True, slots=True)
class LegacyPage:
    title: str
    tab: str
    body: str
    scoped_styles: str
    scripts: str


def _matching_brace(source: str, opening: int) -> int:
    depth = 0
    quote = ""
    escaped = False
    comment = False
    i = opening
    while i < len(source):
        char = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if comment:
            if char == "*" and nxt == "/":
                comment = False
                i += 2
                continue
            i += 1
            continue
        if not quote and char == "/" and nxt == "*":
            comment = True
            i += 2
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            i += 1
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced CSS braces")


def _scope_selector(selector: str) -> str:
    selector = selector.strip()
    if not selector:
        return selector

    # Theme state lives on the real document root. Keep that root selector and
    # insert the compatibility container after it. Replacing ``html`` outright
    # would produce ``.legacy-content[data-theme=dark]`` even though the
    # attribute is never placed on the compatibility container.
    themed_root = re.match(r"^(html(?:\[[^\]]+\])+)(.*)$", selector, re.I | re.S)
    if themed_root:
        root, remainder = themed_root.groups()
        remainder = re.sub(r"^\s*body\b", "", remainder, count=1, flags=re.I)
        return f"{root} .legacy-content{remainder}"

    selector = re.sub(r"^:root\b", ".legacy-content", selector)
    selector = re.sub(r"^(?:html|body)\b", ".legacy-content", selector)
    if selector.startswith(".legacy-content"):
        return selector
    return ".legacy-content " + selector


def scope_css(source: str) -> str:
    """Prefix normal selectors while preserving nested at-rules and keyframes."""
    output: list[str] = []
    cursor = 0
    while cursor < len(source):
        opening = source.find("{", cursor)
        if opening < 0:
            output.append(source[cursor:])
            break
        prelude = source[cursor:opening]
        closing = _matching_brace(source, opening)
        body = source[opening + 1 : closing]
        stripped = prelude.strip()
        lower = stripped.lower()
        if lower.startswith(("@media", "@supports", "@layer", "@container")):
            output.append(prelude + "{" + scope_css(body) + "}")
        elif lower.startswith(("@keyframes", "@-webkit-keyframes", "@font-face", "@page", "@property")):
            output.append(prelude + "{" + body + "}")
        elif lower.startswith("@"):
            output.append(prelude + "{" + body + "}")
        else:
            selectors = ",".join(_scope_selector(item) for item in prelude.split(","))
            output.append(selectors + "{" + body + "}")
        cursor = closing + 1
    return "".join(output)


def _extract_scripts(markup: str) -> str:
    kept: list[str] = []
    for match in re.finditer(r"<script\b([^>]*)>(.*?)</script>", markup, re.I | re.S):
        attrs, body = match.group(1), match.group(2)
        ident = re.search(r"\bid=[\"']([^\"']+)", attrs, re.I)
        if ident and ident.group(1) in _BLOCKED_SCRIPT_IDS:
            continue
        kept.append(match.group(0))
    return "".join(kept)


def parse_legacy(markup: str, tab: str) -> LegacyPage:
    title_match = re.search(r"<title>(.*?)</title>", markup, re.I | re.S)
    main_match = re.search(r"<main\b[^>]*id=[\"']conteudo-principal[\"'][^>]*>(.*?)</main>", markup, re.I | re.S)
    if not main_match:
        raise ValueError("legacy main content not found")
    styles = []
    for match in re.finditer(r"<style\b[^>]*>(.*?)</style>", markup, re.I | re.S):
        styles.append(scope_css(match.group(1)))
    title = unescape(re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "CloudIFF"))
    title = " ".join(title.split())
    return LegacyPage(
        title=title,
        tab=tab or "resumo",
        body=main_match.group(1),
        scoped_styles="<style id=\"legacy-content-styles\">" + "\n".join(styles) + "</style>",
        scripts=_extract_scripts(markup),
    )



_PORTAL_DB = os.environ.get("CLOUDIF_PORTAL_DB", "/var/lib/cloudif/portal/cloudif-portal.db")


def _resource_ownership() -> tuple[dict[str, str], dict[str, str]]:
    return load_resource_ownership(_PORTAL_DB)


def _group_label(owner: str, current_user: str, own_label: str = "") -> str:
    if owner == current_user:
        return own_label or f"{owner} · você"
    return owner or "Sem usuário vinculado"


def _group_cards(body: str, class_token: str, owner_for_card, current_user: str, kind: str, own_label: str = "", resource_scope: str = "") -> str:
    spans = _card_spans(body, class_token)
    if not spans:
        return body
    grouped: "OrderedDict[str, list[str]]" = OrderedDict()
    for _start, _end, card in spans:
        owner = (owner_for_card(card) or "").strip()
        grouped.setdefault(owner, []).append(card)
    blocks: list[str] = []
    ordered = sorted(grouped.items(), key=lambda item: (item[0] != current_user, (item[0] or "~").lower()))
    if resource_scope == "others":
        ordered = [(owner, cards) for owner, cards in ordered if owner != current_user]
    for owner, cards in ordered:
        opened = " open" if (owner != current_user if resource_scope == "others" else owner == current_user) else ""
        label = escape(_group_label(owner, current_user, own_label))
        count = len(cards)
        if kind == "site":
            noun = "site" if count == 1 else "sites"
        elif kind == "publicação":
            noun = "publicação" if count == 1 else "publicações"
        else:
            noun = "banco" if count == 1 else "bancos"
        blocks.append(
            f'<details class="owner-resource-group"{opened}>'
            f'<summary><span>{label}</span><span class="owner-resource-count">{count} {noun}</span></summary>'
            f'<div class="owner-resource-items">{"".join(cards)}</div></details>'
        )
    group_id = ' id="other-user-sites"' if kind == "site" and resource_scope == "others" else ""
    empty = '<div class="resource-empty"><h3>Nenhum site de outro usuário</h3><p>Não existem publicações de outros proprietários disponíveis para esta sessão.</p></div>' if kind == "site" and resource_scope == "others" and not blocks else ""
    return body[: spans[0][0]] + f'<div class="owner-resource-groups"{group_id}>' + ("".join(blocks) or empty) + '</div>' + body[spans[-1][1] :]


def filter_publication_project(body: str, selected_project: str) -> str:
    if not selected_project:
        return body
    spans = _card_spans(body, "publication-project")
    selected = []
    for start, end, card in spans:
        if re.search(
            r'<input\b[^>]*name=["\']slug["\'][^>]*value=["\']' + re.escape(selected_project) + r'["\']',
            card,
            re.I,
        ):
            selected.append((start, end, card))
    if not selected:
        return body
    return body[:spans[0][0]] + selected[0][2] + body[spans[-1][1]:]


def group_resources_by_user(body: str, tab: str, identity: Identity, selected_project: str = "", resource_scope: str = "") -> str:
    """Group only general publication/database screens; the overview is untouched."""
    if tab not in {"publicacao", "bancos"}:
        return body
    project_owners, tenant_owners = _resource_ownership()
    if tab == "publicacao":
        if selected_project:
            return individual_publication_body(body, selected_project)
        body=clean_general_publication_body(body)
        slugs = sorted(project_owners, key=len, reverse=True)
        def publication_owner(card: str) -> str:
            slug = next((item for item in slugs if item in card), "")
            return project_owners.get(slug, "")
        return _group_cards(body, "publication-project", publication_owner, identity.username, "site", "Meus sites", resource_scope)

    def mark_database(match: re.Match[str]) -> str:
        opening = match.group(0)
        ident = re.search(r'\bdata-tenant=["\']([^"\']+)', opening, re.I)
        if ident is None:
            ident = re.search(r'\bid=["\']([^"\']+)', opening, re.I)
        tenant = unescape(ident.group(1)) if ident else ""
        owner = tenant_owners.get(tenant, "")
        if "data-resource-owner=" in opening:
            return opening
        return opening[:-1] + f' data-resource-owner="{escape(owner)}">'

    opening = re.compile(
        r'<article\b[^>]*class=["\'][^"\']*\bdb96-card\b[^"\']*["\'][^>]*>',
        re.I,
    )
    marked = opening.sub(mark_database, body)
    return (
        f'<div class="js-owner-resource-source" data-resource-kind="banco" '
        f'data-current-user="{escape(identity.username)}">{marked}</div>'
    )

def transform(markup: str, identity: Identity, tab: str, selected_project: str = "", resource_scope: str = "") -> str:
    page = parse_legacy(markup, tab)
    if page.tab == "publicacao":
        body = individual_publication_body(page.body, selected_project) if selected_project else group_resources_by_user(page.body, page.tab, identity, "", resource_scope)
        landing = not selected_project
        return render_legacy(
            identity=identity,
            active_tab=page.tab,
            title=page.title,
            body=body,
            legacy_head="",
            legacy_scripts=page.scripts,
            page_title_override="Publicações" if landing else None,
            description_override=(
                "Escolha uma publicação para consultar o resumo ou abrir o gerenciamento."
                if landing else None
            ),
        )
    return render_legacy(
        identity=identity,
        active_tab=page.tab,
        title=page.title,
        body=group_resources_by_user(page.body, page.tab, identity, selected_project),
        legacy_head=page.scoped_styles,
        legacy_scripts=page.scripts,
    )
