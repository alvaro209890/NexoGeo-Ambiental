# -*- coding: utf-8 -*-
"""core.clients.incra — Acervo Fundiário INCRA (SIGEF/SNCI via WFS/GML).

O serviço só responde em GML (geojson é recusado); a geometria vem em lon/lat
(EPSG:4326). Consulta por bbox do imóvel. Porta de ``wfs_parcelas`` do antigo
``gerar_contexto_fundiario.py``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from shapely.geometry import Polygon, MultiPolygon

from core.clients import http

ACERVO = "http://acervofundiario.incra.gov.br/i3geo/ogc.php?tema="
SIGEF = "certificada_sigef_particular_mt"
SNCI = "imoveiscertificados_privado_mt"
_NS = {"gml": "http://www.opengis.net/gml"}


def _coords(text: str):
    pts = []
    for tok in text.split():
        lon, lat = tok.split(",")[:2]
        pts.append((float(lon), float(lat)))
    return pts


def _geom(feat):
    polys = []
    for poly in feat.iter("{http://www.opengis.net/gml}Polygon"):
        outer = poly.find(".//gml:outerBoundaryIs/gml:LinearRing/gml:coordinates", _NS)
        shell = _coords(outer.text)
        holes = [_coords(i.text) for i in
                 poly.findall(".//gml:innerBoundaryIs/gml:LinearRing/gml:coordinates", _NS)]
        polys.append(Polygon(shell, holes))
    if not polys:
        return None
    return polys[0] if len(polys) == 1 else MultiPolygon(polys)


def parcelas(tema: str, bounds, timeout: int = 180):
    """Baixa as parcelas certificadas (lon/lat) que intersectam o bbox.
    Retorna ``[(geom, props), ...]``."""
    minx, miny, maxx, maxy = bounds
    url = (ACERVO + tema + "&service=WFS&version=1.0.0&request=GetFeature"
           f"&typename={tema}&bbox={minx},{miny},{maxx},{maxy}")
    text = http.get_text(url, timeout=timeout)
    root = ET.fromstring(text)
    out = []
    for fm in root.iter("{http://www.opengis.net/gml}featureMember"):
        feat = list(fm)[0]
        g = _geom(feat)
        props = {}
        for child in feat:
            tag = child.tag.split("}")[-1]
            if tag not in ("boundedBy", "msGeometry"):
                props[tag] = child.text
        out.append((g, props))
    return out
