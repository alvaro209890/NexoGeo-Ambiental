# -*- coding: utf-8 -*-
"""Testes da legenda editavel (plano 02): modos auto/manual/misto e swatches."""
import json
import os
import tempfile
import unittest

from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from core.mapspec import mapspec_from_dict
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_layers import DrawnLayer
from core.nexomap_project import load_nexomap_project
from core.nexomap_renderer import _legend_swatch, _montar_legenda, render_pdf_map

from tests.test_layout import _write_project

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _auto_entries():
    peri = Line2D([0], [0], color="#ff3b30", lw=2.4, label="Perimetro do imovel (1)")
    car = Patch(facecolor="#1d4ed8", edgecolor="#1d4ed8", alpha=0.35, label="CAR SEMA-MT (3)")
    return [("perimetro", peri), ("car_sema", car)]


def _drawn_car(n_feats=3):
    return DrawnLayer(id="car_sema", nome="CAR SEMA-MT", tema="car",
                      estilo={"linha": "#1d4ed8", "preenchimento": "#1d4ed8", "opacidade": 0.2},
                      rotulo=False, features=[object()] * n_feats)


class MontarLegendaTests(unittest.TestCase):
    def test_modo_auto_reproduz_baseline(self):
        auto = _auto_entries()
        entries, avisos = _montar_legenda({}, auto, {"car_sema": _drawn_car()})
        self.assertEqual([e.get_label() for e in entries],
                         ["Perimetro do imovel (1)", "CAR SEMA-MT (3)"])
        self.assertEqual(avisos, [])

    def test_modo_manual_respeita_itens_e_ordem(self):
        cfg = {"modo": "manual", "itens": [
            {"rotulo": "Area desmatada (AD)", "tipo": "poligono", "cor": "#e0b400", "hachura": "////"},
            {"rotulo": "Area total da propriedade", "tipo": "linha", "cor": "#ff2d00", "largura": 2.4},
        ]}
        entries, avisos = _montar_legenda(cfg, _auto_entries(), {"car_sema": _drawn_car()})
        self.assertEqual([e.get_label() for e in entries],
                         ["Area desmatada (AD)", "Area total da propriedade"])
        self.assertIsInstance(entries[0], Patch)
        self.assertEqual(entries[0].get_hatch(), "////")
        self.assertIsInstance(entries[1], Line2D)
        self.assertEqual(avisos, [])

    def test_itens_sem_modo_assume_manual(self):
        cfg = {"itens": [{"rotulo": "So um item", "tipo": "linha", "cor": "#000000"}]}
        entries, _ = _montar_legenda(cfg, _auto_entries(), {})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get_label(), "So um item")

    def test_misto_renomeia_apenas_o_item_vinculado(self):
        cfg = {"modo": "misto", "itens": [{"camada": "car_sema", "rotulo": "CAR (validado)"}]}
        entries, avisos = _montar_legenda(cfg, _auto_entries(), {"car_sema": _drawn_car()})
        self.assertEqual(entries[0].get_label(), "Perimetro do imovel (1)")
        self.assertEqual(entries[1].get_label(), "CAR (validado) (3)")
        self.assertEqual(avisos, [])

    def test_item_vinculado_herda_estilo_da_camada(self):
        cfg = {"modo": "manual", "itens": [{"camada": "car_sema"}]}
        entries, _ = _montar_legenda(cfg, _auto_entries(), {"car_sema": _drawn_car()})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get_label(), "CAR SEMA-MT (3)")

    def test_remover_item_mantem_camada_no_mapa(self):
        # legenda manual sem o item do CAR: a legenda encolhe, mas a camada
        # continua desenhada (drawn_by_id nao e alterado pela legenda)
        drawn = {"car_sema": _drawn_car()}
        cfg = {"modo": "manual", "itens": [{"rotulo": "Perimetro", "tipo": "linha", "cor": "#ff2d00"}]}
        entries, _ = _montar_legenda(cfg, _auto_entries(), drawn)
        self.assertEqual(len(entries), 1)
        self.assertEqual(drawn["car_sema"].feature_count, 3)

    def test_camada_inexistente_vira_aviso(self):
        cfg = {"modo": "manual", "itens": [{"camada": "nao_existe", "rotulo": "X",
                                            "tipo": "poligono", "cor": "#123456"}]}
        entries, avisos = _montar_legenda(cfg, _auto_entries(), {})
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(avisos), 1)
        self.assertIn("nao_existe", avisos[0])


