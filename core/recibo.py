# -*- coding: utf-8 -*-
"""core.recibo — leitura do recibo de inscrição do CAR (PDF) via PyMuPDF.

Extrai a seção "Dados das Áreas dos Imóveis Rurais" (Documento – Tipo – Área),
tratando rótulos de documento quebrados em duas linhas e os tipos Matrícula/Posse.
Porta do parser do antigo ``gerar_contexto_ambiental.py``, agora genérico.
"""
from __future__ import annotations

import os
import fitz  # PyMuPDF

from core import io


def _secao(lines: list[str], ini: str, fins: list[str]) -> list[str]:
    """Linhas entre o título ``ini`` e o primeiro título de ``fins``."""
    if ini not in lines:
        return []
    a = lines.index(ini)
    b = len(lines)
    for f in fins:
        if f in lines[a + 1:]:
            b = min(b, lines.index(f, a + 1))
    return [l.strip() for l in lines[a + 1:b] if l.strip()]


def areas_imoveis(pdf_path: str) -> list[tuple[str, str, str]]:
    """Lê a tabela 'Dados das Áreas dos Imóveis Rurais'.
    Retorna ``[(documento, tipo, area_ha_str), ...]``."""
    if not pdf_path or not os.path.exists(pdf_path):
        return []
    doc = fitz.open(pdf_path)
    lines: list[str] = []
    for p in range(doc.page_count):
        lines += [l.strip() for l in doc[p].get_text().splitlines()]
    doc.close()

    raw = _secao(lines, "Dados das Áreas dos Imóveis Rurais",
                 ["Dados de Reserva Legal", "Dados de Reserva"])
    raw = [l for l in raw if l not in ("Documento", "Tipo", "Área (ha)")]

    areas, lbl, i = [], [], 0
    while i < len(raw):
        l = raw[i]
        if l in ("Matrícula", "Posse"):
            area = raw[i + 1] if i + 1 < len(raw) else ""
            areas.append((" ".join(lbl).strip(), l, area))
            lbl, i = [], i + 2
        else:
            lbl.append(l)
            i += 1
    return areas


def areas_do_recibo(projeto, fazenda) -> list[tuple[str, str, str]]:
    """Resolve o recibo PDF da fazenda (em <consultas>/CAR/) e extrai as áreas."""
    if not getattr(fazenda, "recibo_pdf", ""):
        return []
    return areas_imoveis(io.caminho_consulta(projeto, "CAR", fazenda.recibo_pdf))
