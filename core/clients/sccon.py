# -*- coding: utf-8 -*-
"""Cliente público do Dashboard SCCON de Alertas de Mato Grosso."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import requests

ORG_UUID_MT = "597953b9-ee78-4113-80f9-803dbbaa60a0"
TOKEN_URL = "https://plataforma.sccon.com.br/gama-api/auth/token-public-layer"
SEARCH_URL = "https://deforestation-data-mt.sccon.com.br/api/alerts/search?oldGeomCompatibility=true"
COUNT_URL = "https://deforestation-data-mt.sccon.com.br/api-v2/alerts/search/count"

CLASS_TYPES = [
    "BLOW_DOWN",
    "AIRSTRIP_EXPANSION",
    "AIRSTRIP_OPENING",
    "FOCUS_OF_BURN",
    "MINERAL_EXTRACTION",
    "DEGRADATION_SELECTIVE_CUT",
    "SELECTIVE_EXTRACTION",
    "CUT",
    "LANDSLIDES",
    "DEGRADATION_CHEMICAL_AGENT",
    "BURN_SCAR",
    "ACCESS",
]


def _base_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://alertas.sccon.com.br",
        "Referer": "https://alertas.sccon.com.br/matogrosso/",
        "Accept": "application/json, text/plain, */*",
    }


def token_publico(org_uuid: str = ORG_UUID_MT, timeout: int = 45) -> str:
    response = requests.get(
        TOKEN_URL,
        params={"organizationUUID": org_uuid},
        headers=_base_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("SCCON nao retornou access_token publico.")
    return token


def _headers_autorizados(token: str) -> dict[str, str]:
    headers = _base_headers()
    headers["Authorization"] = f"Bearer {token}"
    return headers


def _geometry_json(geojson_or_dict: str | dict[str, Any]) -> str:
    if isinstance(geojson_or_dict, str):
        return geojson_or_dict
    return json.dumps(geojson_or_dict, ensure_ascii=False)


def buscar_alertas_por_geometria(
    geojson_or_dict: str | dict[str, Any],
    data_inicio: str = "2020-01-01",
    data_fim: str | None = None,
    org_uuid: str = ORG_UUID_MT,
    timeout: int = 90,
) -> list[dict[str, Any]]:
    """Busca alertas SCCON que cruzam uma geometria EPSG:4674 em GeoJSON."""
    token = token_publico(org_uuid=org_uuid)
    geom = _geometry_json(geojson_or_dict)
    data_fim = data_fim or date.today().isoformat()
    payload = {
        "fromDate": data_inicio,
        "toDate": data_fim,
        "localIds": None,
        "localType": "DEFORESTATION_MATO_GROSSO_CITY",
        "customGeometryAsGeoJson": geom,
        "classTypes": CLASS_TYPES,
    }
    response = requests.post(
        SEARCH_URL,
        json=payload,
        headers=_headers_autorizados(token),
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def contar_alertas_por_geometria(
    geojson_or_dict: str | dict[str, Any],
    data_inicio: str = "2020-01-01",
    data_fim: str | None = None,
    org_uuid: str = ORG_UUID_MT,
    timeout: int = 90,
) -> int:
    token = token_publico(org_uuid=org_uuid)
    geom = _geometry_json(geojson_or_dict)
    data_fim = data_fim or date.today().isoformat()
    payload = {
        "classTypes": CLASS_TYPES,
        "selectedFilters": [{"localType": "DEFORESTATION_MATO_GROSSO_CITY", "parentLocalIds": []}],
        "rangeDate": [{"start": data_inicio, "end": data_fim}],
        "areaRange": {},
        "alertStatusTypesIds": [1, 2, 3, 4, 5],
        "organizationUUID": org_uuid,
        "cdCars": [],
        "idsLocalAlerts": [],
        "customGeometryAsGeoJson": geom,
    }
    response = requests.post(
        COUNT_URL,
        json=payload,
        headers=_headers_autorizados(token),
        timeout=timeout,
    )
    response.raise_for_status()
    try:
        return int(response.json())
    except Exception:
        return 0


def normalizar_alerta(item: dict[str, Any]) -> dict[str, Any]:
    area_m2 = float(item.get("area") or 0)
    local_ids = item.get("localAlertIds") or []
    geojson = item.get("geoJsonGeometry")
    try:
        geojson_obj = json.loads(geojson) if isinstance(geojson, str) else geojson
    except Exception:
        geojson_obj = None
    return {
        "id": item.get("id"),
        "codigos_locais": local_ids,
        "codigo": ", ".join(str(x) for x in local_ids) or str(item.get("id") or "nao informado"),
        "classe": item.get("classTypeLabel") or item.get("classType") or "nao informado",
        "classe_tipo": item.get("classType"),
        "data_publicacao": item.get("alertDateInserted"),
        "data_deteccao": item.get("alertDetectedDate"),
        "area_ha": area_m2 / 10000.0 if area_m2 else 0.0,
        "imagem_antes": item.get("imageBefore"),
        "imagem_depois": item.get("image"),
        "fonte": "SCCON Dashboard de Alertas MT",
        "geojson": geojson_obj,
    }
