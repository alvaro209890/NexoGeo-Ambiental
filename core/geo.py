# -*- coding: utf-8 -*-
"""core.geo — operações geoespaciais genéricas (Fase 1).

Sem nada específico de imóvel: o CRS de destino, os shapes e os campos vêm do
``Projeto``. A reprojeção é decidida **automaticamente por shape**, lendo o ``.prj``
de cada arquivo — não se assume qual camada está em graus e qual está em UTM
(é o que tornava os scripts antigos frágeis: o "is_geo" ficava cravado no código).

API principal:
    crs_do_prj(shp)                  -> CRS do shapefile (lendo o .prj)
    ler_geometria(shp, dst, unir=…)  -> feições reprojetadas p/ dst (EPSG)
    carregar_cars(projeto)           -> [Car] com o polígono de cada fazenda em UTM
    atribuir(cars, shp, dst, …)      -> soma de área por fazenda (sobreposição > limiar)
"""
from __future__ import annotations

import contextlib
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import shapefile  # pyshp
from shapely.geometry import shape as _shp_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as _transform, unary_union
from pyproj import CRS, Transformer


# --------------------------------------------------------------------------- #
# Reprojeção automática a partir do .prj
# --------------------------------------------------------------------------- #
def crs_do_prj(shp_path: str) -> Optional[CRS]:
    """Lê o ``.prj`` ao lado do shapefile e devolve o ``CRS`` (ou ``None``)."""
    prj = os.path.splitext(shp_path)[0] + ".prj"
    if not os.path.exists(prj):
        return None
    with open(prj, "r", encoding="latin-1") as f:
        wkt = f.read().strip()
    return CRS.from_wkt(wkt) if wkt else None


def _reprojetor(src: Optional[CRS], dst_epsg: int) -> Optional[Callable[[BaseGeometry], BaseGeometry]]:
    """Função geom->geom de ``src`` para ``dst_epsg``; ``None`` se já estiver no destino."""
    dst = CRS.from_epsg(dst_epsg)
    if src is None or src.equals(dst):
        return None
    tr = Transformer.from_crs(src, dst, always_xy=True)
    return lambda g: _transform(lambda x, y, z=None: tr.transform(x, y), g)


def reprojetar(geom: BaseGeometry, src_epsg: int, dst_epsg: int) -> BaseGeometry:
    """Reprojeta uma geometria de ``src_epsg`` para ``dst_epsg`` (identidade se iguais)."""
    rep = _reprojetor(CRS.from_epsg(src_epsg), dst_epsg)
    return rep(geom) if rep else geom


def ler_geometria(shp_path: str, dst_epsg: int, unir: bool = False):
    """Lê um shapefile e reprojeta cada geometria para ``dst_epsg`` conforme o ``.prj``.

    - ``unir=False`` (padrão): devolve ``[(geom, record_dict), ...]``.
    - ``unir=True``: devolve uma única geometria (união de todas) ou ``None``.
    """
    r = shapefile.Reader(shp_path, encoding="latin-1")
    try:
        rep = _reprojetor(crs_do_prj(shp_path), dst_epsg)
        flds = [f[0] for f in r.fields[1:]]
        feats, geoms = [], []
        for rec, sh in zip(r.records(), r.shapes()):
            if sh.shapeType == 0:  # NullShape
                continue
            g = _shp_shape(sh.__geo_interface__)
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty:
                continue
            if rep:
                g = rep(g)
            if unir:
                geoms.append(g)
            else:
                feats.append((g, dict(zip(flds, list(rec)))))
    finally:
        r.close()
    if unir:
        return unary_union(geoms) if geoms else None
    return feats


