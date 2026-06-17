# -*- coding: utf-8 -*-
"""Automações — orquestradores finos.

Cada automação é uma função ``gerar(projeto, ...) -> caminho_de_saida`` que usa o
núcleo (``core``) e lê tudo do ``Projeto``. Nenhuma fazenda/CAR escrito aqui.

Disponíveis:
  quantitativos  — área cultivável por CAR -> .xlsx              [Fase 2 ✓]
  (ctx_ambiental, ctx_fundiario, area_total, apf)                [Fase 2]
"""
