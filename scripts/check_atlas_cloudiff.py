#!/usr/bin/env python3
"""Offline, read-only CloudIFF Portal ↔ Atlas metadata reconciliation."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

EXPECTED_STATUSES = {"published": "publicado", "draft": "rascunho"}


def load_json(path):
    with Path(path).open(encoding="utf-8") as fd:
        return json.load(fd)


def reconcile(portal, atlas):
    projects = portal.get("tables", {}).get("projects", [])
    records = atlas if isinstance(atlas, list) else atlas.get("items", [])
    if not isinstance(projects, list) or not isinstance(records, list):
        raise ValueError("Estrutura JSON inesperada: tables.projects e items devem ser listas")
    if not all(isinstance(x, dict) for x in projects + records):
        raise ValueError("Estrutura JSON inesperada: registros devem ser objetos")

    slugs = []
    issues = []
    atlas_index = defaultdict(list)
    for item in records:
        atlas_index[str(item.get("id", ""))].append(item)
    for project in projects:
        slug = project.get("slug")
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            issues.append({"type": "invalid_source_slug"})
            continue
        slugs.append(slug)
        suffix = slug.replace("-", "_")
        for prefix, kind in (("cloudiff.project.", "project"), ("cloudiff.repo.", "repo")):
            identifier = prefix + suffix
            matches = atlas_index.get(identifier, [])
            if len(matches) != 1:
                issues.append({"id": identifier, "type": "missing" if not matches else "duplicate"})
                continue
            actual = matches[0]
            if actual.get("kind") != kind:
                issues.append({"id": identifier, "type": "kind_mismatch"})
            expected_url = project.get("repo_url", "")
            if expected_url and actual.get("repo_url") != expected_url:
                issues.append({"id": identifier, "type": "repo_url_mismatch"})
            if kind == "project":
                expected = EXPECTED_STATUSES.get(project.get("status"))
                if expected and expected not in str(actual.get("status", "")).lower():
                    issues.append({"id": identifier, "type": "administrative_status_mismatch"})
                if project.get("name") and project["name"] != actual.get("name"):
                    issues.append({"id": identifier, "type": "name_mismatch"})
    for slug, count in Counter(slugs).items():
        if count > 1:
            issues.append({"type": "duplicate_source_slug", "slug": slug})

    expected_ids = {
        prefix + slug.replace("-", "_")
        for slug in slugs
        for prefix in ("cloudiff.project.", "cloudiff.repo.")
    }
    for identifier in atlas_index:
        if (identifier.startswith("cloudiff.project.") or identifier.startswith("cloudiff.repo.")) and identifier not in expected_ids:
            issues.append({"id": identifier, "type": "atlas_only_requires_review"})

    return {
        "schema": "cloudiff-atlas-reconcile/1",
        "readonly": True,
        "source_projects": len(projects),
        "atlas_items": len(records),
        "atlas_cloudiff_projects": sum(k.startswith("cloudiff.project.") for k in atlas_index),
        "atlas_cloudiff_repositories": sum(k.startswith("cloudiff.repo.") for k in atlas_index),
        "issues": sorted(issues, key=lambda x: (x["type"], x.get("id", ""), x.get("slug", ""))),
        "status": "match" if not issues else "review_required",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portal-json", type=Path, required=True)
    parser.add_argument("--atlas-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = reconcile(load_json(args.portal_json), load_json(args.atlas_json))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid_input", "error_type": type(exc).__name__}), file=sys.stderr)
        return 3
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if data["status"] == "match" else 2


if __name__ == "__main__":
    raise SystemExit(main())
