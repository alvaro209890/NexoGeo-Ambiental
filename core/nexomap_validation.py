# -*- coding: utf-8 -*-
"""PDF and rendered-image validation for NexoMap AI."""
from __future__ import annotations

import json
import os

import fitz


def validate_pdf(pdf_path: str, png_path: str, expected_title: str) -> dict:
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

    result["ok"] = all(check["ok"] for check in checks)
    return result


def write_validation_report(path: str, report: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
