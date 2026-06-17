# -*- coding: utf-8 -*-
"""Cliente WFS publico da FUNAI."""
from __future__ import annotations

from core.clients import http

OWS = "https://geoserver.funai.gov.br/geoserver/ows"
LAYER_TI = "Funai:tis_poligonais"


def terras_indigenas(bounds: tuple[float, float, float, float], timeout: int = 90) -> dict:
    params = {
        "service": "WFS", "version": "1.0.0", "request": "GetFeature",
        "typeName": LAYER_TI, "outputFormat": "application/json",
        "bbox": ",".join(str(v) for v in bounds),
    }
    return http.get_json(OWS, params=params, timeout=timeout)
