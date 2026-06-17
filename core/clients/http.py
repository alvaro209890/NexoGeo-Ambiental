# -*- coding: utf-8 -*-
"""core.clients.http — sessão HTTP única para os serviços públicos.

Centraliza a política de TLS (hoje ``verify=False``, herdado dos scripts — os
geosserviços gov. costumam ter cadeia incompleta), timeout e User-Agent. Um único
lugar para, no futuro, reativar verificação e adicionar retry/backoff.
"""
from __future__ import annotations

import requests
import urllib3

urllib3.disable_warnings()

VERIFY_TLS = False  # TODO: reativar onde os servidores permitirem
UA = {"User-Agent": "Mozilla/5.0"}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    return s


def get_json(url: str, params: dict | None = None, timeout: int = 60):
    r = requests.get(url, params=params, headers=UA, timeout=timeout, verify=VERIFY_TLS)
    r.raise_for_status()
    return r.json()


def get_text(url: str, params: dict | None = None, timeout: int = 180) -> str:
    r = requests.get(url, params=params, headers=UA, timeout=timeout, verify=VERIFY_TLS)
    r.raise_for_status()
    return r.text
