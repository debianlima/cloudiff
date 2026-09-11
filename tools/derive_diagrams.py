#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifesto.yaml"


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def label(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', "'").replace("\n", " ")


def load_entries(path: Path = MANIFEST) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("entradas") or []
    if not isinstance(entries, list):
        raise SystemExit("manifesto.yaml: entradas must be a list")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise SystemExit("manifesto.yaml: each entrada must be an object")
        if "id" not in raw or "caminho" not in raw:
            raise SystemExit("manifesto.yaml: entrada requires id and caminho")
        entry_id = int(raw["id"])
        if entry_id in seen_ids:
            raise SystemExit(f"manifesto.yaml: duplicate entrada id {entry_id}")
        seen_ids.add(entry_id)
        item = dict(raw)
        item["id"] = entry_id
        item["caminho"] = str(raw["caminho"])
        item["consome"] = as_list(raw.get("consome"))
        item["produz"] = as_list(raw.get("produz"))
        normalized.append(item)
    return normalized


def dependency_edges(entries: Iterable[dict[str, Any]]) -> list[tuple[int, int]]:
    entries = list(entries)
    producers: dict[str, list[int]] = {}
    for entry in entries:
        for token in entry.get("produz", []):
            producers.setdefault(token, []).append(entry["id"])
    edges: set[tuple[int, int]] = set()
    for entry in entries:
        for token in entry.get("consome", []):
            for producer in producers.get(token, []):
                if producer != entry["id"]:
                    edges.add((producer, entry["id"]))
    return sorted(edges)


def print_section(title: str, direction: str, node_lines: Iterable[str], edge_lines: Iterable[str] = ()) -> None:
    print(f"## {title}")
    print("```mermaid")
    print(direction)
    for line in node_lines:
        print(line)
    for line in edge_lines:
        print(line)
    print("```")
    print()


def main() -> int:
    entries = load_entries()
    edges = dependency_edges(entries)

    print_section(
        "1. Mapa de módulos",
        "graph TD",
        (f'  E{e["id"]}["{label(e["caminho"])}"]' for e in entries),
    )

    print_section(
        "2. Grafo de dependências",
        "graph LR",
        (),
        (f"  E{src} --> E{dst}" for src, dst in edges),
    )

    print_section(
        "3. Fluxo de execução derivado",
        "flowchart TD",
        (
            f'  E{e["id"]}["{label(e.get("proposito") or e["caminho"])}"]'
            for e in entries
        ),
        (f"  E{src} --> E{dst}" for src, dst in edges),
    )

    print_section(
        "4. Progresso",
        "graph TD",
        (
            f'  E{e["id"]}["{e["id"]} {"ACEITO" if e.get("status") == "aceito" else "PENDENTE"} {label(e["caminho"])}"]'
            for e in entries
        ),
    )

    print_section(
        "5. Cobertura de competência",
        "graph TD",
        (
            f'  E{e["id"]}["{label(e.get("tipo", "?"))} :: {label(e["caminho"])}"]'
            for e in entries
        ),
    )

    faro = [
        entry
        for entry in entries
        if "faro-validation-" in entry["caminho"] and not entry["caminho"].endswith("schema.json")
    ]
    if faro:
        faro_ids = {entry["id"] for entry in faro}
        faro_edges = [(src, dst) for src, dst in edges if src in faro_ids and dst in faro_ids]
        print_section(
            "6. Faro — validação distribuída derivada do manifesto",
            "flowchart TD",
            (
                f'  E{e["id"]}["{label(e.get("proposito") or e["caminho"])}"]'
                for e in faro
            ),
            (f"  E{src} --> E{dst}" for src, dst in faro_edges),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
