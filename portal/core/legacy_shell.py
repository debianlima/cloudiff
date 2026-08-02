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
import sqlite3
from collections import OrderedDict
from html import escape

from portal.core.auth import Identity
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


def _readonly_connection() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{_PORTAL_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _resource_ownership() -> tuple[dict[str, str], dict[str, str]]:
    """Return deterministic project and tenant owners without inventing links."""
    projects: dict[str, str] = {}
    tenant_candidates: dict[str, list[str]] = {}
    try:
        con = _readonly_connection()
        for row in con.execute("SELECT slug, owner, created_by, tenant FROM projects"):
            owner = (row["owner"] or row["created_by"] or "").strip()
            if owner:
                projects[row["slug"]] = owner
                tenant = (row["tenant"] or "").strip()
                if tenant:
                    tenant_candidates.setdefault(tenant, []).append(owner)
        for row in con.execute(
            """SELECT pt.tenant, p.owner, p.created_by
               FROM project_tenants pt LEFT JOIN projects p ON p.slug=pt.project"""
        ):
            owner = (row["owner"] or row["created_by"] or "").strip()
            tenant = (row["tenant"] or "").strip()
            if owner and tenant:
                tenant_candidates.setdefault(tenant, []).append(owner)
        for row in con.execute(
            "SELECT tenant, subject FROM tenant_acl WHERE subject_type='user'"
        ):
            tenant = (row["tenant"] or "").strip()
            subject = (row["subject"] or "").strip()
            if tenant and subject:
                tenant_candidates.setdefault(tenant, []).append(subject)
        con.close()
    except Exception:
        return projects, {}
    tenants: dict[str, str] = {}
    for tenant, candidates in tenant_candidates.items():
        unique = list(OrderedDict.fromkeys(item for item in candidates if item))
        if len(unique) == 1:
            tenants[tenant] = unique[0]
        elif unique:
            # Prefer a project owner over extra ACL users; the first candidate is
            # always sourced from projects/project_tenants when available.
            tenants[tenant] = unique[0]
    return projects, tenants


def _group_label(owner: str, current_user: str) -> str:
    if owner == current_user:
        return f"{owner} · você"
    return owner or "Sem usuário vinculado"


def _card_spans(body: str, class_token: str) -> list[tuple[int, int, str]]:
    """Extract complete article elements, including nested article children."""
    opening = re.compile(
        rf'<article\b[^>]*class=["\'][^"\']*\b{re.escape(class_token)}\b[^"\']*["\'][^>]*>',
        re.I,
    )
    tags = re.compile(r'</?article\b[^>]*>', re.I)
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    while True:
        start_match = opening.search(body, cursor)
        if not start_match:
            break
        depth = 0
        end = None
        for tag in tags.finditer(body, start_match.start()):
            if tag.group(0).lower().startswith('</article'):
                depth -= 1
                if depth == 0:
                    end = tag.end()
                    break
            else:
                depth += 1
        if end is None:
            raise ValueError(f"unbalanced article for {class_token}")
        spans.append((start_match.start(), end, body[start_match.start():end]))
        cursor = end
    return spans


def _group_cards(body: str, class_token: str, owner_for_card, current_user: str, kind: str) -> str:
    spans = _card_spans(body, class_token)
    if not spans:
        return body
    grouped: "OrderedDict[str, list[str]]" = OrderedDict()
    for _start, _end, card in spans:
        owner = (owner_for_card(card) or "").strip()
        grouped.setdefault(owner, []).append(card)
    blocks: list[str] = []
    ordered = sorted(grouped.items(), key=lambda item: (item[0] != current_user, (item[0] or "~").lower()))
    for owner, cards in ordered:
        opened = " open" if owner == current_user else ""
        label = escape(_group_label(owner, current_user))
        count = len(cards)
        noun = kind if count == 1 else ("publicações" if kind == "publicação" else "bancos")
        blocks.append(
            f'<details class="owner-resource-group"{opened}>'
            f'<summary><span>{label}</span><span class="owner-resource-count">{count} {noun}</span></summary>'
            f'<div class="owner-resource-items">{"".join(cards)}</div></details>'
        )
    return body[: spans[0][0]] + '<div class="owner-resource-groups">' + "".join(blocks) + '</div>' + body[spans[-1][1] :]


def group_resources_by_user(body: str, tab: str, identity: Identity) -> str:
    """Group only general publication/database screens; the overview is untouched."""
    if tab not in {"publicacao", "bancos"}:
        return body
    project_owners, tenant_owners = _resource_ownership()
    if tab == "publicacao":
        slugs = sorted(project_owners, key=len, reverse=True)
        def publication_owner(card: str) -> str:
            slug = next((item for item in slugs if item in card), "")
            return project_owners.get(slug, "")
        return _group_cards(body, "publication-project", publication_owner, identity.username, "publicação")

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

def transform(markup: str, identity: Identity, tab: str) -> str:
    page = parse_legacy(markup, tab)
    return render_legacy(
        identity=identity,
        active_tab=page.tab,
        title=page.title,
        body=group_resources_by_user(page.body, page.tab, identity),
        legacy_head=page.scoped_styles,
        legacy_scripts=page.scripts,
    )
