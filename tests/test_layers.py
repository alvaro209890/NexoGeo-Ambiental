# -*- coding: utf-8 -*-
"""Testes offline das camadas (plano 03): parser GML, WMS GetMap URL, auth e cache."""
import json
import os
import tempfile
import unittest

from core.mapspec import mapspec_from_dict
from core.nexomap_catalog import load_layer_catalog, layer_index
from core.nexomap_layers import (fetch_layers, gml_para_geojson, wms_getmap_url,
                                 _cache_path, _cache_save_json)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GML_FIXTURE = """<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection
   xmlns:ms="http://example.org/ms"
   xmlns:wfs="http://www.opengis.net/wfs"
   xmlns:gml="http://www.opengis.net/gml">
  <gml:boundedBy><gml:Box srsName="EPSG:4326">
    <gml:coordinates>-52.30,-12.60 -52.10,-12.45</gml:coordinates>
  </gml:Box></gml:boundedBy>
  <gml:featureMember>
    <ms:certificada_sigef_particular_mt>
      <gml:boundedBy><gml:Box srsName="EPSG:4326">
        <gml:coordinates>-52.20,-12.50 -52.18,-12.48</gml:coordinates>
      </gml:Box></gml:boundedBy>
      <ms:msGeometry>
        <gml:Polygon srsName="EPSG:4326">
          <gml:outerBoundaryIs><gml:LinearRing>
            <gml:coordinates>-52.20,-12.50 -52.18,-12.50 -52.18,-12.48 -52.20,-12.48 -52.20,-12.50</gml:coordinates>
          </gml:LinearRing></gml:outerBoundaryIs>
        </gml:Polygon>
      </ms:msGeometry>
      <ms:parcela_codigo>ABC-123</ms:parcela_codigo>
      <ms:status>Certificada</ms:status>
    </ms:certificada_sigef_particular_mt>
  </gml:featureMember>
  <gml:featureMember>
    <ms:certificada_sigef_particular_mt>
      <ms:msGeometry>
        <gml:Polygon srsName="EPSG:4326">
          <gml:exterior><gml:LinearRing>
            <gml:posList>-52.15 -12.55 -52.13 -12.55 -52.13 -12.53 -52.15 -12.53 -52.15 -12.55</gml:posList>
          </gml:LinearRing></gml:exterior>
        </gml:Polygon>
      </ms:msGeometry>
      <ms:parcela_codigo>DEF-456</ms:parcela_codigo>
    </ms:certificada_sigef_particular_mt>
  </gml:featureMember>
</wfs:FeatureCollection>"""


class GmlParserTests(unittest.TestCase):
    def test_parser_le_feature_members(self):
        fc = gml_para_geojson(GML_FIXTURE)
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertEqual(len(fc["features"]), 2)
        f1 = fc["features"][0]
        self.assertEqual(f1["geometry"]["type"], "Polygon")
        self.assertEqual(f1["properties"]["parcela_codigo"], "ABC-123")
        self.assertEqual(f1["properties"]["status"], "Certificada")

    def test_geometria_valida_em_shapely(self):
        from shapely.geometry import shape
        fc = gml_para_geojson(GML_FIXTURE)
        for feat in fc["features"]:
            geom = shape(feat["geometry"])
            self.assertTrue(geom.is_valid)
            self.assertGreater(geom.area, 0)

    def test_poslist_tambem_e_lido(self):
        fc = gml_para_geojson(GML_FIXTURE)
        f2 = fc["features"][1]
        self.assertEqual(f2["properties"]["parcela_codigo"], "DEF-456")
        from shapely.geometry import shape
        self.assertTrue(shape(f2["geometry"]).is_valid)

    def test_gml_vazio_nao_quebra(self):
        fc = gml_para_geojson("<wfs:FeatureCollection xmlns:wfs='http://www.opengis.net/wfs'/>")
        self.assertEqual(fc["features"], [])


