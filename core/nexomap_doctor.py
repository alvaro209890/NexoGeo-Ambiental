# -*- coding: utf-8 -*-
"""Command-line doctor for NexoMap AI."""
from __future__ import annotations

import json
import sys

from core import arcgis_bridge, secrets as secrets_loader
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_geo import summarize_area
from core.nexomap_project import load_nexomap_project


def run(path: str | None = None) -> dict:
    if not path:
        return {"arcgis": arcgis_bridge.doctor().to_dict()}
    project = load_nexomap_project(path)
    sec = secrets_loader.load_secrets(project)
    result = {
        "projeto": project._arquivo,
        "arcgis": arcgis_bridge.doctor(project, sec).to_dict(),
        "catalogo": {"path": project.catalog_path(), "ok": True},
        "templates": {"path": project.template_manifest_path(), "ok": True},
    }
    load_layer_catalog(project.catalog_path())
    load_template_manifest(project.template_manifest_path())
    try:
        result["area"] = summarize_area(project).to_dict()
        result["area"]["ok"] = True
    except Exception as e:
        result["area"] = {"ok": False, "erro": str(e)}
    return result


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else None
    try:
        print(json.dumps(run(path), indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
