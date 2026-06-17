# -*- coding: utf-8 -*-
"""core.io — convenção única de entrada/saída (Fase 1).

Todas as automações gravam em ``<projeto>/<pastas.resultados>`` por aqui — acaba
com os destinos divergentes dos scripts antigos (uns gravavam em ``Scripts/``,
outros em ``Resultados/``, um com caminho absoluto cravado).
"""
from __future__ import annotations

import os


def garantir_dir(path: str) -> str:
    """Cria o diretório (e pais) se não existir; devolve o próprio caminho."""
    os.makedirs(path, exist_ok=True)
    return path


def caminho_resultado(projeto, nome_arquivo: str) -> str:
    """Caminho absoluto de um arquivo de saída dentro da pasta de resultados do projeto."""
    return os.path.join(garantir_dir(projeto.caminho("resultados")), nome_arquivo)


def caminho_consulta(projeto, *partes: str) -> str:
    """Caminho dentro da pasta de consultas públicas (ex.: recibos do CAR, PDFs de APF)."""
    return os.path.join(projeto.caminho("consultas"), *partes)
