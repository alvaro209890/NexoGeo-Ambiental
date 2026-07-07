# -*- coding: utf-8 -*-
"""Doctor do motor nativo de mapas (linha de comando e API).

Checa as dependencias do renderer, o catalogo de camadas, o manifesto de
layouts e a area do projeto. ArcMap nao existe mais no fluxo.
"""
from __future__ import annotations

import json
import sys

from core import secrets as secrets_loader
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_geo import summarize_area
from core.nexomap_project import load_nexomap_project


def engine_doctor() -> dict:
    """Estado do motor nativo: dependencias de renderizacao presentes."""
    deps = {}
    for mod in ("matplotlib", "numpy", "PIL", "shapely", "pyproj", "shapefile", "fitz"):
        try:
            __import__(mod)
            deps[mod] = True
        except Exception:
            deps[mod] = False
    ok = all(deps.values())
    return {
        "motor": "nativo (matplotlib)",
        "dependencias": deps,
        "available": ok,
        "message": "Motor de mapas nativo pronto (PDF/PNG/GeoJSON, sem ArcMap)." if ok
        else "Dependencias ausentes: " + ", ".join(k for k, v in deps.items() if not v),
    }


def run(path: str | None = None) -> dict:
    if not path:
        return {"engine": engine_doctor()}
    project = load_nexomap_project(path)
    secrets_loader.load_secrets(project)
    result = {
        "projeto": project._arquivo,
        "engine": engine_doctor(),
        "catalogo": {"path": project.catalog_path(), "ok": True},
        "templates": {"path": project.template_manifest_path(), "ok": True},
    }
    catalog = load_layer_catalog(project.catalog_path())
    manifest = load_template_manifest(project.template_manifest_path())
    result["catalogo"]["camadas"] = len(catalog.get("camadas", []))
    result["templates"]["layouts"] = len(manifest.get("templates", []))
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
