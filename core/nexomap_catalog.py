# -*- coding: utf-8 -*-
"""Catalog and template manifest helpers for NexoMap AI."""
from __future__ import annotations

import json
import os

from core.nexomap_project import NexoMapError


def _load_json(path: str, label: str) -> dict:
    if not os.path.exists(path):
        raise NexoMapError(f"{label} nao encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise NexoMapError(f"{label} invalido em {path}: {e}") from e


def load_layer_catalog(path: str) -> dict:
    data = _load_json(path, "catalogo de camadas")
    if not isinstance(data.get("camadas"), list):
        raise NexoMapError("catalogo de camadas deve conter lista 'camadas'")
    ids = set()
    for layer in data["camadas"]:
        lid = layer.get("id")
        if not lid:
            raise NexoMapError("camada sem id no catalogo")
        if lid in ids:
            raise NexoMapError(f"id de camada duplicado no catalogo: {lid}")
        ids.add(lid)
    return data


def load_template_manifest(path: str) -> dict:
    data = _load_json(path, "manifesto MXD")
    if not isinstance(data.get("templates"), list):
        raise NexoMapError("manifesto MXD deve conter lista 'templates'")
    ids = set()
    for tpl in data["templates"]:
        tid = tpl.get("id")
        if not tid:
            raise NexoMapError("template sem id no manifesto")
        if tid in ids:
            raise NexoMapError(f"id de template duplicado no manifesto: {tid}")
        ids.add(tid)
    return data


def layer_index(catalog: dict) -> dict[str, dict]:
    return {layer["id"]: layer for layer in catalog.get("camadas", [])}


def template_index(manifest: dict) -> dict[str, dict]:
    return {tpl["id"]: tpl for tpl in manifest.get("templates", [])}


def public_context(catalog: dict, manifest: dict) -> dict:
    """Small context safe to send to the LLM."""
    return {
        "camadas": [
            {
                "id": layer["id"],
                "nome": layer.get("nome", layer["id"]),
                "tipo": layer.get("tipo"),
                "tema": layer.get("tema"),
                "auth": layer.get("auth"),
            }
            for layer in catalog.get("camadas", [])
        ],
        "templates": [
            {
                "id": tpl["id"],
                "nome": tpl.get("nome", tpl["id"]),
                "formato": tpl.get("formato"),
                "orientacao": tpl.get("orientacao"),
            }
            for tpl in manifest.get("templates", [])
        ],
    }