class WmsUrlTests(unittest.TestCase):
    def test_monta_url_getmap(self):
        url = wms_getmap_url("https://siscom.ibama.gov.br/geoserver/publica/wms",
                             "publica:vw_brasil_adm_embargo_a",
                             (400000.0, 8600000.0, 420000.0, 8615000.0), 31982,
                             width=1024)
        self.assertIn("request=GetMap", url)
        self.assertIn("layers=publica%3Avw_brasil_adm_embargo_a", url)
        self.assertIn("bbox=400000.0%2C8600000.0%2C420000.0%2C8615000.0", url)
        self.assertIn("srs=EPSG%3A31982", url)
        self.assertIn("width=1024", url)
        self.assertIn("height=768", url)  # proporcional ao bbox
        self.assertIn("format=image%2Fpng", url)
        self.assertIn("transparent=true", url)

    def test_endpoint_com_query_usa_ampersand(self):
        url = wms_getmap_url("https://x.gov.br/ogc.php?tema=abc", "abc",
                             (0.0, 0.0, 10.0, 10.0), 4674)
        self.assertIn("ogc.php?tema=abc&service=WMS", url)


class FetchLayersOfflineTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_layer_catalog(os.path.join(ROOT, "catalogo", "camadas.json"))

    def _spec(self, layer_id: str) -> object:
        return mapspec_from_dict({
            "titulo": "t", "layout_template": "x",
            "camadas": [
                {"id": "perimetro", "fonte": "area_base"},
                {"id": layer_id, "fonte": f"catalogo.{layer_id}",
                 "estilo": {"linha": "#f97316", "opacidade": 0.4}},
            ],
            "saidas": ["pdf"],
        })

    def test_camada_sem_auth_vira_aviso(self):
        spec = self._spec("embargos_siga")
        drawn, warnings = fetch_layers(spec, self.catalog, (-52.3, -12.6, -52.1, -12.45),
                                       31982, secrets={})
        self.assertEqual(drawn, [])
        self.assertTrue(any("sema_authkey" in w for w in warnings), warnings)

    def test_cache_usado_quando_rede_falha(self):
        # camada sem auth apontando para endpoint impossivel + cache preenchido
        catalog = {"camadas": [{
            "id": "fake", "nome": "Fake", "tema": "teste", "tipo": "wms_wfs",
            "endpoint": "https://nao-existe.invalid/ows", "layer": "x:y", "auth": None,
        }]}
        spec = mapspec_from_dict({
            "titulo": "t", "layout_template": "x",
            "camadas": [{"id": "fake", "fonte": "catalogo.fake"}],
            "saidas": ["pdf"],
        })
        bbox = (-52.3, -12.6, -52.1, -12.45)
        fc = {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[-52.2, -12.5], [-52.18, -12.5],
                                          [-52.18, -12.48], [-52.2, -12.48],
                                          [-52.2, -12.5]]]},
            "properties": {"nome": "do cache"}}]}
        with tempfile.TemporaryDirectory() as tmp:
            # o fetch expande o bbox; pre-calcula o caminho com o mesmo expandido
            from core.nexomap_layers import _expand_bbox_geo
            path = _cache_path(tmp, "fake", _expand_bbox_geo(bbox), ".geojson")
            _cache_save_json(path, fc)
            drawn, warnings = fetch_layers(spec, catalog, bbox, 31982,
                                           secrets={}, cache_dir=tmp)
            self.assertEqual(len(drawn), 1)
            self.assertEqual(drawn[0].feature_count, 1)
            self.assertTrue(any("cache local" in w for w in warnings), warnings)

    def test_catalogo_tem_camadas_do_car_digital(self):
        idx = layer_index(self.catalog)
        for cid in ("car_atp", "car_app", "car_arl", "car_avn", "car_auas",
                    "embargos_siga", "desembargos_sema", "autos_siga",
                    "embargos_ibama_siscom", "alertas_mapbiomas_simpl"):
            self.assertIn(cid, idx, cid)
        # correcoes de 2026-07-08
        self.assertEqual(idx["tipologia_sema"]["layer"], "Geoportal:SIMCAR_D_TIPOLOGIA_VEGETAL")
        self.assertEqual(idx["snci_particular_mt"]["layer"], "imoveiscertificados_privado_mt")
        for cid in ("sigef_particular_mt", "sigef_publico_mt", "snci_particular_mt",
                    "assentamentos_incra"):
            self.assertEqual(idx[cid]["tipo"], "wfs_gml", cid)
            self.assertTrue(idx[cid]["endpoint"].startswith("https://"), cid)
        self.assertEqual(idx["embargos_ibama_siscom"]["tipo"], "wms_raster")
        # toda camada tem descricao (a IA usa para escolher)
        for cid, cfg in idx.items():
            self.assertTrue(cfg.get("descricao"), f"{cid} sem descricao")


if __name__ == "__main__":
    unittest.main()
