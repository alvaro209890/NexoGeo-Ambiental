# -*- coding: utf-8 -*-
"""Validacao de mapas gerados contra o perfil do PDF-modelo IMAP (plano 10)."""
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
from core.nexomap_validation import (
    PERFIL_IMAP_PADRAO,
    extrair_metricas_pdf,
    load_perfil_imap,
    validar_contra_modelo,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQUARE = [(-51.12, -10.02), (-51.11, -10.02), (-51.11, -10.01), (-51.12, -10.01), (-51.12, -10.02)]


def _make_area_zip(shapes_dir: str) -> str:
    base = os.path.join(shapes_dir, "area")
    with shapefile.Writer(base, shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=40)
        w.poly([SQUARE[::-1]])  # anel exterior horario
        w.record("Fazenda Teste")
    with open(base + ".prj", "w", encoding="ascii") as f:
        f.write(CRS.from_epsg(4674).to_wkt())
    zip_path = os.path.join(shapes_dir, "area.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            zf.write(base + ext, "area" + ext)
    return zip_path


def _render(tmp: str, flagship: bool) -> dict:
    shapes = os.path.join(tmp, "Shapes")
    os.makedirs(shapes, exist_ok=True)
    _make_area_zip(shapes)
    project_data = {
        "versao_schema": 1,
        "nome": "Projeto Modelo",
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
    spec_data = {
        "titulo": "Mapa de Teste IMAP",
        "layout_template": "dinamica_a3_paisagem",
        "escala": "auto",
        "basemap": "none",
        "camadas": [{"id": "perimetro", "fonte": "area_base",
                     "estilo": {"linha": "#ff3b30"}, "rotulo": True}],
        "elementos_layout": {"legenda": True, "escala_grafica": True, "norte": True,
                             "grade": True, "minimapa": False, "metadados": True},
        "saidas": ["pdf", "png_validacao"],
    }
    if flagship:
        spec_data["metadados_imagem"] = {
            "satelite": "PLANET", "data_imagem": "OUTUBRO/2025", "datum": "SIRGAS 2000 UTM 22S",
        }
    spec = mapspec_from_dict(spec_data)
    return render_pdf_map(project, spec, catalog, os.path.join(tmp, "job"),
                          manifest=manifest, drawn_layers=[], use_basemap=False)


class PerfilImapTests(unittest.TestCase):
    def test_perfil_existe_e_bem_formado(self):
        self.assertTrue(os.path.exists(PERFIL_IMAP_PADRAO),
                        "perfil_imap.json ausente — rode scripts/extrair_perfil_imap.py")
        perfil = load_perfil_imap()
        self.assertGreaterEqual(perfil["n_paginas"], 20)
        # o titulo do modelo e Tahoma-Bold, preto, grande, no topo
        self.assertIn("Tahoma-Bold", perfil["titulo"]["fontes"])
        self.assertLess(perfil["titulo"]["y0_frac"]["media"], 0.1)
        self.assertGreater(perfil["titulo"]["size"]["media"], 20)
        self.assertGreaterEqual(perfil["legenda"]["presente_em"], 20)


class ValidarContraModeloTests(unittest.TestCase):
    def test_mapa_flagship_conforma_ao_modelo(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _render(tmp, flagship=True)
            res = validar_contra_modelo(out["pdf"])
            self.assertTrue(res["ok"],
                            msg="checks HARD falharam: " + json.dumps(res, indent=2, ensure_ascii=False))
            # estrutura IMAP detectada
            nomes_ok = {c["name"] for c in res["checks"] if c["ok"]}
            for esperado in ("aspecto_pagina", "titulo_presente", "titulo_no_topo",
                             "titulo_centralizado", "legenda_presente", "legenda_no_rodape"):
                self.assertIn(esperado, nomes_ok, f"check {esperado} deveria passar no flagship")

    def test_mapa_painel_direito_nao_tem_legenda_no_rodape(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _render(tmp, flagship=False)
            res = validar_contra_modelo(out["pdf"])
            # legenda existe, mas no painel lateral (topo) — nao conforma a faixa IMAP
            self.assertFalse(res["ok"])
            self.assertIn("legenda_no_rodape", res["hard_falhos"])

    def test_pdf_inexistente(self):
        res = validar_contra_modelo("/caminho/que/nao/existe.pdf")
        self.assertFalse(res["ok"])
        self.assertTrue(any(c["name"] == "pdf_existe" and not c["ok"] for c in res["checks"]))

    def test_perfil_ausente_reporta_sem_quebrar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _render(tmp, flagship=True)
            res = validar_contra_modelo(out["pdf"], perfil=os.path.join(tmp, "nao_existe.json"))
            self.assertFalse(res["ok"])
            self.assertTrue(any(c["name"] == "perfil_disponivel" and not c["ok"]
                                for c in res["checks"]))

    def test_extrair_metricas_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _render(tmp, flagship=True)
            metr = extrair_metricas_pdf(out["pdf"])
            self.assertAlmostEqual(metr["aspect"], 1.413, delta=0.02)
            self.assertIn("titulo", metr)
            self.assertEqual(metr["titulo"]["texto"], "Mapa de Teste IMAP")


if __name__ == "__main__":
    unittest.main()
