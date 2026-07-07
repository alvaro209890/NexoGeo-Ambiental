# -*- coding: utf-8 -*-
"""Busca de camadas do catalogo (WFS) para o motor nativo de mapas.

Cada camada do MapSpec com fonte ``catalogo.<id>`` e buscada por WFS no bbox da
area, reprojetada para o UTM do projeto e devolvida pronta para desenho. O
GeoJSON bruto (EPSG:4674) e salvo em ``camadas/<id>.geojson`` no diretorio do
job — abre direto no QGIS, sem ArcMap.

Falha de rede nao derruba a geracao: a camada sai do mapa e vira um aviso.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from core import overlay
from core.clients import http
from core.mapspec import MapSpec
from core.nexomap_catalog import layer_index


MAX_FEATURES = 500
GEO_EPSG = 4674


@dataclass
class DrawnLayer:
    """Camada pronta para desenho: feicoes em UTM + estilo + GeoJSON bruto."""
    id: str
    nome: str
    tema: str
    estilo: dict
    rotulo: bool
    features: list  # list[overlay.FeatureGeo] em UTM
    geojson: dict = field(default_factory=dict)

    @property
    def feature_count(self) -> int:
        return len(self.features)


def _wfs_get_features(endpoint: str, layer: str, bbox_geo: tuple, authkey: str | None,
                      timeout: int = 90) -> dict:
    bbox_str = ",".join(str(v) for v in bbox_geo)
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": layer, "outputFormat": "application/json",
        "bbox": bbox_str + f",EPSG:{GEO_EPSG}",
        "count": str(MAX_FEATURES),
        "srsName": f"EPSG:{GEO_EPSG}",
    }
    if authkey:
        params["authkey"] = authkey
    try:
        return http.get_json(endpoint, params=params, timeout=timeout)
    except Exception:
        # servidores antigos (ex.: FUNAI) so falam WFS 1.0.0 (typeName/maxFeatures)
        params_v1 = {
            "service": "WFS", "version": "1.0.0", "request": "GetFeature",
            "typeName": layer, "outputFormat": "application/json",
            "bbox": bbox_str,
            "maxFeatures": str(MAX_FEATURES),
        }
        if authkey:
            params_v1["authkey"] = authkey
        return http.get_json(endpoint, params=params_v1, timeout=timeout)


def _arcgis_get_features(endpoint: str, bbox_geo: tuple, timeout: int = 120) -> dict:
    """ArcGIS REST /query (ex.: PAMGIA/IBAMA) devolvendo GeoJSON."""
    import json as _json
    minx, miny, maxx, maxy = bbox_geo
    params = {
        "f": "geojson",
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "geometry": _json.dumps({"xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
                                 "spatialReference": {"wkid": GEO_EPSG}}),
        "geometryType": "esriGeometryEnvelope",
        "inSR": str(GEO_EPSG),
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": str(GEO_EPSG),
        "resultRecordCount": str(MAX_FEATURES),
    }
    return http.get_json(endpoint, params=params, timeout=timeout)


def _expand_bbox_geo(bbox: tuple, fraction: float = 0.25) -> tuple:
    minx, miny, maxx, maxy = bbox
    dx = max((maxx - minx) * fraction, 0.002)
    dy = max((maxy - miny) * fraction, 0.002)
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def fetch_layers(spec: MapSpec, catalog: dict, bbox_geo: tuple, dst_epsg: int,
                 secrets: dict | None = None) -> tuple[list[DrawnLayer], list[str]]:
    """Busca as camadas ``catalogo.*`` do spec no bbox (expandido) da area."""
    layers_cfg = layer_index(catalog)
    secrets = secrets or {}
    bbox = _expand_bbox_geo(bbox_geo)
    drawn: list[DrawnLayer] = []
    warnings: list[str] = []

    for layer in spec.camadas:
        if not layer.fonte.startswith("catalogo."):
            continue
        cid = layer.fonte.split(".", 1)[1]
        cfg = layers_cfg.get(cid)
        if not cfg:
            warnings.append(f"camada {cid} nao existe no catalogo; ignorada")
            continue
        endpoint = cfg.get("endpoint")
        wfs_layer = cfg.get("layer")
        if not endpoint or not wfs_layer:
            warnings.append(f"camada {cid} sem endpoint/layer no catalogo; ignorada")
            continue
        auth_name = cfg.get("auth")
        authkey = secrets.get(auth_name) if auth_name else None
        if auth_name and not authkey:
            warnings.append(f"camada {cid} requer segredo '{auth_name}' ausente; ignorada")
            continue
        try:
            if cfg.get("tipo") == "arcgis_rest":
                data = _arcgis_get_features(endpoint, bbox)
            else:
                data = _wfs_get_features(endpoint, wfs_layer, bbox, authkey)
        except Exception as e:
            warnings.append(f"camada {cid} indisponivel ({type(e).__name__}): {e}")
            continue
        feats = overlay.features_de_geojson(data, cfg.get("nome", cid), wfs_layer,
                                            src_epsg=GEO_EPSG, dst_epsg=dst_epsg)
        if not feats:
            warnings.append(f"camada {cid}: nenhuma feicao no recorte da area")
        drawn.append(DrawnLayer(
            id=cid,
            nome=cfg.get("nome", cid),
            tema=cfg.get("tema", ""),
            estilo=layer.estilo or {},
            rotulo=bool(layer.rotulo),
            features=feats,
            geojson=data,
        ))
    return drawn, warnings


def save_layers_geojson(job_dir: str, drawn: list[DrawnLayer], area_geojson: dict | None = None) -> str | None:
    """Grava ``camadas/<id>.geojson`` (+ area_base.geojson). Devolve o diretorio ou None."""
    if not drawn and not area_geojson:
        return None
    out_dir = os.path.join(job_dir, "camadas")
    os.makedirs(out_dir, exist_ok=True)
    if area_geojson:
        with open(os.path.join(out_dir, "area_base.geojson"), "w", encoding="utf-8") as f:
            json.dump(area_geojson, f, ensure_ascii=False)
    for layer in drawn:
        if not layer.geojson:
            continue
        with open(os.path.join(out_dir, f"{layer.id}.geojson"), "w", encoding="utf-8") as f:
            json.dump(layer.geojson, f, ensure_ascii=False)
    leia_me = os.path.join(out_dir, "LEIA-ME.txt")
    with open(leia_me, "w", encoding="utf-8") as f:
        f.write(
            "Camadas exportadas pelo NexoMap AI (EPSG:4674 / SIRGAS 2000).\n"
            "Abra os .geojson direto no QGIS (arraste para o mapa) — nao requer ArcMap.\n"
        )
    return out_dir


def area_base_geojson(area) -> dict:
    """GeoJSON (EPSG:4674) das feicoes da area base para exportacao."""
    from shapely.geometry import mapping
    features = []
    for geom, rec in area.features_geo:
        props = {k: v for k, v in (rec or {}).items()
                 if isinstance(v, (str, int, float, bool)) or v is None}
        features.append({"type": "Feature", "geometry": mapping(geom), "properties": props})
    return {"type": "FeatureCollection", "features": features}
