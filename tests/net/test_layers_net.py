# -*- coding: utf-8 -*-
"""Testes de REDE das camadas (plano 03). Pulados por padrao.

    NEXO_NET=1 SEMA_AUTHKEY=... python -m pytest tests/net -q
"""
import os
import unittest

from core.mapspec import mapspec_from_dict
from core.nexomap_catalog import load_layer_catalog
from core.nexomap_layers import fetch_layers

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# bbox rural em Querencia/MT com CARs, embargos e parcelas SIGEF conhecidos
BBOX = (-52.30, -12.60, -52.10, -12.45)
UTM = 31982


def _spec(*layer_ids):
    return mapspec_from_dict({
        "titulo": "t", "layout_template": "x",
        "camadas": [{"id": "perimetro", "fonte": "area_base"}] + [
            {"id": lid, "fonte": f"catalogo.{lid}"} for lid in layer_ids],
        "saidas": ["pdf"],
    })


@unittest.skipUnless(os.environ.get("NEXO_NET"), "rede desligada (defina NEXO_NET=1)")
class LayersNetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))
        cls.secrets = {}
        if os.environ.get("SEMA_AUTHKEY"):
            cls.secrets["sema_authkey"] = os.environ["SEMA_AUTHKEY"]

    @unittest.skipUnless(os.environ.get("SEMA_AUTHKEY"), "sem SEMA_AUTHKEY")
    def test_sema_car_digital_retorna_feicoes(self):
        drawn, warnings = fetch_layers(_spec("car_atp"), self.catalog, BBOX, UTM,
                                       secrets=self.secrets)
        self.assertEqual(len(drawn), 1, warnings)
        self.assertGreater(drawn[0].feature_count, 0, warnings)

    @unittest.skipUnless(os.environ.get("SEMA_AUTHKEY"), "sem SEMA_AUTHKEY")
    def test_sema_embargos_siga_retorna(self):
        drawn, warnings = fetch_layers(_spec("embargos_siga", "tipologia_sema"),
                                       self.catalog, BBOX, UTM, secrets=self.secrets)
        self.assertEqual(len(drawn), 2, warnings)

    def test_incra_sigef_gml_retorna_parcelas(self):
        drawn, warnings = fetch_layers(_spec("sigef_particular_mt"), self.catalog,
                                       BBOX, UTM, secrets=self.secrets)
        self.assertEqual(len(drawn), 1, warnings)
        self.assertGreater(drawn[0].feature_count, 0, warnings)
        # atributo de rotulo veio do GML
        self.assertIn("parcela_codigo", drawn[0].features[0].props)

    def test_ibama_pamgia_rest_retorna(self):
        drawn, warnings = fetch_layers(_spec("embargos_ibama"), self.catalog,
                                       BBOX, UTM, secrets=self.secrets)
        self.assertEqual(len(drawn), 1, warnings)
        self.assertGreater(drawn[0].feature_count, 0, warnings)

    def test_ibama_siscom_wms_raster(self):
        # o SISCOM pode bloquear fora do navegador (Cloudflare) — nesse caso o
        # contrato e degradar com aviso, nunca quebrar
        drawn, warnings = fetch_layers(_spec("embargos_ibama_siscom"), self.catalog,
                                       BBOX, UTM, secrets=self.secrets)
        if drawn:
            self.assertIsNotNone(drawn[0].image)
            self.assertEqual(len(drawn[0].image_extent), 4)
        else:
            self.assertTrue(any("siscom" in w.lower() or "WMS raster" in w
                                for w in warnings), warnings)


if __name__ == "__main__":
    unittest.main()
