# -*- coding: utf-8 -*-
"""Configurable AI adapter for chat -> MapSpec.

The provider is deliberately small and OpenAI-compatible. DeepSeek works through
the same chat completions wire format. If no key is configured, the module uses a
deterministic local parser and returns a warning; generation remains testable
without leaking or inventing credentials.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from core.mapspec import MapSpec, build_rule_based_spec, mapspec_from_json, validate_mapspec
from core.nexomap_catalog import public_context
from core.nexomap_project import NexoMapError, NexoMapProject


@dataclass
class ChatSpecResult:
    spec: MapSpec
    provider: str
    raw: str = ""
    warnings: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "raw": self.raw,
            "warnings": self.warnings or [],
            "mapspec": self.spec.to_dict(),
        }


def _provider_config(secrets: dict) -> dict:
    provider = secrets.get("nexomap_ai_provider") or secrets.get("ai_provider") or "deepseek"
    if provider == "deepseek":
        return {
            "provider": provider,
            "api_key": secrets.get("deepseek_api_key") or secrets.get("nexomap_deepseek_api_key"),
            "api_url": secrets.get("deepseek_api_url", "https://api.deepseek.com/chat/completions"),
            "model": secrets.get("nexomap_deepseek_model", "deepseek-chat"),
        }
    if provider == "openai_compatible":
        return {
            "provider": provider,
            "api_key": secrets.get("ai_api_key"),
            "api_url": secrets.get("ai_api_url"),
            "model": secrets.get("ai_model"),
        }
    return {"provider": provider, "api_key": None}


def _system_prompt() -> str:
    return (
        "Voce e o planejador cartografico do NexoMap AI. "
        "Retorne somente JSON valido, sem markdown. "
        "Nunca invente camadas, templates, campos, endpoints ou credenciais. "
        "Use apenas os ids fornecidos no contexto. "
        "A forma obrigatoria e: titulo, tipo, area_base='projeto.area_base', "
        "layout_template, escala, basemap, camadas, elementos_layout, saidas. "
        "Cada camada deve ter id, fonte, filtro, estilo e rotulo. "
        "Para fonte local use 'area_base'; para catalogo use 'catalogo.<id>'."
    )


def _user_prompt(prompt: str, project: NexoMapProject, catalog: dict, manifest: dict) -> str:
    ctx = {
        "projeto": {
            "nome": project.nome,
            "cliente": project.cliente,
            "municipio": {
                "nome": project.municipio.nome,
                "uf": project.municipio.uf,
                "ibge": project.municipio.ibge,
            },
            "crs": {"utm": project.crs.utm, "geografico": project.crs.geografico},
        },
        "permitido": public_context(catalog, manifest),
        "pedido_usuario": prompt,
    }
    return json.dumps(ctx, ensure_ascii=False)


def _call_chat_provider(prompt: str, project: NexoMapProject, catalog: dict, manifest: dict,
                        secrets: dict, timeout: int = 90) -> str:
    cfg = _provider_config(secrets)
    if not cfg.get("api_key") or not cfg.get("api_url") or not cfg.get("model"):
        raise NexoMapError("provedor de IA nao configurado em secrets.local.json")
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(prompt, project, catalog, manifest)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.post(cfg["api_url"], headers=headers, json=payload, timeout=timeout)
    if not response.ok:
        raise NexoMapError(f"IA HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except Exception as e:
        raise NexoMapError(f"resposta de IA invalida: {e}") from e


def spec_from_prompt(prompt: str, project: NexoMapProject, catalog: dict, manifest: dict,
                     secrets: dict, allow_local_fallback: bool = True) -> ChatSpecResult:
    """Generate and validate a MapSpec from a user prompt."""
    warnings: list[str] = []
    raw = ""
    provider = "local_rules"
    try:
        raw = _call_chat_provider(prompt, project, catalog, manifest, secrets)
        spec = mapspec_from_json(raw)
        provider = _provider_config(secrets).get("provider", "ai")
    except Exception as e:
        if not allow_local_fallback:
            raise
        warnings.append(f"IA indisponivel ou nao configurada; usado parser local: {e}")
        spec = build_rule_based_spec(prompt, project.nome, catalog, manifest)

    warnings.extend(validate_mapspec(spec, catalog, manifest, secrets))
    return ChatSpecResult(spec=spec, provider=provider, raw=raw, warnings=warnings)
