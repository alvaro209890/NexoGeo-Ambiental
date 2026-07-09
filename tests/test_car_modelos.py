# -*- coding: utf-8 -*-
"""Busca de CAR (offline) + catalogo de modelos de mapa (cards)."""
import os
import tempfile
import unittest

from core import nexomap_car as car
from core.geo import abrir_shape_zip
from core.mapspec import mapspec_from_dict, validate_mapspec
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_modelos import (aplicar_modelo, listar_modelos, load_modelos,
                                  modelos_index)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# poligono sintetico em Querencia/MT (lon/lat, EPSG:4674) — anel CCW estilo GeoJSON
QUAD = {
    "type": "Polygon",
    "coordinates": [[[-52.20, -12.55], [-52.19, -12.55], [-52.19, -12.54],
                     [-52.20, -12.54], [-52.20, -12.55]]],
}


class CarNumeroTests(unittest.TestCase):
    def test_detectar_campo(self):
        self.assertEqual(car.detectar_campo("MT-5106232-A9BEB0EBC7C64C59A43083E44E3F6944"), "CAR_FEDERAL")
        self.assertEqual(car.detectar_campo("MT313839/2025"), "NUMEROESTADUAL")
        self.assertEqual(car.detectar_campo("MT 313839 / 2025"), "NUMEROESTADUAL")
        self.assertIsNone(car.detectar_campo("banana"))

    def test_normalizar(self):
        self.assertEqual(car.normalizar_numero("  mt313839 / 2025 "), "MT313839/2025")

    def test_utm_por_bbox(self):
        self.assertEqual(car.utm_epsg_from_bbox((-57.5, -14.7, -57.4, -14.6)), 31981)  # 21S
        self.assertEqual(car.utm_epsg_from_bbox((-52.3, -12.6, -52.1, -12.4)), 31982)  # 22S

    def test_buscar_sem_authkey(self):
        r = car.buscar_car("MT313839/2025", {})
        self.assertFalse(r["ok"])
        self.assertIn("sema_authkey", r["erro"])

    def test_escrever_area_zip_e_ler(self):
        with tempfile.TemporaryDirectory() as tmp:
            zp = os.path.join(tmp, "Shapes", "area.zip")
            car.escrever_area_zip(QUAD, {"NOMEPROPRIEDADE": "Faz. Teste", "CAR_FEDERAL": "MT-x"}, zp, epsg=4674)
            self.assertTrue(os.path.exists(zp))
            with abrir_shape_zip(zp, 31982, 4674) as area:
                self.assertGreater(area.area_ha, 0)
                self.assertEqual(area.feature_count, 1)


class ModelosTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
        self.manifest = load_template_manifest(os.path.join(ROOT, "templates", "layouts", "MANIFEST.json"))

    def test_lista_de_modelos(self):
        ids = {m["id"] for m in load_modelos()}
        for esperado in ("car", "uso_consolidado", "tipologia", "dinamica",
                         "embargos", "alertas", "areas_protegidas"):
            self.assertIn(esperado, ids)
        for m in listar_modelos():
            self.assertTrue(m["titulo"] and m["categoria"] and m["icone"])

    def test_aplicar_cada_modelo_gera_mapspec_valido(self):
        car_info = {"nome": "Fazenda Teste", "numero": "MT313839/2025"}
        for mid, modelo in modelos_index().items():
            spec, avisos = aplicar_modelo(modelo, self.catalog, car_info=car_info,
                                          epsg_utm=31981, data_imagem="OUT/2025")
            self.assertEqual(avisos, [], f"{mid}: {avisos}")
            parsed = mapspec_from_dict(spec)
            validate_mapspec(parsed, self.catalog, self.manifest, {"sema_authkey": "x"})
            # padrao IMAP flagship (faixa inferior) + subtitulo do imovel
            self.assertTrue(spec.get("metadados_imagem"))
            self.assertIn("paisagem", spec["layout_template"])
            self.assertIn("Fazenda Teste", spec.get("subtitulo", ""))
            self.assertTrue(any(c["id"] == "perimetro" for c in spec["camadas"]))

    def test_modelo_referencia_so_camadas_do_catalogo(self):
        from core.nexomap_catalog import layer_index
        idx = layer_index(self.catalog)
        for modelo in load_modelos():
            for c in modelo["camadas"]:
                fonte = c["fonte"]
                if fonte.startswith("catalogo."):
                    self.assertIn(fonte.split(".", 1)[1], idx, f"{modelo['id']}: {fonte}")


if __name__ == "__main__":
    unittest.main()
