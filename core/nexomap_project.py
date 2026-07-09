# -*- coding: utf-8 -*-
"""Project loading for NexoMap AI.

This module is intentionally separate from ``core.config``. NexoGeo projects are
analysis-oriented; NexoMap projects are map-generation-oriented and start from a
single base geometry plus map/catalog/template configuration.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any


SCHEMA_VERSION = 1

DEFAULT_LAYOUTS_MANIFEST = os.path.join("templates", "layouts", "MANIFEST.json")

# formatos de geometria aceitos como area_base (alem do classico .zip de shapefile)
AREA_BASE_TIPOS = {"shapefile_zip", "geometria"}


class NexoMapError(Exception):
    """Configuration or runtime error raised by NexoMap modules."""


@dataclass
class NexoMapMunicipio:
    nome: str
    uf: str
    ibge: str


@dataclass
class NexoMapCRS:
    utm: int
    geografico: int = 4674


@dataclass
class NexoMapPastas:
    shapes: str = "Shapes"
    resultados: str = "Resultados"
    mapas: str = "Resultados/Mapas"


@dataclass
class NexoMapAreaBase:
    tipo: str
    path: str


@dataclass
class NexoMapProject:
    versao_schema: int
    nome: str
    cliente: str
    municipio: NexoMapMunicipio
    crs: NexoMapCRS
    raiz_dados: str
    pastas: NexoMapPastas
    area_base: NexoMapAreaBase
    catalogo_camadas: str
    templates_layouts: str
    data_consulta: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)
    # camadas de shapefile LOCAL do imovel (lotes, AVN, AC, AUAS...) que a IA pode
    # adicionar por 'local.<id>'. Cada item: {id, arquivo, nome, tema, estilo, rotulo}.
    camadas_locais: list[dict] = field(default_factory=list)
    _arquivo: str = ""

    def camadas_locais_index(self) -> dict[str, dict]:
        return {str(c.get("id")): c for c in (self.camadas_locais or []) if c.get("id")}

    def data_consulta_efetiva(self) -> str:
        if str(self.data_consulta).strip().lower() == "auto":
            return date.today().strftime("%d/%m/%Y")
        return str(self.data_consulta)

    def raiz_abs(self) -> str:
        if os.path.isabs(self.raiz_dados):
            return os.path.normpath(self.raiz_dados)
        return os.path.normpath(os.path.join(os.path.dirname(self._arquivo), self.raiz_dados))

    def repo_root(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def resolve_data_path(self, value: str) -> str:
        if os.path.isabs(value):
            return os.path.normpath(value)
        return os.path.normpath(os.path.join(self.raiz_abs(), value))

    def resolve_repo_or_data_path(self, value: str) -> str:
        if os.path.isabs(value):
            return os.path.normpath(value)
        data_candidate = os.path.normpath(os.path.join(self.raiz_abs(), value))
        if os.path.exists(data_candidate):
            return data_candidate
        return os.path.normpath(os.path.join(self.repo_root(), value))

    def caminho(self, chave: str) -> str:
        rel = getattr(self.pastas, chave)
        return self.resolve_data_path(rel)

    def area_base_path(self) -> str:
        return self.resolve_data_path(self.area_base.path)

    def catalog_path(self) -> str:
        return self.resolve_repo_or_data_path(self.catalogo_camadas)

    def template_manifest_path(self) -> str:
        path = self.resolve_repo_or_data_path(self.templates_layouts)
        if not os.path.exists(path):
            # projetos antigos apontavam para templates/mxd (ArcMap, removido);
            # cai no manifesto de layouts nativos do repositorio
            fallback = os.path.join(self.repo_root(), DEFAULT_LAYOUTS_MANIFEST)
            if os.path.exists(fallback):
                return fallback
        return path

    def mapas_dir(self) -> str:
        return self.caminho("mapas")

    def save(self):
        """Persiste alteracoes no projeto JSON (area_base, crs, etc.)."""
        import json as _json
        with open(self._arquivo, "r", encoding="utf-8") as f:
            data = _json.load(f)
        data.setdefault("area_base", {})["path"] = self.area_base.path
        data.setdefault("area_base", {})["tipo"] = self.area_base.tipo
        data["crs_utm"] = self.crs.utm
        with open(self._arquivo, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)


def _req(data: dict, key: str, ctx: str):
    if key not in data or data[key] in (None, ""):
        raise NexoMapError(f"campo obrigatorio ausente: {ctx}.{key}")
    return data[key]


def load_nexomap_project(path: str) -> NexoMapProject:
    """Load and minimally validate a NexoMap ``projeto.json``."""
    if not os.path.exists(path):
        raise NexoMapError(f"projeto nao encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise NexoMapError(f"JSON invalido em {path}: {e}") from e

    versao = int(data.get("versao_schema", SCHEMA_VERSION))
    if versao != SCHEMA_VERSION:
        raise NexoMapError(f"versao_schema {versao} nao suportada")

    municipio_data = _req(data, "municipio", "projeto")
    municipio = NexoMapMunicipio(
        nome=str(_req(municipio_data, "nome", "municipio")),
        uf=str(_req(municipio_data, "uf", "municipio")).upper(),
        ibge=str(_req(municipio_data, "ibge", "municipio")),
    )

    crs_data = data.get("crs") or {}
    crs_utm = crs_data.get("utm", data.get("crs_utm"))
    if not crs_utm:
        raise NexoMapError("campo obrigatorio ausente: projeto.crs.utm")
    crs = NexoMapCRS(utm=int(crs_utm), geografico=int(crs_data.get("geografico", 4674)))

    pastas_data = data.get("pastas") or {}
    pastas = NexoMapPastas(
        shapes=str(pastas_data.get("shapes", "Shapes")),
        resultados=str(pastas_data.get("resultados", "Resultados")),
        mapas=str(pastas_data.get("mapas", "Resultados/Mapas")),
    )

    area_data = _req(data, "area_base", "projeto")
    area_base = NexoMapAreaBase(
        tipo=str(area_data.get("tipo", "shapefile_zip")),
        path=str(_req(area_data, "path", "area_base")),
    )
    if area_base.tipo not in AREA_BASE_TIPOS:
        raise NexoMapError("area_base.tipo suportado: shapefile_zip ou geometria (.zip/.shp/.geojson/.kml/.kmz)")

    nome = str(data.get("nome") or data.get("imovel") or "").strip()
    if not nome:
        raise NexoMapError("campo obrigatorio ausente: projeto.nome")

    return NexoMapProject(
        versao_schema=versao,
        nome=nome,
        cliente=str(data.get("cliente", "")),
        municipio=municipio,
        crs=crs,
        raiz_dados=str(_req(data, "raiz_dados", "projeto")),
        pastas=pastas,
        area_base=area_base,
        catalogo_camadas=str(data.get("catalogo_camadas", "catalogo/camadas.json")),
        templates_layouts=str(data.get("templates_layouts") or data.get("templates_mxd") or DEFAULT_LAYOUTS_MANIFEST),
        data_consulta=str(data.get("data_consulta", "auto")),
        metadata=data.get("metadata") or {},
        camadas_locais=data.get("camadas_locais") or [],
        _arquivo=os.path.abspath(path),
    )


def create_project_template(nome: str, cliente: str, destino: str) -> str:
    """Create a new NexoMap project folder and return its ``projeto.json`` path."""
    if not os.path.isdir(destino):
        raise NexoMapError(f"pasta de destino nao existe: {destino}")
    project_dir = os.path.join(destino, nome)
    os.makedirs(os.path.join(project_dir, "Shapes"), exist_ok=True)
    os.makedirs(os.path.join(project_dir, "Resultados", "Mapas"), exist_ok=True)
    template = {
        "versao_schema": SCHEMA_VERSION,
        "nome": nome,
        "cliente": cliente,
        "municipio": {"nome": "", "uf": "MT", "ibge": ""},
        "crs": {"utm": 31982, "geografico": 4674},
        "raiz_dados": ".",
        "pastas": {
            "shapes": "Shapes",
            "resultados": "Resultados",
            "mapas": "Resultados/Mapas",
        },
        "area_base": {"tipo": "shapefile_zip", "path": "Shapes/area.zip"},
        "catalogo_camadas": "catalogo/camadas.json",
        "templates_layouts": DEFAULT_LAYOUTS_MANIFEST,
    }
    path = os.path.join(project_dir, "projeto.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    return path


def ensure_project_from_analysis(analysis_project, area_path: str | None = None) -> str:
    """Create/update the internal NexoMap project for a NexoGeo analysis.

    The generated file lives inside the analysis data root, under ``.nexomap``.
    It is a bridge contract only; the user keeps opening the normal NexoGeo
    ``projeto.json`` in the app.
    """
    root = analysis_project.raiz_abs()
    nexomap_dir = os.path.join(root, ".nexomap")
    os.makedirs(nexomap_dir, exist_ok=True)

    default_area = area_path or os.path.join(root, "Shapes", "area.zip")
    if area_path:
        area_abs = os.path.abspath(area_path)
    else:
        area_abs = os.path.abspath(default_area)
    try:
        area_rel = os.path.relpath(area_abs, root)
        if area_rel.startswith(".."):
            area_rel = area_abs
    except ValueError:
        area_rel = area_abs

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = {
        "versao_schema": SCHEMA_VERSION,
        "nome": analysis_project.imovel,
        "cliente": analysis_project.cliente,
        "municipio": {
            "nome": analysis_project.municipio.nome,
            "uf": analysis_project.municipio.uf,
            "ibge": analysis_project.municipio.ibge,
        },
        "crs": {"utm": analysis_project.crs_utm, "geografico": analysis_project.crs_geo},
        "data_consulta": analysis_project.data_consulta,
        "raiz_dados": root,
        "pastas": {
            "shapes": analysis_project.pastas.shapes,
            "resultados": analysis_project.pastas.resultados,
            "mapas": os.path.join(analysis_project.pastas.resultados, "Mapas_IA"),
        },
        "area_base": {"tipo": "shapefile_zip", "path": area_rel},
        "catalogo_camadas": os.path.join(repo, "catalogo", "camadas.json"),
        "templates_layouts": os.path.join(repo, "templates", "layouts", "MANIFEST.json"),
        "metadata": {
            "origem": "nexogeo_analysis_tab",
            "analysis_project": analysis_project._arquivo,
        },
    }
    path = os.path.join(nexomap_dir, "projeto.nexomap.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def resumo_project(project: NexoMapProject) -> dict:
    """Serializable project summary for the API/UI."""
    area_path = project.area_base_path()
    return {
        "arquivo": project._arquivo,
        "nome": project.nome,
        "cliente": project.cliente,
        "municipio": {
            "nome": project.municipio.nome,
            "uf": project.municipio.uf,
            "ibge": project.municipio.ibge,
        },
        "crs": {"utm": project.crs.utm, "geografico": project.crs.geografico},
        "data_consulta": project.data_consulta_efetiva(),
        "raiz": project.raiz_abs(),
        "area_base": {"path": area_path, "exists": os.path.exists(area_path), "tipo": project.area_base.tipo},
        "pastas": {
            "shapes": {"path": project.caminho("shapes"), "exists": os.path.isdir(project.caminho("shapes"))},
            "resultados": {"path": project.caminho("resultados"), "exists": os.path.isdir(project.caminho("resultados"))},
            "mapas": {"path": project.mapas_dir(), "exists": os.path.isdir(project.mapas_dir())},
        },
        "catalogo_camadas": {"path": project.catalog_path(), "exists": os.path.exists(project.catalog_path())},
        "templates_layouts": {"path": project.template_manifest_path(), "exists": os.path.exists(project.template_manifest_path())},
    }
