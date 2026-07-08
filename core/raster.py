# -*- coding: utf-8 -*-
"""Leitura de raster local (GeoTIFF) como fundo de mapa — sem GDAL/rasterio.

Le a georreferencia embutida no GeoTIFF (ModelPixelScale/ModelTiepoint/
ModelTransformation + GeoKeys) com ``tifffile``, recorta a janela da area
(bbox em UTM do projeto, com folga), reamostra e devolve a imagem pronta para
``imshow`` com o ``extent`` ja no CRS do mapa.

Nao ha warp de pixel: para os satelites usados (Landsat/Planet) o raster esta em
UTM da mesma zona do projeto (datums WGS84/SIRGAS2000 equivalentes dentro do
tamanho do pixel), entao basta reprojetar os cantos com ``pyproj`` e posicionar
por ``extent``. Quando o raster esta numa zona/hemisferio "espelhado" (ex.: UTM
22N com northing negativo para o hemisferio sul), o proprio ``pyproj`` resolve o
deslocamento de 10.000.000 m ao converter para a zona sul do projeto.

Falha de leitura nunca derruba a geracao: devolve ``None`` e um aviso.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from pyproj import CRS, Transformer


# --------------------------------------------------------------------------- #
# GeoKeys (subconjunto necessario para descobrir o EPSG do raster)
# --------------------------------------------------------------------------- #
_PROJECTED_CS_TYPE = 3072      # ProjectedCSTypeGeoKey
_GEOGRAPHIC_TYPE = 2048        # GeographicTypeGeoKey
_GT_MODEL_TYPE = 1024          # GTModelTypeGeoKey (1=proj, 2=geog)


@dataclass
class RasterBackground:
    """Imagem pronta para desenho e seus creditos."""
    image: np.ndarray                 # HxWx3 (ou HxWx4) uint8
    extent: tuple[float, float, float, float]  # (minx, maxx, miny, maxy) no CRS do mapa
    epsg_origem: int | None
    fonte: str


def _geokeys(page) -> dict:
    tag = page.tags.get("GeoKeyDirectoryTag")
    if tag is None:
        return {}
    vals = list(tag.value)
    out: dict[int, int] = {}
    # cabecalho: [KeyDirectoryVersion, KeyRevision, MinorRevision, NumberOfKeys]
    n = vals[3] if len(vals) >= 4 else 0
    for i in range(n):
        base = 4 + i * 4
        if base + 3 >= len(vals):
            break
        key_id, tiff_tag_location, _count, value_offset = vals[base:base + 4]
        if tiff_tag_location == 0:  # valor inline (o que precisamos p/ EPSG)
            out[key_id] = value_offset
    return out


def _epsg_do_geotiff(page) -> int | None:
    gk = _geokeys(page)
    for key in (_PROJECTED_CS_TYPE, _GEOGRAPHIC_TYPE):
        code = gk.get(key)
        if code and code not in (0, 32767):  # 32767 = user-defined
            return int(code)
    return None


def _model_extent(page) -> tuple[float, float, float, float] | None:
    """Extent nativo (minx, miny, maxx, maxy) no CRS do proprio raster."""
    tags = page.tags
    w = int(tags["ImageWidth"].value)
    h = int(tags["ImageLength"].value)

    trans = tags.get("ModelTransformationTag")
    if trans is not None:
        m = list(trans.value)  # matriz 4x4 em ordem de linha
        def xy(px, py):
            x = m[0] * px + m[1] * py + m[3]
            y = m[4] * px + m[5] * py + m[7]
            return x, y
        xs = [xy(0, 0)[0], xy(w, 0)[0], xy(0, h)[0], xy(w, h)[0]]
        ys = [xy(0, 0)[1], xy(w, 0)[1], xy(0, h)[1], xy(w, h)[1]]
        return min(xs), min(ys), max(xs), max(ys)

    scale = tags.get("ModelPixelScaleTag")
    tie = tags.get("ModelTiepointTag")
    if scale is None or tie is None:
        return None
    sx, sy = float(scale.value[0]), float(scale.value[1])
    # tiepoint: (i, j, k, X, Y, Z) — pixel (i,j) corresponde ao ponto (X,Y)
    i, j, _k, X, Y, _Z = [float(v) for v in tie.value[:6]]
    ulx = X - i * sx
    uly = Y + j * sy
    lrx = ulx + w * sx
    lry = uly - h * sy
    return min(ulx, lrx), min(uly, lry), max(ulx, lrx), max(uly, lry)


def _reproj_bbox(bbox: tuple, src_epsg: int, dst_epsg: int) -> tuple:
    """Reprojeta um bbox (minx,miny,maxx,maxy) amostrando a borda (nao so os cantos)."""
    if src_epsg == dst_epsg:
        return bbox
    tr = Transformer.from_crs(CRS.from_epsg(src_epsg), CRS.from_epsg(dst_epsg), always_xy=True)
    minx, miny, maxx, maxy = bbox
    xs, ys = [], []
    steps = 8
    for a in range(steps + 1):
        for b in range(steps + 1):
            x = minx + (maxx - minx) * a / steps
            y = miny + (maxy - miny) * b / steps
            tx, ty = tr.transform(x, y)
            xs.append(tx)
            ys.append(ty)
    return min(xs), min(ys), max(xs), max(ys)


def load_raster_background(path: str, dst_epsg: int,
                           bbox_dst: tuple[float, float, float, float],
                           margin_frac: float = 0.08,
                           max_px: int = 2400,
                           assume_epsg: int | None = None,
                           stretch: bool = True) -> tuple[RasterBackground | None, str | None]:
    """Carrega a janela do raster que cobre ``bbox_dst`` (no CRS do mapa).

    ``bbox_dst`` = (minx, miny, maxx, maxy) no ``dst_epsg`` (UTM do projeto).
    Devolve ``(RasterBackground | None, aviso | None)``.
    """
    if not path or not os.path.exists(path):
        return None, f"raster de fundo nao encontrado: {path}"
    try:
        import tifffile
    except Exception:
        return None, "tifffile indisponivel para ler o raster local"

    try:
        with tifffile.TiffFile(path) as tf:
            page = tf.pages[0]
            src_epsg = _epsg_do_geotiff(page) or assume_epsg
            native = _model_extent(page)
            if native is None:
                return None, "raster sem georreferencia (ModelPixelScale/Transformation ausentes)"
            if src_epsg is None:
                return None, "nao foi possivel determinar o EPSG do raster (informe assume_epsg)"

            W = int(page.tags["ImageWidth"].value)
            H = int(page.tags["ImageLength"].value)
            nx0, ny0, nx1, ny1 = native  # extent nativo (CRS do raster)
            px_w = (nx1 - nx0) / W
            px_h = (ny1 - ny0) / H

            # janela desejada -> CRS do raster, com folga
            minx, miny, maxx, maxy = bbox_dst
            dx = (maxx - minx) * margin_frac
            dy = (maxy - miny) * margin_frac
            want_dst = (minx - dx, miny - dy, maxx + dx, maxy + dy)
            want_src = _reproj_bbox(want_dst, dst_epsg, src_epsg)
            wsx0, wsy0, wsx1, wsy1 = want_src

            # intersecao com o extent nativo
            ix0 = max(nx0, wsx0)
            iy0 = max(ny0, wsy0)
            ix1 = min(nx1, wsx1)
            iy1 = min(ny1, wsy1)
            if ix0 >= ix1 or iy0 >= iy1:
                return None, "raster local nao cobre a area do mapa"

            # janela em pixels (linha 0 = topo = maior Y)
            col0 = int(max(0, (ix0 - nx0) / px_w))
            col1 = int(min(W, np.ceil((ix1 - nx0) / px_w)))
            row0 = int(max(0, (ny1 - iy1) / px_h))
            row1 = int(min(H, np.ceil((ny1 - iy0) / px_h)))
            if col1 <= col0 or row1 <= row0:
                return None, "janela do raster vazia apos recorte"

            # decodifica os pixels da janela (PIL lida com LZW sem imagecodecs)
            arr = _read_window_pixels(tf, path, row0, row1, col0, col1, max_px)

            # extent real (nativo) da janela lida, de volta ao CRS do mapa
            wx0 = nx0 + col0 * px_w
            wx1 = nx0 + col1 * px_w
            wy1 = ny1 - row0 * px_h
            wy0 = ny1 - row1 * px_h
            ext_dst = _reproj_bbox((wx0, wy0, wx1, wy1), src_epsg, dst_epsg)

        img = _to_rgb_uint8(arr, stretch=stretch)
        fonte = os.path.basename(path)
        bg = RasterBackground(
            image=img,
            extent=(ext_dst[0], ext_dst[2], ext_dst[1], ext_dst[3]),  # (minx,maxx,miny,maxy)
            epsg_origem=src_epsg,
            fonte=fonte,
        )
        return bg, None
    except Exception as e:  # nunca derruba a geracao
        return None, f"falha ao ler raster local ({type(e).__name__}): {e}"


def _read_window_pixels(tf, path, row0, row1, col0, col1, max_px):
    """Le a janela [row0:row1, col0:col1] em pixels e reamostra p/ <= max_px no maior lado.

    Tenta ``tifffile.asarray`` (usa overviews/imagecodecs quando disponivel); se a
    compressao exigir codec ausente (ex.: LZW sem ``imagecodecs``), cai para o
    Pillow, que decodifica LZW nativamente e ja e dependencia do projeto.
    """
    try:
        data = tf.series[0].asarray()
        data = data[row0:row1, col0:col1]
        return _subsample(data, max_px)
    except Exception:
        pass

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None  # scenes Landsat/Planet passam do limite anti-bomba
    with Image.open(path) as im:
        crop = im.crop((col0, row0, col1, row1))
        if crop.mode not in ("RGB", "RGBA", "L"):
            crop = crop.convert("RGB")
        w, h = crop.size
        step = max(1, int(np.ceil(max(w, h) / max_px)))
        if step > 1:
            crop = crop.resize((max(1, w // step), max(1, h // step)), Image.BILINEAR)
        return np.asarray(crop)


def _subsample(data, max_px):
    h, w = data.shape[0], data.shape[1]
    step = max(1, int(np.ceil(max(h, w) / max_px)))
    if step > 1:
        data = data[::step, ::step]
    return data


def _to_rgb_uint8(arr: np.ndarray, stretch: bool = True) -> np.ndarray:
    a = np.asarray(arr)
    if a.ndim == 2:
        a = np.stack([a, a, a], axis=-1)
    elif a.ndim == 3 and a.shape[-1] == 1:
        a = np.repeat(a, 3, axis=-1)
    elif a.ndim == 3 and a.shape[-1] > 4:
        a = a[..., :3]
    if a.dtype != np.uint8 or stretch:
        a = a.astype(np.float64)
        out = np.empty_like(a)
        # esticamento por canal (2-98%) — realca o falso-cor (magenta/verde) do satelite,
        # ignorando pixels de borda/nodata (0 e 255) no calculo dos limites
        for c in range(a.shape[-1]):
            ch = a[..., c]
            valid = ch[(ch > 0) & (ch < 255)]
            if valid.size < 16:
                valid = ch.ravel()
            lo, hi = np.percentile(valid, [2, 98]) if valid.size else (0.0, 1.0)
            if hi <= lo:
                hi = lo + 1
            out[..., c] = np.clip((ch - lo) / (hi - lo), 0, 1) * 255
        a = out.astype(np.uint8)
    return a
