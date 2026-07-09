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
from core.nexomap_ai import spec_edit_from_prompt, spec_from_prompt
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_geo import summarize_area
from core.nexomap_project import NexoMapError, load_nexomap_project
from core.nexomap_quantitativos import resolver_tabela_calculada
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

    return _run_pipeline(project, catalog, manifest, secrets, spec,
                         prompt=prompt, provider=ai_provider, ai_raw=ai_raw,
                         ai_warnings=ai_warnings, use_basemap=use_basemap)


def _run_pipeline(project, catalog, manifest, secrets, spec,
                  prompt=None, provider="", ai_raw="", ai_warnings=None,
                  use_basemap=True) -> dict:
    """Pipeline compartilhado: camadas -> render -> GeoJSON -> resultado.json.

    Usado tanto pela geracao nova quanto pela edicao versionada.
    """
    ai_warnings = list(ai_warnings or [])
    area = summarize_area(project)
    job_id = _job_id()
    job_dir = os.path.join(project.mapas_dir(), job_id)
    os.makedirs(job_dir, exist_ok=True)

    _append_history(project, {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "job_id": job_id,
        "prompt": prompt,
        "provider": provider,
        "versao": spec.versao,
        "parent_job_id": spec.parent_job_id,
        "mapspec": spec.to_dict(),
    })

    # camadas reais do catalogo (WFS/GML/REST/WMS) — desenhadas e exportadas
    drawn_layers, layer_warnings = nexomap_layers.fetch_layers(
        spec, catalog, area.bbox_geo, project.crs.utm, secrets,
        cache_dir=os.path.join(project.mapas_dir(), ".cache"),
    )

    # ── resolver tabela calculada (plano 04) ──
    tabela = spec.tabela or {}
    if tabela.get("fonte") == "quantitativos":
        with abrir_shape_zip(
            project.area_base_path(), project.crs.utm, project.crs.geografico
        ) as area_shape:
            recorte = area_shape.union_utm
        resolved = resolver_tabela_calculada(tabela, drawn_layers, recorte, project.crs.utm)
        spec.tabela = resolved

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
        "provider": provider,
        "ai_raw": ai_raw,
        "versao": spec.versao,
        "parent_job_id": spec.parent_job_id,
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


def _load_job_mapspec(project, job_id: str) -> dict:
    path = os.path.join(project.mapas_dir(), job_id, "mapspec.json")
    if not os.path.exists(path):
        raise NexoMapError(f"mapspec.json nao encontrado para o job {job_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _append_versions(project, entry: dict) -> None:
    os.makedirs(project.mapas_dir(), exist_ok=True)
    path = os.path.join(project.mapas_dir(), "versoes.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def edit_map(project_path: str, parent_job_id: str, prompt: str,
             allow_local_ai_fallback: bool = True, use_basemap: bool = True) -> dict:
    """Edita um mapa ja gerado a partir do seu MapSpec (fonte de verdade), gerando
    uma NOVA versao com linhagem (``parent_job_id``, ``versao``). Nao usa PDF/PNG.
    """
    project = load_nexomap_project(project_path)
    catalog = load_layer_catalog(project.catalog_path())
    manifest = load_template_manifest(project.template_manifest_path())
    secrets = secrets_loader.load_secrets(project)

    parent_dict = _load_job_mapspec(project, parent_job_id)
    parent_spec = mapspec_from_dict(parent_dict)
    chat = spec_edit_from_prompt(parent_spec, prompt, project, catalog, manifest, secrets,
                                 allow_local_fallback=allow_local_ai_fallback)
    spec = chat.spec
    spec.parent_job_id = parent_job_id
    spec.versao = int(parent_dict.get("versao", 1) or 1) + 1

    result = _run_pipeline(project, catalog, manifest, secrets, spec,
                           prompt=prompt, provider=chat.provider, ai_raw=chat.raw,
                           ai_warnings=chat.warnings or [], use_basemap=use_basemap)
    _append_versions(project, {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "job_id": result["job_id"], "parent_job_id": parent_job_id,
        "versao": spec.versao, "prompt": prompt, "provider": chat.provider,
    })
    return result


def chat_tools(project_path: str, prompt: str, parent_job_id: str | None = None,
               allow_local_ai_fallback: bool = True, use_basemap: bool = True,
               max_steps: int = 12) -> dict:
    """Opera o mapa via tools/function calling (plano 00).

    Com ``parent_job_id``: edita o MapSpec do job pai gerando NOVA versao com
    linhagem. Sem: a IA cria o mapa do zero (tool ``criar_mapa``). Cada tool_call
    e registrado no ``chat_history.jsonl`` e no ``tool_calls`` do resultado.
    """
    from core.nexomap_agent import run_rule_based
    from core.nexomap_ai import run_tools

    project = load_nexomap_project(project_path)
    catalog = load_layer_catalog(project.catalog_path())
    manifest = load_template_manifest(project.template_manifest_path())
    secrets = secrets_loader.load_secrets(project)

    parent_dict = None
    if parent_job_id:
        parent_dict = _load_job_mapspec(project, parent_job_id)

    try:
        agent = run_tools(prompt, project, catalog, manifest, secrets,
                          spec_dict=parent_dict, max_steps=max_steps)
    except Exception as e:
        if not allow_local_ai_fallback:
            raise
        if parent_dict is None:
            # sem mapa-pai o fallback e o parser local de geracao
            return generate(project_path, prompt=prompt,
                            allow_local_ai_fallback=True, use_basemap=use_basemap)
        from core.nexomap_tools import ToolContext
        ctx = ToolContext(catalog=catalog, manifest=manifest, secrets=secrets,
                          project_name=project.nome)
        agent = run_rule_based(prompt, ctx, parent_dict)
        agent.warnings.append(f"tools indisponiveis: {e}")

    spec = agent.spec
    if parent_job_id:
        spec.parent_job_id = parent_job_id
        spec.versao = int((parent_dict or {}).get("versao", 1) or 1) + 1

    warnings = list(agent.warnings)
    warnings.extend(validate_mapspec(spec, catalog, manifest, secrets))

    result = _run_pipeline(project, catalog, manifest, secrets, spec,
                           prompt=prompt, provider=agent.provider or "tools",
                           ai_raw=json.dumps(agent.tool_log, ensure_ascii=False),
                           ai_warnings=warnings, use_basemap=use_basemap)
    result["tool_calls"] = agent.tool_log
    result["resumo"] = agent.resumo
    _append_history(project, {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "job_id": result["job_id"],
        "modo": "tools",
        "prompt": prompt,
        "provider": agent.provider or "tools",
        "tool_calls": agent.tool_log,
    })
    if parent_job_id:
        _append_versions(project, {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "job_id": result["job_id"], "parent_job_id": parent_job_id,
            "versao": spec.versao, "prompt": prompt,
            "provider": agent.provider or "tools",
            "tool_calls": [t["tool"] for t in agent.tool_log],
        })
    with open(os.path.join(result["job_dir"], "resultado.json"), "w", encoding="utf-8") as f:
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
