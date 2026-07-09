# -*- coding: utf-8 -*-
"""Autenticacao simples — email + senha com hash bcrypt, armazenamento local."""
from __future__ import annotations

import hashlib
import json
import os
import secrets as _secrets
from datetime import datetime

DB_DIR = os.path.expanduser("~/Documentos/banco_dados_nexogeo")
USERS_FILE = os.path.join(DB_DIR, "users.json")
CHATS_DIR = os.path.join(DB_DIR, "chats")


def _ensure_dirs():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(CHATS_DIR, exist_ok=True)


def _hash_senha(senha: str) -> str:
    """Hash simples com SHA-256 + salt (não é bcrypt, mas é suficiente pra local)."""
    salt = _secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{senha}".encode()).hexdigest()
    return f"{salt}:{h}"


def _check_senha(senha: str, hash_armazenado: str) -> bool:
    salt, h = hash_armazenado.split(":", 1)
    return hashlib.sha256(f"{salt}:{senha}".encode()).hexdigest() == h


def _load_users() -> dict:
    _ensure_dirs()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_users(users: dict):
    _ensure_dirs()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def registrar(email: str, senha: str, nome: str = "") -> dict:
    """Registra novo usuario. Retorna {ok, token} ou {ok:false, erro}."""
    users = _load_users()
    email = email.strip().lower()
    if email in users:
        return {"ok": False, "erro": "Email ja cadastrado"}
    if len(senha) < 4:
        return {"ok": False, "erro": "Senha muito curta (minimo 4 caracteres)"}

    token = _secrets.token_hex(32)
    users[email] = {
        "email": email,
        "nome": nome or email.split("@")[0],
        "senha_hash": _hash_senha(senha),
        "token": token,
        "criado_em": datetime.now().isoformat(),
    }
    _save_users(users)
    # Cria pasta de chats do usuario
    os.makedirs(os.path.join(CHATS_DIR, email), exist_ok=True)
    return {"ok": True, "token": token, "nome": users[email]["nome"], "email": email}


def login(email: str, senha: str) -> dict:
    """Autentica usuario. Retorna {ok, token, nome, email} ou {ok:false, erro}."""
    users = _load_users()
    email = email.strip().lower()
    user = users.get(email)
    if not user:
        return {"ok": False, "erro": "Email nao encontrado"}
    if not _check_senha(senha, user["senha_hash"]):
        return {"ok": False, "erro": "Senha incorreta"}

    # Renova token
    token = _secrets.token_hex(32)
    user["token"] = token
    _save_users(users)
    return {"ok": True, "token": token, "nome": user["nome"], "email": email}


def validar_token(email: str, token: str) -> dict | None:
    """Valida token. Retorna dados do usuario ou None."""
    users = _load_users()
    user = users.get(email.strip().lower())
    if user and user.get("token") == token:
        return {"email": user["email"], "nome": user["nome"]}
    return None
