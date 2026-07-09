# -*- coding: utf-8 -*-
"""Busca de camadas do catalogo (WFS/GML/REST/WMS) para o motor nativo de mapas.

Cada camada do MapSpec com fonte ``catalogo.<id>`` e buscada no bbox da area,
reprojetada para o UTM do projeto e devolvida pronta para desenho. O GeoJSON
bruto (EPSG:4674) e salvo em ``camadas/<id>.geojson`` no diretorio do job —
abre direto no QGIS, sem ArcMap.

Tipos de fetch (campo ``tipo`` do catalogo):
- ``wms_wfs``     WFS GetFeature JSON (2.0.0 com fallback 1.0.0)
- ``arcgis_rest`` ArcGIS REST /query GeoJSON (ex.: IBAMA PAMGIA)
- ``wfs_gml``     WFS GetFeature GML -> parser proprio (ex.: INCRA acervo, EPSG:4326)
- ``wms_raster``  WMS GetMap PNG por bbox -> overlay de imagem com opacidade

Falha de rede nao derruba a geracao: a camada sai do mapa e vira um aviso.
Com ``cache_dir``, cada resposta e cacheada por (id, bbox) — re-render sem rede.
"""
from __future__ import annotations

import hashlib
import json
import os
import re as _re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from core import overlay
from core.clients import http
from core.mapspec import MapSpec
from core.nexomap_catalog import layer_index


MAX_FEATURES = 500
GEO_EPSG = 4674


@dataclass
class DrawnLayer:
    """Camada pronta para desenho: feicoes em UTM + estilo + GeoJSON bruto.

    Camadas ``wms_raster`` nao tem feicoes: trazem ``image`` (RGBA) +
    ``image_extent`` (UTM) para overlay via imshow.
    """
    id: str
    nome: str
    tema: str
    estilo: dict
    rotulo: bool
    features: list  # list[overlay.FeatureGeo] em UTM
    geojson: dict = field(default_factory=dict)
    rotulo_atributo: str = ""
    rotulo_texto: str = ""          # rotulo estatico (1 por camada), no centroide
    image: object = None            # numpy array RGBA (wms_raster)
    image_extent: tuple | None = None  # (minx, maxx, miny, maxy) em UTM

    @property
    def feature_count(self) -> int:
        return len(self.features)


# --------------------------------------------------------------------------- #
# Parser GML (acervo INCRA — WFS 1.0.0, geometria lon/lat)
# --------------------------------------------------------------------------- #

def _tag_local(el) -> str:
    return el.tag.rsplit('}', 1)[-1].lower()


def _gml_coords_to_pairs(texto: str) -> list[tuple[float, float]]:
    """'x1,y1 x2,y2 ...' (coordinates) ou 'x1 y1 x2 y2 ...' (posList) -> pares."""
    txt = (texto or "").strip()
    if not txt:
        return []
    if "," in txt:
        pares = []
        for tok in txt.split():
            partes = tok.split(",")
            if len(partes) >= 2:
                pares.append((float(partes[0]), float(partes[1])))
        return pares
    nums = [float(t) for t in txt.split()]
    return list(zip(nums[0::2], nums[1::2]))


def _gml_polygons(el) -> list:
    """Extrai shapely Polygons de um elemento GML (Polygon/MultiPolygon/etc.)."""
    from shapely.geometry import Polygon
    polys = []
    for poly_el in el.iter():
        if _tag_local(poly_el) != "polygon":
            continue
        exterior, interiores = None, []
        for sub in poly_el.iter():
            tag = _tag_local(sub)
            if tag in ("outerboundaryis", "exterior"):
                for c in sub.iter():
                    if _tag_local(c) in ("coordinates", "poslist"):
                        exterior = _gml_coords_to_pairs(c.text)
                        break
            elif tag in ("innerboundaryis", "interior"):
                for c in sub.iter():
                    if _tag_local(c) in ("coordinates", "poslist"):
                        interiores.append(_gml_coords_to_pairs(c.text))
                        break
        if exterior and len(exterior) >= 3:
            try:
                polys.append(Polygon(exterior, [i for i in interiores if len(i) >= 3]))
            except Exception:
                continue
    return polys


def gml_para_geojson(xml_text: str) -> dict:
    """Converte um GML de WFS 1.0.0 (``gml:featureMember``) em FeatureCollection.

    Parser tolerante a namespaces (INCRA usa ``ms:``); atributos escalares viram
    ``properties``. Geometria: Polygon/MultiPolygon via coordinates/posList.
    """
    from shapely.geometry import MultiPolygon, mapping
    root = ET.fromstring(xml_text)
    features = []
    for member in root.iter():
        if _tag_local(member) not in ("featuremember", "member"):
            continue
        for feat_el in list(member):
            props = {}
            polys = _gml_polygons(feat_el)
            for child in feat_el.iter():
                if len(list(child)) == 0 and child.text and child.text.strip():
                    tag = _tag_local(child)
                    if tag in ("coordinates", "poslist", "x", "y"):
                        continue
                    props[tag] = child.text.strip()
            if not polys:
                continue
            geom = polys[0] if len(polys) == 1 else MultiPolygon(polys)
            features.append({"type": "Feature", "geometry": mapping(geom),
                             "properties": props})
    return {"type": "FeatureCollection", "features": features}


