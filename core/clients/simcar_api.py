# -*- coding: utf-8 -*-
"""Download direto dos recibos publicos do SIMCAR."""
from __future__ import annotations

import os
import re
import unicodedata

import requests

from core.clients import http

URL_DOWNLOAD = "https://monitoramento.sema.mt.gov.br/simcar/tecnico.api/api/Publico/DownloadReciboCar/{id}"


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "recibo"


def baixar_recibo(requerimento_id: int | str, destino: str, overwrite: bool = False,
                  timeout: int = 120) -> int:
    if os.path.exists(destino) and not overwrite and os.path.getsize(destino) > 0:
        return os.path.getsize(destino)
    url = URL_DOWNLOAD.format(id=str(requerimento_id).strip())
    headers = {"Accept": "application/pdf,*/*", "User-Agent": http.UA["User-Agent"]}
    tentativas = [
        {"method": "POST", "headers": headers},
        {"method": "POST", "headers": {**headers, "Content-Type": "application/json"}, "data": b"{}"},
    ]
    last_error = None
    for kwargs in tentativas:
        try:
            r = requests.request(url=url, timeout=timeout, verify=http.VERIFY_TLS, **kwargs)
            if r.ok and r.content[:4] == b"%PDF":
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as f:
                    f.write(r.content)
                return len(r.content)
            last_error = f"HTTP {r.status_code} {r.headers.get('Content-Type', '')}"
        except Exception as e:
            last_error = str(e)
    raise RuntimeError(f"falha ao baixar recibo SIMCAR {requerimento_id}: {last_error}")


def nome_arquivo(nome_imovel: str, requerimento_id: int | str) -> str:
    return f"recibo_{slug(nome_imovel)}_{requerimento_id}.pdf"
