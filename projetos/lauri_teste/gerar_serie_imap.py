# -*- coding: utf-8 -*-
"""Gera a SÉRIE de mapas IMAP do imóvel a partir das camadas locais do projeto.

Usa as ``camadas_locais`` declaradas no projeto.json (lotes, AVN, AC, AUAS,
tipologia) + a tabela de quantitativos MATRIZ (propriedade x classe, calculada
por overlay no render). Produz: Dinâmica, Uso Consolidado e Tipologia Vegetal.

    .venv\\Scripts\\python.exe projetos\\lauri_teste\\gerar_serie_imap.py
"""
import os, sys
sys.path.insert(0, r"C:\GIS\NexoGeo-Ambiental")
os.chdir(r"C:\GIS\NexoGeo-Ambiental")

from core.nexomap_generator import generate
from core.nexomap_project import load_nexomap_project

PROJ = r"projetos\lauri_teste\projeto.json"
project = load_nexomap_project(PROJ)
LOC = project.camadas_locais_index()  # id -> {arquivo, estilo, ...}


def camada(cid, **over):
    """Monta uma camada do MapSpec a partir de uma camada local do projeto."""
    cfg = LOC[cid]
    estilo = dict(cfg.get("estilo") or {})
    estilo.update(over.pop("estilo", {}))
    return {"id": cid, "fonte": "arquivo:" + cfg["arquivo"], "filtro": "", "estilo": estilo,
            "rotulo": over.pop("rotulo", False), **over}


PERIM_INVISIVEL = {"id": "perimetro", "fonte": "area_base", "filtro": "",
                   "estilo": {"linha": "transparente", "largura": 0, "preenchimento": "transparente"},
                   "rotulo": False}
METADADOS = {"satelite_sensor": "PLANET", "data_aquisicao": "Maio/2026",
             "orbita_ponto": "Não se aplica", "datum": "SIRGAS 2000 UTM 22S"}
TITULO_LAYOUT = {"elementos": {"titulo": {"ancora": "in-map-top-center", "x": 0.5, "y": 0.972,
                                          "estilo": {"fundo": "white", "cor": "#111827", "tamanho": 22}}}}
ELEMS = {"legenda": True, "escala_grafica": True, "norte": True, "grade": True, "minimapa": True,
         "metadados_imagem": True, "tabela": True, "inset_tipologia": False, "titulo_caixa": True,
         "logo": True, "rosa_dos_ventos": False}

# tabela MATRIZ propriedade x classe (calculada por overlay no render)
def tabela_matriz(classes):
    return {"fonte": "quantitativos_matriz", "titulo": "",
            "config": {"propriedades": [{"rotulo": "Fazenda Trevisol (Lote 65)", "camada": "lote65"},
                                        {"rotulo": "Lote Rural nº 66-A", "camada": "lote66a"}],
                       "classes": classes, "area_total_col": True, "linha_total": True}}

LEGENDA_LOTES = [
    {"rotulo": "Fazenda Trevisol (Lote 65)", "tipo": "linha", "cor": "#ff2d00", "largura": 2.6},
    {"rotulo": "Lote Rural nº 66-A", "tipo": "linha", "cor": "#00b0f0", "largura": 2.6},
]

# Estilos IMAP (padrão oficial — alinhados com catalogo/modelos_mapas.json)
# AVN: verde #16a34a preenchido 0.45 | AC: âmbar #f59e0b preenchido 0.4 | AUAS: transparente hachura ....
ESTILO_AVN = {"preenchimento": "#16a34a", "opacidade": 0.45, "linha": "#166534", "largura": 1.2}
ESTILO_AC  = {"preenchimento": "#f59e0b", "opacidade": 0.4,  "linha": "#b45309", "largura": 1.4}
ESTILO_AUAS = {"preenchimento": "transparente", "hachura": "....", "linha": "#c2410c", "largura": 1.4, "opacidade": 0.95}
ESTILO_TIPOLOGIA = {"preenchimento": "transparente", "hachura": "----", "linha": "#059669", "largura": 1.2, "opacidade": 0.65}