def _wfs_gml_get_features(endpoint: str, layer: str, bbox_geo: tuple,
                          timeout: int = 120) -> dict:
    """GetFeature GML (WFS 1.0.0) -> GeoJSON dict. Usado no acervo INCRA."""
    params = {
        "service": "WFS", "version": "1.0.0", "request": "GetFeature",
        "typeName": layer,
        "bbox": ",".join(str(v) for v in bbox_geo),
        "maxFeatures": str(MAX_FEATURES),
    }
    texto = http.get_text(endpoint, params=params, timeout=timeout)
    return gml_para_geojson(texto)


# --------------------------------------------------------------------------- #
# WMS GetMap (camadas raster-only, ex.: IBAMA SISCOM)
# --------------------------------------------------------------------------- #

def wms_getmap_url(endpoint: str, layer: str, bbox: tuple, epsg: int,
                   width: int = 1024, height: int | None = None,
                   authkey: str | None = None) -> str:
    """Monta a URL GetMap (WMS 1.1.1, PNG transparente) para o bbox dado."""
    minx, miny, maxx, maxy = bbox
    if height is None:
        prop = (maxy - miny) / max(maxx - minx, 1e-9)
        height = max(64, int(width * prop))
    params = {
        "service": "WMS", "version": "1.1.1", "request": "GetMap",
        "layers": layer, "styles": "",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "srs": f"EPSG:{epsg}",
        "width": str(width), "height": str(height),
        "format": "image/png", "transparent": "true",
    }
    if authkey:
        params["authkey"] = authkey
    from urllib.parse import urlencode
    sep = "&" if "?" in endpoint else "?"
    return endpoint + sep + urlencode(params)


def _wms_raster_fetch(endpoint: str, layer: str, bbox_geo: tuple, dst_epsg: int,
                      authkey: str | None = None, timeout: int = 120):
    """Baixa o GetMap no bbox (reprojetado p/ UTM) -> (np.array RGBA, extent_utm)."""
    import io
    import numpy as np
    from PIL import Image
    from pyproj import CRS, Transformer

    to_utm = Transformer.from_crs(CRS.from_epsg(GEO_EPSG), CRS.from_epsg(dst_epsg),
                                  always_xy=True)
    minx, miny = to_utm.transform(bbox_geo[0], bbox_geo[1])
    maxx, maxy = to_utm.transform(bbox_geo[2], bbox_geo[3])
    url = wms_getmap_url(endpoint, layer, (minx, miny, maxx, maxy), dst_epsg,
                         authkey=authkey)
    r = http.session().get(url, timeout=timeout, verify=http.VERIFY_TLS)
    r.raise_for_status()
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "image" not in ctype:
        raise ValueError(f"WMS nao devolveu imagem (Content-Type={ctype}): "
                         f"{r.text[:120]}")
    img = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGBA"))
    return img, (minx, maxx, miny, maxy)


# --------------------------------------------------------------------------- #
# Cache local por (id, bbox) — re-render sem rebaixar a rede
# --------------------------------------------------------------------------- #

def _cache_path(cache_dir: str, cid: str, bbox: tuple, ext: str) -> str:
    chave = hashlib.md5(f"{cid}|{','.join(f'{v:.6f}' for v in bbox)}".encode()).hexdigest()[:16]
    safe = _re.sub(r"[^A-Za-z0-9_-]", "_", cid)
    return os.path.join(cache_dir, f"{safe}_{chave}{ext}")