# --------------------------------------------------------------------------- #
# Importacao de shapefile compactado (.zip)
# --------------------------------------------------------------------------- #
@dataclass
class ShapeImportado:
    """Resultado da leitura temporaria de um shapefile zipado.

    ``temp_dir`` existe apenas dentro do contexto de ``abrir_shape_zip``; depois
    do ``with`` ele e removido por ``TemporaryDirectory``.
    """
    zip_path: str
    temp_dir: str
    shp_path: str
    src_crs: Optional[CRS]
    dst_epsg: int
    geo_epsg: int
    features_utm: list[tuple[BaseGeometry, dict]]
    features_geo: list[tuple[BaseGeometry, dict]]
    union_utm: BaseGeometry
    union_geo: BaseGeometry
    bbox_utm: tuple[float, float, float, float]
    bbox_geo: tuple[float, float, float, float]
    area_ha: float
    avisos: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        return len(self.features_utm)

    def resumo(self) -> dict:
        epsg = None
        if self.src_crs:
            try:
                epsg = self.src_crs.to_epsg()
            except Exception:
                epsg = None
        return {
            "zip": self.zip_path,
            "shp": self.shp_path,
            "crs_origem": epsg or (self.src_crs.to_string() if self.src_crs else None),
            "crs_utm": self.dst_epsg,
            "crs_geo": self.geo_epsg,
            "poligonos": self.feature_count,
            "area_ha": self.area_ha,
            "bbox_geo": self.bbox_geo,
            "bbox_utm": self.bbox_utm,
            "avisos": list(self.avisos),
        }


def _safe_extract(zip_path: str, dest_dir: str) -> None:
    root = Path(dest_dir).resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for item in zf.infolist():
            target = (root / item.filename).resolve()
            if not str(target).startswith(str(root)):
                raise ValueError(f"zip contem caminho inseguro: {item.filename}")
        zf.extractall(root)


def _achar_shp(root: str, prefer_stem: str | None = None) -> str:
    candidatos = []
    for shp in Path(root).rglob("*.shp"):
        base = shp.with_suffix("")
        if base.with_suffix(".shx").exists() and base.with_suffix(".dbf").exists():
            score = 0
            if prefer_stem and shp.stem.lower() == prefer_stem.lower():
                score += 1000
            try:
                score += shp.stat().st_size
            except OSError:
                pass
            candidatos.append((score, shp))
    if not candidatos:
        raise FileNotFoundError("zip nao contem um conjunto .shp/.shx/.dbf valido")
    candidatos.sort(reverse=True)
    return str(candidatos[0][1])


def _reader(shp_path: str):
    last = None
    for enc in ("latin-1", "utf-8", "cp1252"):
        try:
            return shapefile.Reader(shp_path, encoding=enc)
        except Exception as e:
            last = e
    raise last  # type: ignore[misc]


def _features(shp_path: str, dst_epsg: int, assume_epsg: int, avisos: list[str]):
    src = crs_do_prj(shp_path)
    if src is None:
        src = CRS.from_epsg(assume_epsg)
        avisos.append(f".prj ausente; assumido EPSG:{assume_epsg}.")
    rep = _reprojetor(src, dst_epsg)
    r = _reader(shp_path)
    try:
        flds = [f[0] for f in r.fields[1:]]
        out = []
        for idx, (rec, sh) in enumerate(zip(r.records(), r.shapes()), start=1):
            if sh.shapeType == 0:
                avisos.append(f"feicao {idx} ignorada: geometria nula.")
                continue
            g = _shp_shape(sh.__geo_interface__)
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty:
                avisos.append(f"feicao {idx} ignorada: geometria vazia/invalida.")
                continue
            if rep:
                g = rep(g)
            out.append((g, dict(zip(flds, list(rec)))))
    finally:
        try:
            r.close()
        except Exception:
            pass
    if not out:
        raise ValueError("shapefile sem geometrias validas")
    return src, out


def _montar_importado(origem_path: str, temp_dir: str, shp_path: str, src: Optional[CRS],
                      feats_utm: list, dst_epsg: int, geo_epsg: int,
                      avisos: list[str]) -> ShapeImportado:
    feats_geo = []
    for geom_utm, rec in feats_utm:
        # Reprojeta a partir do UTM ja carregado quando necessario.
        if dst_epsg == geo_epsg:
            g_geo = geom_utm
        else:
            g_geo = reprojetar(geom_utm, dst_epsg, geo_epsg)
        feats_geo.append((g_geo, rec))
    union_utm = unary_union([g for g, _ in feats_utm])
    union_geo = unary_union([g for g, _ in feats_geo])
    return ShapeImportado(
        zip_path=os.path.abspath(origem_path),
        temp_dir=temp_dir,
        shp_path=os.path.abspath(shp_path) if shp_path else "",
        src_crs=src,
        dst_epsg=dst_epsg,
        geo_epsg=geo_epsg,
        features_utm=feats_utm,
        features_geo=feats_geo,
        union_utm=union_utm,
        union_geo=union_geo,
        bbox_utm=tuple(union_utm.bounds),
        bbox_geo=tuple(union_geo.bounds),
        area_ha=union_utm.area / 10000.0,
        avisos=avisos,
    )


