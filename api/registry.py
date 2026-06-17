# -*- coding: utf-8 -*-
"""Registro das automações disponíveis (metadados + função ``gerar``).

Desacopla a camada web das automações: a UI lê os metadados daqui e o endpoint
de execução chama ``fn(projeto)``.
"""
from __future__ import annotations

from automations import quantitativos, area_total, ctx_ambiental, ctx_fundiario, apf, pre_analise

AUTOMACOES = [
    {"id": "pre_analise", "label": "Pré-Análise", "desc": "shapefile zip -> relatório Word completo",
     "saida": "docx", "rede": True, "fn": pre_analise.gerar},
    {"id": "quantitativos", "label": "Quantitativos", "desc": "área cultivável por CAR",
     "saida": "xlsx", "rede": False, "fn": quantitativos.gerar},
    {"id": "area_total", "label": "Área total", "desc": "certificação × matrícula",
     "saida": "docx", "rede": False, "fn": area_total.gerar},
    {"id": "ctx_ambiental", "label": "Contexto ambiental", "desc": "CAR + APF + recibo",
     "saida": "docx", "rede": True, "fn": ctx_ambiental.gerar},
    {"id": "ctx_fundiario", "label": "Contexto fundiário", "desc": "certificações INCRA",
     "saida": "docx", "rede": True, "fn": ctx_fundiario.gerar},
    {"id": "apf", "label": "APF", "desc": "consulta SEMA-MT",
     "saida": "xlsx", "rede": True, "fn": apf.gerar},
]

BY_ID = {a["id"]: a for a in AUTOMACOES}


def meta_publica() -> list[dict]:
    """Metadados sem a função (serializável para a UI)."""
    return [{k: v for k, v in a.items() if k != "fn"} for a in AUTOMACOES]
