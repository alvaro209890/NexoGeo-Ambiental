# -*- coding: utf-8 -*-
"""core.clients.sema — SEMA-MT GeoServer (situação do CAR via WFS).

A camada ``Geoportal:MVW_REQUERIMENTO_ATP`` traz os requerimentos do CAR estadual.
Consulta-se por ``NUMEROESTADUAL`` e usa-se o requerimento mais recente
(maior ``REQUERIMENTO_ID``). Requer ``authkey`` (vinda dos segredos).
"""
from __future__ import annotations

import os
import re

from core.clients import http

OWS = "https://geo.sema.mt.gov.br/geoserver/ows"
LAYER_CAR = "Geoportal:MVW_REQUERIMENTO_ATP"


def consulta_car(num_estadual: str, authkey: str, ows: str = OWS,
                 layer: str = LAYER_CAR, timeout: int = 60) -> dict | None:
    """Retorna as propriedades do requerimento mais recente do CAR, ou ``None``."""
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": layer, "outputFormat": "application/json",
        "cql_filter": f"NUMEROESTADUAL='{num_estadual}'", "authkey": authkey,
    }
    data = http.get_json(ows, params=params, timeout=timeout)
    feats = data.get("features", [])
    if not feats:
        return None
    feats.sort(key=lambda f: float(f["properties"].get("REQUERIMENTO_ID") or 0), reverse=True)
    return feats[0]["properties"]


def authkey_local(raiz: str) -> str | None:
    """Tenta reaproveitar a authkey registrada nos wfsrequest.txt do projeto.

    Nao grava nem imprime a chave; e apenas um fallback para projetos legados que
    ja vieram com requests exportados do GeoServer.
    """
    for dirpath, _, filenames in os.walk(raiz):
        if "wfsrequest.txt" not in filenames:
            continue
        path = os.path.join(dirpath, "wfsrequest.txt")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
        except OSError:
            continue
        m = re.search(r"authkey=([0-9a-fA-F-]{20,})", txt)
        if m:
            return m.group(1)
    return None


def get_features(layer: str, authkey: str, bounds: tuple[float, float, float, float] | None = None,
                 cql_filter: str | None = None, count: int | None = None,
                 ows: str = OWS, timeout: int = 90) -> dict:
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": layer, "outputFormat": "application/json", "authkey": authkey,
    }
    if bounds:
        params["bbox"] = ",".join(str(v) for v in bounds) + ",EPSG:4674"
    if cql_filter:
        params["cql_filter"] = cql_filter
    if count:
        params["count"] = str(count)
    return http.get_json(ows, params=params, timeout=timeout)


def features_bbox(layer: str, bounds: tuple[float, float, float, float], authkey: str,
                  count: int | None = None, timeout: int = 90) -> list[dict]:
    return get_features(layer, authkey, bounds=bounds, count=count, timeout=timeout).get("features", [])


def consulta_car_por_bbox(bounds: tuple[float, float, float, float], authkey: str,
                          timeout: int = 90) -> list[dict]:
    feats = features_bbox(LAYER_CAR, bounds, authkey, timeout=timeout)
    return [f.get("properties") or {} for f in feats]
