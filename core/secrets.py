# -*- coding: utf-8 -*-
"""core.secrets — carga de credenciais fora do código e do Git.

Procura ``secrets.local.json`` ao lado do ``projeto.json`` e, em seguida, na raiz
de dados. Devolve um dict (vazio se não houver). Nunca versionar o arquivo real.
"""
from __future__ import annotations

import json
import os


def load_secrets(projeto) -> dict:
    candidatos = []
    if getattr(projeto, "_arquivo", ""):
        candidatos.append(os.path.join(os.path.dirname(projeto._arquivo), "secrets.local.json"))
    candidatos.append(os.path.join(projeto.raiz_abs(), "secrets.local.json"))
    for c in candidatos:
        if os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}
