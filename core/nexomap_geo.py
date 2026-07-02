# -*- coding: utf-8 -*-
"""Geospatial helpers for NexoMap AI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from shapely.geometry.base import BaseGeometry

from core.geo import abrir_shape_zip
from core.nexomap_project import NexoMapProject


@dataclass
class AreaSummary:
    area_ha: float
    bbox_geo: tuple[float, float, float, float]
    bbox_utm: tuple[float, float, float, float]
    centroid_geo: tuple[float, float]
    centroid_utm: tuple[float, float]
    feature_count: int
    crs_origem: str | int | None
    avisos: list[str]

    def to_dict(self) -> dict:
        return {
            "area_ha": self.area_ha,
            "bbox_geo": self.bbox_geo,
            "bbox_utm": self.bbox_utm,
            "centroid_geo": self.centroid_geo,
            "centroid_utm": self.centroid_utm,
            "feature_count": self.feature_count,
            "crs_origem": self.crs_origem,
            "avisos": self.avisos,
        }


def summarize_area(project: NexoMapProject) -> AreaSummary:
    with abrir_shape_zip(project.area_base_path(), project.crs.utm, project.crs.geografico) as area:
        epsg = None
        if area.src_crs:
            try:
                epsg = area.src_crs.to_epsg()
            except Exception:
                epsg = None
        return AreaSummary(
            area_ha=area.area_ha,
            bbox_geo=tuple(float(x) for x in area.bbox_geo),
            bbox_utm=tuple(float(x) for x in area.bbox_utm),
            centroid_geo=(float(area.union_geo.centroid.x), float(area.union_geo.centroid.y)),
            centroid_utm=(float(area.union_utm.centroid.x), float(area.union_utm.centroid.y)),
            feature_count=area.feature_count,
            crs_origem=epsg or (area.src_crs.to_string() if area.src_crs else None),
            avisos=list(area.avisos),
        )


def iter_polygons(geom: BaseGeometry) -> Iterable[BaseGeometry]:
    """Yield polygon components from Polygon/MultiPolygon/GeometryCollection."""
    if geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        yield geom
        return
    if hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from iter_polygons(part)


def scale_suggestion_from_bbox(bbox_utm: tuple[float, float, float, float]) -> int:
    """Coarse cartographic scale suggestion for the current bbox."""
    minx, miny, maxx, maxy = bbox_utm
    extent = max(maxx - minx, maxy - miny)
    if extent <= 2500:
        return 10000
    if extent <= 6000:
        return 25000
    if extent <= 12000:
        return 50000
    if extent <= 26000:
        return 100000
    return 250000
