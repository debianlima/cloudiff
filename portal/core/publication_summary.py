"""Presentation-only adapters for publication landing and detail pages."""
from __future__ import annotations

from html import escape, unescape
import re
from urllib.parse import quote

from portal.core.html_fragments import article_spans, balanced_element_by_class


def clean_general_publication_body(body: str) -> str:
    """Render the publications landing page as summaries, never as managers."""
    cards: list[str] = []
    for _start, _end, card in article_spans(body, "publication-project"):
        heading = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S | re.I)
        code = re.search(r'<code[^>]*>(.*?)</code>', card, re.S | re.I)
        title = heading.group(1) if heading else "Projeto"
        slug = unescape(re.sub(r'<[^>]+>', '', code.group(1))).strip() if code else ""
        if not slug:
            slug_input = re.search(
                r'<input\b[^>]*name=["\']slug["\'][^>]*value=["\']([^"\']+)', card, re.I
            )
            slug = unescape(slug_input.group(1)).strip() if slug_input else ""

        active = balanced_element_by_class(card, "div", "publication-active-card")
        site_match = (
            re.search(
                r'<a\b[^>]*href=["\']https://([^/"\']+)/?[^"\']*["\'][^>]*>(.*?)</a>',
                active,
                re.S | re.I,
            )
            if active
            else None
        )
        version_match = (
            re.search(
                r'<span\b[^>]*class=["\'][^"\']*\bpill\b[^"\']*["\'][^>]*>(.*?)</span>',
                active,
                re.S | re.I,
            )
            if active
            else None
        )
        site = re.sub(r'<[^>]+>', '', site_match.group(2)).strip() if site_match else ""
        site_host = site_match.group(1).strip() if site_match else ""
        version = re.sub(r'<[^>]+>', '', version_match.group(1)).strip() if version_match else ""
        published = bool(site_match) or ("Site publicado" in active if active else False)
        state = "Publicado" if published else "Ainda não publicado"
        state_class = "ok" if published else "warn"

        site_html = (
            f'<a class="publication-summary-site" href="https://{escape(site_host)}/" '
            f'target="_blank" rel="noopener">{escape(site or site_host)}</a>'
            if site_host
            else '<span class="publication-summary-site is-empty">Sem endereço ativo</span>'
        )
        version_html = (
            f'<span class="pill ok publication-summary-version">{escape(version)}</span>'
            if version
            else '<span class="publication-summary-version">Sem versão ativa</span>'
        )
        manage = (
            f'/cloudiff/portal/?tab=publicacao&amp;project={quote(slug, safe="")}'
            if slug
            else '/cloudiff/portal/?tab=publicacao'
        )
        cards.append(
            '<article class="publication-project card publication-summary-card">'
            '<div class="publication-summary-main">'
            f'<div class="publication-summary-title"><h2>{title}</h2><code>{escape(slug)}</code></div>'
            f'<div class="publication-summary-state"><span>Estado</span>'
            f'<strong class="pill {state_class}">{state}</strong></div>'
            f'<div class="publication-summary-address"><span>Endereço</span>{site_html}</div>'
            f'<div class="publication-summary-active"><span>Versão ativa</span>{version_html}</div>'
            f'<div class="publication-summary-action"><a class="btn" href="{manage}">Gerenciar publicação</a></div>'
            '</div></article>'
        )
    return ''.join(cards) if cards else body


def individual_publication_body(body: str, selected_project: str) -> str:
    """Return only the selected publication card for the individual manager."""
    if not selected_project:
        return body
    for _start, _end, card in article_spans(body, "publication-project"):
        if re.search(
            r'<input\b[^>]*name=["\']slug["\'][^>]*value=["\']'
            + re.escape(selected_project)
            + r'["\']',
            card,
            re.I,
        ):
            resource = balanced_element_by_class(card, "div", "cm-resource")
            heading = re.search(r'<h2[^>]*>(.*?)</h2>', card, re.S | re.I)
            title = heading.group(1) if heading else escape(selected_project)
            if resource:
                return (
                    '<section class="publication-single">'
                    '<nav class="publication-detail-nav"><a class="btn light" href="/cloudiff/portal/?tab=publicacao">← Voltar às publicações</a></nav>'
                    '<article class="publication-project card publication-manager">'
                    f'<div class="publication-manager-head"><div><p>Gerenciar site</p><h2>{title}</h2></div></div>{resource}'
                    '</article></section>'
                )
            return f'<section class="publication-single">{card}</section>'
    return body
