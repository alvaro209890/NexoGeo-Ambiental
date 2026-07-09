# -*- coding: utf-8 -*-
"""Testes do posicionamento de elementos (plano 01): ancoras, clamping e render."""
import json
import os
import tempfile
import unittest
import zipfile

import shapefile
from pyproj import CRS

from core.mapspec import mapspec_from_dict
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_layout import (anchor_alignment, element_rect,
                                 element_text_anchor, resolve_rect)
from core.nexomap_project import load_nexomap_project
from core.nexomap_renderer import _rects_overlap, render_pdf_map

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SQUARE = [(-51.12, -10.02), (-51.11, -10.02), (-51.11, -10.01), (-51.12, -10.01), (-51.12, -10.02)]


def _make_area_zip(shapes_dir: str) -> str:
    base = os.path.join(shapes_dir, "area")
    with shapefile.Writer(base, shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=40)
        w.poly([SQUARE[::-1]])
        w.record("Fazenda Teste")
    with open(base + ".prj", "w", encoding="ascii") as f:
        f.write(CRS.from_epsg(4674).to_wkt())
    zip_path = os.path.join(shapes_dir, "area.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            zf.write(base + ext, "area" + ext)
    return zip_path


def _write_project(tmp: str) -> str:
    shapes = os.path.join(tmp, "Shapes")
    os.makedirs(shapes, exist_ok=True)
    _make_area_zip(shapes)
    project_data = {
        "versao_schema": 1,
        "nome": "Projeto Layout",
        "municipio": {"nome": "Vila Rica", "uf": "MT", "ibge": "5108601"},
        "crs": {"utm": 31982, "geografico": 4674},
        "raiz_dados": ".",
        "area_base": {"tipo": "shapefile_zip", "path": "Shapes/area.zip"},
        "catalogo_camadas": os.path.join(ROOT, "catalogo", "camadas.json"),
        "templates_layouts": os.path.join(ROOT, "templates", "layouts", "MANIFEST.json"),
    }
    path = os.path.join(tmp, "projeto.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project_data, f)
    return path


class ResolveRectTests(unittest.TestCase):
    def test_ancoras_basicas(self):
        # (ancora, esperado x0, esperado y0) para elemento 0.2 x 0.1 no ponto (0.5, 0.5)
        casos = {
            "bottom-left": (0.5, 0.5),
            "bottom-center": (0.4, 0.5),
            "bottom-right": (0.3, 0.5),
            "center-left": (0.5, 0.45),
            "center": (0.4, 0.45),
            "center-right": (0.3, 0.45),
            "top-left": (0.5, 0.4),
            "top-center": (0.4, 0.4),
            "top-right": (0.3, 0.4),
        }
        for ancora, (x0, y0) in casos.items():
            rect, aviso = resolve_rect(ancora, 0.5, 0.5, 0.2, 0.1)
            self.assertAlmostEqual(rect[0], x0, places=9, msg=ancora)
            self.assertAlmostEqual(rect[1], y0, places=9, msg=ancora)
            self.assertEqual((rect[2], rect[3]), (0.2, 0.1), msg=ancora)
            self.assertEqual(aviso, "", msg=ancora)

    def test_ancora_in_map(self):
        map_rect = (0.1, 0.2, 0.8, 0.6)
        rect, aviso = resolve_rect("in-map-bottom-right", 1.0, 0.0, 0.2, 0.1, map_rect=map_rect)
        # ponto (1,0) do quadro = (0.9, 0.2) da pagina; bottom-right -> x0 = 0.9-0.2
        self.assertAlmostEqual(rect[0], 0.7, places=9)
        self.assertAlmostEqual(rect[1], 0.2, places=9)
        self.assertEqual(aviso, "")

    def test_clamping_avisa_e_mantem_na_pagina(self):
        rect, aviso = resolve_rect("bottom-right", 0.05, 0.0, 0.3, 0.1)
        self.assertGreaterEqual(rect[0], 0.0)
        self.assertNotEqual(aviso, "")

    def test_ancora_invalida_levanta(self):
        with self.assertRaises(ValueError):
            resolve_rect("meio", 0.5, 0.5, 0.2, 0.1)

    def test_alignment(self):
        self.assertEqual(anchor_alignment("top-right"), ("right", "top"))
        self.assertEqual(anchor_alignment("center"), ("center", "center"))
        self.assertEqual(anchor_alignment("bottom-left"), ("left", "bottom"))


class ElementRectTests(unittest.TestCase):
    def test_sem_layout_usa_default(self):
        default = (0.52, 0.012, 0.30, 0.11)
        self.assertEqual(element_rect({}, "legenda", default), default)
        self.assertEqual(element_rect({"elementos": {}}, "legenda", default), default)

    def test_com_layout_move(self):
        layout = {"elementos": {"legenda": {"ancora": "bottom-left", "x": 0.02, "y": 0.02,
                                            "largura": 0.28}}}
        default = (0.52, 0.012, 0.30, 0.11)
        rect = element_rect(layout, "legenda", default)
        self.assertAlmostEqual(rect[0], 0.02)
        self.assertAlmostEqual(rect[1], 0.02)
        self.assertAlmostEqual(rect[2], 0.28)
        self.assertAlmostEqual(rect[3], 0.11)  # altura ausente herda o default

    def test_config_invalida_cai_no_default_com_aviso(self):
        avisos = []
        default = (0.5, 0.5, 0.2, 0.1)
        layout = {"elementos": {"legenda": {"ancora": "inexistente", "x": 0.1, "y": 0.1}}}
        rect = element_rect(layout, "legenda", default, avisos=avisos)
        self.assertEqual(rect, default)
        self.assertEqual(len(avisos), 1)

    def test_mover_legenda_nao_sobrepoe_logo(self):
        logo = (0.85, 0.01, 0.12, 0.115)
        layout = {"elementos": {"legenda": {"ancora": "bottom-left", "x": 0.02, "y": 0.02,
                                            "largura": 0.28, "altura": 0.11}}}
        legenda = element_rect(layout, "legenda", (0.52, 0.012, 0.30, 0.11))
        self.assertEqual(_rects_overlap(legenda, logo), 0.0)

    def test_text_anchor_converte_para_eixos(self):
        map_rect = (0.0, 0.0, 1.0, 1.0)
        layout = {"elementos": {"titulo": {"ancora": "top-left", "x": 0.05, "y": 0.95}}}
        x, y, ha, va = element_text_anchor(layout, "titulo", map_rect,
                                           (0.985, 0.985, "right", "top"))
        self.assertAlmostEqual(x, 0.05)
        self.assertAlmostEqual(y, 0.95)
        self.assertEqual((ha, va), ("left", "top"))


class RenderComLayoutTests(unittest.TestCase):
    def _spec_flagship(self, layout: dict | None = None, elementos_layout: dict | None = None):
        data = {
            "titulo": "Mapa Layout Teste",
            "layout_template": "dinamica_a3_paisagem",
            "escala": "auto",
            "basemap": "none",
            "camadas": [{"id": "perimetro", "fonte": "area_base",
                         "estilo": {"linha": "#ff3b30"}, "rotulo": False}],
            "elementos_layout": elementos_layout or {"legenda": True, "escala_grafica": True,
                                                     "norte": True, "grade": True,
                                                     "minimapa": False, "metadados": True},
            "metadados_imagem": {"satelite_sensor": "Landsat-5/TM", "data_aquisicao": "30/07/2000"},
            "saidas": ["pdf", "png_validacao"],
        }
        if layout:
            data["layout"] = layout
        return mapspec_from_dict(data)

    def test_sem_layout_renderiza_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = load_nexomap_project(_write_project(tmp))
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            spec = self._spec_flagship()
            outputs = render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                                     manifest=manifest, drawn_layers=[], use_basemap=False)
            self.assertTrue(outputs["validacao_result"]["ok"],
                            msg=json.dumps(outputs["validacao_result"], indent=2))

    def test_mover_legenda_renderiza_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = load_nexomap_project(_write_project(tmp))
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            # minimapa desligado -> o espaco 0.02..0.19 da faixa esta livre
            layout = {"elementos": {"legenda": {"ancora": "bottom-left", "x": 0.02, "y": 0.012,
                                                "largura": 0.15}}}
            spec = self._spec_flagship(layout=layout)
            outputs = render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                                     manifest=manifest, drawn_layers=[], use_basemap=False)
            self.assertTrue(outputs["validacao_result"]["ok"],
                            msg=json.dumps(outputs["validacao_result"], indent=2))

    def test_sobreposicao_proposital_detectada(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = load_nexomap_project(_write_project(tmp))
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            # joga a legenda em cima do bloco de metadados-imagem da faixa
            layout = {"elementos": {"legenda": {"ancora": "bottom-left", "x": 0.19, "y": 0.005,
                                                "largura": 0.24, "altura": 0.12}}}
            spec = self._spec_flagship(layout=layout)
            outputs = render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                                     manifest=manifest, drawn_layers=[], use_basemap=False)
            checks = {c["name"]: c for c in outputs["validacao_result"]["checks"]}
            self.assertFalse(checks["sem_sobreposicao_elementos"]["ok"],
                             msg=json.dumps(outputs["validacao_result"], indent=2))


if __name__ == "__main__":
    unittest.main()
