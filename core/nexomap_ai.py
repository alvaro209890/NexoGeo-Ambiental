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

from core.mapspec import (MapSpec, apply_rule_based_edit, build_rule_based_spec,
                          mapspec_from_json, validate_mapspec)
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
            # cerebro cartografico padrao = DeepSeek V4 Pro (raciocinio p/ layout/simbologia)
            "model": secrets.get("nexomap_deepseek_model", "deepseek-v4-pro"),
            # v4-pro raciocina; sem 'thinking' controlado e max_tokens alto o content pode
            # voltar vazio. Padrao: thinking desligado (JSON estruturado, rapido e confiavel).
            "thinking": secrets.get("nexomap_deepseek_thinking", "disabled"),
            "max_tokens": int(secrets.get("nexomap_max_tokens", 4096)),
        }
    if provider == "openai_compatible":
        return {
            "provider": provider,
            "api_key": secrets.get("ai_api_key"),
            "api_url": secrets.get("ai_api_url"),
            "model": secrets.get("ai_model"),
            "thinking": None,
            "max_tokens": int(secrets.get("nexomap_max_tokens", 4096)),
        }
    return {"provider": provider, "api_key": None}


def _build_payload(cfg: dict, system: str, user: str) -> dict:
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "max_tokens": cfg.get("max_tokens", 4096),
    }
    if cfg.get("provider") == "deepseek" and cfg.get("thinking"):
        payload["thinking"] = {"type": cfg["thinking"]}
    return payload


def _system_prompt() -> str:
    return (
        "Voce e o planejador cartografico do NexoMap AI, especialista em mapas "
        "ambientais/fundiarios no padrao IMAP (Mato Grosso). "
        "Retorne somente JSON valido, sem markdown. "
        "Nunca invente camadas, templates, campos, endpoints ou credenciais. "
        "Use apenas os ids fornecidos no contexto. "
        "Campos obrigatorios: titulo, tipo, area_base='projeto.area_base', "
        "layout_template, escala, basemap, camadas, elementos_layout, saidas. "
        "Campos opcionais do padrao profissional: subtitulo; "
        "grade_tipo ('dms' padrao lat/long, ou 'utm'); "
        "raster_fundo (caminho de GeoTIFF local de satelite, quando fornecido); "
        "metadados_imagem {satelite_sensor, data_aquisicao, orbita_ponto, datum}; "
        "tabela {titulo, colunas[], linhas[[]]}; marca {logo, texto}. "
        "Cada camada tem id, fonte, filtro, estilo, rotulo. "
        "estilo aceita: linha, preenchimento, opacidade, largura e hachura "
        "(padroes matplotlib como '////', '----', '....' p/ vegetacao/desmatamento). "
        "Para fonte local use 'area_base'; para catalogo use 'catalogo.<id>'. "
        "elementos_layout e um objeto de BOOLEANOS que liga/desliga cada peca do mapa; "
        "chaves: grade, norte, rosa_dos_ventos, escala_grafica, legenda, metadados, "
        "minimapa, titulo_caixa (a caixa preta do titulo), inset_tipologia, tabela, "
        "metadados_imagem, logo. Para 'remover o titulo preto' use titulo_caixa=false; "
        "para 'sem tabela' use tabela=false; e assim por diante. "
        "Voce e responsavel pelo layout: escolha cores legiveis sobre o satelite e nao "
        "sobreponha legenda, metadados ou tabela ao conteudo essencial do mapa."
    )


def _edit_system_prompt() -> str:
    return (
        "Voce edita um MapSpec existente do NexoMap AI. "
        "Recebe o MapSpec atual (JSON) e uma instrucao do usuario. "
        "Aplique APENAS o que a instrucao pede, preservando o resto. "
        "Retorne o MapSpec completo e valido em JSON, sem markdown. "
        "Nao invente camadas/templates/endpoints; use so os ids do contexto. "
        "O MapSpec e a unica fonte de verdade — nao dependa de PDF/PNG."
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
    payload = _build_payload(cfg, _system_prompt(), _user_prompt(prompt, project, catalog, manifest))
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


def _call_edit_provider(current: dict, instruction: str, project: NexoMapProject,
                        catalog: dict, manifest: dict, secrets: dict, timeout: int = 90) -> str:
    cfg = _provider_config(secrets)
    if not cfg.get("api_key") or not cfg.get("api_url") or not cfg.get("model"):
        raise NexoMapError("provedor de IA nao configurado em secrets.local.json")
    ctx = {
        "mapspec_atual": current,
        "permitido": public_context(catalog, manifest),
        "projeto": {"nome": project.nome, "municipio": {"nome": project.municipio.nome,
                    "uf": project.municipio.uf}, "crs": {"utm": project.crs.utm}},
        "instrucao": instruction,
    }
    payload = _build_payload(cfg, _edit_system_prompt(), json.dumps(ctx, ensure_ascii=False))
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json",
               "Accept": "application/json"}
    response = requests.post(cfg["api_url"], headers=headers, json=payload, timeout=timeout)
    if not response.ok:
        raise NexoMapError(f"IA HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except Exception as e:
        raise NexoMapError(f"resposta de IA invalida: {e}") from e


def spec_edit_from_prompt(current: MapSpec, instruction: str, project: NexoMapProject,
                          catalog: dict, manifest: dict, secrets: dict,
                          allow_local_fallback: bool = True) -> ChatSpecResult:
    """Edita um MapSpec existente aplicando a instrucao (IA ou fallback deterministico).

    O MapSpec e a unica fonte de verdade: parte-se sempre do ``current`` (nunca do
    PDF/PNG). Preserva o que a instrucao nao mudar.
    """
    warnings: list[str] = []
    raw = ""
    provider = "local_rules"
    try:
        raw = _call_edit_provider(current.to_dict(), instruction, project, catalog, manifest, secrets)
        spec = mapspec_from_json(raw)
        provider = _provider_config(secrets).get("provider", "ai")
    except Exception as e:
        if not allow_local_fallback:
            raise
        warnings.append(f"IA indisponivel ou nao configurada; edicao local: {e}")
        spec = apply_rule_based_edit(current, instruction, catalog, manifest)

    # preserva a linhagem/campos estruturais que a edicao nao deve perder
    spec.raster_fundo = spec.raster_fundo or current.raster_fundo
    if not spec.marca:
        spec.marca = current.marca
    if not spec.metadados_imagem:
        spec.metadados_imagem = current.metadados_imagem
    warnings.extend(validate_mapspec(spec, catalog, manifest, secrets))
    return ChatSpecResult(spec=spec, provider=provider, raw=raw, warnings=warnings)
