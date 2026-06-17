# -*- coding: utf-8 -*-
"""Clientes de serviços geoespaciais (WMS/WFS) e de raspagem.

  http   — sessão HTTP única (TLS, timeout) usada por todos
  sema   — SEMA-MT GeoServer (situação do CAR via WFS) + APF Rural (scraping)
  incra  — Acervo Fundiário INCRA (SIGEF/SNCI via WFS/GML)

Endpoints e credenciais não ficam aqui: vêm do catálogo (catalogo/servicos_geo.json)
e do projeto/segredos.
"""