def importar_shape_extraido(shp_path: str, temp_dir: str, zip_path: str,
                            dst_epsg: int, geo_epsg: int = 4674,
                            assume_epsg: int = 4674) -> ShapeImportado:
    avisos: list[str] = []
    src, feats_utm = _features(shp_path, dst_epsg, assume_epsg, avisos)
    return _montar_importado(zip_path, temp_dir, shp_path, src, feats_utm, dst_epsg, geo_epsg, avisos)


# --------------------------------------------------------------------------- #
# GeoJSON / KML / KMZ
# --------------------------------------------------------------------------- #
def _geojson_features(path: str, dst_epsg: int, avisos: list[str]):
    """Feicoes de um .geojson/.json (WGS84 por especificacao; aceita crs legado)."""
    import json as _json
    from shapely.geometry import shape as _gshape

    with open(path, "r", encoding="utf-8") as f:
        data = _json.load(f)
    src_epsg = 4326
    crs_name = str(((data.get("crs") or {}).get("properties") or {}).get("name", ""))
    m_epsg = None
    if crs_name:
        import re as _re
        m_epsg = _re.search(r"(?:EPSG|epsg)[:.]+(\d+)", crs_name)
    if m_epsg:
        src_epsg = int(m_epsg.group(1))
        avisos.append(f"GeoJSON com crs legado EPSG:{src_epsg}.")
    src = CRS.from_epsg(src_epsg)
    rep = _reprojetor(src, dst_epsg)
    raw = data.get("features") if data.get("type") == "FeatureCollection" else None
    if raw is None:
        if data.get("type") == "Feature":
            raw = [data]
        elif data.get("type"):
            raw = [{"type": "Feature", "geometry": data, "properties": {}}]
        else:
            raise ValueError(f"GeoJSON invalido (sem features): {path}")
    feats = []
    for idx, feat in enumerate(raw, start=1):
        geom_data = feat.get("geometry")
        if not geom_data:
            avisos.append(f"feicao {idx} ignorada: sem geometria.")
            continue
        g = _gshape(geom_data)
        if not g.is_valid:
            g = g.buffer(0)
        if g.is_empty:
            avisos.append(f"feicao {idx} ignorada: geometria vazia/invalida.")
            continue
        if rep:
            g = rep(g)
        feats.append((g, dict(feat.get("properties") or {})))
    if not feats:
        raise ValueError(f"GeoJSON sem geometrias validas: {path}")
    return src, feats


def _kml_coords(text: str):
    pts = []
    for token in (text or "").split():
        parts = token.split(",")
        if len(parts) >= 2:
            pts.append((float(parts[0]), float(parts[1])))
    return pts


