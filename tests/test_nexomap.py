import json
import os
import tempfile
import unittest

from core.mapspec import build_rule_based_spec, mapspec_from_dict, validate_mapspec
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_project import NexoMapError, load_nexomap_project


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NexoMapContractTests(unittest.TestCase):
    def _project_file(self):
        temp = tempfile.TemporaryDirectory()
        project = {
            "versao_schema": 1,
            "nome": "Projeto Teste",
            "cliente": "Cliente",
            "municipio": {"nome": "Vila Rica", "uf": "MT", "ibge": "5108601"},
            "crs": {"utm": 31982, "geografico": 4674},
            "raiz_dados": ".",
            "pastas": {"shapes": "Shapes", "resultados": "Resultados", "mapas": "Resultados/Mapas"},
            "area_base": {"tipo": "shapefile_zip", "path": "Shapes/area.zip"},
            "catalogo_camadas": os.path.join(ROOT, "catalogo", "camadas.json"),
            "templates_mxd": os.path.join(ROOT, "templates", "mxd", "MANIFEST.json"),
        }
        os.makedirs(os.path.join(temp.name, "Shapes"))
        path = os.path.join(temp.name, "projeto.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(project, f)
        return temp, path

    def test_load_project_contract(self):
        temp, path = self._project_file()
        self.addCleanup(temp.cleanup)
        project = load_nexomap_project(path)
        self.assertEqual(project.nome, "Projeto Teste")
        self.assertEqual(project.crs.utm, 31982)
        self.assertTrue(project.catalog_path().endswith("camadas.json"))

    def test_catalog_and_manifest_load(self):
        catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
        manifest = load_template_manifest(os.path.join(ROOT, "templates", "mxd", "MANIFEST.json"))
        self.assertGreaterEqual(len(catalog["camadas"]), 3)
        self.assertGreaterEqual(len(manifest["templates"]), 1)

    def test_rule_based_mapspec_validates(self):
        catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
        manifest = load_template_manifest(os.path.join(ROOT, "templates", "mxd", "MANIFEST.json"))
        spec = build_rule_based_spec("mapa com car e embargos", "Projeto Teste", catalog, manifest)
        warnings = validate_mapspec(spec, catalog, manifest, {})
        self.assertTrue(spec.titulo)
        self.assertIn("mxd", spec.saidas)
        self.assertTrue(any(layer.id == "embargos_ibama" for layer in spec.camadas))
        self.assertTrue(any("sema_authkey" in warning for warning in warnings))

    def test_unknown_layer_is_blocked(self):
        catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
        manifest = load_template_manifest(os.path.join(ROOT, "templates", "mxd", "MANIFEST.json"))
        spec = mapspec_from_dict({
            "titulo": "Mapa",
            "tipo": "teste",
            "area_base": "projeto.area_base",
            "layout_template": "tematico_a3_retrato",
            "escala": "auto",
            "basemap": "light",
            "camadas": [{"id": "inventada", "fonte": "catalogo.inventada"}],
            "elementos_layout": {"legenda": True},
            "saidas": ["pdf"],
        })
        with self.assertRaises(NexoMapError):
            validate_mapspec(spec, catalog, manifest, {})


if __name__ == "__main__":
    unittest.main()
