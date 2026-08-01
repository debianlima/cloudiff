"""Adapt legacy GET pages into the canonical Portal v2 shell.

The adapter changes presentation only. Forms, CSRF fields, links, element IDs and
functional scripts remain intact. Failure is explicit to the caller, which must
return the untouched legacy response (auto-recovery/fail-open).
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re

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


def transform(markup: str, identity: Identity, tab: str) -> str:
    page = parse_legacy(markup, tab)
    return render_legacy(
        identity=identity,
        active_tab=page.tab,
        title=page.title,
        body=page.body,
        legacy_head=page.scoped_styles,
        legacy_scripts=page.scripts,
    )
