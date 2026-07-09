# -*- coding: utf-8 -*-
"""Motor cartografico NATIVO do NexoMap AI (matplotlib, sem ArcMap).

Produz o PDF/PNG oficial do mapa com escala verdadeira (1:N honesto no papel),
basemap de tiles, camadas WFS reais do catalogo, grade UTM, barra de escala
segmentada, seta de norte, legenda, minimapa de localizacao e bloco de
metadados. Tudo roda em qualquer maquina com Python — ArcMap nao e usado.
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
from matplotlib import patches  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from core import basemap as basemap_mod
from core.geo import abrir_shape_zip
from core.mapspec import MapSpec
from core.nexomap_catalog import template_index
from core.nexomap_geo import iter_polygons
from core.nexomap_layout import element_rect, element_text_anchor
from core.nexomap_project import NexoMapProject
from core.nexomap_validation import validate_pdf, write_validation_report


MM = 1 / 25.4  # mm -> polegadas

NICE_SCALES = [1000, 2000, 2500, 5000, 10000, 15000, 25000, 50000, 75000,
               100000, 150000, 250000, 500000, 1000000]

# cores padrao por tema quando o estilo do MapSpec nao define
THEME_COLORS = {
    "embargos": "#d93025",
    "car": "#1d4ed8",
    "areas_protegidas": "#7c3aed",
    "desmatamento": "#f59e0b",
    "tipologia": "#16a34a",
}

_INK = "#111827"
_MUTED = "#4b5563"


def _resolver_caminho(project: NexoMapProject, path: str) -> str:
    """Resolve um caminho (raster/logo) absoluto ou relativo a raiz de dados/repo."""
    if not path:
        return path
    if os.path.isabs(path) and os.path.exists(path):
        return path
    for meth in ("resolve_repo_or_data_path", "resolve_data_path"):
        fn = getattr(project, meth, None)
        if fn:
            try:
                cand = fn(path)
                if cand and os.path.exists(cand):
                    return cand
            except Exception:
                pass
    return path


def _page_mm(spec: MapSpec, manifest: dict) -> tuple[float, float]:
    tpl = template_index(manifest).get(spec.layout_template) or {}
    page = tpl.get("pagina_mm") or [420, 297]
    return float(page[0]), float(page[1])


def _auto_scale(bbox_utm: tuple, frame_w_m: float, frame_h_m: float) -> int:
    """Menor escala 'redonda' em que a area (com folga de 15%) cabe no quadro."""
    minx, miny, maxx, maxy = bbox_utm
    need_w = max(maxx - minx, 10.0) * 1.15
    need_h = max(maxy - miny, 10.0) * 1.15
    for s in NICE_SCALES:
        if frame_w_m * s >= need_w and frame_h_m * s >= need_h:
            return s
    return NICE_SCALES[-1]


def _nice_length(target_m: float) -> float:
    """Comprimento 'redondo' (1-2-5) mais proximo abaixo do alvo."""
    if target_m <= 0:
        return 100.0
    import math
    exp = math.floor(math.log10(target_m))
    for mult in (5, 2, 1):
        val = mult * (10 ** exp)
        if val <= target_m:
            return float(val)
    return float(10 ** exp)


def _fmt_coord(value: float, _pos=None) -> str:
    return f"{value:,.0f}".replace(",", ".")


# --------------------------------------------------------------------------- #
# Grade DMS (graus/minutos/segundos) — padrao IMAP
# --------------------------------------------------------------------------- #
# passos em graus decimais: 1°, 30', 15', 10', 5', 2'30", 1', 30", 15", 10", 5"
_DMS_STEPS = [1.0, 0.5, 0.25, 1 / 6, 1 / 12, 1 / 24, 1 / 60, 1 / 120, 1 / 240, 1 / 360, 1 / 720]


def _nice_dms_step(span_deg: float, alvo: int = 4) -> float:
    if span_deg <= 0:
        return _DMS_STEPS[-1]
    for step in _DMS_STEPS:
        if span_deg / step >= alvo:
            return step
    return _DMS_STEPS[-1]


def _fmt_dms(value: float, is_lat: bool) -> str:
    hemi = ("S" if value < 0 else "N") if is_lat else ("W" if value < 0 else "E")
    total_sec = round(abs(value) * 3600)  # arredonda no segundo
    d, rem = divmod(total_sec, 3600)
    m, s = divmod(rem, 60)
    if s:
        return f"{d}°{m:02d}'{s:02d}\"{hemi}"
    if m:
        return f"{d}°{m:02d}'{hemi}"
    return f"{d}°{hemi}"


def _dms_ticks(lo: float, hi: float, step: float) -> list[float]:
    import math
    start = math.ceil(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 1e-6:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _draw_graticule_dms(ax, extent_utm: tuple, utm_epsg: int, geo_epsg: int, mostrar_linhas: bool):
    """Desenha uma grade lat/long (DMS) sobre eixos em UTM, com rotulos nos 4 lados."""
    from pyproj import CRS, Transformer
    minx, maxx, miny, maxy = extent_utm
    to_geo = Transformer.from_crs(CRS.from_epsg(utm_epsg), CRS.from_epsg(geo_epsg), always_xy=True)
    to_utm = Transformer.from_crs(CRS.from_epsg(geo_epsg), CRS.from_epsg(utm_epsg), always_xy=True)

    # bbox geografico do extent (amostra a borda p/ pegar a curvatura)
    lons, lats = [], []
    for a in range(9):
        for (x, y) in ((minx + (maxx - minx) * a / 8, miny), (minx + (maxx - minx) * a / 8, maxy),
                       (minx, miny + (maxy - miny) * a / 8), (maxx, miny + (maxy - miny) * a / 8)):
            lo, la = to_geo.transform(x, y)
            lons.append(lo)
            lats.append(la)
    lon0, lon1 = min(lons), max(lons)
    lat0, lat1 = min(lats), max(lats)

    step_lon = _nice_dms_step(lon1 - lon0)
    step_lat = _nice_dms_step(lat1 - lat0)
    lon_ticks = _dms_ticks(lon0, lon1, step_lon)
    lat_ticks = _dms_ticks(lat0, lat1, step_lat)

    ax.set_xticks([])
    ax.set_yticks([])
    n = 60

    # meridianos (lon fixo) — linha vertical-ish
    for lon in lon_ticks:
        pts = [to_utm.transform(lon, lat0 + (lat1 - lat0) * k / n) for k in range(n + 1)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if mostrar_linhas:
            ax.plot(xs, ys, color="#ffffff", alpha=0.35, lw=0.7, zorder=8,
                    dashes=(5, 4))
        xb, _ = to_utm.transform(lon, lat0)
        xt, _ = to_utm.transform(lon, lat1)
        label = _fmt_dms(lon, is_lat=False)
        if minx <= xb <= maxx:
            ax.annotate(label, xy=(xb, miny), xytext=(0, -4), textcoords="offset points",
                        ha="center", va="top", fontsize=6.8, color=_INK, annotation_clip=False, zorder=21)
        if minx <= xt <= maxx:
            ax.annotate(label, xy=(xt, maxy), xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", fontsize=6.8, color=_INK, annotation_clip=False, zorder=21)

    # paralelos (lat fixo) — linha horizontal-ish
    for lat in lat_ticks:
        pts = [to_utm.transform(lon0 + (lon1 - lon0) * k / n, lat) for k in range(n + 1)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if mostrar_linhas:
            ax.plot(xs, ys, color="#ffffff", alpha=0.35, lw=0.7, zorder=8, dashes=(5, 4))
        _, yl = to_utm.transform(lon0, lat)
        _, yr = to_utm.transform(lon1, lat)
        label = _fmt_dms(lat, is_lat=True)
        if miny <= yl <= maxy:
            ax.annotate(label, xy=(minx, yl), xytext=(-4, 0), textcoords="offset points",
                        ha="right", va="center", fontsize=6.8, color=_INK, rotation=90,
                        annotation_clip=False, zorder=21)
        if miny <= yr <= maxy:
            ax.annotate(label, xy=(maxx, yr), xytext=(4, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=6.8, color=_INK, rotation=90,
                        annotation_clip=False, zorder=21)


def _layer_color(layer_spec_estilo: dict, tema: str) -> tuple[str, str, float, str]:
    line = layer_spec_estilo.get("linha")
    fill = layer_spec_estilo.get("preenchimento")
    base = line or fill or THEME_COLORS.get(tema, "#64748b")
    alpha = float(layer_spec_estilo.get("opacidade", 0.4) or 0.4)
    hatch = layer_spec_estilo.get("hachura") or layer_spec_estilo.get("hatch") or ""
    is_transp = fill in (None, "", "transparente")
    # com hachura, o preenchimento em geral e "vazado" (so as linhas da hachura aparecem)
    fill_final = "none" if (is_transp and hatch) else (base if is_transp else fill)
    return (line or base), fill_final, alpha, hatch


def _draw_geoms(ax, feats, line: str, fill: str, alpha: float, lw: float = 1.1,
                zorder: int = 6, hatch: str = ""):
    for feat in feats:
        geom = feat.geom
        gtype = geom.geom_type
        if gtype in ("Polygon", "MultiPolygon", "GeometryCollection"):
            for poly in iter_polygons(geom):
                xs, ys = poly.exterior.xy
                ax.fill(xs, ys, facecolor=fill, edgecolor=line, linewidth=lw, alpha=alpha,
                        hatch=hatch or None, zorder=zorder)
                for ring in poly.interiors:
                    ax.plot(*ring.xy, color=line, linewidth=lw * 0.6, zorder=zorder)
        elif gtype in ("LineString", "MultiLineString"):
            parts = geom.geoms if hasattr(geom, "geoms") else [geom]
            for part in parts:
                ax.plot(*part.xy, color=line, linewidth=max(lw, 1.4), alpha=min(1.0, alpha + 0.35), zorder=zorder)
        else:  # pontos
            parts = geom.geoms if hasattr(geom, "geoms") else [geom]
            xs = [p.x for p in parts]
            ys = [p.y for p in parts]
            ax.scatter(xs, ys, s=26, color=line, edgecolor="white", linewidth=0.6, alpha=0.9, zorder=zorder + 1)


def _feature_label(rec: dict) -> str:
    for key in ("NOME", "nome", "NOME_IMOVEL", "NOMEIMOVELRURAL", "imovel", "Name", "name", "NM_MUNICIP"):
        val = (rec or {}).get(key)
        if val:
            return str(val)
    return ""


def _label_features(ax, layer, max_labels: int = 30):
    """Rotula as feicoes de uma camada (atributo configuravel no catalogo)."""
    attr = getattr(layer, "rotulo_atributo", "") or ""
    for feat in layer.features[:max_labels]:
        props = getattr(feat, "props", {}) or {}
        label = str(props.get(attr) or "") if attr else _feature_label(props)
        if not label:
            continue
        try:
            rp = feat.geom.representative_point()
        except Exception:
            continue
        txt = ax.text(rp.x, rp.y, label, fontsize=6.4, color="#ffe27a",
                      ha="center", va="center", zorder=11, fontweight="bold")
        txt.set_path_effects([patheffects.withStroke(linewidth=1.8, foreground="#111827")])


def _draw_perimeter(ax, area, style: dict, rotulo: bool):
    line = style.get("linha", "#ff3b30")
    fill = style.get("preenchimento")
    width = float(style.get("largura", 2.4) or 2.4)
    for geom, rec in area.features_utm:
        for poly in iter_polygons(geom):
            xs, ys = poly.exterior.xy
            ax.plot(xs, ys, color=line, linewidth=width, zorder=10, solid_joinstyle="round")
            if fill and fill != "transparente":
                ax.fill(xs, ys, color=fill, alpha=0.12, zorder=5)
            for ring in poly.interiors:
                ax.plot(*ring.xy, color=line, linewidth=max(0.8, width * 0.6), zorder=10)
        if rotulo:
            label = _feature_label(rec)
            if label:
                rp = geom.representative_point()
                txt = ax.text(rp.x, rp.y, label, fontsize=7.5, color="white",
                              ha="center", va="center", zorder=12, fontweight="bold")
                txt.set_path_effects([patheffects.withStroke(linewidth=2.2, foreground="#111827")])


def _draw_north(ax, x: float = 0.962, y: float = 0.935):
    ax.annotate("", xy=(x, y), xytext=(x, y - 0.075), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="fancy,head_width=0.55,head_length=0.9",
                                facecolor=_INK, edgecolor="white", linewidth=0.8),
                zorder=20, annotation_clip=False)
    txt = ax.text(x, y + 0.014, "N", transform=ax.transAxes, ha="center", va="bottom",
                  fontsize=13, fontweight="bold", color=_INK, zorder=20)
    txt.set_path_effects([patheffects.withStroke(linewidth=2.5, foreground="white")])


def _draw_scale_bar(ax, extent: tuple, scale: int, pos: tuple | None = None):
    """Barra de escala segmentada. ``pos`` = (x_axes, y_axes, ha, va) opcional."""
    minx, maxx, miny, maxy = extent
    width = maxx - minx
    height = maxy - miny
    total = _nice_length(width * 0.28)
    seg = total / 4.0
    xf, yf, ha, va = pos or (0.035, 0.035, "left", "bottom")
    x0 = minx + width * xf
    if ha == "right":
        x0 -= total
    elif ha == "center":
        x0 -= total / 2.0
    y0 = miny + height * yf
    if va == "top":
        y0 -= height * 0.030
    elif va == "center":
        y0 -= height * 0.015
    x0 = min(max(x0, minx + width * 0.01), maxx - total - width * 0.01)
    y0 = min(max(y0, miny + height * 0.012), maxy - height * 0.04)
    bar_h = height * 0.010

    ax.add_patch(patches.Rectangle((x0 - width * 0.008, y0 - bar_h * 2.2),
                                   total + width * 0.016, bar_h * 7.2,
                                   facecolor="white", edgecolor="#9ca3af", linewidth=0.5,
                                   alpha=0.85, zorder=18))
    for i in range(4):
        ax.add_patch(patches.Rectangle((x0 + i * seg, y0), seg, bar_h,
                                       facecolor=_INK if i % 2 == 0 else "white",
                                       edgecolor=_INK, linewidth=0.7, zorder=19))
    unit_km = total >= 1000
    for i in (0, 2, 4):
        val = i * seg
        label = f"{val / 1000:g}" if unit_km else f"{val:g}"
        ax.text(x0 + val, y0 + bar_h * 1.5, label, fontsize=6.5, ha="center", color=_INK, zorder=19)
    ax.text(x0 + total, y0 - bar_h * 1.4, "km" if unit_km else "m",
            fontsize=6.5, ha="center", va="top", color=_INK, zorder=19)


def _draw_minimap(fig, rect, area, extent: tuple, utm_epsg: int, basemap_style: str):
    mini = fig.add_axes(rect)
    minx, maxx, miny, maxy = extent
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    half_w = (maxx - minx) * 5
    half_h = (maxy - miny) * 5
    mini_extent = (cx - half_w, cx + half_w, cy - half_h, cy + half_h)
    mini.set_xlim(mini_extent[0], mini_extent[1])
    mini.set_ylim(mini_extent[2], mini_extent[3])
    mini.set_facecolor("#e2e8f0")
    bm = basemap_mod.fetch_basemap_utm((mini_extent[0], mini_extent[2], mini_extent[1], mini_extent[3]),
                                       utm_epsg, style=basemap_style)
    if bm:
        img, ext, _ = bm
        mini.imshow(img, extent=ext, origin="upper", interpolation="bilinear", zorder=1)
    for poly in iter_polygons(area.union_utm):
        mini.fill(*poly.exterior.xy, facecolor="#ef4444", edgecolor="#b91c1c", alpha=0.85, zorder=3)
    mini.add_patch(patches.Rectangle((minx, miny), maxx - minx, maxy - miny,
                                     facecolor="none", edgecolor="#ef4444", linewidth=1.1, zorder=4))
    mini.set_xticks([])
    mini.set_yticks([])
    for spine in mini.spines.values():
        spine.set_color("#94a3b8")
        spine.set_linewidth(0.8)
    return mini


def _draw_compass_rose(fig, rect):
    """Rosa-dos-ventos (estrela de 8 pontas com N/S/E/W) no padrao IMAP."""
    import numpy as np
    from matplotlib.patches import Polygon
    axc = fig.add_axes(rect)
    axc.set_xlim(-1.25, 1.25)
    axc.set_ylim(-1.25, 1.25)
    axc.set_aspect("equal")
    axc.axis("off")
    long_r, short_r = 0.9, 0.34
    verts = []
    for k in range(8):
        ang = np.deg2rad(90 - k * 45)  # N no topo, sentido horario
        r = long_r if k % 2 == 0 else short_r
        verts.append((r * np.cos(ang), r * np.sin(ang)))
    axc.add_patch(Polygon(verts, closed=True, facecolor="white", edgecolor=_INK, lw=0.9, zorder=3))
    # ponta norte destacada
    axc.add_patch(Polygon([(0, long_r), (short_r * 0.72, short_r * 0.72), (0, 0),
                           (-short_r * 0.72, short_r * 0.72)], closed=True,
                          facecolor=_INK, edgecolor=_INK, lw=0.5, zorder=4))
    for a, lab in [(90, "N"), (0, "E"), (-90, "S"), (180, "W")]:
        ar = np.deg2rad(a)
        axc.text(1.12 * np.cos(ar), 1.12 * np.sin(ar), lab, ha="center", va="center",
                 fontsize=6.2, fontweight="bold", color=_INK)
    axc.plot(0, 0, marker="o", ms=2.2, color=_INK, zorder=4)


def _draw_title_box(ax, titulo: str, subtitulo: str, x: float = 0.985, y: float = 0.97,
                    ha: str = "right", va: str = "top", fundo: str = "#2b2b2b",
                    cor: str = "white", tamanho: float = 16.0, borda: str | None = None):
    """Caixa de titulo (padrao IMAP). Estilo editavel: fundo/cor/tamanho/borda.

    O padrao historico e a caixa escura; o modelo IMAP recente usa caixa branca
    com texto preto no topo-centro (layout.elementos.titulo.estilo).
    """
    texto = titulo + (("\n" + subtitulo) if subtitulo else "")
    if borda is None:
        borda = "white" if fundo not in ("white", "#fff", "#ffffff") else "#111827"
    ax.text(x, y, texto, transform=ax.transAxes, ha=ha, va=va,
            fontsize=tamanho, fontweight="bold", color=cor, linespacing=1.25, zorder=26,
            bbox=dict(boxstyle="round,pad=0.55", fc=fundo, ec=borda, lw=1.3, alpha=0.93))


def _draw_legend_swatches(fig, rect, entries, titulo="Legenda", ncols=1, fontsize=8.0):
    """Legenda com swatches (patches/linhas) — usada na faixa inferior do flagship."""
    axl = fig.add_axes(rect)
    axl.axis("off")
    axl.text(0.0, 1.0, titulo, fontsize=11, fontweight="bold", va="top", color=_INK,
             transform=axl.transAxes)
    if entries:
        axl.legend(handles=entries, loc="upper left", bbox_to_anchor=(0.0, 0.84),
                   frameon=False, fontsize=fontsize, ncols=max(1, int(ncols)),
                   handlelength=1.9, handleheight=1.4, borderaxespad=0)


# --------------------------------------------------------------------------- #
# Legenda editavel (plano 02): modos auto / manual / misto
# --------------------------------------------------------------------------- #

def _legend_swatch(item: dict, label: str):
    """Artista matplotlib para um item de legenda ({tipo, cor, preenchimento, ...})."""
    tipo = str(item.get("tipo") or "poligono").lower()
    cor = item.get("cor") or "#64748b"
    largura = float(item.get("largura", 2.0) or 2.0)
    opacidade = float(item.get("opacidade", 0.85) or 0.85)
    hachura = item.get("hachura") or item.get("hatch") or ""
    fill = item.get("preenchimento")
    if tipo == "linha":
        return Line2D([0], [0], color=cor, lw=largura, label=label)
    if tipo == "ponto":
        return Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=cor,
                      markeredgecolor="white", markersize=7, label=label)
    if tipo == "imagem":
        # swatch de raster: bloco solido com borda discreta
        return patches.Patch(facecolor=cor, edgecolor="#6b7280", alpha=1.0, label=label)
    if fill in (None, "", "transparente"):
        fill_final = "none" if hachura else cor
    else:
        fill_final = fill
    return patches.Patch(facecolor=fill_final, edgecolor=cor, alpha=max(opacidade, 0.35),
                         hatch=hachura or None, label=label)


def _linked_item_swatch(item: dict, layer):
    """Swatch de item vinculado a uma camada: herda o estilo dela (com overrides)."""
    line, fill, alpha, hatch = _layer_color(layer.estilo, layer.tema)
    merged = {
        "tipo": item.get("tipo") or "poligono",
        "cor": item.get("cor") or line,
        "preenchimento": item.get("preenchimento", fill),
        "hachura": item.get("hachura", hatch),
        "opacidade": item.get("opacidade", max(alpha, 0.35)),
        "largura": item.get("largura", 2.0),
    }
    label = str(item.get("rotulo") or layer.nome)
    if item.get("contagem", True) is not False:
        label += f" ({layer.feature_count})" if layer.features else " (sem feicoes no recorte)"
    return _legend_swatch(merged, label)


def _montar_legenda(legenda_cfg: dict, auto_entries: list, drawn_by_id: dict) -> tuple[list, list]:
    """Resolve os modos da legenda (plano 02) -> (entries, avisos).

    ``auto_entries`` = lista de (camada_id, artista) na ordem do desenho (com o
    perimetro em primeiro). ``modo``: 'auto' (padrao sem itens), 'manual' (usa
    so os itens) e 'misto' (auto + overrides por ``camada``). Quando ha ``itens``
    e o modo nao foi dito, assume 'manual'.
    """
    cfg = legenda_cfg or {}
    itens = cfg.get("itens") or []
    modo = str(cfg.get("modo") or ("manual" if itens else "auto")).lower()
    avisos: list[str] = []

    if modo == "auto" or not itens:
        return [artist for _, artist in auto_entries], avisos

    if modo == "manual":
        entries = []
        for item in itens:
            if not isinstance(item, dict):
                continue
            cid = item.get("camada")
            layer = drawn_by_id.get(cid) if cid else None
            if cid and layer is None:
                avisos.append(f"legenda: item vinculado a camada inexistente '{cid}'; "
                              "usado o simbolo do proprio item")
            if layer is not None:
                entries.append(_linked_item_swatch(item, layer))
            else:
                entries.append(_legend_swatch(item, str(item.get("rotulo") or cid or "item")))
        return entries, avisos

    # misto: comeca do auto e aplica overrides por camada; itens soltos sao anexados
    entries_por_id = {cid: artist for cid, artist in auto_entries}
    ordem = [cid for cid, _ in auto_entries]
    extras = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        cid = item.get("camada")
        layer = drawn_by_id.get(cid) if cid else None
        if cid and cid in entries_por_id and layer is not None:
            entries_por_id[cid] = _linked_item_swatch(item, layer)
        elif cid and cid in entries_por_id:  # perimetro ou entrada sem DrawnLayer
            artist = entries_por_id[cid]
            if item.get("rotulo"):
                artist.set_label(str(item["rotulo"]))
        else:
            if cid:
                avisos.append(f"legenda: item vinculado a camada inexistente '{cid}'; anexado")
            extras.append(_legend_swatch(item, str(item.get("rotulo") or cid or "item")))
    return [entries_por_id[cid] for cid in ordem] + extras, avisos


def _draw_tipologia_inset(fig, rect, area, tipo_layers, base_color="#c9c15a"):
    """Inset 'Tipologia vegetal': imovel preenchido (Cerrado) + camadas de vegetacao (Floresta)."""
    axi = fig.add_axes(rect)
    axi.set_aspect("equal")
    axi.axis("off")
    axi.add_patch(patches.FancyBboxPatch((0, 0), 1, 1, transform=axi.transAxes,
                                         boxstyle="round,pad=0.005,rounding_size=0.02",
                                         facecolor="white", edgecolor="#9ca3af", linewidth=0.9, zorder=0))
    inner = fig.add_axes((rect[0] + rect[2] * 0.40, rect[1] + rect[3] * 0.10,
                          rect[2] * 0.56, rect[3] * 0.62))
    inner.set_aspect("equal")
    inner.axis("off")
    for poly in iter_polygons(area.union_utm):
        inner.fill(*poly.exterior.xy, facecolor=base_color, edgecolor="#7a7333", linewidth=0.5, zorder=2)
    for layer in tipo_layers:
        for feat in layer.features:
            for poly in iter_polygons(feat.geom):
                inner.fill(*poly.exterior.xy, facecolor="#5aa85a", edgecolor="#2f6d2f",
                           linewidth=0.3, zorder=3)
    minx, miny, maxx, maxy = area.bbox_utm
    mx = max(maxx - minx, maxy - miny) * 0.08
    inner.set_xlim(minx - mx, maxx + mx)
    inner.set_ylim(miny - mx, maxy + mx)
    # titulo + mini legenda
    axi.text(0.06, 0.93, "Tipologia vegetal", fontsize=9.5, fontweight="bold", va="top", color=_INK,
             transform=axi.transAxes)
    axi.text(0.06, 0.52, "LEGENDA", fontsize=6.2, fontweight="bold", va="top", color=_INK,
             transform=axi.transAxes)
    axi.add_patch(patches.Rectangle((0.06, 0.34), 0.09, 0.07, transform=axi.transAxes,
                                    facecolor="#5aa85a", edgecolor="#2f6d2f", lw=0.5))
    axi.text(0.17, 0.375, "Tipologia: Floresta", fontsize=6.0, va="center", transform=axi.transAxes)
    axi.add_patch(patches.Rectangle((0.06, 0.20), 0.09, 0.07, transform=axi.transAxes,
                                    facecolor=base_color, edgecolor="#7a7333", lw=0.5))
    axi.text(0.17, 0.235, "Tipologia: Cerrado", fontsize=6.0, va="center", transform=axi.transAxes)


def _draw_metadados_imagem(ax_or_fig, x: float, y: float, meta: dict, transform=None):
    """Caixa 'Metadados imagem' no padrao IMAP (Satelite/Sensor, Data, Orbita/Ponto, Datum)."""
    linhas = [
        ("Satelite/Sensor", meta.get("satelite_sensor") or meta.get("satelite") or "-"),
        ("Data da imagem", meta.get("data_aquisicao") or meta.get("data") or "-"),
        ("Orbita/Ponto", meta.get("orbita_ponto") or meta.get("orbita") or "-"),
        ("Datum", meta.get("datum") or "SIRGAS 2000"),
    ]
    txt = "METADADOS IMAGEM\n" + "\n".join(f"{k}: {v}" for k, v in linhas)
    kw = dict(fontsize=7.0, va="top", ha="left", color=_INK, linespacing=1.6,
              bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#9ca3af", lw=0.9))
    if transform is not None:
        kw["transform"] = transform
    ax_or_fig.text(x, y, txt, **kw)


def _draw_metadados_imagem_band(fig, rect, meta: dict, scale: int):
    """Bloco 'METADADOS IMAGEM' centralizado da faixa inferior (rotulos em negrito)."""
    axm = fig.add_axes(rect)
    axm.axis("off")
    axm.text(0.5, 1.0, "METADADOS IMAGEM", ha="center", va="top", fontsize=9.5,
             fontweight="bold", color=_INK, transform=axm.transAxes)
    linhas = [
        ("Satelite/Sensor", meta.get("satelite_sensor") or meta.get("satelite") or "-"),
        ("Data da imagem", meta.get("data_aquisicao") or meta.get("data") or "-"),
        ("Orbita/Ponto", meta.get("orbita_ponto") or meta.get("orbita") or "-"),
        ("Datum", meta.get("datum") or "SIRGAS 2000"),
        ("Escala", f"1:{scale:,}".replace(",", ".")),
    ]
    y = 0.78
    for k, v in linhas:
        axm.text(0.49, y, k + ":", ha="right", va="top", fontsize=7.4, fontweight="bold",
                 color=_INK, transform=axm.transAxes)
        axm.text(0.51, y, str(v), ha="left", va="top", fontsize=7.4, color=_INK,
                 transform=axm.transAxes)
        y -= 0.165


def _draw_logo(fig, rect, logo_path: str) -> bool:
    """Desenha o logo (PNG) num eixo proprio. Devolve True se conseguiu."""
    if not logo_path or not os.path.exists(logo_path):
        return False
    try:
        import matplotlib.image as mpimg
        img = mpimg.imread(logo_path)
        axl = fig.add_axes(rect)
        axl.imshow(img)
        axl.axis("off")
        return True
    except Exception:
        return False


def _draw_table(fig, rect, tabela: dict):
    """Tabela de dados no padrao IMAP (cabecalho azul, zebra).

    ``tabela`` = {titulo, colunas[], linhas[[]], colunas_grupos?[]}.

    Com ``colunas_grupos`` (multinivel): cada grupo = {titulo, sub[]}.
    O renderer desenha duas linhas de cabecalho com celulas mescladas.
    """
    colunas = tabela.get("colunas") or []
    linhas = tabela.get("linhas") or []
    if not colunas or not linhas:
        return None
    axt = fig.add_axes(rect)
    axt.axis("off")
    titulo = tabela.get("titulo")
    if titulo:
        axt.text(0.5, 1.03, titulo, ha="center", va="bottom", fontsize=8.5,
                 fontweight="bold", color=_INK, transform=axt.transAxes,
                 bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#9ca3af", lw=0.6, alpha=0.95))

    grupos = tabela.get("colunas_grupos")
    if grupos:
        # ── cabeçalho multinível ──
        # linha 0: subcolunas, linha 1: grupos (acima, mesclados)
        sub_labels = []
        for g in grupos:
            sub_labels.extend(g.get("sub", []))
        # build rowLabels + cellText (matplotlib puts rowLabels as the topmost header row)
        # Usamos duas linhas de cabecalho custom: grupos como row 0, subs como row 1.
        # matplotlib.table: row 0 = colLabels (se passado), row 1+ = cellText.
        # Para 2 niveis de cabecalho, passamos os grupos como primeira linha de cellText
        # e tratamos visualmente.
        cell_text = [[str(c) for c in row] for row in linhas]
        # Prepend grupo labels as first data row (will be styled blue)
        grupo_row = []
        for g in grupos:
            tit = g.get("titulo", "")
            nsub = len(g.get("sub", []))
            grupo_row.append(tit)
            # fill remaining sub-columns of this group with empty (merged visually)
            grupo_row.extend([""] * (nsub - 1))
        # Also add the sub-labels as a second header row
        header_rows = [grupo_row, sub_labels]
        full_text = [list(map(str, sub_labels))] + cell_text
        t = axt.table(cellText=full_text, loc="center", cellLoc="center")
        # Style: first row (sub_labels) = blue header, data rows = zebra
        t.auto_set_font_size(False)
        t.set_fontsize(6.6)
        t.scale(1, 1.35)
        n_data_rows = len(cell_text)
        for (r, c), cell in t.get_celld().items():
            cell.set_edgecolor("#9ca3af")
            cell.set_linewidth(0.5)
            if r == 0:
                # sub-label header row
                cell.set_facecolor("#1f4e78")
                cell.set_text_props(color="white", weight="bold", fontsize=6.2)
            else:
                # zebra for data rows
                cell.set_facecolor("#eef3f8" if r % 2 else "white")

        # ── Mesclar células dos grupos (row acima dos sub-labels) ──
        # As células de grupo são desenhadas como um texto extra acima da tabela
        # porque matplotlib.table não suporta merged header cells nativamente.
        # Desenhamos os rótulos dos grupos acima das subcolunas.
        col_offset = 0
        # Get table bbox for positioning
        try:
            fig.canvas.draw()
            tbbox = t.get_window_extent()
            # Convert to axes coords
            inv = axt.transAxes.inverted()
            tbbox_ax = inv.transform(tbbox)
            tx0, ty0 = tbbox_ax[0]
            tx1, ty1 = tbbox_ax[1]
            tw = tx1 - tx0
        except Exception:
            tw = 1.0
            tx0 = 0.0
            ty1 = 1.0

        total_subs = len(sub_labels)
        for g in grupos:
            tit = g.get("titulo", "")
            nsub = len(g.get("sub", []))
            if nsub == 0:
                continue
            frac = nsub / max(total_subs, 1)
            cx = tx0 + (col_offset + nsub / 2) / total_subs * tw
            # acima da tabela
            axt.text(cx / tw if tw else 0.5, ty1 + 0.02, tit,
                     ha="center", va="bottom", fontsize=7.2,
                     fontweight="bold", color="#1f4e78",
                     transform=axt.transAxes)
            col_offset += nsub
    else:
        # ── cabeçalho simples (retrocompatível) ──
        t = axt.table(cellText=[[str(c) for c in row] for row in linhas],
                      colLabels=[str(c) for c in colunas], loc="center", cellLoc="center")
        t.auto_set_font_size(False)
        t.set_fontsize(6.6)
        t.scale(1, 1.35)
        for (r, c), cell in t.get_celld().items():
            cell.set_edgecolor("#9ca3af")
            cell.set_linewidth(0.5)
            if r == 0:
                cell.set_facecolor("#1f4e78")
                cell.set_text_props(color="white", weight="bold")
            else:
                cell.set_facecolor("#eef3f8" if r % 2 else "white")
    return axt


def _rects_overlap(a: tuple, b: tuple) -> float:
    """Area de intersecao entre dois retangulos (x,y,w,h) em fracao da pagina."""
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ix = max(0.0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    iy = max(0.0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    return ix * iy


def _layout_report(fig, regions: dict, element_regions: dict | None = None) -> dict:
    """Detecta sobreposicao entre regioes de topo e texto cortado nas bordas.

    ``element_regions`` (plano 01): rects dos elementos do mobiliario — sao
    comparados apenas entre si (elementos in-map flutuam sobre o mapa por design).
    """
    from itertools import combinations
    from matplotlib.text import Text

    report = {"sobreposicoes": [], "texto_cortado": []}
    itens = [(k, v) for k, v in regions.items() if v is not None]
    for (na, ra), (nb, rb) in combinations(itens, 2):
        if _rects_overlap(ra, rb) > 0.0008:  # ~0.08% da pagina de folga
            report["sobreposicoes"].append(f"{na} x {nb}")
    elems = [(k, v) for k, v in (element_regions or {}).items() if v is not None]
    for (na, ra), (nb, rb) in combinations(elems, 2):
        if _rects_overlap(ra, rb) > 0.0008:
            report["sobreposicoes"].append(f"{na} x {nb}")

    fig.canvas.draw()
    fw, fh = fig.bbox.width, fig.bbox.height
    tol = 2.0
    vistos = set()
    for t in fig.findobj(Text):
        s = (t.get_text() or "").strip()
        if not s:
            continue
        try:
            bb = t.get_window_extent()
        except Exception:
            continue
        if bb.width <= 0 or bb.height <= 0:
            continue
        if bb.x0 < -tol or bb.y0 < -tol or bb.x1 > fw + tol or bb.y1 > fh + tol:
            if s not in vistos:
                report["texto_cortado"].append(s[:24])
                vistos.add(s)
    return report


def _flagship_furniture(fig, ax, spec, project, area, scale, extent,
                        drawn_layers, legend_entries, map_rect, band_rect, on,
                        avisos: list | None = None, regioes: dict | None = None):
    """Mobiliario full-bleed padrao IMAP. Cada peca respeita spec.elementos_layout
    (visibilidade) e spec.layout.elementos (posicao/tamanho, plano 01)."""
    mx, my, mw, mh = map_rect
    layout = spec.layout or {}

    def rect_de(elemento: str, default_rect: tuple) -> tuple:
        r = element_rect(layout, elemento, default_rect, map_rect=map_rect, avisos=avisos)
        if regioes is not None:
            regioes[elemento] = r
        return r

    # rosa-dos-ventos no canto superior direito extremo
    if on("norte"):
        if on("rosa_dos_ventos", True):
            _draw_compass_rose(fig, rect_de("rosa_dos_ventos",
                                            (mx + mw - 0.043, my + mh - 0.058, 0.038, 0.055)))
        else:
            _draw_north(ax)
    # caixa de titulo preta a esquerda da rosa-dos-ventos.
    # Desligar via elementos_layout.titulo_caixa=false ("remova o titulo preto").
    if on("titulo_caixa", True) and spec.titulo:
        tx, ty, tha, tva = element_text_anchor(layout, "titulo", map_rect,
                                               ((mw - 0.058) / mw, 0.985, "right", "top"),
                                               avisos=avisos)
        est = ((layout.get("elementos") or {}).get("titulo") or {}).get("estilo") or {}
        _draw_title_box(ax, spec.titulo, spec.subtitulo, x=tx, y=ty, ha=tha, va=tva,
                        fundo=est.get("fundo", "#2b2b2b"), cor=est.get("cor", "white"),
                        tamanho=float(est.get("tamanho", 16) or 16))
    if on("escala_grafica"):
        pos = None
        cfg = (layout.get("elementos") or {}).get("escala")
        if isinstance(cfg, dict) and cfg:
            ex, ey, eha, eva = element_text_anchor(layout, "escala", map_rect,
                                                   (0.035, 0.035, "left", "bottom"),
                                                   avisos=avisos)
            pos = (ex, ey, eha, eva)
        _draw_scale_bar(ax, extent, scale, pos=pos)

    # inset "Tipologia vegetal" (topo esquerdo)
    if on("inset_tipologia", True):
        tipo_layers = [l for l in drawn_layers if getattr(l, "tema", "") == "tipologia" and l.features]
        _draw_tipologia_inset(fig, rect_de("inset_tipologia",
                                           (mx + 0.006, my + mh - 0.232, 0.205, 0.222)),
                              area, tipo_layers)

    # tabela flutuando sobre o canto inferior direito do mapa
    if on("tabela", True) and spec.tabela:
        tw, th = 0.46, 0.205
        _draw_table(fig, rect_de("tabela", (mx + mw - tw - 0.005, my + 0.006, tw, th)), spec.tabela)

    # ---- faixa inferior: [localizacao] [METADADOS IMAGEM] [Legenda] [logo] ----
    if band_rect is not None:
        bx, by, bw, bh = band_rect
        if on("minimapa", True):
            _draw_minimap(fig, rect_de("minimapa", (0.02, by + 0.012, 0.10, bh - 0.02)),
                          area, extent, project.crs.utm, "light")
        if on("metadados_imagem", True) and spec.metadados_imagem:
            _draw_metadados_imagem_band(fig, rect_de("metadados_imagem",
                                                     (0.19, by + 0.005, 0.24, bh - 0.01)),
                                        spec.metadados_imagem, scale)
        if on("legenda") and legend_entries:
            leg_cfg = spec.legenda or {}
            leg_rect = rect_de("legenda", (0.52, by + 0.012, 0.30, bh - 0.02))
            pos_cfg = leg_cfg.get("posicao")
            if isinstance(pos_cfg, dict) and pos_cfg:
                leg_rect = element_rect({"elementos": {"legenda": pos_cfg}}, "legenda",
                                        leg_rect, map_rect=map_rect, avisos=avisos)
                if regioes is not None:
                    regioes["legenda"] = leg_rect
            _draw_legend_swatches(fig, leg_rect, legend_entries, titulo=_legend_title(spec),
                                  ncols=int(leg_cfg.get("colunas", 1) or 1),
                                  fontsize=float(leg_cfg.get("fonte_tamanho", 8.0) or 8.0))
        if on("logo", True) and spec.marca:
            logo_rect = rect_de("logo", (0.85, by + 0.01, 0.12, bh - 0.02))
            logo_path = _resolver_caminho(project, str(spec.marca.get("logo", "")))
            logo_ok = _draw_logo(fig, logo_rect, logo_path) if logo_path else False
            if not logo_ok and spec.marca.get("texto"):
                fig.text(logo_rect[0] + logo_rect[2] / 2, logo_rect[1] + logo_rect[3] / 2,
                         str(spec.marca.get("texto")), ha="center", va="center",
                         fontsize=13, fontweight="bold", color="#17324d")


def _legend_title(spec) -> str:
    return str(((getattr(spec, "legenda", None) or {}).get("titulo")) or "Legenda")


def _standard_furniture(fig, ax, spec, project, area, scale, extent,
                        drawn_layers, legend_entries, map_rect, panel_rect,
                        band_rect, landscape, on, avisos: list | None = None,
                        regioes: dict | None = None):
    """Mobiliario com painel lateral/inferior (mapas simples, retrato, sem satelite)."""
    layout = spec.layout or {}
    if on("norte"):
        nx, ny, _, _ = element_text_anchor(layout, "rosa_dos_ventos", map_rect,
                                           (0.962, 0.935, "center", "center"), avisos=avisos)
        _draw_north(ax, x=nx, y=ny)
    if on("escala_grafica"):
        pos = None
        cfg = (layout.get("elementos") or {}).get("escala")
        if isinstance(cfg, dict) and cfg:
            ex, ey, eha, eva = element_text_anchor(layout, "escala", map_rect,
                                                   (0.035, 0.035, "left", "bottom"),
                                                   avisos=avisos)
            pos = (ex, ey, eha, eva)
        _draw_scale_bar(ax, extent, scale, pos=pos)

    cx_map = map_rect[0] + map_rect[2] / 2
    top_map = map_rect[1] + map_rect[3]
    if spec.titulo:
        fig.text(cx_map, min(0.99, top_map + 0.055), spec.titulo, ha="center",
                 fontsize=17, fontweight="bold", color=_INK, va="top")
    subtitle = spec.subtitulo or (
        f"{project.municipio.nome}/{project.municipio.uf}  |  SIRGAS 2000 / UTM "
        f"(EPSG:{project.crs.utm})  |  Escala 1:{scale:,}".replace(",", ".")
        + f"  |  {project.data_consulta_efetiva()}")
    fig.text(cx_map, min(0.96, top_map + 0.028), subtitle, ha="center",
             fontsize=8.5, color=_MUTED, va="top")

    if panel_rect is None:
        return
    panel = fig.add_axes(panel_rect)
    panel.axis("off")
    panel.add_patch(patches.FancyBboxPatch((0, 0), 1, 1, transform=panel.transAxes,
                                           boxstyle="round,pad=0.008,rounding_size=0.015",
                                           facecolor="#f8fafc", edgecolor="#d1d5db", linewidth=0.8))
    leg_cfg = spec.legenda or {}
    leg_fs = float(leg_cfg.get("fonte_tamanho", 0) or 0)
    if landscape:
        panel.text(0.07, 0.975, _legend_title(spec), fontsize=11, fontweight="bold",
                   color=_INK, va="top")
        if legend_entries and on("legenda"):
            panel.legend(handles=legend_entries, loc="upper left", bbox_to_anchor=(0.04, 0.955),
                         frameon=False, fontsize=leg_fs or 7.4,
                         ncols=int(leg_cfg.get("colunas", 1) or 1),
                         handlelength=1.6, borderaxespad=0)
        meta_y = 0.60
    else:
        if legend_entries and on("legenda"):
            panel.legend(handles=legend_entries, loc="upper left", bbox_to_anchor=(0.03, 0.97),
                         frameon=False, fontsize=leg_fs or 7.2,
                         ncols=int(leg_cfg.get("colunas", 2) or 2),
                         handlelength=1.5, borderaxespad=0)
        meta_y = 0.50

    if on("metadados"):
        area_fmt = f"{area.area_ha:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
        metadata = [
            f"Projeto: {project.nome}",
            f"Cliente: {project.cliente or '-'}",
            f"Area: {area_fmt} ha  |  Feicoes: {area.feature_count}",
            f"Fonte da area: {os.path.basename(project.area_base_path())}",
            f"Datum: SIRGAS 2000  |  Escala 1:{scale:,}".replace(",", "."),
        ]
        x_meta = 0.07 if landscape else 0.52
        panel.text(x_meta, meta_y + 0.045, "Metadados", fontsize=10, fontweight="bold", color=_INK, va="bottom")
        panel.text(x_meta, meta_y, "\n".join(metadata), fontsize=7.2, color=_MUTED, va="top", linespacing=1.7)

    if on("minimapa"):
        if landscape:
            mini_rect = (panel_rect[0] + 0.028, panel_rect[1] + 0.035,
                         panel_rect[2] - 0.056, panel_rect[3] * 0.30)
        else:
            mini_rect = (panel_rect[0] + panel_rect[2] - 0.20, panel_rect[1] + 0.015,
                         0.185, panel_rect[3] * 0.62)
        mini_rect = element_rect(layout, "minimapa", mini_rect, map_rect=map_rect, avisos=avisos)
        if regioes is not None:
            regioes["minimapa"] = mini_rect
        _draw_minimap(fig, mini_rect, area, extent, project.crs.utm, "light")


def render_pdf_map(project: NexoMapProject, spec: MapSpec, catalog: dict, job_dir: str,
                   manifest: dict | None = None, drawn_layers: list | None = None,
                   use_basemap: bool = True) -> dict:
    """Renderiza o mapa oficial (PDF + PNGs + validacao) sem ArcMap."""
    os.makedirs(job_dir, exist_ok=True)
    pdf_path = os.path.join(job_dir, "mapa.pdf")
    preview_path = os.path.join(job_dir, "preview.png")
    validation_png_path = os.path.join(job_dir, "png_validacao.png")
    validation_path = os.path.join(job_dir, "validacao.json")
    manifest = manifest or {"templates": []}
    drawn_layers = drawn_layers or []
    render_warnings: list[str] = []

    page_w_mm, page_h_mm = _page_mm(spec, manifest)
    fig = plt.figure(figsize=(page_w_mm * MM, page_h_mm * MM), facecolor="white")

    # "flagship" = layout padrao IMAP (satelite full-bleed + faixa inferior com
    # logo / metadados-imagem / tabela). Ativa quando o MapSpec traz esses campos.
    flagship = bool(spec.metadados_imagem or spec.tabela or spec.marca)

    # geometria do layout (fracoes da pagina)
    landscape = page_w_mm >= page_h_mm
    if landscape and flagship:
        map_rect = (0.035, 0.155, 0.935, 0.80)   # full-bleed
        panel_rect = None
        band_rect = (0.0, 0.0, 1.0, 0.135)        # faixa inferior full-width
    elif landscape:
        map_rect = (0.045, 0.075, 0.655, 0.83)
        panel_rect = (0.725, 0.075, 0.245, 0.83)
        band_rect = None
    else:
        map_rect = (0.06, 0.30, 0.88, 0.62)
        panel_rect = (0.06, 0.045, 0.88, 0.22)
        band_rect = None

    with abrir_shape_zip(project.area_base_path(), project.crs.utm, project.crs.geografico) as area:
        bbox = area.bbox_utm
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2

        # escala verdadeira: extent = quadro (mm no papel) x escala
        frame_w_m = page_w_mm * map_rect[2] / 1000.0
        frame_h_m = page_h_mm * map_rect[3] / 1000.0
        if isinstance(spec.escala, (int, float)) and float(spec.escala) > 0:
            scale = int(spec.escala)
        else:
            scale = _auto_scale(bbox, frame_w_m, frame_h_m)
        half_w = frame_w_m * scale / 2.0
        half_h = frame_h_m * scale / 2.0
        extent = (cx - half_w, cx + half_w, cy - half_h, cy + half_h)

        ax = fig.add_axes(map_rect)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_facecolor("#eef2f7")

        # fundo do mapa: 1) raster local (GeoTIFF); 2) tiles; 3) neutro
        credito_basemap = ""
        fundo_desenhado = False
        if spec.raster_fundo:
            from core import raster as raster_mod
            bg, warn = raster_mod.load_raster_background(
                _resolver_caminho(project, spec.raster_fundo), project.crs.utm,
                (extent[0], extent[2], extent[1], extent[3]))
            if bg:
                ax.imshow(bg.image, extent=bg.extent, origin="upper",
                          interpolation="bilinear", zorder=1)
                credito_basemap = f"Imagem: {bg.fonte}"
                fundo_desenhado = True
            elif warn:
                render_warnings.append(warn)
        if not fundo_desenhado and use_basemap and spec.basemap not in ("none", "nenhum"):
            bm = basemap_mod.fetch_basemap_utm((extent[0], extent[2], extent[1], extent[3]),
                                               project.crs.utm, style=spec.basemap)
            if bm:
                img, ext, credito_basemap = bm
                ax.imshow(img, extent=ext, origin="upper", interpolation="bilinear", zorder=1)
                fundo_desenhado = True
            else:
                render_warnings.append("basemap indisponivel (sem internet ou provedor fora do ar); fundo neutro usado")
        fundo_escuro = fundo_desenhado  # imagem/satelite => rotulos claros

        # camadas do catalogo (dados reais via WFS/GML/REST/WMS)
        auto_entries: list[tuple[str, object]] = []
        for layer in drawn_layers:
            line, fill, alpha, hatch = _layer_color(layer.estilo, layer.tema)
            if getattr(layer, "image", None) is not None:
                # camada raster (WMS GetMap): overlay de imagem com opacidade
                ax.imshow(layer.image, extent=layer.image_extent, origin="upper",
                          interpolation="bilinear", alpha=alpha, zorder=4)
                auto_entries.append((layer.id,
                                     patches.Patch(facecolor=line, edgecolor="#6b7280",
                                                   alpha=max(alpha, 0.5), label=layer.nome)))
                continue
            if layer.features:
                _draw_geoms(ax, layer.features, line, fill, alpha, hatch=hatch)
                if layer.rotulo:
                    _label_features(ax, layer)
            suffix = f" ({layer.feature_count})" if layer.features else " (sem feicoes no recorte)"
            auto_entries.append((layer.id,
                                 patches.Patch(facecolor=(fill if fill != "none" else "white"),
                                               edgecolor=line, alpha=max(alpha, 0.35),
                                               hatch=hatch or None, label=layer.nome + suffix)))

        # perimetro da area base
        perimeter_layer = next((l for l in spec.camadas if l.fonte == "area_base"), None)
        peri_style = perimeter_layer.estilo if perimeter_layer else {}
        _draw_perimeter(ax, area, peri_style, bool(perimeter_layer.rotulo) if perimeter_layer else False)
        auto_entries.insert(0, ("perimetro", Line2D([0], [0], color=peri_style.get("linha", "#ff3b30"),
                                                    lw=2.4, label=f"Perimetro do imovel ({area.feature_count})")))

        # legenda editavel (plano 02): auto (atual) / manual / misto
        legend_entries, legend_avisos = _montar_legenda(
            spec.legenda or {}, auto_entries, {l.id: l for l in drawn_layers})
        render_warnings.extend(legend_avisos)

        # grade de coordenadas: DMS (padrao IMAP) ou UTM
        mostrar_grade = bool(spec.elementos_layout.get("grade", True))
        if spec.grade_tipo == "utm":
            if mostrar_grade:
                ax.grid(True, color="#64748b", alpha=0.35, linewidth=0.5, linestyle=(0, (6, 4)))
            ax.xaxis.set_major_locator(MaxNLocator(5, steps=[1, 2, 5]))
            ax.yaxis.set_major_locator(MaxNLocator(6, steps=[1, 2, 5]))
            ax.xaxis.set_major_formatter(FuncFormatter(_fmt_coord))
            ax.yaxis.set_major_formatter(FuncFormatter(_fmt_coord))
            ax.tick_params(labelsize=6.5, colors=_MUTED, length=3)
            plt.setp(ax.get_yticklabels(), rotation=90, va="center")
        else:
            _draw_graticule_dms(ax, extent, project.crs.utm, project.crs.geografico, mostrar_grade)
        for spine in ax.spines.values():
            spine.set_color(_INK)
            spine.set_linewidth(1.2)

        # ============================================================= #
        # Mobiliario do mapa — TODOS os elementos sao ligaveis/desligaveis
        # pela IA via spec.elementos_layout (a IA controla o layout, nada e
        # cravado no codigo). Ex.: elementos_layout.titulo_caixa=false remove
        # a caixa de titulo preta.
        # ============================================================= #
        el = spec.elementos_layout or {}

        def on(chave: str, padrao: bool = True) -> bool:
            return bool(el.get(chave, padrao))

        regioes_elementos: dict = {}
        if flagship:
            _flagship_furniture(fig, ax, spec, project, area, scale, extent,
                                drawn_layers, legend_entries, map_rect, band_rect, on,
                                avisos=render_warnings, regioes=regioes_elementos)
        else:
            _standard_furniture(fig, ax, spec, project, area, scale, extent,
                                 drawn_layers, legend_entries, map_rect, panel_rect,
                                 band_rect, landscape, on,
                                 avisos=render_warnings, regioes=regioes_elementos)

        # rodape de creditos
        fontes = sorted({layer.nome for layer in drawn_layers})
        credito = "Fontes: " + ("; ".join(fontes) if fontes else "area do projeto")
        if credito_basemap:
            credito += f".  {credito_basemap}"
        credito += ".  Gerado pelo NexoGeo Ambiental (motor nativo, sem ArcMap)."
        cred_y = 0.006 if band_rect is None else 0.001
        fig.text(map_rect[0], cred_y, credito, fontsize=6.0, color="#6b7280", va="bottom")

        # relatorio de layout (sobreposicao/corte de texto) antes de salvar
        regioes = {"mapa": map_rect, "painel": panel_rect, "faixa": band_rect}
        layout_report = _layout_report(fig, regioes, regioes_elementos)

        fig.savefig(pdf_path, dpi=200)
        fig.savefig(preview_path, dpi=130)
        plt.close(fig)

        area_summary = {
            "area_ha": area.area_ha,
            "feature_count": area.feature_count,
            "bbox_utm": list(area.bbox_utm),
        }

    validation = validate_pdf(pdf_path, validation_png_path, spec.titulo,
                              map_region=map_rect, layout_report=layout_report)
    validation["escala"] = scale
    validation["camadas_desenhadas"] = [
        {"id": l.id, "nome": l.nome, "feicoes": l.feature_count} for l in drawn_layers
    ]
    validation["render_warnings"] = render_warnings
    write_validation_report(validation_path, validation)
    with open(os.path.join(job_dir, "mapspec.json"), "w", encoding="utf-8") as f:
        json.dump(spec.to_dict(), f, indent=2, ensure_ascii=False)

    return {
        "pdf": pdf_path,
        "preview_png": preview_path,
        "png_validacao": validation_png_path,
        "validacao": validation_path,
        "validacao_result": validation,
        "escala": scale,
        "area": area_summary,
        "render_warnings": render_warnings,
    }
