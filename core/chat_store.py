# -*- coding: utf-8 -*-
"""Persistencia de chats — armazena conversas por usuario em JSON."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

CHATS_DIR = os.path.expanduser("~/Documentos/banco_dados_nexogeo/chats")


def _chat_dir(email: str) -> str:
    d = os.path.join(CHATS_DIR, email.strip().lower())
    os.makedirs(d, exist_ok=True)
    return d


def listar_chats(email: str) -> list[dict]:
    """Lista todos os chats do usuario, mais recente primeiro."""
    d = _chat_dir(email)
    chats = []
    for fname in sorted(os.listdir(d), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(d, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            chats.append({
                "id": data.get("id", fname.replace(".json", "")),
                "titulo": data.get("titulo", "Sem título"),
                "criado_em": data.get("criado_em", ""),
                "atualizado_em": data.get("atualizado_em", ""),
                "mensagens": len(data.get("mensagens", [])),
            })
        except Exception:
            pass
    return chats


def carregar_chat(email: str, chat_id: str) -> dict | None:
    """Carrega um chat completo pelo ID."""
    path = os.path.join(_chat_dir(email), f"{chat_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def criar_chat(email: str, titulo: str = "Novo mapa") -> str:
    """Cria um novo chat e retorna o ID."""
    chat_id = uuid.uuid4().hex[:12]
    data = {
        "id": chat_id,
        "titulo": titulo,
        "criado_em": datetime.now().isoformat(),
        "atualizado_em": datetime.now().isoformat(),
        "mensagens": [],
        "mapspec_atual": None,  # MapSpec corrente do chat
    }
    path = os.path.join(_chat_dir(email), f"{chat_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return chat_id


def salvar_mensagem(email: str, chat_id: str, role: str, content: str,
                    tool_calls: list | None = None, result: dict | None = None):
    """Adiciona uma mensagem ao chat e atualiza o MapSpec corrente."""
    data = carregar_chat(email, chat_id)
    if not data:
        return
    data["mensagens"].append({
        "role": role,
        "content": content,
        "ts": datetime.now().isoformat(),
        "tool_calls": tool_calls,
    })
    data["atualizado_em"] = datetime.now().isoformat()
    if result and result.get("mapspec"):
        data["mapspec_atual"] = result["mapspec"]
        # Atualiza titulo com base no mapspec
        titulo = result["mapspec"].get("titulo", "")
        if titulo and data["titulo"] == "Novo mapa":
            data["titulo"] = titulo
    path = os.path.join(_chat_dir(email), f"{chat_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_mapspec_atual(email: str, chat_id: str) -> dict | None:
    """Retorna o MapSpec corrente do chat (para edição continuada)."""
    data = carregar_chat(email, chat_id)
    return data.get("mapspec_atual") if data else None
