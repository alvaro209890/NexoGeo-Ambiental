# -*- coding: utf-8 -*-
"""core.clients.apf_rural — raspagem do portal APF Rural (SEMA-MT).

Site ASP.NET WebForms (postbacks com __VIEWSTATE/__EVENTVALIDATION e paginação).
Consulta APFs por nº de CAR (Federal e Estadual) e baixa os PDFs das REGULAR.
Porta de ``puxar_apfs.py`` + ``baixar_pdfs_apf.py``, agora sem CARs hardcoded.
"""
from __future__ import annotations

import re

from core.clients import http

URL = "https://monitoramento.sema.mt.gov.br/apfruralconsulta/index.aspx"
TIMEOUT = 90

CAMPOS = ["ApfNumero", "Situacao", "Imovel", "CarNumero", "Responsavel",
          "Atividade", "Municipio", "DataEmissao", "DataValidade", "UltimaAtualizacao"]


def _hid(name: str, html: str) -> str:
    m = re.search(r'id="%s"[^>]*value="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else ""


def _base_fields(html: str) -> dict:
    return {
        "__VIEWSTATE": _hid("__VIEWSTATE", html),
        "__VIEWSTATEGENERATOR": _hid("__VIEWSTATEGENERATOR", html),
        "__SCROLLPOSITIONX": "0", "__SCROLLPOSITIONY": "0",
        "__EVENTVALIDATION": _hid("__EVENTVALIDATION", html),
        "txtCpfCnpjProprietario": "", "txtCpfResponsavel": "", "txtNumeroApf": "",
    }


def _parse_entries(html: str) -> list[dict]:
    out = []
    idxs = sorted(set(int(i) for i in re.findall(r'id="repeater_labApfNumero_(\d+)"', html)))
    for i in idxs:
        rec = {}
        for f in CAMPOS:
            m = re.search(r'id="repeater_lab%s_%d">(.*?)</span>' % (f, i), html, re.S)
            rec[f] = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        out.append(rec)
    return out


def _next_target(html: str):
    i = html.find('class="next"')
    if i < 0:
        return None
    seg = html[i:i + 400]
    m = (re.search(r"__doPostBack\(&#39;([^&]+)&#39;", seg)
         or re.search(r"__doPostBack\('([^']+)'", seg))
    return m.group(1) if m else None


def _paginar(S, html, modo, numero, entries):
    seen = 0
    while True:
        tgt = _next_target(html)
        if not tgt or seen > 50:
            break
        d = {"__EVENTTARGET": tgt, "__EVENTARGUMENT": "", "__LASTFOCUS": "",
             "rblNumeroCar": modo, "txtNumeroSicar": numero}
        d.update(_base_fields(html))
        r = S.post(URL, data=d, verify=http.VERIFY_TLS, timeout=TIMEOUT)
        r.encoding = "latin-1"
        html = r.text
        new = _parse_entries(html)
        if not new or (entries and new == entries[-len(new):]):
            break
        entries += new
        seen += 1
    return entries


def consultar(numero: str, modo: str) -> list[dict]:
    """Lista as APFs de um CAR. ``modo`` = 'FEDERAL' ou 'ESTADUAL'."""
    S = http.session()
    r = S.get(URL, verify=http.VERIFY_TLS, timeout=60)
    r.encoding = "latin-1"
    html = r.text
    if modo == "ESTADUAL":
        d0 = {"__EVENTTARGET": "rblNumeroCar$1", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
              "rblNumeroCar": "ESTADUAL", "txtNumeroSicar": ""}
        d0.update(_base_fields(html))
        r = S.post(URL, data=d0, verify=http.VERIFY_TLS, timeout=TIMEOUT)
        r.encoding = "latin-1"
        html = r.text
    d = {"__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
         "rblNumeroCar": modo, "txtNumeroSicar": numero, "btnBuscar": "Buscar"}
    d.update(_base_fields(html))
    r = S.post(URL, data=d, verify=http.VERIFY_TLS, timeout=TIMEOUT)
    r.encoding = "latin-1"
    html = r.text
    entries = _parse_entries(html)
    return _paginar(S, html, modo, numero, entries)


# -------- download dos PDFs das APFs REGULAR --------
def entradas_regular(html: str):
    """Lista (indice, apf_numero, target_pdf) das APFs com situação REGULAR."""
    out = []
    for m in re.finditer(r'id="repeater_labApfNumero_(\d+)">(.*?)</span>', html, re.S):
        i = int(m.group(1))
        apf = re.sub(r"\s+", " ", m.group(2)).strip()
        ms = re.search(r'id="repeater_labSituacao_%d">(.*?)</span>' % i, html, re.S)
        sit = re.sub(r"\s+", " ", ms.group(1)).strip() if ms else ""
        if sit.upper() == "REGULAR":
            mt = re.search(r'id="repeater_btnPdfApf_%d"[^>]*__doPostBack\(&#39;([^&]+)&#39;' % i, html)
            out.append((i, apf, mt.group(1) if mt else None))
    return out


def buscar_html(S, numero: str, modo: str) -> str:
    r = S.get(URL, verify=http.VERIFY_TLS, timeout=60)
    r.encoding = "latin-1"
    html = r.text
    if modo == "ESTADUAL":
        d0 = {"__EVENTTARGET": "rblNumeroCar$1", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
              "rblNumeroCar": "ESTADUAL", "txtNumeroSicar": ""}
        d0.update(_base_fields(html))
        r = S.post(URL, data=d0, verify=http.VERIFY_TLS, timeout=TIMEOUT)
        r.encoding = "latin-1"
        html = r.text
    d = {"__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": "",
         "rblNumeroCar": modo, "txtNumeroSicar": numero, "btnBuscar": "Buscar"}
    d.update(_base_fields(html))
    r = S.post(URL, data=d, verify=http.VERIFY_TLS, timeout=TIMEOUT)
    r.encoding = "latin-1"
    return r.text


def baixar_pdf(S, html, target, modo, numero, destino) -> int:
    d = {"__EVENTTARGET": target, "__EVENTARGUMENT": "", "__LASTFOCUS": "",
         "rblNumeroCar": modo, "txtNumeroSicar": numero}
    d.update(_base_fields(html))
    rp = S.post(URL, data=d, verify=http.VERIFY_TLS, timeout=180)
    ct = rp.headers.get("Content-Type", "")
    if "pdf" in ct.lower() and rp.content[:4] == b"%PDF":
        with open(destino, "wb") as f:
            f.write(rp.content)
        return len(rp.content)
    return 0
