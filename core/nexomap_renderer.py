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


def _layer_color(layer_spec_estilo: dict, tema: str) -> tuple[str, str, float]:
    line = layer_spec_estilo.get("linha")
    fill = layer_spec_estilo.get("preenchimento")
    base = line or fill or THEME_COLORS.get(tema, "#64748b")
    alpha = float(layer_spec_estilo.get("opacidade", 0.4) or 0.4)
    return (line or base), (fill if fill not in (None, "", "transparente") else base), alpha


def _draw_geoms(ax, feats, line: str, fill: str, alpha: float, lw: float = 1.1, zorder: int = 6):
    for feat in feats:
        geom = feat.geom
        gtype = geom.geom_type
        if gtype in ("Polygon", "MultiPolygon", "GeometryCollection"):
            for poly in iter_polygons(geom):
                xs, ys = poly.exterior.xy
                ax.fill(xs, ys, facecolor=fill, edgecolor=line, linewidth=lw, alpha=alpha, zorder=zorder)
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


def _draw_north(ax):
    x, y = 0.962, 0.935
    ax.annotate("", xy=(x, y), xytext=(x, y - 0.075), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="fancy,head_width=0.55,head_length=0.9",
                                facecolor=_INK, edgecolor="white", linewidth=0.8),
                zorder=20, annotation_clip=False)
    txt = ax.text(x, y + 0.014, "N", transform=ax.transAxes, ha="center", va="bottom",
                  fontsize=13, fontweight="bold", color=_INK, zorder=20)
    txt.set_path_effects([patheffects.withStroke(linewidth=2.5, foreground="white")])


