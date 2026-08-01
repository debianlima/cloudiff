"""Semantic HTML primitives backed exclusively by portal/design."""
from html import escape


def button(label: str, href: str, *, quiet: bool = False) -> str:
    css = "btn btn-quiet" if quiet else "btn"
    return f'<a class="{css}" href="{escape(href, quote=True)}">{escape(label)}</a>'


def chip(label: str, state: str = "live") -> str:
    modifier = {"drift": " is-drift", "halt": " is-halt", "mute": " is-mute"}.get(state, "")
    return f'<span class="chip{modifier}">{escape(label)}</span>'
