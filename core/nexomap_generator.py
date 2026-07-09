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
from core.nexomap_ai import spec_edit_from_prompt, spec_from_prompt, run_tools
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
        cache_dir=os.path.join(project.mapas_dir(), ".cache"), project=project,
    )

    # ── resolver tabela calculada (plano 04) ──
    tabela = spec.tabela or {}
    if tabela.get("fonte") in ("quantitativos", "quantitativos_matriz"):
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


CAR_WEB_PROJECT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "projetos", "car_web", "projeto.json")


# série padrão de mapas gerada por número do CAR (ordem = ordem de saída)
SERIE_CAR_PADRAO = ["car", "uso_consolidado", "tipologia", "dinamica",
                    "areas_protegidas", "embargos", "alertas"]


def _car_project_secrets(project_path: str | None):
    """Carrega o projeto CAR + secrets (cai no secrets da raiz do repo se preciso)."""
    project_path = project_path or CAR_WEB_PROJECT
    project = load_nexomap_project(project_path)
    catalog = load_layer_catalog(project.catalog_path())
    manifest = load_template_manifest(project.template_manifest_path())
    secrets = secrets_loader.load_secrets(project)
    if not secrets.get("sema_authkey"):
        repo_secrets = os.path.join(project.repo_root(), "secrets.local.json")
        if os.path.exists(repo_secrets):
            with open(repo_secrets, "r", encoding="utf-8") as f:
                secrets = json.load(f)
    return project, catalog, manifest, secrets


def _preparar_area_por_car(numero_car: str, project, secrets: dict) -> dict:
    """Busca a ATP do imovel na SEMA (WFS) pelo numero do CAR, grava como
    area_base do projeto e ajusta o CRS UTM. Devolve o dict ``busca``.

    Feito UMA vez por CAR — a serie inteira reusa a mesma area_base.
    """
    from core import nexomap_car
    busca = nexomap_car.buscar_car(numero_car, secrets)
    if not busca.get("ok"):
        raise NexoMapError(busca.get("erro", "CAR nao encontrado"))
    epsg_utm = nexomap_car.utm_epsg_from_bbox(busca["bbox_geo"])
    shapes_dir = os.path.join(project.raiz_abs(), "Shapes")
    zip_name = "area_" + _job_id() + ".zip"
    zip_path = os.path.join(shapes_dir, zip_name)
    nexomap_car.escrever_area_zip(busca["geometry"], busca["propriedades"], zip_path, epsg=busca["epsg"])
    project.area_base.path = os.path.join("Shapes", zip_name)
    project.area_base.tipo = "shapefile_zip"
    project.crs.utm = epsg_utm
    busca["epsg_utm"] = epsg_utm
    return busca