def _draw_scale_bar(ax, extent: tuple, scale: int):
    minx, maxx, miny, maxy = extent
    width = maxx - minx
    height = maxy - miny
    total = _nice_length(width * 0.28)
    seg = total / 4.0
    x0 = minx + width * 0.035
    y0 = miny + height * 0.035
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

    # geometria do layout (fracoes da pagina)
    landscape = page_w_mm >= page_h_mm
    if landscape:
        map_rect = (0.045, 0.075, 0.655, 0.83)
        panel_rect = (0.725, 0.075, 0.245, 0.83)
    else:
        map_rect = (0.06, 0.30, 0.88, 0.62)
        panel_rect = (0.06, 0.045, 0.88, 0.22)

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

        # basemap
        credito_basemap = ""
        if use_basemap and spec.basemap not in ("none", "nenhum"):
            bm = basemap_mod.fetch_basemap_utm((extent[0], extent[2], extent[1], extent[3]),
                                               project.crs.utm, style=spec.basemap)
            if bm:
                img, ext, credito_basemap = bm
                ax.imshow(img, extent=ext, origin="upper", interpolation="bilinear", zorder=1)
            else:
                render_warnings.append("basemap indisponivel (sem internet ou provedor fora do ar); fundo neutro usado")

        # camadas do catalogo (dados reais via WFS)
        legend_entries: list = []
        for layer in drawn_layers:
            line, fill, alpha = _layer_color(layer.estilo, layer.tema)
            if layer.features:
                _draw_geoms(ax, layer.features, line, fill, alpha)
            suffix = f" ({layer.feature_count})" if layer.features else " (sem feicoes no recorte)"
            legend_entries.append(patches.Patch(facecolor=fill, edgecolor=line, alpha=max(alpha, 0.35),
                                                label=layer.nome + suffix))

        # perimetro da area base
        perimeter_layer = next((l for l in spec.camadas if l.fonte == "area_base"), None)
        peri_style = perimeter_layer.estilo if perimeter_layer else {}
        _draw_perimeter(ax, area, peri_style, bool(perimeter_layer.rotulo) if perimeter_layer else False)
        legend_entries.insert(0, Line2D([0], [0], color=peri_style.get("linha", "#ff3b30"),
                                        lw=2.4, label=f"Perimetro do imovel ({area.feature_count})"))

        # grade de coordenadas UTM
        if spec.elementos_layout.get("grade", True):
            ax.grid(True, color="#64748b", alpha=0.35, linewidth=0.5, linestyle=(0, (6, 4)))
        ax.xaxis.set_major_locator(MaxNLocator(5, steps=[1, 2, 5]))
        ax.yaxis.set_major_locator(MaxNLocator(6, steps=[1, 2, 5]))
        ax.xaxis.set_major_formatter(FuncFormatter(_fmt_coord))
        ax.yaxis.set_major_formatter(FuncFormatter(_fmt_coord))
        ax.tick_params(labelsize=6.5, colors=_MUTED, length=3)
        plt.setp(ax.get_yticklabels(), rotation=90, va="center")
        for spine in ax.spines.values():
            spine.set_color(_INK)
            spine.set_linewidth(1.2)

        if spec.elementos_layout.get("norte", True):
            _draw_north(ax)
        if spec.elementos_layout.get("escala_grafica", True):
            _draw_scale_bar(ax, extent, scale)

        # titulo
        fig.text(map_rect[0], 0.965 if landscape else 0.975, spec.titulo,
                 fontsize=17, fontweight="bold", color=_INK, va="top")
        subtitle = (f"{project.municipio.nome}/{project.municipio.uf}  |  SIRGAS 2000 / UTM "
                    f"(EPSG:{project.crs.utm})  |  Escala 1:{scale:,}".replace(",", ".")
                    + f"  |  {project.data_consulta_efetiva()}")
        fig.text(map_rect[0], 0.937 if landscape else 0.952, subtitle, fontsize=8.5, color=_MUTED, va="top")

        # painel lateral/inferior: legenda + metadados + minimapa
        panel = fig.add_axes(panel_rect)
        panel.axis("off")
        panel.add_patch(patches.FancyBboxPatch((0, 0), 1, 1, transform=panel.transAxes,
                                               boxstyle="round,pad=0.008,rounding_size=0.015",
                                               facecolor="#f8fafc", edgecolor="#d1d5db", linewidth=0.8))

        if landscape:
            panel.text(0.07, 0.975, "Legenda", fontsize=11, fontweight="bold", color=_INK, va="top")
            if legend_entries and spec.elementos_layout.get("legenda", True):
                panel.legend(handles=legend_entries, loc="upper left", bbox_to_anchor=(0.04, 0.955),
                             frameon=False, fontsize=7.4, handlelength=1.6, borderaxespad=0)
            meta_y = 0.60
        else:
            if legend_entries and spec.elementos_layout.get("legenda", True):
                panel.legend(handles=legend_entries, loc="upper left", bbox_to_anchor=(0.03, 0.97),
                             frameon=False, fontsize=7.2, ncols=2, handlelength=1.5, borderaxespad=0)
            meta_y = 0.50

        if spec.elementos_layout.get("metadados", True):
            area_fmt = f"{area.area_ha:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
            metadata = [
                f"Projeto: {project.nome}",
                f"Cliente: {project.cliente or '-'}",
                f"Area: {area_fmt} ha  |  Feicoes: {area.feature_count}",
                f"Fonte da area: {os.path.basename(project.area_base_path())}",
                "Datum: SIRGAS 2000  |  Motor: NexoMap nativo",
            ]
            x_meta = 0.07 if landscape else 0.52
            panel.text(x_meta, meta_y + 0.045, "Metadados", fontsize=10, fontweight="bold", color=_INK, va="bottom")
            panel.text(x_meta, meta_y, "\n".join(metadata), fontsize=7.2, color=_MUTED,
                       va="top", linespacing=1.7)

        if spec.elementos_layout.get("minimapa", True):
            if landscape:
                mini_rect = (panel_rect[0] + 0.028, panel_rect[1] + 0.035,
                             panel_rect[2] - 0.056, panel_rect[3] * 0.30)
            else:
                mini_rect = (panel_rect[0] + panel_rect[2] - 0.20, panel_rect[1] + 0.015,
                             0.185, panel_rect[3] * 0.62)
            _draw_minimap(fig, mini_rect, area, extent, project.crs.utm, "light")

        # rodape de creditos
        fontes = sorted({layer.nome for layer in drawn_layers})
        credito = "Fontes: " + ("; ".join(fontes) if fontes else "area do projeto")
        if credito_basemap:
            credito += f".  {credito_basemap}"
        credito += ".  Gerado pelo NexoGeo Ambiental (motor nativo, sem ArcMap)."
        fig.text(map_rect[0], 0.018, credito, fontsize=6.4, color="#6b7280")

        fig.savefig(pdf_path, dpi=200)
        fig.savefig(preview_path, dpi=130)
        plt.close(fig)

        area_summary = {
            "area_ha": area.area_ha,
            "feature_count": area.feature_count,
            "bbox_utm": list(area.bbox_utm),
        }

    validation = validate_pdf(pdf_path, validation_png_path, spec.titulo)
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
