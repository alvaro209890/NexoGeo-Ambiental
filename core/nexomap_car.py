# -*- coding: utf-8 -*-
"""Busca de imovel no CAR digital da SEMA-MT pelo numero do CAR (WFS).

Fluxo web: o usuario escolhe um MODELO de mapa (card) e informa o numero do CAR;
esta modulo consulta o GeoServer da SEMA (camada ``Geoportal:CAR_ATP``) filtrando
por ``CAR_FEDERAL`` (SICAR, ex. ``MT-5106232-<hash>``) ou ``NUMEROESTADUAL``
(ex. ``MT313839/2025``), devolve o poligono do imovel + metadados e escreve um
shapefile-zip que serve de ``area_base`` para o pipeline de render.

Requer a ``sema_authkey`` (em ``secrets.local.json``). Sem rede/segredo -> erro
claro (nao levanta excecao para o loop web).
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import json as _json

SEMA_OWS = "https://geo.sema.mt.gov.br/geoserver/ows"
EPSG_GEO = 4674  # SIRGAS 2000 geografico

# Fontes da ATP no WFS da SEMA, em ordem de prioridade:
# 1) CAR digital validado (CAR_ATP); 2) requerimento do SIMCAR (ainda nao validado).
# Cada fonte mapeia o campo LOGICO -> nome real do atributo naquela camada.
FONTES_ATP = [
    {
        "typename": "Geoportal:CAR_ATP",
        "origem": "car_digital",
        "campos": {"CAR_FEDERAL": "CAR_FEDERAL", "NUMEROESTADUAL": "NUMEROESTADUAL"},
        "situacao": "SITUACAO_CAR",
    },
    {
        "typename": "Geoportal:MVW_REQUERIMENTO_ATP",
        "origem": "requerimento",
        "campos": {"CAR_FEDERAL": "CODIGO_CAR_FEDERAL", "NUMEROESTADUAL": "NUMEROESTADUAL"},
        "situacao": "SITUACAO",
    },
]

# CAR federal (SICAR): MT-<ibge7>-<hash hex de 32>. Estadual: MT<numero>/<ano>.
_RE_FEDERAL = re.compile(r"^[A-Z]{2}-\d{6,7}-[0-9A-F]{20,40}$", re.I)
_RE_ESTADUAL = re.compile(r"^[A-Z]{2}\s?\d{3,}\s?/\s?\d{4}$", re.I)


class CarError(Exception):
    """Erro de busca de CAR — vira mensagem amigavel no endpoint."""


def normalizar_numero(numero: str) -> str:
    return re.sub(r"\s+", "", str(numero or "")).strip().upper()


def detectar_campo(numero: str) -> str | None:
    """Detecta o campo do WFS a partir do formato do numero informado.

    Retorna 'CAR_FEDERAL', 'NUMEROESTADUAL' ou None (formato desconhecido).
    """
    n = normalizar_numero(numero)
    if _RE_FEDERAL.match(n):
        return "CAR_FEDERAL"
    if _RE_ESTADUAL.match(n):
        return "NUMEROESTADUAL"
    return None


def _cql_escape(valor: str) -> str:
    return valor.replace("'", "''")


def _get_features(typename: str, attr: str, numero: str, authkey: str,
                  timeout: float = 40.0) -> list[dict]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": typename,
        "outputFormat": "application/json",
        "srsName": f"EPSG:{EPSG_GEO}",
        "count": "5",
        "CQL_FILTER": f"{attr}='{_cql_escape(numero)}'",
        "authkey": authkey,
    }
    url = SEMA_OWS + "?" + urlencode(params)
    with urlopen(url, timeout=timeout) as resp:
        data = _json.loads(resp.read().decode("utf-8", "replace"))
    return data.get("features") or []


def buscar_car(numero: str, secrets: dict, timeout: float = 40.0) -> dict:
    """Busca a ATP do imovel pelo numero do CAR no WFS da SEMA.

    Consulta, em ordem: (1) CAR digital validado (``CAR_ATP``); (2) requerimento
    do SIMCAR (``MVW_REQUERIMENTO_ATP``) — muitos CARs recentes so existem como
    requerimento. Em cada fonte tenta o campo detectado e depois o outro.

    Devolve ``{ok, numero, campo, origem, propriedades, geometry, bbox_geo, epsg,
    area_ha, nome, situacao}`` ou ``{ok: False, erro}``.
    """
    authkey = (secrets or {}).get("sema_authkey")
    if not authkey:
        return {"ok": False, "erro": "sema_authkey ausente — configure secrets.local.json"}
    n = normalizar_numero(numero)
    if not n:
        return {"ok": False, "erro": "numero do CAR vazio"}

    campo_pref = detectar_campo(n)
    ordem = [campo_pref] if campo_pref else []
    # padrao do sistema = CAR ESTADUAL (NUMEROESTADUAL); federal e fallback.
    for c in ("NUMEROESTADUAL", "CAR_FEDERAL"):
        if c not in ordem:
            ordem.append(c)

    ultimo_erro = None
    for fonte in FONTES_ATP:
        for campo in ordem:
            attr = fonte["campos"].get(campo)
            if not attr:
                continue
            try:
                feats = _get_features(fonte["typename"], attr, n, authkey, timeout=timeout)
            except Exception as e:  # rede/timeout/parse
                ultimo_erro = f"{type(e).__name__}: {e}"
                continue
            if not feats:
                continue
            f = feats[0]
            props = f.get("properties") or {}
            geom = f.get("geometry")
            if not geom:
                continue
            return {
                "ok": True,
                "numero": n,
                "campo": campo,
                "origem": fonte["origem"],
                "propriedades": props,
                "geometry": geom,
                "bbox_geo": _bbox_geojson(geom),
                "epsg": EPSG_GEO,
                "area_ha": props.get("AREA_HA"),
                "nome": props.get("NOMEPROPRIEDADE") or n,
                "municipio_codigo": props.get("MUNICIPIO_CODIGO"),
                "situacao": props.get(fonte["situacao"]) or props.get("SITUACAO_CAR") or props.get("SITUACAO"),
                "n_feicoes": len(feats),
            }
    if ultimo_erro:
        return {"ok": False, "erro": f"falha ao consultar a SEMA: {ultimo_erro}"}
    return {"ok": False, "erro": f"CAR '{n}' nao encontrado no CAR digital nem no requerimento (SIMCAR) da SEMA-MT"}


def _bbox_geojson(geom: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            xs.append(float(coords[0]))
            ys.append(float(coords[1]))
        else:
            for c in coords:
                walk(c)

    walk(geom.get("coordinates"))
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def utm_epsg_from_bbox(bbox_geo: tuple[float, float, float, float]) -> int:
    """EPSG UTM SIRGAS 2000 pela longitude do centro (MT: 21S=31981, 22S=31982)."""
    lon_c = (bbox_geo[0] + bbox_geo[2]) / 2.0
    return 31981 if lon_c < -54.0 else 31982


def escrever_area_zip(geometry: dict, propriedades: dict, dest_zip: str,
                      epsg: int = EPSG_GEO) -> str:
    """Escreve o poligono do CAR como shapefile-zip (area_base do pipeline).

    Usa shapely para orientar o anel externo em sentido horario (exigido pelo
    shapefile) e pyshp para gravar. Campo NOME = NOMEPROPRIEDADE.
    """
    import shapefile  # pyshp
    from pyproj import CRS
    from shapely.geometry import shape
    from shapely.geometry.polygon import orient

    geom = shape(geometry)
    if geom.geom_type == "Polygon":
        polygons = [geom]
    elif geom.geom_type == "MultiPolygon":
        polygons = list(geom.geoms)
    else:
        raise CarError(f"geometria do CAR nao e poligonal: {geom.geom_type}")

    nome = str(propriedades.get("NOMEPROPRIEDADE") or "Imovel CAR")[:60]
    car_fed = str(propriedades.get("CAR_FEDERAL") or "")[:80]

    os.makedirs(os.path.dirname(os.path.abspath(dest_zip)), exist_ok=True)
    buffers = {ext: io.BytesIO() for ext in ("shp", "shx", "dbf")}
    with shapefile.Writer(shp=buffers["shp"], shx=buffers["shx"], dbf=buffers["dbf"],
                          shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=60)
        w.field("CAR", "C", size=80)
        for poly in polygons:
            poly = orient(poly, sign=-1.0)  # exterior horario, buracos anti-horario
            parts = [list(poly.exterior.coords)]
            parts += [list(r.coords) for r in poly.interiors]
            w.poly(parts)
            w.record(nome, car_fed)

    prj = CRS.from_epsg(epsg).to_wkt()
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext, buf in buffers.items():
            zf.writestr("area." + ext, buf.getvalue())
        zf.writestr("area.prj", prj)
    return dest_zip
