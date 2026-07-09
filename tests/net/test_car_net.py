# -*- coding: utf-8 -*-
"""Testes de REDE do fluxo CAR (busca ao vivo na SEMA). Pulados por padrao.

    NEXO_NET=1 SEMA_AUTHKEY=... python -m pytest tests/net/test_car_net.py -q
"""
import os
import unittest

from core import nexomap_car as car

# CAR estadual real usado na validacao ao vivo (Fazenda Boa Vista V, Querencia-ish)
CAR_ESTADUAL = "MT313839/2025"


@unittest.skipUnless(os.environ.get("NEXO_NET"), "rede desligada (defina NEXO_NET=1)")
class CarNetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secrets = {}
        if os.environ.get("SEMA_AUTHKEY"):
            cls.secrets["sema_authkey"] = os.environ["SEMA_AUTHKEY"]

    @unittest.skipUnless(os.environ.get("SEMA_AUTHKEY"), "sem SEMA_AUTHKEY")
    def test_busca_car_estadual_ao_vivo(self):
        r = car.buscar_car(CAR_ESTADUAL, self.secrets)
        self.assertTrue(r["ok"], r.get("erro"))
        self.assertEqual(r["campo"], "NUMEROESTADUAL")
        self.assertIn(r["origem"], ("car_digital", "requerimento"))
        self.assertIn(r["geometry"]["type"], ("Polygon", "MultiPolygon"))
        self.assertGreater(float(r["area_ha"]), 0)

    @unittest.skipUnless(os.environ.get("SEMA_AUTHKEY"), "sem SEMA_AUTHKEY")
    def test_busca_no_requerimento_ao_vivo(self):
        # forca a fonte de requerimento diretamente (mesma numeracao existe la)
        feats = car._get_features("Geoportal:MVW_REQUERIMENTO_ATP", "NUMEROESTADUAL",
                                  CAR_ESTADUAL, self.secrets["sema_authkey"])
        self.assertTrue(feats and feats[0].get("geometry"))

    @unittest.skipUnless(os.environ.get("SEMA_AUTHKEY"), "sem SEMA_AUTHKEY")
    def test_car_inexistente(self):
        r = car.buscar_car("MT000000/1900", self.secrets)
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
