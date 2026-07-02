# -*- coding: utf-8 -*-
"""core.matriculas — extração de matrículas de imóvel por PDF + IA (Frente A / M1).

Fluxo (decisão §0.1 do PLANO_MELHORIAS): o analista envia os PDFs das matrículas;
o DeepSeek extrai nº/denominação/proprietário/CPF-CNPJ/área/CRI/CNS; a UI mostra a
**grade de conferência obrigatória** (dado jurídico) e, confirmado, o resultado é
gravado em ``dominialidade`` no projeto.json via :func:`salvar_dominialidade`.

A IA é obrigatória: sem chave DeepSeek a extração falha rápido com mensagem clara.
"""
from __future__ import annotations

import json
import os

import fitz

from core import normalize as nz
from core import secrets as secrets_loader
from core.llm import deepseek

CONFIANCA_MINIMA = 0.8  # abaixo disso a UI destaca o campo para conferência


class MatriculasError(RuntimeError):
    pass


def _deepseek_key(projeto) -> str:
    sec = secrets_loader.load_secrets(projeto)
    key = (sec.get("deepseek_api_key") or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if not key:
        raise MatriculasError(
            "Chave DeepSeek ausente: a extração de matrículas exige IA. Configure "
            "'deepseek_api_key' no secrets.local.json da análise (tela Config) e tente novamente."
        )
    return key


def _texto_pdf(path: str, avisos: list[str]) -> str:
    """Texto do PDF via fitz; OCR (pytesseract) como fallback para digitalizados."""
    doc = fitz.open(path)
    try:
        texto = "\n".join(page.get_text() for page in doc)
        if len(texto.strip()) >= 50:
            return texto
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            avisos.append(
                f"{os.path.basename(path)}: PDF sem camada de texto e OCR indisponível "
                f"({e}); instale pytesseract/Tesseract para matrículas digitalizadas."
            )
            return texto
        partes = []
        for page in doc:
            pix = page.get_pixmap(dpi=220)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            partes.append(pytesseract.image_to_string(img, lang="por"))
        avisos.append(f"{os.path.basename(path)}: texto obtido por OCR (conferir com atenção).")
        return "\n".join(partes)
    finally:
        doc.close()


def _validacoes(item: dict) -> dict:
    area = nz.numero_br(item.get("area_ha"))
    return {
        "cpf_cnpj_valido": nz.validar_cpf_cnpj(str(item.get("cpf_cnpj") or "")),
        "area_valida": area is not None and area > 0,
        "numero_presente": bool(str(item.get("numero") or "").strip()),
    }


def _campos_baixa_confianca(item: dict) -> list[str]:
    conf = item.get("confianca") or {}
    if not isinstance(conf, dict):
        return []
    out = []
    for campo, valor in conf.items():
        try:
            if float(valor) < CONFIANCA_MINIMA:
                out.append(campo)
        except (TypeError, ValueError):
            out.append(campo)
    return sorted(out)


def extrair_de_pdfs(projeto, pdf_paths: list[str]) -> dict:
    """Extrai 1+ PDFs de matrícula; devolve itens prontos para a grade de conferência."""
    if not pdf_paths:
        raise MatriculasError("nenhum PDF de matrícula informado")
    api_key = _deepseek_key(projeto)
    avisos: list[str] = []
    itens: list[dict] = []
    registro = {"cri": "", "cns": ""}
    for path in pdf_paths:
        nome = os.path.basename(path)
        if not os.path.exists(path):
            itens.append({"arquivo": nome, "erro": f"arquivo não encontrado: {path}"})
            continue
        texto = _texto_pdf(path, avisos)
        if not texto.strip():
            itens.append({"arquivo": nome, "erro": "PDF sem texto extraível (nem por OCR)"})
            continue
        r = deepseek.extrair_matricula(texto, nome, api_key=api_key)
        if not r.ok:
            itens.append({"arquivo": nome, "erro": f"IA falhou: {r.error}"})
            continue
        data = r.data or {}
        area = nz.numero_br(data.get("area_ha"))
        item = {
            "arquivo": nome,
            "numero": str(data.get("numero") or "").strip(),
            "denominacao": str(data.get("denominacao") or "").strip(),
            "proprietario": str(data.get("proprietario") or "").strip(),
            "cpf_cnpj": str(data.get("cpf_cnpj") or "").strip(),
            "area_ha": area,
            "cri": str(data.get("cri") or "").strip(),
            "cns": str(data.get("cns") or "").strip(),
            "confianca": data.get("confianca") or {},
            "observacoes": data.get("observacoes") or [],
        }
        item["validacoes"] = _validacoes(item)
        item["conferir"] = _campos_baixa_confianca(item) + [
            campo for campo, ok in item["validacoes"].items() if ok is False
        ]
        itens.append(item)
        if not registro["cri"] and item["cri"]:
            registro["cri"] = item["cri"]
        if not registro["cns"] and item["cns"]:
            registro["cns"] = item["cns"]
    return {
        "registro": registro,
        "matriculas": itens,
        "avisos": avisos,
        "conferencia_obrigatoria": True,
    }


def salvar_dominialidade(projeto_path: str, registro: dict, matriculas: list[dict]) -> str:
    """Grava a dominialidade CONFERIDA pelo analista no projeto.json."""
    if not os.path.exists(projeto_path):
        raise MatriculasError(f"projeto.json não encontrado: {projeto_path}")
    validas = []
    for i, m in enumerate(matriculas):
        numero = str(m.get("numero") or "").strip()
        if not numero:
            raise MatriculasError(f"matrícula [{i}] sem 'numero' — corrija na grade antes de salvar")
        area = nz.numero_br(m.get("area_ha"))
        cpf_cnpj = str(m.get("cpf_cnpj") or "").strip()
        if cpf_cnpj and nz.validar_cpf_cnpj(cpf_cnpj) is False:
            raise MatriculasError(
                f"matrícula {numero}: CPF/CNPJ inválido ('{cpf_cnpj}') — corrija na grade antes de salvar"
            )
        validas.append({
            "numero": numero,
            "denominacao": str(m.get("denominacao") or "").strip(),
            "proprietario": str(m.get("proprietario") or "").strip(),
            "cpf_cnpj": cpf_cnpj,
            **({"area_ha": area} if area is not None else {}),
        })
    if not validas:
        raise MatriculasError("nenhuma matrícula para salvar")
    with open(projeto_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["dominialidade"] = {
        "registro": {
            "cri": str((registro or {}).get("cri") or "").strip(),
            "cns": str((registro or {}).get("cns") or "").strip(),
        },
        "matriculas": validas,
    }
    with open(projeto_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return projeto_path
