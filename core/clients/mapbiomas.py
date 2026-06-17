# -*- coding: utf-8 -*-
"""Cliente WFS MapBiomas Alerta."""
from __future__ import annotations

from core.clients import http

OWS = "https://production.alerta.mapbiomas.org/geoserver/ows"
LAYERS_ALERTA = [
    "mapbiomas-alertas:v_alerts_last_status",
    "mapbiomas-alertas:crew_simplified-alerts",
]


def alertas(bounds: tuple[float, float, float, float], timeout: int = 90) -> tuple[str, dict]:
    last_error = None
    for layer in LAYERS_ALERTA:
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": layer, "outputFormat": "application/json",
            "bbox": ",".join(str(v) for v in bounds) + ",EPSG:4674",
            "count": "100",
        }
        try:
            data = http.get_json(OWS, params=params, timeout=timeout)
            return layer, data
        except Exception as e:
            last_error = e
    raise RuntimeError(f"MapBiomas indisponivel: {last_error}")
