"""Small HTML fragment helpers shared by legacy adapters."""
from __future__ import annotations

import re


def article_spans(markup: str, class_token: str) -> list[tuple[int, int, str]]:
    """Extract complete article elements, including nested article children."""
    opening = re.compile(
        rf'<article\b[^>]*class=["\'][^"\']*\b{re.escape(class_token)}\b[^"\']*["\'][^>]*>',
        re.I,
    )
    tags = re.compile(r'</?article\b[^>]*>', re.I)
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    while True:
        start_match = opening.search(markup, cursor)
        if not start_match:
            break
        depth = 0
        end = None
        for tag in tags.finditer(markup, start_match.start()):
            if tag.group(0).lower().startswith('</article'):
                depth -= 1
                if depth == 0:
                    end = tag.end()
                    break
            else:
                depth += 1
        if end is None:
            raise ValueError(f"unbalanced article for {class_token}")
        spans.append((start_match.start(), end, markup[start_match.start():end]))
        cursor = end
    return spans


def balanced_element_by_class(markup: str, tag_name: str, class_token: str) -> str:
    """Return one balanced element selected by tag and class token."""
    opening = re.compile(
        rf'<{tag_name}\b[^>]*class=["\'][^"\']*\b{re.escape(class_token)}\b[^"\']*["\'][^>]*>',
        re.I,
    )
    start = opening.search(markup)
    if not start:
        return ""
    tags = re.compile(rf'</?{tag_name}\b[^>]*>', re.I)
    depth = 0
    for tag in tags.finditer(markup, start.start()):
        if tag.group(0).lower().startswith(f'</{tag_name}'):
            depth -= 1
            if depth == 0:
                return markup[start.start():tag.end()]
        else:
            depth += 1
    return ""
