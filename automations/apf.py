# -*- coding: utf-8 -*-
"""Automação: APFs por CAR (consulta SEMA-MT) -> .xlsx (+ download dos PDFs).

Consulta o portal APF Rural por CAR Federal e Estadual de cada fazenda, deduplica
por nº de APF e monta a planilha. Opcionalmente baixa os PDFs das APFs REGULAR.
Porta genérica de ``puxar_apfs.py`` + ``baixar_pdfs_apf.py``.

Uso (a partir de software/):
    python -m automations.apf <projeto.json> [saida.xlsx] [--pdfs]
"""
from __future__ import annotations

import os
import re
import time
import unicodedata

import openpyxl

from core import io
from core import xlsx_builder as xb
from core.clients import apf_rural as apf

NOME_PADRAO = "APFs_por_CAR.xlsx"

HEADERS = ["CAR / Fazenda", "Nº APF", "Situação", "Atividade", "Responsável",
           "Município", "Data Emissão", "Data Validade", "Última Atualização",
           "Nº CAR (consulta)", "Buscado por"]
_KEYMAP = ["__nome", "ApfNumero", "Situacao", "Atividade", "Responsavel",
           "Municipio", "DataEmissao", "DataValidade", "UltimaAtualizacao", "CarNumero", "__busca"]


def coletar(projeto, pausa: float = 1.0):
    """Consulta as APFs de todas as fazendas. Retorna ``[(nome_fazenda, dict_apf), ...]``."""
    rows = []
    for fz in projeto.fazendas:
        combinado = {}
        for numero, modo in [(fz.car_federal, "FEDERAL"), (fz.car_estadual, "ESTADUAL")]:
            if not numero:
                continue
            for e in apf.consultar(numero, modo):
                e = dict(e)
                e["__busca"] = modo
                combinado[e["ApfNumero"]] = e   # dedupe por nº de APF
            time.sleep(pausa)
        for e in combinado.values():
            rows.append((fz.nome, e))
    return rows


def _montar_xlsx(rows) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "APFs por CAR"
    xb.titulo_merge(ws, "A1:K1", "APFs por CAR — Consulta SEMA-MT (APF Rural)", altura=28)
    xb.cabecalho(ws, 2, HEADERS, altura=28)
    rows = sorted(rows, key=lambda t: (t[0], t[1].get("ApfNumero", "")))
    r = 3
    for nome, e in rows:
        reg = dict(e)
        reg["__nome"] = nome
        for c, k in enumerate(_KEYMAP, start=1):
            align = xb.CENTER if k in ("ApfNumero", "Situacao", "DataEmissao", "DataValidade",
                                       "UltimaAtualizacao", "__busca") else xb.LEFT
            xb.celula(ws, r, c, reg.get(k, ""), align=align,
                      fundo=("FFF2F2F2" if r % 2 == 1 else None))
        r += 1
    xb.larguras(ws, [26, 12, 14, 22, 34, 14, 13, 13, 16, 46, 12])
    ws.freeze_panes = "A3"
    return wb


def gerar(projeto, destino: str | None = None, baixar: bool = False) -> str:
    rows = coletar(projeto)
    wb = _montar_xlsx(rows)
    destino = destino or io.caminho_resultado(projeto, NOME_PADRAO)
    wb.save(destino)
    if baixar:
        baixar_pdfs(projeto)
    return destino


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def baixar_pdfs(projeto) -> list[tuple[str, str, str]]:
    """Baixa os PDFs das APFs REGULAR para <consultas>/APF. Retorna [(fazenda, apf, arquivo)]."""
    dest_dir = io.garantir_dir(io.caminho_consulta(projeto, "APF"))
    baixados = []
    for fz in projeto.fazendas:
        achou = {}
        for numero, modo in [(fz.car_estadual, "ESTADUAL"), (fz.car_federal, "FEDERAL")]:
            if not numero:
                continue
            S = apf.http.session()
            html = apf.buscar_html(S, numero, modo)
            for i, num, tgt in apf.entradas_regular(html):
                if num in achou or not tgt:
                    continue
                fname = "APF_%s_%s.pdf" % (_slug(fz.nome), num.replace("/", "-"))
                n = apf.baixar_pdf(S, html, tgt, modo, numero, os.path.join(dest_dir, fname))
                if n:
                    achou[num] = fname
                    baixados.append((fz.nome, num, fname))
            time.sleep(1)
    return baixados


def _main(argv: list[str]) -> int:
    from core.config import load_projeto
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print("uso: python -m automations.apf <projeto.json> [saida.xlsx] [--pdfs]")
        return 2
    proj = load_projeto(args[0])
    out = gerar(proj, args[1] if len(args) > 1 else None, baixar=("--pdfs" in argv))
    print("Gerado:", out)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv))
