# -*- coding: utf-8 -*-
"""Modelos de mapa (cards) do NexoGeo — plano 09 (aplicar_modelo) + fluxo CAR.

Cada modelo (``catalogo/modelos_mapas.json``) descreve um tipo de mapa IMAP
(CAR, uso consolidado, tipologia, dinamica, embargos, alertas, areas protegidas)
com camadas do catalogo e estilos. ``aplicar_modelo`` monta um MapSpec completo,
no padrao IMAP (paisagem + faixa inferior), a partir dos dados do imovel (CAR).

O pipeline ja recorta cada camada a ``area_base`` (a ATP do imovel) e calcula os
quantitativos por overlay — e o "cruzamento" da ATP com o SIMCAR digital.
"""
from __future__ import annotations

import json
import os

from core.nexomap_catalog import layer_index

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELOS_PADRAO = os.path.join(ROOT, "catalogo", "modelos_mapas.json")

# A4 paisagem = padrao IMAP do cliente (docs/PADRAO_IMAP_RENDERER.md); o A3
# abria demais o enquadramento e fugia dos PDFs-modelo de referencia.
LAYOUT_PAISAGEM = "dinamica_a4_paisagem"


def load_modelos(path: str = MODELOS_PADRAO) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("modelos") or []


def modelos_index(path: str = MODELOS_PADRAO) -> dict[str, dict]:
    return {m["id"]: m for m in load_modelos(path)}


def listar_modelos(path: str = MODELOS_PADRAO) -> list[dict]:
    """Resumo dos modelos para o frontend (sem detalhes de estilo)."""
    out = []
    for m in load_modelos(path):
        out.append({
            "id": m["id"],
            "titulo": m.get("titulo", m["id"]),
            "categoria": m.get("categoria", ""),
            "icone": m.get("icone", "map"),
            "cor": m.get("cor", "#2563eb"),
            "descricao": m.get("descricao", ""),
            "camadas": [c.get("fonte") for c in m.get("camadas", [])],
            "tem_tabela": bool(m.get("tabela")),
        })
    return out


def _datum_utm(epsg_utm: int) -> str:
    zona = "21S" if int(epsg_utm) == 31981 else "22S"
    return f"SIRGAS 2000 UTM {zona}"


def aplicar_modelo(modelo: dict, catalog: dict, *, car_info: dict | None = None,
                   epsg_utm: int = 31982, data_imagem: str = "") -> tuple[dict, list[str]]:
    """Monta um MapSpec (dict) a partir de um modelo + dados do imovel.

    Camadas com ``fonte`` catalogo.<id> inexistente no catalogo sao ignoradas
    (com aviso). Retorna ``(mapspec_dict, avisos)``.
    """
    avisos: list[str] = []
    idx = layer_index(catalog)
    car_info = car_info or {}
    nome_imovel = str(car_info.get("nome") or "").strip()
    numero = str(car_info.get("numero") or "").strip()

    camadas: list[dict] = []
    for c in modelo.get("camadas", []):
        fonte = c.get("fonte")
        estilo = c.get("estilo") or {}
        rotulo = bool(c.get("rotulo", False))
        if fonte == "area_base":
            camadas.append({"id": "perimetro", "fonte": "area_base", "filtro": "",
                            "estilo": estilo, "rotulo": rotulo})
        elif isinstance(fonte, str) and fonte.startswith("catalogo."):
            cid = fonte.split(".", 1)[1]
            if cid not in idx:
                avisos.append(f"camada '{cid}' fora do catalogo — ignorada no modelo {modelo.get('id')}")
                continue
            camadas.append({"id": cid, "fonte": fonte, "filtro": "intersecta_area_base",
                            "estilo": estilo, "rotulo": rotulo})
        else:
            avisos.append(f"fonte invalida '{fonte}' no modelo {modelo.get('id')}")
    if not any(c["id"] == "perimetro" for c in camadas):
        camadas.insert(0, {"id": "perimetro", "fonte": "area_base", "filtro": "",
                           "estilo": {"linha": "#c00000", "largura": 2.8,
                                      "preenchimento": "transparente"}, "rotulo": True})

    titulo = modelo.get("titulo", modelo.get("id", "Mapa"))
    partes_sub = [p for p in (nome_imovel, (f"CAR {numero}" if numero else "")) if p]
    subtitulo = "  |  ".join(partes_sub)

    spec: dict = {
        "titulo": titulo,
        "tipo": modelo.get("id", "geral"),
        "area_base": "projeto.area_base",
        "layout_template": LAYOUT_PAISAGEM,
        "escala": "auto",
        "basemap": "satellite",
        "grade_tipo": "dms",
        "camadas": camadas,
        "metadados_imagem": {
            "satelite_sensor": "PLANET",
            "data_aquisicao": data_imagem or "",
            "datum": _datum_utm(epsg_utm),
        },
        "marca": {"logo": os.path.join("assets", "logo_imap.png"), "texto": "IMAP"},
        # sem escala_grafica: o padrao IMAP nao usa barra de escala (o default
        # flagship do renderer ja desliga; forcar True aqui quebrava a paridade)
        "elementos_layout": {"legenda": True, "norte": True,
                             "grade": True, "minimapa": True, "metadados": True},
        "saidas": ["pdf", "png_validacao", "geojson"],
    }
    if subtitulo:
        spec["subtitulo"] = subtitulo
    if modelo.get("tabela"):
        spec["tabela"] = modelo["tabela"]
        spec["elementos_layout"]["tabela"] = True
    return spec, avisos