def _cache_load_json(path: str) -> dict | None:
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _cache_save_json(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


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


def _read_local_layer(layer, dst_epsg: int, project=None) -> tuple[DrawnLayer | None, str | None]:
    """Le uma camada de arquivo LOCAL (``fonte='arquivo:<path>'``) e devolve um
    DrawnLayer com as feicoes em UTM. Path absoluto ou relativo a raiz de dados/repo.

    Aceita .shp/.zip/.geojson/.kml/.kmz (via core.geo). Rotulo estatico e por
    atributo vem de ``estilo.rotulo_texto`` / ``estilo.rotulo_atributo``.
    """
    from core import geo as geo_mod
    from core import overlay as overlay_mod

    raw = layer.fonte.split(":", 1)[1].strip()
    path = raw
    if not os.path.isabs(path) and project is not None:
        try:
            path = project.resolve_repo_or_data_path(raw)
        except Exception:
            path = raw
    if not os.path.exists(path):
        return None, f"camada {layer.id}: arquivo local nao encontrado: {raw}"
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".shp":
            pares = geo_mod.ler_geometria(path, dst_epsg)  # [(geom_utm, rec), ...]
        else:
            with geo_mod.abrir_shape_zip(path, dst_epsg) as sh:
                pares = list(sh.features_utm)
    except Exception as e:  # leitura/reprojecao
        return None, f"camada {layer.id}: falha ao ler arquivo local ({type(e).__name__}): {e}"
    estilo = layer.estilo or {}
    feats = [overlay_mod.FeatureGeo(geom=g, props=(rec or {}), fonte=layer.id, layer=layer.id)
             for g, rec in pares]
    dl = DrawnLayer(
        id=layer.id,
        nome=str(estilo.get("nome") or layer.id),
        tema=str(estilo.get("tema") or ""),
        estilo=estilo,
        rotulo=bool(layer.rotulo),
        rotulo_atributo=str(estilo.get("rotulo_atributo") or ""),
        rotulo_texto=str(estilo.get("rotulo_texto") or ""),
        features=feats,
    )
    return dl, (None if feats else f"camada {layer.id}: arquivo local sem feicoes")


def fetch_layers(spec: MapSpec, catalog: dict, bbox_geo: tuple, dst_epsg: int,
                 secrets: dict | None = None,
                 cache_dir: str | None = None, project=None) -> tuple[list[DrawnLayer], list[str]]:
    """Busca as camadas do spec no bbox (expandido) da area.

    ``catalogo.<id>`` = WFS/REST/WMS (rede, com cache). ``arquivo:<path>`` =
    shapefile/geojson LOCAL (sem rede). ``cache_dir`` (opcional): respostas
    cacheadas por (id, bbox); falha de rede cai no cache se existir.
    """
    layers_cfg = layer_index(catalog)
    secrets = secrets or {}
    bbox = _expand_bbox_geo(bbox_geo)
    drawn: list[DrawnLayer] = []
    warnings: list[str] = []

    for layer in spec.camadas:
        if layer.fonte.startswith("arquivo:"):
            dl, aviso = _read_local_layer(layer, dst_epsg, project=project)
            if aviso:
                warnings.append(aviso)
            if dl is not None:
                drawn.append(dl)
            continue
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
        tipo = cfg.get("tipo") or "wms_wfs"

        # ---- camadas raster (WMS GetMap): imagem, sem feicoes ----
        if tipo == "wms_raster":
            try:
                img, extent_utm = _wms_raster_fetch(endpoint, wfs_layer, bbox, dst_epsg,
                                                    authkey=authkey)
                drawn.append(DrawnLayer(
                    id=cid, nome=cfg.get("nome", cid), tema=cfg.get("tema", ""),
                    estilo=layer.estilo or {}, rotulo=False, features=[],
                    rotulo_atributo=str(cfg.get("rotulo_atributo") or ""),
                    image=img, image_extent=extent_utm,
                ))
            except Exception as e:
                warnings.append(f"camada {cid} (WMS raster) indisponivel "
                                f"({type(e).__name__}): {e}")
            continue

        # ---- camadas vetoriais (JSON/GML/REST) com cache opcional ----
        cache_file = _cache_path(cache_dir, cid, bbox, ".geojson") if cache_dir else ""
        data = None
        try:
            if tipo == "arcgis_rest":
                data = _arcgis_get_features(endpoint, bbox)
            elif tipo == "wfs_gml":
                data = _wfs_gml_get_features(endpoint, wfs_layer, bbox)
            else:
                data = _wfs_get_features(endpoint, wfs_layer, bbox, authkey)
            if cache_file and isinstance(data, dict):
                _cache_save_json(cache_file, data)
        except Exception as e:
            data = _cache_load_json(cache_file)
            if data is not None:
                warnings.append(f"camada {cid}: rede indisponivel; usado cache local")
            else:
                warnings.append(f"camada {cid} indisponivel ({type(e).__name__}): {e}")
                continue
        src_epsg = int(cfg.get("epsg") or GEO_EPSG)
        feats = overlay.features_de_geojson(data, cfg.get("nome", cid), wfs_layer,
                                            src_epsg=src_epsg, dst_epsg=dst_epsg)
        if not feats:
            warnings.append(f"camada {cid}: nenhuma feicao no recorte da area")
        drawn.append(DrawnLayer(
            id=cid,
            nome=cfg.get("nome", cid),
            tema=cfg.get("tema", ""),
            estilo=layer.estilo or {},
            rotulo=bool(layer.rotulo),
            rotulo_atributo=str(cfg.get("rotulo_atributo") or ""),
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
