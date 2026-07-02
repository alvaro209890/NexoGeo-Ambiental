# -*- coding: utf-8 -*-
"""MapSpec model, deterministic prompt parser, and validation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from core.nexomap_catalog import layer_index, template_index
from core.nexomap_project import NexoMapError


ALLOWED_OUTPUTS = {"mxd", "pdf", "png_validacao"}


@dataclass
class MapLayerSpec:
    id: str
    fonte: str
    filtro: str = ""
    estilo: dict[str, Any] = field(default_factory=dict)
    rotulo: bool = False


@dataclass
class MapSpec:
    titulo: str
    tipo: str
    area_base: str
    layout_template: str
    escala: str | int | float
    basemap: str
    camadas: list[MapLayerSpec]
    elementos_layout: dict[str, bool]
    saidas: list[str]

    def to_dict(self) -> dict:
        return {
            "titulo": self.titulo,
            "tipo": self.tipo,
            "area_base": self.area_base,
            "layout_template": self.layout_template,
            "escala": self.escala,
            "basemap": self.basemap,
            "camadas": [
                {
                    "id": layer.id,
                    "fonte": layer.fonte,
                    "filtro": layer.filtro,
                    "estilo": layer.estilo,
                    "rotulo": layer.rotulo,
                }
                for layer in self.camadas
            ],
            "elementos_layout": self.elementos_layout,
            "saidas": self.saidas,
        }


def mapspec_from_dict(data: dict) -> MapSpec:
    if not isinstance(data, dict):
        raise NexoMapError("MapSpec deve ser um objeto JSON")
    layers = []
    for raw in data.get("camadas") or []:
        layers.append(MapLayerSpec(
            id=str(raw.get("id", "")),
            fonte=str(raw.get("fonte", "")),
            filtro=str(raw.get("filtro", "")),
            estilo=raw.get("estilo") or {},
            rotulo=bool(raw.get("rotulo", False)),
        ))
    return MapSpec(
        titulo=str(data.get("titulo", "")).strip(),
        tipo=str(data.get("tipo", "geral")).strip() or "geral",
        area_base=str(data.get("area_base", "projeto.area_base")),
        layout_template=str(data.get("layout_template", "")),
        escala=data.get("escala", "auto"),
        basemap=str(data.get("basemap", "satellite")),
        camadas=layers,
        elementos_layout=data.get("elementos_layout") or {},
        saidas=[str(x) for x in (data.get("saidas") or ["mxd", "pdf", "png_validacao"])],
    )


def mapspec_from_json(text: str) -> MapSpec:
    try:
        return mapspec_from_dict(json.loads(text))
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text or "", re.S)
        if not match:
            raise
        return mapspec_from_dict(json.loads(match.group(0)))


def validate_mapspec(spec: MapSpec, catalog: dict, manifest: dict, secrets: dict | None = None) -> list[str]:
    """Validate a MapSpec and return non-fatal warnings."""
    warnings: list[str] = []
    errors: list[str] = []
    layers = layer_index(catalog)
    templates = template_index(manifest)

    if not spec.titulo:
        errors.append("titulo ausente")
    if spec.area_base != "projeto.area_base":
        errors.append("area_base deve ser 'projeto.area_base'")
    if spec.layout_template not in templates:
        errors.append(f"layout_template inexistente: {spec.layout_template}")
    if not spec.camadas:
        errors.append("MapSpec sem camadas")

    unknown_outputs = sorted(set(spec.saidas) - ALLOWED_OUTPUTS)
    if unknown_outputs:
        errors.append("saidas invalidas: " + ", ".join(unknown_outputs))

    for layer in spec.camadas:
        if not layer.id:
            errors.append("camada sem id")
            continue
        if layer.fonte == "area_base":
            continue
        if not layer.fonte.startswith("catalogo."):
            errors.append(f"fonte invalida em {layer.id}: {layer.fonte}")
            continue
        catalog_id = layer.fonte.split(".", 1)[1]
        if catalog_id not in layers:
            errors.append(f"camada de catalogo inexistente: {catalog_id}")
            continue
        required_secret = layers[catalog_id].get("auth")
        if required_secret and not (secrets or {}).get(required_secret):
            warnings.append(f"camada {catalog_id} requer segredo '{required_secret}'")

    if errors:
        raise NexoMapError("MapSpec invalido: " + "; ".join(errors))
    return warnings


def _first_template_id(manifest: dict) -> str:
    templates = manifest.get("templates") or []
    return templates[0]["id"] if templates else "tematico_a3_retrato"


def _has_layer(catalog: dict, layer_id: str) -> bool:
    return layer_id in layer_index(catalog)


def _catalog_layer(layer_id: str, style: dict, filtro: str = "intersecta_area_base") -> MapLayerSpec:
    return MapLayerSpec(id=layer_id, fonte=f"catalogo.{layer_id}", filtro=filtro, estilo=style, rotulo=False)


def build_rule_based_spec(prompt: str, project_name: str, catalog: dict, manifest: dict) -> MapSpec:
    """Deterministic fallback used when no configured AI provider is available."""
    text = (prompt or "").lower()
    layers: list[MapLayerSpec] = [
        MapLayerSpec(
            id="perimetro",
            fonte="area_base",
            estilo={"linha": "#ff3b30", "largura": 2.4, "preenchimento": "transparente"},
            rotulo=True,
        )
    ]
    tipo = "geral"
    titulo = f"Mapa do imovel - {project_name}"
    basemap = "satellite" if any(k in text for k in ("satelite", "satellite", "imagem", "planet", "google")) else "light"

    def add(layer_id: str, color: str, opacity: float = 0.4):
        if _has_layer(catalog, layer_id) and all(layer.id != layer_id for layer in layers):
            layers.append(_catalog_layer(layer_id, {"preenchimento": color, "opacidade": opacity, "linha": color}))

    if "embargo" in text:
        tipo = "embargos"
        titulo = f"Mapa de Embargos Ambientais - {project_name}"
        add("embargos_ibama", "#d93025", 0.45)
        add("embargos_sema", "#f97316", 0.42)
    if "car" in text or "simcar" in text:
        tipo = "car" if tipo == "geral" else tipo
        titulo = f"Mapa de CAR - {project_name}" if tipo == "car" else titulo
        add("car_sema", "#1d4ed8", 0.18)
    if "tipologia" in text or "vegetacao" in text or "vegetação" in text:
        tipo = "tipologia"
        titulo = f"Mapa de Tipologia - {project_name}"
        add("tipologia_sema", "#16a34a", 0.35)
    if "terra indigena" in text or "terra indígena" in text or re.search(r"\bti\b", text):
        tipo = "areas_protegidas"
        titulo = f"Mapa de Terras Indigenas - {project_name}"
        add("terras_indigenas_funai", "#8b5cf6", 0.35)
    if "unidade" in text or re.search(r"\buc\b", text):
        tipo = "areas_protegidas"
        titulo = f"Mapa de Unidades de Conservacao - {project_name}"
        add("unidades_conservacao", "#059669", 0.35)
    if "alerta" in text or "mapbiomas" in text or "desmat" in text or "prodes" in text:
        tipo = "desmatamento"
        titulo = f"Mapa de Alertas e Desmatamento - {project_name}"
        add("alertas_mapbiomas", "#facc15", 0.55)
        add("prodes_inpe", "#ef4444", 0.35)
    if "dinamica" in text or "dinâmica" in text:
        tipo = "dinamica"
        titulo = f"Mapa de Dinamica Temporal - {project_name}"
        basemap = "satellite"

    return MapSpec(
        titulo=titulo,
        tipo=tipo,
        area_base="projeto.area_base",
        layout_template=_first_template_id(manifest),
        escala="auto",
        basemap=basemap,
        camadas=layers,
        elementos_layout={
            "legenda": True,
            "escala_grafica": True,
            "norte": True,
            "grade": True,
            "minimapa": True,
            "metadados": True,
        },
        saidas=["mxd", "pdf", "png_validacao"],
    )
