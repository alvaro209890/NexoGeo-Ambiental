# -*- coding: utf-8 -*-
"""API FastAPI do software de Análise de Área.

Endpoints (todos sob /api):
    GET  /api/health                  -> {"ok": true}
    POST /api/projeto/validar  {path} -> resumo do projeto (fazendas, pastas, etc.)
    GET  /api/automacoes              -> metadados das automações
    POST /api/run  {path, ids}        -> SSE: progresso por automação
    GET  /api/resultados?path=...     -> arquivos gerados em Resultados/
    POST /api/abrir  {alvo}           -> abre arquivo/pasta no SO (local)

Servir a UI: se ``ui/dist`` existir, é montada na raiz.
Rodar (a partir de software/):  uvicorn api.app:app --port 8000
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import load_projeto, ProjetoError, Projeto
from api import registry
from automations import pre_analise

app = FastAPI(title="Análise de Área", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ----------------------------- modelos -----------------------------
class CaminhoBody(BaseModel):
    path: str


class RunBody(BaseModel):
    path: str
    ids: list[str]


class AbrirBody(BaseModel):
    alvo: str


class PreAnaliseBody(BaseModel):
    path: str
    shapefile_zip: str | None = None
    destino: str | None = None
    saida_dir: str | None = None
    usar_ia: bool = True


class NovoProjetoBody(BaseModel):
    nome: str
    cliente: str
    destino: str


# ----------------------------- config global -----------------------------
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.json")

def load_app_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"recentes": []}

def save_app_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def add_recent(nome, path):
    cfg = load_app_config()
    cfg["recentes"] = [p for p in cfg.get("recentes", []) if p["path"] != path]
    cfg["recentes"].insert(0, {"nome": nome, "path": path})
    save_app_config(cfg)


# ----------------------------- helpers -----------------------------
def _carregar(path: str) -> Projeto:
    try:
        return load_projeto(path)
    except ProjetoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _resumo(proj: Projeto) -> dict:
    cardir = proj.caminho("car")
    fazendas = []
    for fz in proj.fazendas:
        shp = os.path.join(cardir, fz.shape_car, "CAR_ATP.shp")
        fazendas.append({
            "id": fz.id, "nome": fz.nome, "car_estadual": fz.car_estadual,
            "recibo": fz.recibo_pdf, "shp_ok": os.path.exists(shp),
        })
    pastas = {chave: {"path": proj.caminho(chave), "exists": os.path.exists(proj.caminho(chave))}
              for chave in ("shapes", "car", "consultas", "resultados")}
    return {
        "arquivo": proj._arquivo,
        "imovel": proj.imovel, "cliente": proj.cliente,
        "municipio": {"nome": proj.municipio.nome, "uf": proj.municipio.uf, "ibge": proj.municipio.ibge},
        "crs_utm": proj.crs_utm, "data_consulta": proj.data_consulta_efetiva(),
        "raiz": proj.raiz_abs(), "pastas": pastas,
        "fazendas": fazendas, "automacoes": proj.automacoes,
    }


def _listar_resultados(proj: Projeto) -> list[dict]:
    d = proj.caminho("resultados")
    out = []
    if os.path.isdir(d):
        for nome in sorted(os.listdir(d)):
            if nome.startswith("~$"):
                continue
            p = os.path.join(d, nome)
            if os.path.isfile(p):
                st = os.stat(p)
                out.append({"nome": nome, "tamanho": st.st_size, "mtime": st.st_mtime,
                            "path": p, "ext": os.path.splitext(nome)[1].lstrip(".")})
    return out


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


# ----------------------------- endpoints -----------------------------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def get_config():
    return load_app_config()


@app.post("/api/projeto/validar")
def validar(body: CaminhoBody):
    proj = _carregar(body.path)
    add_recent(proj.imovel, proj._arquivo)
    return _resumo(proj)


@app.get("/api/automacoes")
def automacoes():
    return registry.meta_publica()


@app.get("/api/resultados")
def resultados(path: str):
    return _listar_resultados(_carregar(path))


@app.post("/api/run")
async def run(body: RunBody):
    proj = _carregar(body.path)

    async def stream():
        for aid in body.ids:
            meta = registry.BY_ID.get(aid)
            if not meta:
                yield _sse({"automacao": aid, "status": "error", "erro": "automação desconhecida"})
                continue
            yield _sse({"automacao": aid, "status": "started", "label": meta["label"]})
            try:
                arq = await asyncio.to_thread(meta["fn"], proj)
                yield _sse({"automacao": aid, "status": "done", "arquivo": os.path.basename(arq)})
            except Exception as e:  # automação falhou -> reporta e segue
                yield _sse({"automacao": aid, "status": "error", "erro": str(e)})
        yield _sse({"status": "complete"})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/pre-analise/resumo")
def pre_analise_resumo(body: PreAnaliseBody):
    proj = _carregar(body.path)
    return pre_analise.resumo_shape(proj, body.shapefile_zip)


@app.post("/api/pre-analise/run")
def pre_analise_run(body: PreAnaliseBody):
    proj = _carregar(body.path)
    out = pre_analise.gerar(proj, body.shapefile_zip, body.destino, usar_ia=body.usar_ia, saida_dir=body.saida_dir)
    return {"ok": True, "arquivo": out, "nome": os.path.basename(out)}


@app.post("/api/abrir")
def abrir(body: AbrirBody):
    alvo = body.alvo
    if not os.path.exists(alvo):
        raise HTTPException(status_code=404, detail="caminho não encontrado")
    try:
        os.startfile(alvo)  # type: ignore[attr-defined]  (Windows)
    except AttributeError:
        raise HTTPException(status_code=501, detail="abrir só é suportado no Windows")
    return {"ok": True}


@app.post("/api/projeto/novo")
def novo_projeto(body: NovoProjetoBody):
    if not os.path.isdir(body.destino):
        raise HTTPException(400, "Pasta de destino não existe")
    
    proj_dir = os.path.join(body.destino, body.nome)
    os.makedirs(proj_dir, exist_ok=True)
    
    os.makedirs(os.path.join(proj_dir, "Shapes", "CAR"), exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "Consultas_Publicas"), exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "Automacoes", "Resultados"), exist_ok=True)
    
    template = {
        "versao_schema": 1,
        "imovel": body.nome,
        "cliente": body.cliente,
        "municipio": {"nome": "", "uf": "", "ibge": ""},
        "crs_utm": 0,
        "raiz_dados": ".",
        "fazendas": [
            {
                "id": "fz_1",
                "nome": "Fazenda Principal",
                "shape_car": "CAR"
            }
        ]
    }
    
    proj_file = os.path.join(proj_dir, "projeto.json")
    with open(proj_file, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
        
    add_recent(body.nome, proj_file)
    return {"ok": True, "path": proj_file}


import subprocess

@app.get("/api/dialog/file")
def ask_file():
    code = "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.attributes('-topmost', True); root.withdraw(); print(filedialog.askopenfilename(), end='')"
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return {"path": res.stdout.strip()}


@app.get("/api/dialog/folder")
def ask_folder():
    code = "import tkinter as tk; from tkinter import filedialog; root = tk.Tk(); root.attributes('-topmost', True); root.withdraw(); print(filedialog.askdirectory(), end='')"
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return {"path": res.stdout.strip()}


# ----------------------------- UI estática -----------------------------
_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="ui")