def base(titulo, camadas, tabela=None, legenda_itens=None):
    spec = {"titulo": titulo, "tipo": "imap", "area_base": "projeto.area_base",
            "layout_template": "dinamica_a3_paisagem", "escala": "auto", "basemap": "satellite",
            "grade_tipo": "dms", "camadas": camadas, "metadados_imagem": METADADOS,
            "marca": {"logo": os.path.join("assets", "logo_imap.png"), "texto": "IMAP"},
            "layout": TITULO_LAYOUT, "elementos_layout": dict(ELEMS),
            "saidas": ["pdf", "png_validacao"]}
    if tabela:
        spec["tabela"] = tabela
    if legenda_itens:
        spec["legenda"] = {"modo": "manual", "titulo": "Legenda", "colunas": 1,
                           "fonte_tamanho": 8.0, "itens": legenda_itens}
    return spec


# lotes desenhados por cima (rotulo_texto ja garante zorder alto)
LOTE65 = camada("lote65")
LOTE66 = camada("lote66a")

MAPAS = {
    "Dinamica_2026": base(
        "Dinâmica 2026",
        [PERIM_INVISIVEL, camada("avn", estilo=ESTILO_AVN), camada("ac", estilo=ESTILO_AC),
         camada("auas", estilo=ESTILO_AUAS), LOTE65, LOTE66],
        tabela=tabela_matriz([{"rotulo": "AVN", "camada": "avn"},
                              {"rotulo": "AC", "camada": "ac"},
                              {"rotulo": "AUAS", "camada": "auas"}]),
        legenda_itens=LEGENDA_LOTES + [
            {"rotulo": "Área de Vegetação Nativa (AVN)", "tipo": "poligono",
             "cor": "#166534", "preenchimento": "#16a34a", "opacidade": 0.45},
            {"rotulo": "Área Consolidada Cultivável (AC)", "tipo": "poligono",
             "cor": "#b45309", "preenchimento": "#f59e0b", "opacidade": 0.4},
            {"rotulo": "Área de Uso Alt. do Solo (AUAS)", "tipo": "poligono",
             "cor": "#c2410c", "preenchimento": "transparente", "hachura": "...."},
        ]),
    "Uso_Consolidado": base(
        "Uso Consolidado",
        [PERIM_INVISIVEL, camada("avn", estilo=ESTILO_AVN), camada("ac", estilo=ESTILO_AC),
         camada("auas", estilo=ESTILO_AUAS), LOTE65, LOTE66],
        tabela=tabela_matriz([{"rotulo": "AVN", "camada": "avn"},
                              {"rotulo": "AC", "camada": "ac"},
                              {"rotulo": "AUAS", "camada": "auas"}]),
        legenda_itens=LEGENDA_LOTES + [
            {"rotulo": "Área de Vegetação Nativa (AVN)", "tipo": "poligono",
             "cor": "#166534", "preenchimento": "#16a34a", "opacidade": 0.45},
            {"rotulo": "Área Consolidada Cultivável (AC)", "tipo": "poligono",
             "cor": "#b45309", "preenchimento": "#f59e0b", "opacidade": 0.4},
            {"rotulo": "Área de Uso Alt. do Solo (AUAS)", "tipo": "poligono",
             "cor": "#c2410c", "preenchimento": "transparente", "hachura": "...."},
        ]),
    "Tipologia_Vegetal": base(
        "Tipologia Vegetal",
        [PERIM_INVISIVEL, camada("tipologia", estilo=ESTILO_TIPOLOGIA), LOTE65, LOTE66],
        legenda_itens=LEGENDA_LOTES + [
            {"rotulo": "Tipologia Vegetal (Floresta/Cerrado)", "tipo": "poligono",
             "cor": "#059669", "preenchimento": "transparente", "hachura": "----"},
        ]),
}

if __name__ == "__main__":
    for nome, spec in MAPAS.items():
        res = generate(PROJ, mapspec=spec, use_basemap=True)
        t = res.get("mapspec", {}).get("tabela", {})
        print(f"[{nome}] ok={res['ok']} escala={res.get('escala')} -> {res['outputs']['preview_png']}")
        if t.get("linhas"):
            for row in t["linhas"]:
                print("     ", " | ".join(str(c).replace('\n', ' ') for c in row))
