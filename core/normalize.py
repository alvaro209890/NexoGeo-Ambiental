# -*- coding: utf-8 -*-
"""core.normalize — formatação e normalização no padrão brasileiro.

Números e datas BR; nome de pessoa/empresa (Title Case + conectores em minúsculo);
máscara de CNPJ; e a formatação de proprietários do CAR (porta do antigo
``formata_proprietario``).
"""
from __future__ import annotations

import re

_CONECTORES = ("Da", "De", "Do", "Das", "Dos", "E")


def br(n: float, dec: int = 4) -> str:
    """Número no formato brasileiro: ``1234.5678`` -> ``'1.234,5678'``."""
    return f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero_br(v) -> float | None:
    """Converte número em formato BR ou US para float: ``'3.823,9140'`` -> ``3823.914``.

    Devolve ``None`` quando não é interpretável.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _dv_mod11(digitos: str, pesos: list[int]) -> int:
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(cpf: str) -> bool:
    d = re.sub(r"\D", "", cpf or "")
    if len(d) != 11 or d == d[0] * 11:
        return False
    if _dv_mod11(d[:9], list(range(10, 1, -1))) != int(d[9]):
        return False
    return _dv_mod11(d[:10], list(range(11, 1, -1))) == int(d[10])


def validar_cnpj(cnpj: str) -> bool:
    d = re.sub(r"\D", "", cnpj or "")
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    if _dv_mod11(d[:12], pesos1) != int(d[12]):
        return False
    return _dv_mod11(d[:13], pesos2) == int(d[13])


def validar_cpf_cnpj(v: str) -> bool | None:
    """``True``/``False`` para CPF (11 díg.) ou CNPJ (14 díg.); ``None`` se vazio/outro tamanho."""
    d = re.sub(r"\D", "", v or "")
    if not d:
        return None
    if len(d) == 11:
        return validar_cpf(d)
    if len(d) == 14:
        return validar_cnpj(d)
    return False


def casas_decimais(v: float, cheio: int = 4, curto: int = 2) -> int:
    """Quantas casas usar: ``cheio`` se o valor tem mais de 2 decimais, senão ``curto``.
    Reproduz a regra do antigo ``gerar_area_total.py`` para a área de matrícula."""
    parte = str(v).split(".")
    return cheio if (v != int(v) and len(parte) > 1 and len(parte[-1]) > 2) else curto


def br_data(s: str) -> str:
    """``'AAAA-MM-DD...'`` -> ``'DD/MM/AAAA'``; devolve a entrada se não casar."""
    s = (s or "").strip()[:10]
    if len(s) == 10 and s[4] == "-":
        a, m, d = s.split("-")
        return f"{d}/{m}/{a}"
    return s


def nome(s: str) -> str:
    """Normaliza um nome: tira espaços duplos, CAIXA ALTA -> Title Case, conectores em minúsculo."""
    s = re.sub(r"\s{2,}", " ", (s or "").strip())
    if s.isupper():
        s = " ".join(w.capitalize() for w in s.split())
    s = re.sub(r"\b(" + "|".join(_CONECTORES) + r")\b", lambda m: m.group(1).lower(), s)
    return s


def mascara_cnpj(d14: str) -> str:
    """``'00000000000191'`` -> ``'00.000.000/0001-91'``."""
    d = re.sub(r"\D", "", d14 or "")
    if len(d) != 14:
        return d14
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def proprietarios(raw: str) -> str:
    """Formata a lista de proprietários do CAR (campo NOMESPROPRIETARIOS).

    Pessoa jurídica ``'00000000000191 - Empresa Exemplo Ltda  Me'`` ->
        ``'Empresa Exemplo Ltda ME – CNPJ: 00.000.000/0001-91'``.
    Pessoas físicas (CPF mascarado) -> apenas os nomes, unidos por ``' e '``.
    """
    partes = []
    for trecho in (raw or "").split(";"):
        trecho = trecho.strip()
        if not trecho:
            continue
        m = re.match(r"^(\d{14})\s*-\s*(.+)$", trecho)
        if m:
            nm = re.sub(r"\s{2,}", " ", m.group(2)).strip()
            nm = re.sub(r"\bMe\b", "ME", nm)
            partes.append((nm, mascara_cnpj(m.group(1))))
        else:
            nm = re.sub(r"^[X\d]*X[X\d]*\s*-\s*", "", trecho)  # remove CPF mascarado
            partes.append((nome(nm), None))
    nomes = " e ".join(p[0] for p in partes)
    cnpjs = [p[1] for p in partes if p[1]]
    return f"{nomes} – CNPJ: {cnpjs[0]}" if cnpjs else nomes