class SwatchTests(unittest.TestCase):
    def test_tipos_de_swatch(self):
        linha = _legend_swatch({"tipo": "linha", "cor": "#ff0000"}, "L")
        self.assertIsInstance(linha, Line2D)
        ponto = _legend_swatch({"tipo": "ponto", "cor": "#00ff00"}, "P")
        self.assertIsInstance(ponto, Line2D)
        self.assertEqual(ponto.get_marker(), "o")
        poli = _legend_swatch({"tipo": "poligono", "cor": "#0000ff", "hachura": "----"}, "G")
        self.assertIsInstance(poli, Patch)
        self.assertEqual(poli.get_hatch(), "----")
        img = _legend_swatch({"tipo": "imagem", "cor": "#999999"}, "I")
        self.assertIsInstance(img, Patch)

    def test_poligono_vazado_com_hachura(self):
        # preenchimento transparente + hachura => so as linhas da hachura (fill none)
        p = _legend_swatch({"tipo": "poligono", "cor": "#1a7d1a",
                            "preenchimento": "none", "hachura": "----"}, "AVN")
        self.assertEqual(p.get_hatch(), "----")


class RenderComLegendaTests(unittest.TestCase):
    def test_flagship_com_legenda_manual_renderiza_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = load_nexomap_project(_write_project(tmp))
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            spec = mapspec_from_dict({
                "titulo": "Mapa Legenda Teste",
                "layout_template": "dinamica_a3_paisagem",
                "escala": "auto",
                "basemap": "none",
                "camadas": [{"id": "perimetro", "fonte": "area_base",
                             "estilo": {"linha": "#ff3b30"}}],
                "elementos_layout": {"legenda": True, "minimapa": False},
                "metadados_imagem": {"satelite_sensor": "PLANET", "data_aquisicao": "OUT/2025"},
                "legenda": {
                    "modo": "manual",
                    "titulo": "LEGENDA",
                    "colunas": 1,
                    "itens": [
                        {"rotulo": "Area total da propriedade", "tipo": "linha",
                         "cor": "#ff2d00", "largura": 2.4},
                        {"rotulo": "Alertas MapBiomas", "tipo": "poligono",
                         "cor": "#e0b400", "hachura": "////"},
                    ],
                },
                "saidas": ["pdf", "png_validacao"],
            })
            outputs = render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                                     manifest=manifest, drawn_layers=[], use_basemap=False)
            self.assertTrue(outputs["validacao_result"]["ok"],
                            msg=json.dumps(outputs["validacao_result"], indent=2))

    def test_titulo_estilo_imap_branco_renderiza_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = load_nexomap_project(_write_project(tmp))
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            spec = mapspec_from_dict({
                "titulo": "Dinamica 2025",
                "layout_template": "dinamica_a3_paisagem",
                "escala": "auto",
                "basemap": "none",
                "camadas": [{"id": "perimetro", "fonte": "area_base"}],
                "elementos_layout": {"minimapa": False},
                "metadados_imagem": {"satelite_sensor": "PLANET"},
                "layout": {"elementos": {"titulo": {
                    "ancora": "in-map-top-center", "x": 0.5, "y": 0.985,
                    "estilo": {"fundo": "white", "cor": "#111827", "tamanho": 15},
                }}},
                "saidas": ["pdf", "png_validacao"],
            })
            outputs = render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                                     manifest=manifest, drawn_layers=[], use_basemap=False)
            self.assertTrue(outputs["validacao_result"]["ok"],
                            msg=json.dumps(outputs["validacao_result"], indent=2))


if __name__ == "__main__":
    unittest.main()
