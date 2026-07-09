# -*- coding: utf-8 -*-
import os, sys, json
sys.path.insert(0, r"C:\GIS\NexoGeo-Ambiental")
os.chdir(r"C:\GIS\NexoGeo-Ambiental")
from core.nexomap_generator import generate

B = r"C:\Users\Usuario\Downloads\Analise_de_area\Lauri_Anlise_2\SHP"
SIM = os.path.join(B, "SIMCAR_Recorte_f74e2290-0236-4276-a679-88842db1faa0")
L65 = os.path.join(B, "Lote 65.shp")
L66 = os.path.join(B, "Lote 66A.shp")

spec = {
    "titulo": "Dinâmica 2026",
    "tipo": "dinamica",
    "area_base": "projeto.area_base",
    "layout_template": "dinamica_a4_paisagem",
    "escala": "auto",
    "basemap": "satellite",
    "grade_tipo": "dms",
    "camadas": [
        {"id": "perimetro", "fonte": "area_base", "filtro": "",
         "estilo": {"linha": "#ffffff", "largura": 0, "preenchimento": "transparente"}, "rotulo": False},
        {"id": "avn", "fonte": "arquivo:" + os.path.join(SIM, "AVN.shp"), "filtro": "",
         "estilo": {"nome": "Área de Vegetação Nativa", "linha": "#00b050",
                    "preenchimento": "transparente", "hachura": "xxx", "opacidade": 0.95, "largura": 0.7}},
        {"id": "ac", "fonte": "arquivo:" + os.path.join(SIM, "AREA_CONSOLIDADA.shp"), "filtro": "",
         "estilo": {"nome": "Área consolidada cultivável", "linha": "#ff00ff",
                    "preenchimento": "none", "opacidade": 1.0, "largura": 1.6}},
        {"id": "auas", "fonte": "arquivo:" + os.path.join(SIM, "AUAS.shp"), "filtro": "",
         "estilo": {"nome": "Área de desmate após 2008 a ser regularizada", "linha": "#ffa500",
                    "preenchimento": "transparente", "hachura": "///", "opacidade": 0.95, "largura": 0.7}},
        {"id": "lote65", "fonte": "arquivo:" + L65, "filtro": "",
         "estilo": {"nome": "Fazenda Trevisol (Lote 65)", "linha": "#c00000",
                    "preenchimento": "none", "opacidade": 1.0, "largura": 2.8,
                    "rotulo_texto": "Fazenda Trevisol (Lote 65)\nMatrícula 13.533", "rotulo_cor": "white"}},
        {"id": "lote66a", "fonte": "arquivo:" + L66, "filtro": "",
         "estilo": {"nome": "Lote Rural nº 66-A", "linha": "#00b0f0",
                    "preenchimento": "none", "opacidade": 1.0, "largura": 2.8,
                    "rotulo_texto": "Lote Rural nº 66-A\nMatrícula 3.115", "rotulo_cor": "white"}},
    ],
    "metadados_imagem": {
        "satelite_sensor": "PLANET", "data_aquisicao": "Maio/2026",
        "orbita_ponto": "Não se aplica", "datum": "SIRGAS 2000 UTM 22S",
    },
    "tabela": {
        "titulo": "",
        "colunas": ["Propriedade", "Área total da\npropriedade (ha)", "AVN (ha)", "AC (ha)", "AUAS (ha)"],
        "linhas": [
            ["Fazenda Trevisol (Lote 65)", "279,8962", "55,3378", "217,9836", "6,5682"],
            ["Lote Rural nº 66-A", "98,6888", "15,8452", "80,7357", "2,1064"],
            ["TOTAL", "378,5849", "71,1830", "298,7193", "8,6746"],
        ],
    },
    "marca": {"texto": "IMAP"},
    "legenda": {
        "modo": "manual", "titulo": "Legenda", "colunas": 1, "fonte_tamanho": 8.0,
        "itens": [
            {"rotulo": "Fazenda Trevisol (Lote 65)", "tipo": "poligono", "cor": "#c00000",
             "preenchimento": "none", "largura": 2.8},
            {"rotulo": "Lote Rural nº 66-A", "tipo": "poligono", "cor": "#00b0f0",
             "preenchimento": "none", "largura": 2.8},
            {"rotulo": "Área consolidada cultivável", "tipo": "poligono", "cor": "#ff00ff",
             "preenchimento": "none", "largura": 1.6},
            {"rotulo": "Área de desmate após 2008 a ser regularizada", "tipo": "poligono",
             "cor": "#ffa500", "preenchimento": "transparente", "hachura": "///"},
            {"rotulo": "Área de Vegetação Nativa", "tipo": "poligono", "cor": "#00b050",
             "preenchimento": "transparente", "hachura": "xxx"},
        ],
    },
    "layout": {"elementos": {"titulo": {"ancora": "in-map-top-center", "x": 0.5, "y": 0.972,
                                        "estilo": {"fundo": "white", "cor": "#111827", "tamanho": 22}}}},
    "elementos_layout": {
        "legenda": True, "escala_grafica": False, "norte": True, "grade": True,
        "minimapa": True, "metadados_imagem": True, "tabela": True,
        "inset_tipologia": False, "titulo_caixa": True, "logo": True, "rosa_dos_ventos": False,
    },
    "saidas": ["pdf", "png_validacao"],
}

res = generate(r"projetos\lauri_teste\projeto.json", mapspec=spec, use_basemap=True)
print("OK:", res["ok"], "| escala:", res.get("escala"), "| job:", os.path.basename(res["job_dir"]))
print("preview:", res["outputs"]["preview_png"])
for w in res.get("warnings", []):
    print("  WARN:", w)
