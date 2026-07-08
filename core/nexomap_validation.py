# -*- coding: utf-8 -*-
"""PDF and rendered-image validation for NexoMap AI."""
from __future__ import annotations

import json
import os

import fitz


def validate_pdf(pdf_path: str, png_path: str, expected_title: str,
                 map_region: tuple | None = None, layout_report: dict | None = None) -> dict:
    """Valida o PDF/PNG do mapa.

    Alem dos checks basicos (abre, titulo, pagina nao vazia), quando informados:
    - ``map_region`` = (x0, y0, w, h) em fracao da pagina -> confere que o quadro
      do mapa tem imagem/camadas (variancia de cor), i.e. nao esta em branco.
    - ``layout_report`` do renderer -> confere sem sobreposicao de elementos e
      sem texto cortado nas bordas.
    """
    checks = []
    result = {
        "ok": False,
        "pdf": pdf_path,
        "png_validacao": png_path,
        "checks": checks,
    }

    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("pdf_existe", os.path.exists(pdf_path), pdf_path)
    if not os.path.exists(pdf_path):
        return result
    size = os.path.getsize(pdf_path)
    add("pdf_tamanho_minimo", size > 1000, f"{size} bytes")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        add("pdf_abre", False, str(e))
        return result
    add("pdf_abre", True, f"{doc.page_count} pagina(s)")
    add("pdf_tem_pagina", doc.page_count > 0, str(doc.page_count))
    if doc.page_count <= 0:
        return result

    page = doc[0]
    text = page.get_text() or ""
    title_ok = expected_title.lower() in text.lower()
    add("titulo_presente", title_ok, expected_title)

    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    pix.save(png_path)
    add("png_validacao_salvo", os.path.exists(png_path), png_path)

    samples = pix.samples
    step = max(1, len(samples) // 30000)
    unique = len(set(samples[::step]))
    nonblank = unique > 8
    add("pagina_nao_vazia", nonblank, f"amostras_unicas={unique}")

    # imagem/camadas presentes no quadro do mapa (nao em branco)
    if map_region is not None:
        std, detalhe = _region_color_std(pix, map_region)
        add("mapa_tem_imagem", std > 6.0, f"std_cor={std:.1f} ({detalhe})")

    # relatorio de layout do renderer
    if layout_report is not None:
        overlaps = layout_report.get("sobreposicoes") or []
        add("sem_sobreposicao_elementos", not overlaps,
            "; ".join(overlaps) if overlaps else "ok")
        clipped = layout_report.get("texto_cortado") or []
        add("sem_texto_cortado", not clipped,
            (f"{len(clipped)} artefato(s): " + "; ".join(clipped[:3])) if clipped else "ok")

    result["ok"] = all(check["ok"] for check in checks)
    return result


def _region_color_std(pix, region: tuple) -> tuple[float, str]:
    """Desvio-padrao medio de cor numa regiao (fracao da pagina) do pixmap."""
    x0f, y0f, wf, hf = region
    W, H = pix.width, pix.height
    n = pix.n  # canais por pixel
    samples = pix.samples
    x0 = int(x0f * W); x1 = int((x0f + wf) * W)
    y0 = int((1 - y0f - hf) * H); y1 = int((1 - y0f) * H)  # fracao com origem embaixo -> topo
    x0, x1 = max(0, min(x0, W)), max(0, min(x1, W))
    y0, y1 = max(0, min(y0, H)), max(0, min(y1, H))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0, "regiao pequena"
    # amostra em grade para nao varrer tudo
    import statistics
    vals_r, vals_g, vals_b = [], [], []
    sx = max(1, (x1 - x0) // 40)
    sy = max(1, (y1 - y0) // 40)
    for yy in range(y0, y1, sy):
        row = yy * W * n
        for xx in range(x0, x1, sx):
            idx = row + xx * n
            vals_r.append(samples[idx])
            vals_g.append(samples[idx + 1] if n > 1 else samples[idx])
            vals_b.append(samples[idx + 2] if n > 2 else samples[idx])
    if len(vals_r) < 4:
        return 0.0, "poucas amostras"
    std = (statistics.pstdev(vals_r) + statistics.pstdev(vals_g) + statistics.pstdev(vals_b)) / 3
    return std, f"{len(vals_r)} amostras"


def write_validation_report(path: str, report: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
