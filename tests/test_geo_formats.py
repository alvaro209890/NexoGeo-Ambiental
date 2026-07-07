# -*- coding: utf-8 -*-
"""Testes dos formatos de geometria aceitos por core.geo.abrir_shape_zip."""
import json
import os
import tempfile
import unittest
import zipfile

import shapefile
from pyproj import CRS

from core.geo import abrir_geometria, abrir_shape_zip


# quadrado ~1.1 km x 1.1 km perto de Vila Rica/MT (EPSG:4674)
SQUARE = [(-51.12, -10.02), (-51.11, -10.02), (-51.11, -10.01), (-51.12, -10.01), (-51.12, -10.02)]
UTM = 31982


def _write_shapefile(dirpath: str, stem: str = "area") -> str:
    base = os.path.join(dirpath, stem)
    with shapefile.Writer(base, shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=40)
        w.poly([SQUARE[::-1]])  # shapefile exige anel exterior em sentido horario
        w.record("Fazenda Teste")
    with open(base + ".prj", "w", encoding="ascii") as f:
        f.write(CRS.from_epsg(4674).to_wkt())
    return base + ".shp"


def _zip_shapefile(dirpath: str) -> str:
    shp = _write_shapefile(dirpath)
    zip_path = os.path.join(dirpath, "area.zip")
    base = os.path.splitext(shp)[0]
    with zipfile.ZipFile(zip_path, "w") as zf:
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            zf.write(base + ext, "area" + ext)
    return zip_path


KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>
<name>Area KML</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
{coords}
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document></kml>
""".format(coords=" ".join(f"{x},{y},0" for x, y in SQUARE))


class GeoFormatsTests(unittest.TestCase):
    def _check(self, area):
        self.assertEqual(area.feature_count, 1)
        self.assertGreater(area.area_ha, 100)   # ~121 ha
        self.assertLess(area.area_ha, 150)
        self.assertAlmostEqual(area.bbox_geo[0], -51.12, places=3)
        # UTM em metros: coordenadas na casa das centenas de milhar
        self.assertGreater(area.bbox_utm[0], 100000)

    def test_zip_shapefile(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = _zip_shapefile(tmp)
            with abrir_shape_zip(zip_path, UTM) as area:
                self._check(area)

    def test_shp_solto(self):
        with tempfile.TemporaryDirectory() as tmp:
            shp = _write_shapefile(tmp)
            with abrir_geometria(shp, UTM) as area:
                self._check(area)

    def test_shp_incompleto_da_erro_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            shp = _write_shapefile(tmp)
            os.remove(os.path.splitext(shp)[0] + ".dbf")
            with self.assertRaises(FileNotFoundError) as ctx:
                with abrir_geometria(shp, UTM):
                    pass
            self.assertIn(".dbf", str(ctx.exception))

    def test_geojson(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "area.geojson")
            payload = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
                    "properties": {"NOME": "Area GeoJSON"},
                }],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            with abrir_geometria(path, UTM) as area:
                self._check(area)

    def test_kml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "area.kml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(KML)
            with abrir_geometria(path, UTM) as area:
                self._check(area)
                self.assertEqual(area.features_utm[0][1].get("Name"), "Area KML")

    def test_kmz(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "area.kmz")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("doc.kml", KML)
            with abrir_geometria(path, UTM) as area:
                self._check(area)

    def test_formato_desconhecido_da_erro_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "area.gpx")
            with open(path, "w") as f:
                f.write("x")
            with self.assertRaises(ValueError) as ctx:
                with abrir_geometria(path, UTM):
                    pass
            self.assertIn("nao suportado", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
