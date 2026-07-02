# -*- coding: utf-8 -*-
"""Cliente DeepSeek v4 para extracao de PDFs e resumo juridico."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import requests

API_URL = "https://api.deepseek.com/chat/completions"
MODEL_FLASH = "deepseek-v4-flash"
MODEL_PRO = "deepseek-v4-pro"


class DeepSeekError(RuntimeError):
    pass


@dataclass
class LLMResult:
    ok: bool
    model: str
    content: str = ""
    data: dict | None = None
    error: str = ""


def _api_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise DeepSeekError("DeepSeek API key ausente. Configure DEEPSEEK_API_KEY ou secrets.local.json.")
    return key


def _post(payload: dict, timeout: int = 180, api_key: str | None = None, api_url: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {_api_key(api_key)}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    r = requests.post(api_url or API_URL, headers=headers, json=payload, timeout=timeout)
    if not r.ok:
        raise DeepSeekError(f"DeepSeek HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def _content(resp: dict) -> str:
    try:
        return resp["choices"][0]["message"]["content"] or ""
    except Exception as e:
        raise DeepSeekError(f"resposta DeepSeek invalida: {e}") from e


def _json_from_text(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def extrair_documento_pdf(texto: str, nome_arquivo: str, tipo_documento: str,
                          timeout: int = 180, api_key: str | None = None,
                          api_url: str | None = None) -> LLMResult:
    """Extrai dados estruturados de recibos CAR e APFs com DeepSeek v4 Flash."""
    prompt = f"""
Voce recebera texto bruto/OCR de um PDF publico ambiental brasileiro.
Documento: {tipo_documento}
Arquivo: {nome_arquivo}

Retorne somente JSON valido, sem markdown, com esta forma:
{{
  "arquivo": "...",
  "tipo_documento": "recibo_car|apf|outro",
  "imovel": "...",
  "car": "...",
  "proprietarios": ["..."],
  "status": "...",
  "areas_imoveis": [
    {{"documento": "...", "tipo": "Matricula|Posse|Outro", "area_ha": "..."}}
  ],
  "apfs": [
    {{"numero": "...", "situacao": "...", "validade": "...", "atividade": "..."}}
  ],
  "observacoes": []
}}

Preserve valores, numeros, matriculas, areas e status exatamente como aparecem.
Use null ou lista vazia quando o dado nao estiver no texto. Nao invente dados.

TEXTO:
{texto[:120000]}
""".strip()
    payload = {
        "model": MODEL_FLASH,
        "messages": [
            {"role": "system", "content": "Voce extrai dados ambientais em JSON estrito."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 4096,
    }
    try:
        resp = _post(payload, timeout=timeout, api_key=api_key, api_url=api_url)
        content = _content(resp)
        return LLMResult(ok=True, model=MODEL_FLASH, content=content, data=_json_from_text(content))
    except Exception as e:
        return LLMResult(ok=False, model=MODEL_FLASH, error=str(e))


def extrair_matricula(texto: str, nome_arquivo: str, timeout: int = 180,
                      api_key: str | None = None, api_url: str | None = None) -> LLMResult:
    """Extrai os campos de uma matrícula de imóvel (CRI) com DeepSeek v4 Flash.

    Alimenta a grade de conferência da Dominialidade — a resposta traz um bloco
    ``confianca`` por campo para a UI destacar o que precisa de atenção do analista.
    """
    prompt = f"""
Voce recebera o texto bruto/OCR de uma MATRICULA DE IMOVEL RURAL emitida por um
Cartorio de Registro de Imoveis (CRI) brasileiro.
Arquivo: {nome_arquivo}

Retorne somente JSON valido, sem markdown, com esta forma:
{{
  "arquivo": "...",
  "numero": "...",
  "denominacao": "...",
  "proprietario": "...",
  "cpf_cnpj": "...",
  "area_ha": 0.0,
  "cri": "...",
  "cns": "...",
  "confianca": {{
    "numero": 1.0, "denominacao": 1.0, "proprietario": 1.0,
    "cpf_cnpj": 1.0, "area_ha": 1.0, "cri": 1.0, "cns": 1.0
  }},
  "observacoes": []
}}

Regras:
- "numero" e o numero da matricula como grafado (ex.: "7.569").
- "proprietario" e o proprietario ATUAL: o do ultimo registro/averbacao de
  transmissao de dominio (R-N mais recente), nao o primeiro da cadeia.
- "area_ha" e a area do imovel em hectares, como numero com ponto decimal.
- "cri" e a comarca do cartorio (ex.: "Vila Rica/MT"); "cns" o codigo CNS se constar.
- "confianca" por campo, de 0.0 a 1.0 (1.0 = literal e inequivoco no texto).
- Use null quando o dado nao estiver no texto. Nao invente dados.

TEXTO:
{texto[:120000]}
""".strip()
    payload = {
        "model": MODEL_FLASH,
        "messages": [
            {"role": "system", "content": "Voce extrai dados de matriculas de imoveis em JSON estrito."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0,
        "max_tokens": 2048,
    }
    try:
        resp = _post(payload, timeout=timeout, api_key=api_key, api_url=api_url)
        content = _content(resp)
        return LLMResult(ok=True, model=MODEL_FLASH, content=content, data=_json_from_text(content))
    except Exception as e:
        return LLMResult(ok=False, model=MODEL_FLASH, error=str(e))


def resumir_juridico(texto: str, timeout: int = 240, api_key: str | None = None,
                     api_url: str | None = None) -> LLMResult:
    """Resume embargos/autos/desembargos com DeepSeek v4 Pro."""
    prompt = f"""
Analise os registros oficiais abaixo para uma pre-analise juridico-ambiental.
Produza um resumo claro, conciso e rastreavel, em portugues do Brasil, sem
concluir regularidade absoluta. Destaque orgao, autuado, CPF/CNPJ, dano,
auto/termo/processo, area, criterio de vinculo e necessidade de conferencia humana.
Nao inferir nada alem dos atributos oficiais.

REGISTROS:
{texto[:160000]}
""".strip()
    payload = {
        "model": MODEL_PRO,
        "messages": [
            {"role": "system", "content": "Voce apoia analise juridico-ambiental cautelosa e rastreavel."},
            {"role": "user", "content": prompt},
        ],
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "temperature": 0,
        "max_tokens": 4096,
    }
    try:
        resp = _post(payload, timeout=timeout, api_key=api_key, api_url=api_url)
        return LLMResult(ok=True, model=MODEL_PRO, content=_content(resp))
    except Exception as e:
        return LLMResult(ok=False, model=MODEL_PRO, error=str(e))
