# -*- coding: utf-8 -*-
"""Núcleo reutilizável do software de Análise de Área.

Módulos previstos (ver Automacoes/PLANO_SOFTWARE.md §4):
  config        — esquema e carga do projeto.json               [Fase 0 ✓]
  geo           — reprojeção (via .prj) + atribuição espacial     [Fase 1 ✓]
  io            — convenção única de saída (Resultados/)          [Fase 1 ✓]
  normalize     — nomes (Title Case, conectores), CNPJ/CPF, datas BR
  docx_builder  — estilo padrão dos .docx (bullets, bordas, Tahoma)
  xlsx_builder  — estilo padrão dos .xlsx (cabeçalho azul, totais)
  recibo        — parser do recibo PDF do CAR
  clients/      — sema, incra, ibama, funai, inpe, mapbiomas, planet
  overlay       — motor genérico de cruzamento perímetro × camada de restrição (v2)
"""
__all__ = ["Projeto", "load_projeto", "ProjetoError", "SCHEMA_VERSION"]


def __getattr__(name):
    """Import preguiçoso (PEP 562): permite ``from core import load_projeto`` sem
    importar ``core.config`` no carregamento do pacote — evita o RuntimeWarning ao
    rodar ``python -m core.config`` e mantém a Fase 0 sem dependências externas."""
    if name in __all__:
        from . import config
        return getattr(config, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
