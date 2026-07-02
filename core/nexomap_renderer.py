# -*- coding: utf-8 -*-
"""Fallback PDF/PNG renderer for NexoMap AI.

The renderer creates a validated cartographic draft without ArcGIS. Real MXD
production is handled by ``core.arcgis_bridge`` when ArcMap/templates exist.
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
from matplotlib import patches  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from core.geo import abrir_shape_zip
from core.mapspec import MapSpec
from core.nexomap_catalog import layer_index
from core.nexomap_geo import iter_polygons, scale_suggestion_from_bbox
from core.nexomap_project import NexoMapProject
from core.nexomap_validation import validate_pdf, write_validation_report


def _expand_bbox(bounds: tuple[float, float, float, float], fraction: float = 0.08) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    dx = max(maxx - minx, 1.0)
    dy = max(maxy - miny, 1.0)
    return (minx - dx * fraction, miny - dy * fraction, maxx + dx * fraction, maxy + dy * fraction)


def _plot_geom(ax, geom, line: str = "#ff3b30", fill: str | None = None, width: float = 2.2, alpha: float = 0.2):
    for poly in iter_polygons(geom):
        x, y = poly.exterior.xy
        ax.plot(x, y, color=line, linewidth=width)
        if fill and fill != "transparente":
            ax.fill(x, y, color=fill, alpha=alpha)
        for ring in poly.interiors:
            ix, iy = ring.xy
            ax.plot(ix, iy, color=line, linewidth=max(0.8, width * 0.6))


def _draw_north(ax):
    ax.annotate("N", xy=(0.955, 0.9), xytext=(0.955, 0.78), xycoords="axes fraction",
                ha="center", va="center", color="#0f172a", fontsize=12, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="#0f172a", lw=1.5))


def _draw_scale_bar(ax, bbox: tuple[float, float, float, float]):
    minx, miny, maxx, maxy = bbox
    width = maxx - minx
    bar_m = max(100, round((width / 5) / 100.0) * 100)
    x0 = minx + width * 0.06
    y0 = miny + (maxy - miny) * 0.055
    ax.plot([x0, x0 + bar_m], [y0, y0], color="#0f172a", linewidth=4, solid_capstyle="butt")
    ax.text(x0, y0 + (maxy - miny) * 0.025, "0", fontsize=8, color="#0f172a")
    ax.text(x0 + bar_m, y0 + (maxy - miny) * 0.025, f"{bar_m/1000:g} km", fontsize=8, color="#0f172a", ha="right")


def _legend_items(spec: MapSpec, catalog: dict):
    items = []
    catalog_layers = layer_index(catalog)
    for layer in spec.camadas:
        if layer.fonte == "area_base":
            items.append(Line2D([0], [0], color=layer.estilo.get("linha", "#ff3b30"), lw=2.4,
                                label="Perimetro do projeto"))
            continue
        cid = layer.fonte.split(".", 1)[1] if layer.fonte.startswith("catalogo.") else layer.id
        color = layer.estilo.get("linha") or layer.estilo.get("preenchimento") or "#64748b"
        label = catalog_layers.get(cid, {}).get("nome", cid)
        items.append(patches.Patch(facecolor=color, edgecolor=color, alpha=0.45, label=label))
    return items


def render_pdf_map(project: NexoMapProject, spec: MapSpec, catalog: dict, job_dir: str) -> dict:
    os.makedirs(job_dir, exist_ok=True)
    pdf_path = os.path.join(job_dir, "mapa.pdf")
    preview_path = os.path.join(job_dir, "preview.png")
    validation_png_path = os.path.join(job_dir, "png_validacao.png")
    validation_path = os.path.join(job_dir, "validacao.json")

    with abrir_shape_zip(project.area_base_path(), project.crs.utm, project.crs.geografico) as area:
        bbox = _expand_bbox(area.bbox_utm)
        scale = scale_suggestion_from_bbox(area.bbox_utm) if spec.escala == "auto" else spec.escala

        fig = plt.figure(figsize=(16.54, 11.69), facecolor="#f8fafc")
        ax = fig.add_axes([0.055, 0.115, 0.69, 0.77])
        panel = fig.add_axes([0.77, 0.115, 0.18, 0.77])
        panel.axis("off")

        ax.set_facecolor("#dbeafe" if spec.basemap == "light" else "#14251f")
        ax.grid(bool(spec.elementos_layout.get("grade", True)), color="#94a3b8", alpha=0.32, linewidth=0.55)
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])
        ax.set_aspect("equal", adjustable="box")
        ax.ticklabel_format(style="plain")
        ax.tick_params(labelsize=8, colors="#334155")

        perimeter_layer = next((layer for layer in spec.camadas if layer.fonte == "area_base"), None)
        style = perimeter_layer.estilo if perimeter_layer else {}
        _plot_geom(
            ax,
            area.union_utm,
            line=style.get("linha", "#ff3b30"),
            fill=style.get("preenchimento"),
            width=float(style.get("largura", 2.4) or 2.4),
            alpha=0.12,
        )

        if spec.elementos_layout.get("norte", True):
            _draw_north(ax)
        if spec.elementos_layout.get("escala_grafica", True):
            _draw_scale_bar(ax, bbox)

        fig.text(0.055, 0.935, spec.titulo, fontsize=22, fontweight="bold", color="#0f172a")
        fig.text(0.055, 0.91, f"{project.municipio.nome}/{project.municipio.uf} | EPSG:{project.crs.utm} | Escala 1:{scale}",
                 fontsize=11, color="#475569")

        panel.text(0.0, 0.98, "Legenda", fontsize=14, fontweight="bold", color="#0f172a", va="top")
        handles = _legend_items(spec, catalog)
        if handles:
            panel.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 0.93), frameon=False, fontsize=9)
        panel.text(0.0, 0.55, "Metadados", fontsize=13, fontweight="bold", color="#0f172a")
        metadata = [
            f"Projeto: {project.nome}",
            f"Cliente: {project.cliente or '-'}",
            f"Data: {project.data_consulta_efetiva()}",
            f"Area: {area.area_ha:,.4f} ha".replace(",", "X").replace(".", ",").replace("X", "."),
            f"Feicoes: {area.feature_count}",
            f"Fonte base: {os.path.basename(project.area_base_path())}",
        ]
        panel.text(0.0, 0.51, "\n".join(metadata), fontsize=9.5, color="#334155", va="top", linespacing=1.55)
        panel.text(0.0, 0.19, "Camadas externas", fontsize=13, fontweight="bold", color="#0f172a")
        external = [layer.fonte.replace("catalogo.", "") for layer in spec.camadas if layer.fonte.startswith("catalogo.")]
        panel.text(0.0, 0.155, "\n".join(external) if external else "Nenhuma", fontsize=8.8, color="#475569", va="top")
        panel.text(0.0, 0.02, "NexoMap AI - validacao automatica", fontsize=8, color="#64748b")

        fig.savefig(pdf_path, dpi=180, bbox_inches="tight")
        fig.savefig(preview_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    validation = validate_pdf(pdf_path, validation_png_path, spec.titulo)
    write_validation_report(validation_path, validation)
    with open(os.path.join(job_dir, "mapspec.json"), "w", encoding="utf-8") as f:
        json.dump(spec.to_dict(), f, indent=2, ensure_ascii=False)

    return {
        "pdf": pdf_path,
        "preview_png": preview_path,
        "png_validacao": validation_png_path,
        "validacao": validation_path,
        "validacao_result": validation,
    }
