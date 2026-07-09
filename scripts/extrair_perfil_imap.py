# -*- coding: utf-8 -*-
"""Extrai o perfil visual do PDF-modelo IMAP (plano 10).

Le ``referencias/Mapas_unidos.pdf`` (24 mapas reais do IMAP) e extrai metricas
de estilo (posicao/tamanho/cor do titulo, presenca e posicao de norte, legenda,
metadados e faixa inferior) para servir de gabarito na validacao dos mapas
gerados pelo NexoGeo.

Gera ``referencias/perfil_imap.json`` com medias, extremos e tolerancias.

A extracao por pagina e a MESMA usada pela validacao de PDF gerado
(``core.nexomap_validation.extrair_metricas_pagina``), garantindo que perfil e
medida sejam comparaveis.

Uso:
    .venv/bin/python scripts/extrair_perfil_imap.py \
        [--pdf referencias/Mapas_unidos.pdf] [--out referencias/perfil_imap.json]

Todas as posicoes/tamanhos sao gravados em **fracao da pagina** (0..1, origem no
topo-esquerda), independentes do tamanho fisico da folha.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Iterable

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.nexomap_validation import extrair_metricas_pagina  # noqa: E402

PDF_PADRAO = os.path.join(ROOT, "referencias", "Mapas_unidos.pdf")
OUT_PADRAO = os.path.join(ROOT, "referencias", "perfil_imap.json")


def _resumo(valores: Iterable[float], tol_frac: float = 0.0, tol_min: float = 0.0) -> dict:
    """Estatisticas de uma lista de valores + tolerancia sugerida.

    ``tol`` = max(tol_min, tol_frac * amplitude, desvio-padrao). Serve de margem
    na comparacao mapa-gerado x modelo.
    """
    vals = [float(v) for v in valores]
    if not vals:
        return {"n": 0}
    media = statistics.mean(vals)
    lo, hi = min(vals), max(vals)
    desvio = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    tol = max(tol_min, tol_frac * (hi - lo), desvio)
    return {
        "n": len(vals),
        "media": round(media, 4),
        "min": round(lo, 4),
        "max": round(hi, 4),
        "desvio": round(desvio, 4),
        "tol": round(tol, 4),
    }


def extrair_perfil(pdf_path: str = PDF_PADRAO) -> dict:
    """Extrai o perfil de estilo IMAP do PDF-modelo (agrega as 24 paginas)."""
    doc = fitz.open(pdf_path)
    metricas = [extrair_metricas_pagina(page) for page in doc]
    doc.close()
    metricas = [m for m in metricas if m]

    def coluna(*caminho):
        """Coleta um campo (aninhado) de cada pagina, ignorando ausentes."""
        out = []
        for m in metricas:
            no = m
            for chave in caminho:
                no = no.get(chave) if isinstance(no, dict) else None
                if no is None:
                    break
            if no is not None:
                out.append(no)
        return out

    aspects = coluna("aspect")
    fontes: dict[str, int] = {}
    for f in coluna("titulo", "fonte"):
        fontes[f] = fontes.get(f, 0) + 1
    cores: dict[str, int] = {}
    for c in coluna("titulo", "cor"):
        cores[c] = cores.get(c, 0) + 1

    # topo da faixa inferior = menor y0 entre os cabecalhos de rodape por pagina
    faixa_y0 = []
    for m in metricas:
        ys = [m[k]["y0_frac"] for k in ("legenda", "metadados_imagem") if k in m]
        if ys:
            faixa_y0.append(min(ys))

    perfil = {
        "gerado_de": os.path.relpath(pdf_path, ROOT),
        "n_paginas": len(metricas),
        "descricao": "Perfil visual extraido dos mapas IMAP reais (plano 10). "
                     "Posicoes em fracao da pagina, origem topo-esquerda.",
        "pagina": {
            "aspect": _resumo(aspects, tol_frac=0.5, tol_min=0.02),
            "orientacao": "paisagem" if aspects and statistics.mean(aspects) > 1 else "retrato",
        },
        "titulo": {
            "size": _resumo(coluna("titulo", "size"), tol_frac=0.5, tol_min=3.0),
            "cx_frac": _resumo(coluna("titulo", "cx_frac"), tol_min=0.12),
            "y0_frac": _resumo(coluna("titulo", "y0_frac"), tol_min=0.06),
            "largura_frac": _resumo(coluna("titulo", "largura_frac")),
            "fontes": fontes,
            "cores": cores,
        },
        "norte": {
            "presente_em": len(coluna("norte", "cx_frac")),
            "cx_frac": _resumo(coluna("norte", "cx_frac"), tol_min=0.05),
            "cy_frac": _resumo(coluna("norte", "cy_frac"), tol_min=0.05),
        },
        "legenda": {
            "presente_em": len(coluna("legenda", "cx_frac")),
            "cx_frac": _resumo(coluna("legenda", "cx_frac"), tol_min=0.08),
            "y0_frac": _resumo(coluna("legenda", "y0_frac"), tol_min=0.06),
        },
        "metadados_imagem": {
            "presente_em": len(coluna("metadados_imagem", "cx_frac")),
            "cx_frac": _resumo(coluna("metadados_imagem", "cx_frac"), tol_min=0.08),
            "y0_frac": _resumo(coluna("metadados_imagem", "y0_frac"), tol_min=0.06),
        },
        "faixa_inferior": {
            "y0_frac": _resumo(faixa_y0, tol_min=0.06),
        },
    }
    return perfil


def main() -> None:
    ap = argparse.ArgumentParser(description="Extrai o perfil visual do PDF-modelo IMAP.")
    ap.add_argument("--pdf", default=PDF_PADRAO, help="PDF-modelo (default: referencias/Mapas_unidos.pdf)")
    ap.add_argument("--out", default=OUT_PADRAO, help="Saida JSON (default: referencias/perfil_imap.json)")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        raise SystemExit(f"PDF-modelo nao encontrado: {args.pdf}")

    perfil = extrair_perfil(args.pdf)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)

    print(f"Perfil extraido de {perfil['n_paginas']} paginas -> {os.path.relpath(args.out, ROOT)}")
    t = perfil["titulo"]
    print(f"  titulo: size~{t['size']['media']} cx~{t['cx_frac']['media']} y0~{t['y0_frac']['media']} "
          f"fontes={list(t['fontes'])} cores={list(t['cores'])}")
    print(f"  norte presente em {perfil['norte']['presente_em']}/{perfil['n_paginas']}")
    print(f"  legenda presente em {perfil['legenda']['presente_em']}/{perfil['n_paginas']}")


if __name__ == "__main__":
    main()
