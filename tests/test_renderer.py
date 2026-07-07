# -*- coding: utf-8 -*-
"""Smoke test do motor cartografico nativo (sem rede: basemap desligado)."""
import json
import os
import tempfile
import unittest
import zipfile

import shapefile
from pyproj import CRS

from core.mapspec import mapspec_from_dict
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_project import load_nexomap_project
from core.nexomap_renderer import render_pdf_map

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SQUARE = [(-51.12, -10.02), (-51.11, -10.02), (-51.11, -10.01), (-51.12, -10.01), (-51.12, -10.02)]


def _make_area_zip(shapes_dir: str) -> str:
    base = os.path.join(shapes_dir, "area")
    with shapefile.Writer(base, shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=40)
        w.poly([SQUARE[::-1]])  # shapefile exige anel exterior em sentido horario
        w.record("Fazenda Teste")
    with open(base + ".prj", "w", encoding="ascii") as f:
        f.write(CRS.from_epsg(4674).to_wkt())
    zip_path = os.path.join(shapes_dir, "area.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            zf.write(base + ext, "area" + ext)
    return zip_path


class RendererSmokeTests(unittest.TestCase):
    def test_render_pdf_sem_arcgis_nem_rede(self):
        with tempfile.TemporaryDirectory() as tmp:
            shapes = os.path.join(tmp, "Shapes")
            os.makedirs(shapes)
            _make_area_zip(shapes)
            project_data = {
                "versao_schema": 1,
                "nome": "Projeto Smoke",
                "cliente": "Cliente",
                "municipio": {"nome": "Vila Rica", "uf": "MT", "ibge": "5108601"},
                "crs": {"utm": 31982, "geografico": 4674},
                "raiz_dados": ".",
                "area_base": {"tipo": "shapefile_zip", "path": "Shapes/area.zip"},
                "catalogo_camadas": os.path.join(ROOT, "catalogo", "camadas.json"),
                "templates_layouts": os.path.join(ROOT, "templates", "layouts", "MANIFEST.json"),
            }
            project_path = os.path.join(tmp, "projeto.json")
            with open(project_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f)

            project = load_nexomap_project(project_path)
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            spec = mapspec_from_dict({
                "titulo": "Mapa Smoke Test",
                "layout_template": "dinamica_a3_paisagem",
                "escala": "auto",
                "basemap": "none",
                "camadas": [{"id": "perimetro", "fonte": "area_base",
                             "estilo": {"linha": "#ff3b30"}, "rotulo": True}],
                "elementos_layout": {"legenda": True, "escala_grafica": True, "norte": True,
                                     "grade": True, "minimapa": False, "metadados": True},
                "saidas": ["pdf", "png_validacao"],
            })
            job_dir = os.path.join(tmp, "job")
            outputs = render_pdf_map(project, spec, catalog, job_dir,
                                     manifest=manifest, drawn_layers=[], use_basemap=False)

            self.assertTrue(os.path.exists(outputs["pdf"]))
            self.assertTrue(os.path.exists(outputs["preview_png"]))
            self.assertTrue(os.path.exists(outputs["png_validacao"]))
            self.assertTrue(outputs["validacao_result"]["ok"],
                            msg=json.dumps(outputs["validacao_result"], indent=2))
            # escala honesta: valor redondo da tabela e suficiente para a area
            self.assertIn(outputs["escala"], (1000, 2000, 2500, 5000, 10000))

    def test_escala_fixa_e_honrada(self):
        with tempfile.TemporaryDirectory() as tmp:
            shapes = os.path.join(tmp, "Shapes")
            os.makedirs(shapes)
            _make_area_zip(shapes)
            project_data = {
                "versao_schema": 1,
                "nome": "Projeto Escala",
                "municipio": {"nome": "Vila Rica", "uf": "MT", "ibge": "5108601"},
                "crs": {"utm": 31982},
                "raiz_dados": ".",
                "area_base": {"tipo": "shapefile_zip", "path": "Shapes/area.zip"},
                "catalogo_camadas": os.path.join(ROOT, "catalogo", "camadas.json"),
                "templates_layouts": os.path.join(ROOT, "templates", "layouts", "MANIFEST.json"),
            }
            project_path = os.path.join(tmp, "projeto.json")
            with open(project_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f)
            project = load_nexomap_project(project_path)
            catalog = load_layer_catalog(project.catalog_path())
            manifest = load_template_manifest(project.template_manifest_path())
            spec = mapspec_from_dict({
                "titulo": "Mapa Escala Fixa",
                "layout_template": "tematico_a3_retrato",
                "escala": 25000,
                "basemap": "none",
                "camadas": [{"id": "perimetro", "fonte": "area_base"}],
                "saidas": ["pdf"],
            })
            outputs = render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                                     manifest=manifest, drawn_layers=[], use_basemap=False)
            self.assertEqual(outputs["escala"], 25000)
            self.assertTrue(outputs["validacao_result"]["ok"])


if __name__ == "__main__":
    unittest.main()