def _gerar_modelo(project, catalog, manifest, secrets, busca: dict, modelo_id: str,
                  use_basemap: bool, data_imagem: str) -> dict:
    """Aplica um modelo sobre a area_base ja preparada (ATP) e renderiza."""
    from core.nexomap_modelos import aplicar_modelo, modelos_index
    modelos = modelos_index()
    if modelo_id not in modelos:
        raise NexoMapError(f"modelo '{modelo_id}' inexistente; use {sorted(modelos)}")
    car_info = {"nome": busca.get("nome"), "numero": busca.get("numero")}
    spec_dict, avisos = aplicar_modelo(modelos[modelo_id], catalog, car_info=car_info,
                                       epsg_utm=busca["epsg_utm"], data_imagem=data_imagem)
    spec = mapspec_from_dict(spec_dict)
    result = _run_pipeline(project, catalog, manifest, secrets, spec,
                           prompt=f"[CAR {busca.get('numero')}] modelo {modelo_id}",
                           provider="car_modelo", ai_raw="",
                           ai_warnings=avisos, use_basemap=use_basemap)
    result["car"] = {
        "numero": busca.get("numero"), "campo": busca.get("campo"),
        "origem": busca.get("origem"), "nome": busca.get("nome"),
        "area_ha": busca.get("area_ha"), "situacao": busca.get("situacao"),
        "epsg_utm": busca["epsg_utm"],
    }
    result["modelo"] = modelo_id
    try:
        with open(os.path.join(result["job_dir"], "resultado.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return result


def gerar_mapa_por_car(numero_car: str, modelo_id: str,
                       project_path: str | None = None,
                       use_basemap: bool = True, data_imagem: str = "") -> dict:
    """Gera UM mapa a partir do numero do CAR + um modelo (card).

    Busca a ATP do imovel na SEMA (WFS), grava como area_base, aplica o modelo
    (cruzando a ATP com as camadas SIMCAR digital via o pipeline) e renderiza.
    """
    project, catalog, manifest, secrets = _car_project_secrets(project_path)
    busca = _preparar_area_por_car(numero_car, project, secrets)
    return _gerar_modelo(project, catalog, manifest, secrets, busca, modelo_id,
                         use_basemap, data_imagem)


def gerar_serie_por_car(numero_car: str, modelos: list[str] | None = None,
                        project_path: str | None = None, use_basemap: bool = True,
                        data_imagem: str = "") -> dict:
    """Gera a SERIE COMPLETA de mapas IMAP a partir do numero do CAR (100% WFS).

    Busca a ATP UMA vez e gera cada modelo (car, uso consolidado, tipologia,
    dinamica, areas protegidas, embargos, alertas). Camadas que exigem segredo
    ausente saem do mapa com aviso — os demais mapas continuam. Devolve
    ``{car, mapas:[{modelo, ok, job_id, pdf, preview, warnings}], erros:[...]}``.
    """
    modelos = modelos or SERIE_CAR_PADRAO
    project, catalog, manifest, secrets = _car_project_secrets(project_path)
    busca = _preparar_area_por_car(numero_car, project, secrets)
    mapas, erros = [], []
    for modelo_id in modelos:
        try:
            r = _gerar_modelo(project, catalog, manifest, secrets, busca, modelo_id,
                              use_basemap, data_imagem)
            mapas.append({
                "modelo": modelo_id, "ok": r.get("ok"), "job_id": r.get("job_id"),
                "pdf": r["outputs"]["pdf"], "preview": r["outputs"]["preview_png"],
                "camadas": [c["nome"] for c in r["validacao"].get("camadas_desenhadas", [])],
                "warnings": r.get("warnings", []),
            })
        except Exception as e:  # um modelo falho nao derruba a serie
            erros.append({"modelo": modelo_id, "erro": f"{type(e).__name__}: {e}"})
    return {
        "car": {"numero": busca.get("numero"), "nome": busca.get("nome"),
                "area_ha": busca.get("area_ha"), "origem": busca.get("origem"),
                "situacao": busca.get("situacao"), "epsg_utm": busca["epsg_utm"]},
        "mapas": mapas, "erros": erros,
    }


def gerar_mapa_por_car_stream(numero_car: str, modelo_id: str,
                              project_path: str | None = None,
                              use_basemap: bool = True,
                              heartbeat_s: float = 4.0,
                              timeout_s: float = 240.0) -> Iterator[dict]:
    """Versao SSE de gerar_mapa_por_car.

    O render (busca + camadas + matplotlib) roda numa thread; enquanto isso o
    gerador emite HEARTBEATS a cada ``heartbeat_s`` segundos para manter a conexao
    viva — sem eles, o proxy/Cloudflare corta o SSE ocioso (~100s) e o frontend
    mostra "nao conectou no servidor".
    """
    import queue
    import threading

    yield {"status": "started", "stage": "buscar_car"}
    yield {"status": "progress", "stage": "consultando_sema", "numero": numero_car}

    box: dict = {}
    fim = queue.Queue()

    def _worker():
        try:
            box["result"] = gerar_mapa_por_car(numero_car, modelo_id,
                                               project_path=project_path, use_basemap=use_basemap)
        except NexoMapError as e:
            box["erro"] = str(e)
        except Exception as e:  # pragma: no cover - defensivo
            box["erro"] = f"{type(e).__name__}: {e}"
        finally:
            fim.put(True)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    esperado = 0.0
    while True:
        try:
            fim.get(timeout=heartbeat_s)
            break
        except queue.Empty:
            esperado += heartbeat_s
            if esperado >= timeout_s:
                yield {"status": "error", "erro": "tempo excedido ao gerar o mapa (a SEMA pode "
                                                  "estar lenta). Tente novamente."}
                return
            yield {"status": "progress", "stage": "renderizando", "aguardando_s": int(esperado)}

    if "erro" in box:
        yield {"status": "error", "erro": box["erro"]}
    else:
        yield {"status": "progress", "stage": "renderizado"}
        yield {"status": "done", "result": box["result"]}


def gerar_serie_por_car_stream(numero_car: str, modelos: list[str] | None = None,
                               project_path: str | None = None, use_basemap: bool = True,
                               data_imagem: str = "") -> Iterator[dict]:
    """Versao SSE de gerar_serie_por_car: emite um evento por mapa concluido."""
    modelos = modelos or SERIE_CAR_PADRAO
    yield {"status": "started", "stage": "buscar_car", "total": len(modelos)}
    try:
        project, catalog, manifest, secrets = _car_project_secrets(project_path)
        busca = _preparar_area_por_car(numero_car, project, secrets)
    except NexoMapError as e:
        yield {"status": "error", "erro": str(e)}
        return
    except Exception as e:  # pragma: no cover - defensivo
        yield {"status": "error", "erro": f"{type(e).__name__}: {e}"}
        return

    car = {"numero": busca.get("numero"), "nome": busca.get("nome"),
           "area_ha": busca.get("area_ha"), "origem": busca.get("origem"),
           "situacao": busca.get("situacao")}
    yield {"status": "progress", "stage": "car_ok", "car": car}

    mapas, erros = [], []
    for i, modelo_id in enumerate(modelos, 1):
        yield {"status": "progress", "stage": "renderizando", "modelo": modelo_id,
               "i": i, "total": len(modelos)}
        try:
            r = _gerar_modelo(project, catalog, manifest, secrets, busca, modelo_id,
                              use_basemap, data_imagem)
            item = {"modelo": modelo_id, "ok": r.get("ok"), "job_id": r.get("job_id"),
                    "pdf": r["outputs"]["pdf"], "preview": r["outputs"]["preview_png"],
                    "warnings": r.get("warnings", [])}
            mapas.append(item)
            yield {"status": "mapa", **item}
        except Exception as e:
            erros.append({"modelo": modelo_id, "erro": f"{type(e).__name__}: {e}"})
            yield {"status": "mapa_erro", "modelo": modelo_id, "erro": f"{type(e).__name__}: {e}"}
    yield {"status": "done", "car": car, "mapas": mapas, "erros": erros}


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

def chat_tools_stream(project_path: str, prompt: str,
                      parent_job_id: str | None = None,
                      allow_local_ai_fallback: bool = True,
                      use_basemap: bool = False,
                      max_steps: int = 12) -> Iterator[dict]:
    """Versao streaming de chat_tools: emite eventos SSE a cada tool_call.

    Yields: {"status":"started"} -> {"tool": nome, "args": {...}} para cada
    tool -> {"status":"done", "result": {...}} ou {"status":"error", "erro": ...}
    """
    yield {"status": "started", "stage": "tools"}
    project = load_nexomap_project(project_path)
    catalog = load_layer_catalog(project.catalog_path())
    manifest = load_template_manifest(project.template_manifest_path())
    secrets = secrets_loader.load_secrets(project)

    parent_dict = None
    if parent_job_id:
        yield {"status": "progress", "stage": "carregar_mapa_pai"}
        parent_dict = _load_job_mapspec(project, parent_job_id)

    tool_events = []
    def _on_tool(nome, args, resultado):
        ev = {"status": "tool", "tool": nome, "args": args, "resultado": resultado}
        tool_events.append(ev)

    try:
        yield {"status": "progress", "stage": "ia_pensando"}
        agent = run_tools(prompt, project, catalog, manifest, secrets,
                          spec_dict=parent_dict, max_steps=max_steps,
                          on_tool_call=_on_tool)
    except Exception as e:
        if not allow_local_ai_fallback:
            yield {"status": "error", "erro": str(e)}
            return
        if parent_dict is None:
            yield {"status": "progress", "stage": "fallback_local"}
            result = generate(project_path, prompt=prompt,
                              allow_local_ai_fallback=True, use_basemap=use_basemap)
            yield {"status": "done", "result": result, "tool_calls": []}
            return
        from core.nexomap_tools import ToolContext
        ctx = ToolContext(catalog=catalog, manifest=manifest, secrets=secrets,
                          project_name=project.nome)
        agent = run_rule_based(prompt, ctx, parent_dict)
        agent.warnings.append(f"tools indisponiveis: {e}")

    # Emite cada tool call para o frontend
    for ev in tool_events:
        yield ev

    spec = agent.spec
    if parent_job_id:
        spec.parent_job_id = parent_job_id
        spec.versao = int((parent_dict or {}).get("versao", 1) or 1) + 1

    warnings = list(agent.warnings)
    warnings.extend(validate_mapspec(spec, catalog, manifest, secrets))

    yield {"status": "progress", "stage": "renderizando"}
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
    yield {"status": "done", "result": result}
