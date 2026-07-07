# -*- coding: utf-8 -*-
"""Orquestracao ponta a ponta da geracao de mapas (100% nativa, sem ArcMap)."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Iterator

from core import secrets as secrets_loader
from core import nexomap_layers
from core.geo import abrir_shape_zip
from core.mapspec import MapSpec, mapspec_from_dict, validate_mapspec
from core.nexomap_ai import spec_from_prompt
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_geo import summarize_area
from core.nexomap_project import NexoMapError, load_nexomap_project
from core.nexomap_renderer import render_pdf_map


def _job_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]


def _append_history(project, entry: dict) -> None:
    os.makedirs(project.mapas_dir(), exist_ok=True)
    path = os.path.join(project.mapas_dir(), "chat_history.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def generate(project_path: str, prompt: str | None = None, mapspec: dict | None = None,
             allow_local_ai_fallback: bool = True, use_basemap: bool = True) -> dict:
    project = load_nexomap_project(project_path)
    catalog = load_layer_catalog(project.catalog_path())
    manifest = load_template_manifest(project.template_manifest_path())
    secrets = secrets_loader.load_secrets(project)

    if mapspec:
        spec = mapspec_from_dict(mapspec)
        ai_provider = "provided_mapspec"
        ai_warnings: list[str] = []
        ai_raw = ""
        ai_warnings.extend(validate_mapspec(spec, catalog, manifest, secrets))
    else:
        if not prompt:
            raise NexoMapError("prompt ausente")
        chat = spec_from_prompt(prompt, project, catalog, manifest, secrets, allow_local_fallback=allow_local_ai_fallback)
        spec = chat.spec
        ai_provider = chat.provider
        ai_warnings = chat.warnings or []
        ai_raw = chat.raw

    area = summarize_area(project)
    job_id = _job_id()
    job_dir = os.path.join(project.mapas_dir(), job_id)
    os.makedirs(job_dir, exist_ok=True)

    _append_history(project, {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "job_id": job_id,
        "prompt": prompt,
        "provider": ai_provider,
        "mapspec": spec.to_dict(),
    })

    # camadas reais do catalogo (WFS) — desenhadas no mapa e exportadas em GeoJSON
    drawn_layers, layer_warnings = nexomap_layers.fetch_layers(
        spec, catalog, area.bbox_geo, project.crs.utm, secrets,
    )

    outputs = render_pdf_map(project, spec, catalog, job_dir,
                             manifest=manifest, drawn_layers=drawn_layers,
                             use_basemap=use_basemap)

    camadas_dir = None
    if "geojson" in spec.saidas:
        with abrir_shape_zip(
            project.area_base_path(), project.crs.utm, project.crs.geografico
        ) as area_shape:
            area_geojson = nexomap_layers.area_base_geojson(area_shape)
        camadas_dir = nexomap_layers.save_layers_geojson(job_dir, drawn_layers, area_geojson)

    warnings = list(ai_warnings) + layer_warnings + outputs.get("render_warnings", [])

    result = {
        "ok": bool(outputs["validacao_result"].get("ok")),
        "job_id": job_id,
        "job_dir": job_dir,
        "provider": ai_provider,
        "ai_raw": ai_raw,
        "mapspec": spec.to_dict(),
        "area": area.to_dict(),
        "escala": outputs.get("escala"),
        "outputs": {
            "pdf": outputs["pdf"],
            "preview_png": outputs["preview_png"],
            "png_validacao": outputs["png_validacao"],
            "validacao": outputs["validacao"],
            "camadas": camadas_dir,
        },
        "validacao": outputs["validacao_result"],
        "warnings": warnings + area.avisos,
    }
    with open(os.path.join(job_dir, "resultado.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def generate_stream(project_path: str, prompt: str | None = None,
                    mapspec: dict | None = None) -> Iterator[dict]:
    yield {"status": "started", "stage": "carregar_projeto"}
    try:
        yield {"status": "progress", "stage": "interpretar_mapspec"}
        yield {"status": "progress", "stage": "buscar_camadas_wfs"}
        yield {"status": "progress", "stage": "renderizar_mapa_nativo"}
        result = generate(project_path, prompt=prompt, mapspec=mapspec)
        yield {"status": "done", "stage": "complete", "result": result}
    except Exception as e:
        yield {"status": "error", "stage": "failed", "erro": str(e)}


def list_results(project_path: str) -> list[dict]:
    project = load_nexomap_project(project_path)
    root = project.mapas_dir()
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root), reverse=True):
        job_dir = os.path.join(root, name)
        if not os.path.isdir(job_dir):
            continue
        result_path = os.path.join(job_dir, "resultado.json")
        result = {}
        if os.path.exists(result_path):
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    result = json.load(f)
            except Exception:
                result = {}
        out.append({
            "job_id": name,
            "job_dir": job_dir,
            "titulo": (result.get("mapspec") or {}).get("titulo", name),
            "ok": result.get("ok", False),
            "outputs": result.get("outputs", {}),
            "warnings": result.get("warnings", []),
        })
    return out
