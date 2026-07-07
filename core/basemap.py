# -*- coding: utf-8 -*-
"""Basemap por tiles XYZ para o motor nativo de mapas (sem ArcMap).

Baixa tiles publicos (satelite Esri World Imagery ou OSM), monta o mosaico e o
reamostra (vizinho mais proximo) para o extent UTM do mapa, para que a imagem
caia corretamente sob as camadas vetoriais desenhadas em metros.

Sem internet (ou bloqueio), devolve ``None`` e o mapa sai com fundo neutro —
a geracao nunca falha por causa do basemap.
"""
from __future__ import annotations

import io
import math

import numpy as np
import requests
from pyproj import Transformer

TILE = 256
MAX_ZOOM = 17
TARGET_PX = 1400  # largura-alvo do mosaico reamostrado
TIMEOUT = 12
UA = {"User-Agent": "NexoGeoAmbiental/1.0 (+https://github.com/alvaro209890/NexoGeo-Ambiental)"}

PROVIDERS = {
    "satellite": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "credito": "Basemap: Esri World Imagery (Earthstar Geographics)",
    },
    "light": {
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "credito": "Basemap: (c) OpenStreetMap contributors",
    },
}


def _lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[float, float]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def _pick_zoom(bbox_geo: tuple) -> int:
    minx, _, maxx, _ = bbox_geo
    for z in range(MAX_ZOOM, 2, -1):
        x0, _ = _lonlat_to_tile(minx, 0, z)
        x1, _ = _lonlat_to_tile(maxx, 0, z)
        if (x1 - x0) * TILE <= TARGET_PX * 1.4:
            return z
    return 3


def _fetch_tile(session: requests.Session, url_tpl: str, z: int, x: int, y: int):
    from PIL import Image
    n = 2 ** z
    x %= n
    if y < 0 or y >= n:
        return None
    r = session.get(url_tpl.format(z=z, x=x, y=y), timeout=TIMEOUT)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def fetch_basemap_utm(bbox_utm: tuple, utm_epsg: int, style: str = "satellite"):
    """Mosaico de tiles reamostrado para o extent UTM.

    Devolve ``(imagem ndarray HxWx3, extent (minx, maxx, miny, maxy), credito)``
    ou ``None`` se indisponivel.
    """
    provider = PROVIDERS.get(style) or PROVIDERS["satellite"]
    try:
        to_geo = Transformer.from_crs(utm_epsg, 4326, always_xy=True)
        minx, miny, maxx, maxy = bbox_utm
        # bbox geografico do extent UTM (amostra as bordas para cobrir a rotacao da grade)
        xs = np.linspace(minx, maxx, 16)
        ys = np.linspace(miny, maxy, 16)
        border_x = np.concatenate([xs, xs, np.full(16, minx), np.full(16, maxx)])
        border_y = np.concatenate([np.full(16, miny), np.full(16, maxy), ys, ys])
        lons, lats = to_geo.transform(border_x, border_y)
        bbox_geo = (float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max()))

        z = _pick_zoom(bbox_geo)
        tx0, ty1 = _lonlat_to_tile(bbox_geo[0], bbox_geo[1], z)
        tx1, ty0 = _lonlat_to_tile(bbox_geo[2], bbox_geo[3], z)
        x_min, x_max = int(math.floor(tx0)), int(math.floor(tx1))
        y_min, y_max = int(math.floor(ty0)), int(math.floor(ty1))
        if (x_max - x_min + 1) * (y_max - y_min + 1) > 64:
            return None  # area grande demais para o zoom escolhido; nao insiste

        session = requests.Session()
        session.headers.update(UA)
        mosaic = np.zeros(((y_max - y_min + 1) * TILE, (x_max - x_min + 1) * TILE, 3), dtype=np.uint8)
        mosaic[:] = 235
        got = 0
        for ty in range(y_min, y_max + 1):
            for tx in range(x_min, x_max + 1):
                try:
                    img = _fetch_tile(session, provider["url"], z, tx, ty)
                except Exception:
                    img = None
                if img is None:
                    continue
                oy, ox = (ty - y_min) * TILE, (tx - x_min) * TILE
                mosaic[oy:oy + TILE, ox:ox + TILE] = np.asarray(img)
                got += 1
        if not got:
            return None

        # grade alvo em UTM -> lon/lat -> pixel do mosaico (nearest neighbor)
        out_w = TARGET_PX
        out_h = max(200, int(out_w * (maxy - miny) / max(maxx - minx, 1e-9)))
        gx, gy = np.meshgrid(np.linspace(minx, maxx, out_w), np.linspace(maxy, miny, out_h))
        glon, glat = to_geo.transform(gx.ravel(), gy.ravel())
        n = 2 ** z
        px = ((glon + 180.0) / 360.0 * n - x_min) * TILE
        glat = np.clip(glat, -85.05112878, 85.05112878)
        py = ((1.0 - np.arcsinh(np.tan(np.radians(glat))) / math.pi) / 2.0 * n - y_min) * TILE
        px = np.clip(px.astype(int), 0, mosaic.shape[1] - 1)
        py = np.clip(py.astype(int), 0, mosaic.shape[0] - 1)
        warped = mosaic[py, px].reshape(out_h, out_w, 3)
        return warped, (minx, maxx, miny, maxy), provider["credito"]
    except Exception:
        return None
