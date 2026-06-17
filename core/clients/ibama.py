# -*- coding: utf-8 -*-
"""Clientes oficiais IBAMA/PAMGIA para embargos."""
from __future__ import annotations

import json

from core.clients import http

PAMGIA_EMBARGOS = (
    "https://pamgia.ibama.gov.br/server/rest/services/"
    "01_Publicacoes_Bases/adm_embargos_ibama_a/MapServer/0/query"
)


def embargos_pamgia(bounds: tuple[float, float, float, float], timeout: int = 120) -> dict:
    minx, miny, maxx, maxy = bounds
    geom = {
        "xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
        "spatialReference": {"wkid": 4674},
    }
    params = {
        "f": "geojson",
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "geometry": json.dumps(geom),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4674",
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "4674",
    }
    return http.get_json(PAMGIA_EMBARGOS, params=params, timeout=timeout)
