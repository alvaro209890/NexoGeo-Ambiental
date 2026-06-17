# -*- coding: utf-8 -*-
"""Calculos de sobreposicao e distancia para a pre-analise."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from pyproj import Transformer
from shapely.geometry import shape as geojson_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform


@dataclass
class FeatureGeo:
    geom: BaseGeometry
    props: dict
    fonte: str
    layer: str = ""


@dataclass
class OverlayHit:
    fonte: str
    layer: str
    props: dict
    area_intersecao_ha: float
    percentual_area: float
    distancia_km: float
    criterio: str
    fazenda_id: str | None = None
    fazenda_nome: str | None = None
    extras: dict = field(default_factory=dict)


def reprojetar_geom(geom: BaseGeometry, src_epsg: int, dst_epsg: int) -> BaseGeometry:
    if src_epsg == dst_epsg:
        return geom
    tr = Transformer.from_crs(src_epsg, dst_epsg, always_xy=True)
    return shapely_transform(lambda x, y, z=None: tr.transform(x, y), geom)


def features_de_geojson(data: dict, fonte: str, layer: str = "",
                        src_epsg: int = 4674, dst_epsg: int | None = None) -> list[FeatureGeo]:
    out: list[FeatureGeo] = []
    for feat in data.get("features", []):
        geom_data = feat.get("geometry")
        if not geom_data:
            continue
        geom = geojson_shape(geom_data)
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            continue
        if dst_epsg and dst_epsg != src_epsg:
            geom = reprojetar_geom(geom, src_epsg, dst_epsg)
        out.append(FeatureGeo(geom=geom, props=feat.get("properties") or {}, fonte=fonte, layer=layer))
    return out


def cruzar(area_utm: BaseGeometry, features: Iterable[FeatureGeo], layer_area_field: str | None = None,
           min_area_ha: float = 0.0001, min_percentual_feature: float = 0.0) -> list[OverlayHit]:
    hits: list[OverlayHit] = []
    area_total = area_utm.area or 1.0
    for feat in features:
        geom = feat.geom
        if not geom.intersects(area_utm):
            continue
        inter = geom.intersection(area_utm)
        if inter.is_empty:
            continue
        area_ha = inter.area / 10000.0
        if geom.area > 0 and min_percentual_feature > 0:
            frac = inter.area / geom.area
            if frac < min_percentual_feature:
                continue
        if geom.area > 0 and area_ha < min_area_ha:
            # Pontos publicados como poligonos minimos devem continuar validos
            # quando o centroide cai dentro da area de analise.
            if not area_utm.contains(geom.centroid):
                continue
        if layer_area_field and feat.props.get(layer_area_field) not in (None, ""):
            try:
                area_ha = float(feat.props[layer_area_field])
            except (TypeError, ValueError):
                pass
        hits.append(OverlayHit(
            fonte=feat.fonte,
            layer=feat.layer,
            props=feat.props,
            area_intersecao_ha=area_ha,
            percentual_area=(inter.area / area_total) * 100.0,
            distancia_km=0.0,
            criterio="intersecao espacial",
        ))
    return hits


def calcular_distancias(area_utm: BaseGeometry, features: Iterable[FeatureGeo],
                        limite_km: float | None = None) -> list[OverlayHit]:
    hits: list[OverlayHit] = []
    for feat in features:
        dist_km = area_utm.distance(feat.geom) / 1000.0
        if limite_km is not None and dist_km > limite_km:
            continue
        inter = feat.geom.intersection(area_utm) if feat.geom.intersects(area_utm) else None
        area_ha = (inter.area / 10000.0) if inter and not inter.is_empty else 0.0
        criterio = "intersecao espacial" if area_ha > 0 else ("divisa/proximidade" if dist_km < 0.05 else "distancia")
        hits.append(OverlayHit(
            fonte=feat.fonte,
            layer=feat.layer,
            props=feat.props,
            area_intersecao_ha=area_ha,
            percentual_area=(inter.area / area_utm.area * 100.0) if inter and area_utm.area else 0.0,
            distancia_km=dist_km,
            criterio=criterio,
        ))
    hits.sort(key=lambda h: h.distancia_km)
    return hits


def atribuir_fazenda(hit: OverlayHit, geom_feature: BaseGeometry, cars) -> OverlayHit:
    centro = geom_feature.centroid
    for car in cars:
        if car.geom.contains(centro) or car.geom.touches(centro):
            hit.fazenda_id = car.id
            hit.fazenda_nome = car.nome
            return hit
    melhor = None
    melhor_area = 0.0
    for car in cars:
        if not geom_feature.intersects(car.geom):
            continue
        inter = geom_feature.intersection(car.geom)
        area = inter.area
        if area > melhor_area:
            melhor_area = area
            melhor = car
    if melhor:
        hit.fazenda_id = melhor.id
        hit.fazenda_nome = melhor.nome
    return hit
