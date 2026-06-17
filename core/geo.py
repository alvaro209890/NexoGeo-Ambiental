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


def importar_shape_extraido(shp_path: str, temp_dir: str, zip_path: str,
                            dst_epsg: int, geo_epsg: int = 4674,
                            assume_epsg: int = 4674) -> ShapeImportado:
    avisos: list[str] = []
    src, feats_utm = _features(shp_path, dst_epsg, assume_epsg, avisos)
    rep_geo = _reprojetor(src, geo_epsg)
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
        zip_path=os.path.abspath(zip_path),
        temp_dir=temp_dir,
        shp_path=os.path.abspath(shp_path),
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


@contextlib.contextmanager
def abrir_shape_zip(zip_path: str, dst_epsg: int, geo_epsg: int = 4674,
                    assume_epsg: int = 4674, temp_root: str | None = None):
    """Extrai um .zip de shapefile em pasta temporaria e limpa ao final.

    Uso:
        with abrir_shape_zip("area.zip", 31982) as shp:
            ...
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"shapefile zip nao encontrado: {zip_path}")
    if temp_root:
        os.makedirs(temp_root, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shape_", dir=temp_root) as tmp:
        _safe_extract(zip_path, tmp)
        shp = _achar_shp(tmp, prefer_stem=Path(zip_path).stem)
        yield importar_shape_extraido(shp, tmp, zip_path, dst_epsg, geo_epsg, assume_epsg)


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
        flds = [f[0] for f in r.fields[1:]]
        attrs = dict(zip(flds, list(r.records()[0])))
        geom = ler_geometria(shp, projeto.crs_utm, unir=True)
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