def _kml_features(kml_bytes: bytes, path: str, dst_epsg: int, avisos: list[str]):
    """Placemarks de um KML (sempre WGS84). Suporta Polygon/MultiGeometry/LineString/Point."""
    import xml.etree.ElementTree as ET
    from shapely.geometry import LineString, Point, Polygon

    root = ET.fromstring(kml_bytes)
    ns = {"k": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {"k": ""}

    def q(tag: str) -> str:
        return f"{{{ns['k']}}}{tag}" if ns["k"] else tag

    src = CRS.from_epsg(4326)
    rep = _reprojetor(src, dst_epsg)
    feats = []

    def _poly(poly_el):
        outer = poly_el.find(f"{q('outerBoundaryIs')}/{q('LinearRing')}/{q('coordinates')}")
        if outer is None or not (outer.text or "").strip():
            return None
        shell = _kml_coords(outer.text)
        holes = []
        for inner in poly_el.findall(f"{q('innerBoundaryIs')}/{q('LinearRing')}/{q('coordinates')}"):
            if (inner.text or "").strip():
                holes.append(_kml_coords(inner.text))
        if len(shell) < 4:
            return None
        g = Polygon(shell, holes)
        return g if g.is_valid else g.buffer(0)

    for pm in root.iter(q("Placemark")):
        nome_el = pm.find(q("name"))
        props = {"Name": (nome_el.text or "").strip() if nome_el is not None else ""}
        geoms = []
        for poly_el in pm.iter(q("Polygon")):
            g = _poly(poly_el)
            if g is not None and not g.is_empty:
                geoms.append(g)
        if not geoms:
            for line_el in pm.iter(q("LineString")):
                coords_el = line_el.find(q("coordinates"))
                pts = _kml_coords(coords_el.text if coords_el is not None else "")
                if len(pts) >= 2:
                    geoms.append(LineString(pts))
        if not geoms:
            for pt_el in pm.iter(q("Point")):
                coords_el = pt_el.find(q("coordinates"))
                pts = _kml_coords(coords_el.text if coords_el is not None else "")
                if pts:
                    geoms.append(Point(pts[0]))
        for g in geoms:
            g_final = rep(g) if rep else g
            feats.append((g_final, dict(props)))
    if not feats:
        raise ValueError(f"KML sem Placemarks com geometria valida: {path}")
    return src, feats


_EXTS_GEOMETRIA = (".zip", ".shp", ".geojson", ".json", ".kml", ".kmz")


@contextlib.contextmanager
def abrir_shape_zip(zip_path: str, dst_epsg: int, geo_epsg: int = 4674,
                    assume_epsg: int = 4674, temp_root: str | None = None):
    """Abre uma geometria de area em varios formatos e limpa temporarios ao final.

    Formatos aceitos: ``.zip`` (shapefile compactado), ``.shp`` solto (com
    ``.shx``/``.dbf`` ao lado), ``.geojson``/``.json``, ``.kml`` e ``.kmz``.
    O nome historico ``abrir_shape_zip`` foi mantido por compatibilidade;
    ``abrir_geometria`` e um alias.

    Uso:
        with abrir_shape_zip("area.zip", 31982) as shp:
            ...
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(
            f"geometria nao encontrada: {zip_path} "
            f"(formatos aceitos: {', '.join(_EXTS_GEOMETRIA)})"
        )
    ext = os.path.splitext(zip_path)[1].lower()
    if ext not in _EXTS_GEOMETRIA:
        raise ValueError(
            f"formato de geometria nao suportado: '{ext or zip_path}'. "
            f"Use {', '.join(_EXTS_GEOMETRIA)}."
        )
    if temp_root:
        os.makedirs(temp_root, exist_ok=True)

    avisos: list[str] = []
    if ext == ".shp":
        base = Path(zip_path).with_suffix("")
        faltando = [s for s in (".shx", ".dbf") if not base.with_suffix(s).exists()]
        if faltando:
            raise FileNotFoundError(
                f"shapefile incompleto: faltam {', '.join(faltando)} ao lado de {zip_path}"
            )
        src, feats = _features(zip_path, dst_epsg, assume_epsg, avisos)
        yield _montar_importado(zip_path, "", zip_path, src, feats, dst_epsg, geo_epsg, avisos)
        return
    if ext in (".geojson", ".json"):
        src, feats = _geojson_features(zip_path, dst_epsg, avisos)
        yield _montar_importado(zip_path, "", "", src, feats, dst_epsg, geo_epsg, avisos)
        return
    if ext == ".kml":
        with open(zip_path, "rb") as f:
            src, feats = _kml_features(f.read(), zip_path, dst_epsg, avisos)
        yield _montar_importado(zip_path, "", "", src, feats, dst_epsg, geo_epsg, avisos)
        return
    if ext == ".kmz":
        with zipfile.ZipFile(zip_path) as zf:
            kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kml_names:
                raise ValueError(f"kmz sem arquivo .kml interno: {zip_path}")
            kml_names.sort(key=lambda n: (n.lower() != "doc.kml", n))
            src, feats = _kml_features(zf.read(kml_names[0]), zip_path, dst_epsg, avisos)
        yield _montar_importado(zip_path, "", "", src, feats, dst_epsg, geo_epsg, avisos)
        return

    # .zip: shapefile compactado (ou kml compactado sem extensao .kmz)
    with tempfile.TemporaryDirectory(prefix="shape_", dir=temp_root) as tmp:
        _safe_extract(zip_path, tmp)
        try:
            shp = _achar_shp(tmp, prefer_stem=Path(zip_path).stem)
        except FileNotFoundError:
            kmls = sorted(Path(tmp).rglob("*.kml"))
            if kmls:
                src, feats = _kml_features(kmls[0].read_bytes(), zip_path, dst_epsg, avisos)
                yield _montar_importado(zip_path, tmp, "", src, feats, dst_epsg, geo_epsg, avisos)
                return
            raise FileNotFoundError(
                f"zip nao contem um conjunto .shp/.shx/.dbf valido nem .kml: {zip_path}"
            )
        yield importar_shape_extraido(shp, tmp, zip_path, dst_epsg, geo_epsg, assume_epsg)


abrir_geometria = abrir_shape_zip


# --------------------------------------------------------------------------- #
# CARs (perímetro de cada fazenda)
# --------------------------------------------------------------------------- #
@dataclass
class Car:
    """Perímetro (unido, em UTM do projeto) e atributos do CAR de uma fazenda."""
    id: str
    nome: str
    geom: BaseGeometry
    attrs: dict = field(default_factory=dict)

    def attr(self, projeto, chave_logica: str, padrao=None):
        """Lê um atributo do dbf pelo nome lógico (via ``projeto.mapa_campos``).

        Ex.: ``car.attr(projeto, "area_ha")`` resolve para a coluna ``AREA_HA``.
        """
        coluna = projeto.mapa_campos.get(chave_logica, chave_logica)
        return self.attrs.get(coluna, padrao)


def carregar_cars(projeto) -> list[Car]:
    """Carrega o polígono (unido, em UTM) e os atributos do CAR de cada fazenda do projeto."""
    cardir = projeto.caminho("car")
    cars: list[Car] = []
    for fz in projeto.fazendas:
        shp = os.path.join(cardir, fz.shape_car, "CAR_ATP.shp")
        if not os.path.exists(shp):
            raise FileNotFoundError(f"shape do CAR não encontrado: {shp}")
        r = shapefile.Reader(shp, encoding="latin-1")
        try:
            flds = [f[0] for f in r.fields[1:]]
            records = r.records()
            attrs = dict(zip(flds, list(records[0]))) if records else {}
        finally:
            r.close()
        geom = ler_geometria(shp, projeto.crs_utm, unir=True)
        if geom is None:
            raise ValueError(f"shape do CAR sem geometrias válidas: {shp}")
        cars.append(Car(fz.id, fz.nome, geom, attrs))
    return cars


# --------------------------------------------------------------------------- #
# Atribuição espacial (sobreposição > limiar)
# --------------------------------------------------------------------------- #
def atribuir(cars: list[Car], shp_path: str, dst_epsg: int,
             area_fields=("Area", "AREA"), limiar: float = 0.5):
    """Atribui cada polígono de ``shp_path`` ao CAR de maior sobreposição (> ``limiar``).

    Devolve ``(assoc, detalhe)``::

        assoc[id] = {"area": soma_ha, "n": qtd_poligonos}
        detalhe   = [(indice, area_ha, id_do_car|None), ...]

    A área vem do 1º campo existente em ``area_fields``; se nenhum existir, usa a
    área da geometria reprojetada (m² → ha). Mesma regra dos scripts originais,
    agora genérica e dirigida por configuração.
    """
    assoc = {c.id: {"area": 0.0, "n": 0} for c in cars}
    detalhe = []
    for i, (g, rec) in enumerate(ler_geometria(shp_path, dst_epsg, unir=False), start=1):
        if g.is_empty or g.area <= 0:
            detalhe.append((i, 0.0, None))
            continue
        area_val = None
        for campo in area_fields:
            if campo in rec:
                try:
                    area_val = float(rec[campo])
                    break
                except (TypeError, ValueError):
                    pass
        if area_val is None:
            area_val = g.area / 10000.0
        best, bestf = None, 0.0
        for c in cars:
            f = g.intersection(c.geom).area / g.area
            if f > bestf:
                bestf, best = f, c.id
        if best is not None and bestf > limiar:
            assoc[best]["area"] += area_val
            assoc[best]["n"] += 1
            detalhe.append((i, area_val, best))
        else:
            detalhe.append((i, area_val, None))
    return assoc, detalhe
