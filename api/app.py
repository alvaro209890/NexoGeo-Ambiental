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
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import load_projeto, ProjetoError, Projeto
from api import registry
from automations import pre_analise
from core.nexomap_project import (
    NexoMapError,
    create_project_template as create_nexomap_project_template,
    ensure_project_from_analysis,
    load_nexomap_project,
    resumo_project as resumo_nexomap_project,
)
from core.nexomap_catalog import load_layer_catalog, load_template_manifest
from core.nexomap_ai import spec_from_prompt
from core.nexomap_geo import summarize_area
from core import matriculas
from core import nexomap_doctor as nexomap_doctor_mod
from core import nexomap_generator
from core import secrets as secrets_loader

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
    # DEPRECATED: a IA é obrigatória (decisão §0.1 do PLANO_MELHORIAS); campo ignorado.
    usar_ia: bool = True


class NovoProjetoBody(BaseModel):
    nome: str
    cliente: str
    destino: str


class MatriculasExtrairBody(BaseModel):
    path: str                 # projeto.json da análise
    pdfs: list[str]           # caminhos locais dos PDFs de matrícula


class DominialidadeSalvarBody(BaseModel):
    path: str                 # projeto.json da análise
    registro: dict = {}
    matriculas: list[dict]    # linhas CONFERIDAS na grade da UI


class NexoMapChatBody(BaseModel):
    path: str
    prompt: str
    allow_local_fallback: bool = True


class NexoMapGenerateBody(BaseModel):
    path: str
    prompt: str | None = None
    mapspec: dict | None = None
    # DEPRECATED: MXD/ArcMap removidos; aceito e ignorado por compatibilidade.
    strict_mxd: bool = False


class NexoMapAreaBaseBody(BaseModel):
    path: str
    area_path: str


class NexoMapFromAnalysisBody(BaseModel):
    analysis_path: str
    area_path: str | None = None


# ----------------------------- config global -----------------------------
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.json")

def load_app_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
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


def _carregar_nexomap(path: str):
    try:
        return load_nexomap_project(path)
    except NexoMapError as e:
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
        "dominialidade": {
            "registro": {"cri": proj.dominialidade.cri, "cns": proj.dominialidade.cns},
            "matriculas": [
                {"numero": m.numero, "denominacao": m.denominacao, "proprietario": m.proprietario,
                 "cpf_cnpj": m.cpf_cnpj, "area_ha": m.area_ha}
                for m in proj.dominialidade.matriculas
            ],
        },
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
    out = pre_analise.gerar(proj, body.shapefile_zip, body.destino, saida_dir=body.saida_dir)
    return {"ok": True, "arquivo": out, "nome": os.path.basename(out)}


@app.post("/api/matriculas/extrair")
def matriculas_extrair(body: MatriculasExtrairBody):
    """Extrai matrículas de PDFs por IA. A resposta alimenta a grade de conferência
    OBRIGATÓRIA da UI; nada é gravado no projeto aqui."""
    proj = _carregar(body.path)
    try:
        return matriculas.extrair_de_pdfs(proj, body.pdfs)
    except matriculas.MatriculasError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/dominialidade/salvar")
def dominialidade_salvar(body: DominialidadeSalvarBody):
    """Grava a dominialidade conferida/corrigida pelo analista no projeto.json."""
    _carregar(body.path)  # valida o projeto antes de reescrever
    try:
        matriculas.salvar_dominialidade(body.path, body.registro, body.matriculas)
    except matriculas.MatriculasError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "path": body.path}


@app.post("/api/abrir")
def abrir(body: AbrirBody):
    alvo = body.alvo
    if not os.path.exists(alvo):
        raise HTTPException(status_code=404, detail="caminho não encontrado")
    try:
        if sys.platform.startswith("win"):
            os.startfile(alvo)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", alvo])
        else:
            subprocess.Popen(["xdg-open", alvo])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"não foi possível abrir: {e}")
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


# ----------------------------- NexoMap AI -----------------------------
@app.post("/api/nexomap/projeto/validar")
def nexomap_validar(body: CaminhoBody):
    proj = _carregar_nexomap(body.path)
    resumo = resumo_nexomap_project(proj)
    add_recent(proj.nome, proj._arquivo)
    if resumo["area_base"]["exists"]:
        try:
            resumo["area"] = summarize_area(proj).to_dict()
        except Exception as e:
            resumo["area_error"] = str(e)
    else:
        resumo["area"] = None
        resumo["area_error"] = "area_base ainda nao encontrada"
    return resumo


@app.post("/api/nexomap/projeto/novo")
def nexomap_novo_projeto(body: NovoProjetoBody):
    try:
        path = create_nexomap_project_template(body.nome, body.cliente, body.destino)
    except NexoMapError as e:
        raise HTTPException(status_code=400, detail=str(e))
    add_recent(body.nome, path)
    return {"ok": True, "path": path}


@app.post("/api/nexomap/from-analysis")
def nexomap_from_analysis(body: NexoMapFromAnalysisBody):
    analysis = _carregar(body.analysis_path)
    try:
        nexomap_path = ensure_project_from_analysis(analysis, body.area_path)
        proj = load_nexomap_project(nexomap_path)
        resumo = resumo_nexomap_project(proj)
        if resumo["area_base"]["exists"]:
            try:
                resumo["area"] = summarize_area(proj).to_dict()
            except Exception as e:
                resumo["area_error"] = str(e)
        else:
            resumo["area"] = None
            resumo["area_error"] = "area_base ainda nao encontrada"
        return {"ok": True, "path": nexomap_path, "project": resumo}
    except NexoMapError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/nexomap/projeto/area-base")
def nexomap_area_base(body: NexoMapAreaBaseBody):
    proj = _carregar_nexomap(body.path)
    if not os.path.exists(body.area_path):
        raise HTTPException(status_code=404, detail=f"geometria nao encontrada: {body.area_path}")
    ext = os.path.splitext(body.area_path)[1].lower()
    if ext not in (".zip", ".shp", ".geojson", ".json", ".kml", ".kmz"):
        raise HTTPException(status_code=400,
                            detail=f"formato nao suportado: {ext} (use .zip, .shp, .geojson, .kml ou .kmz)")
    try:
        with open(proj._arquivo, "r", encoding="utf-8") as f:
            data = json.load(f)
        root = proj.raiz_abs()
        area_abs = os.path.abspath(body.area_path)
        try:
            rel = os.path.relpath(area_abs, root)
            stored = rel if not rel.startswith("..") else area_abs
        except ValueError:
            stored = area_abs
        data.setdefault("area_base", {})["tipo"] = "shapefile_zip" if ext == ".zip" else "geometria"
        data["area_base"]["path"] = stored
        with open(proj._arquivo, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return {"ok": True, "path": proj._arquivo, "area_path": stored}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/nexomap/chat")
def nexomap_chat(body: NexoMapChatBody):
    proj = _carregar_nexomap(body.path)
    try:
        catalog = load_layer_catalog(proj.catalog_path())
        manifest = load_template_manifest(proj.template_manifest_path())
        sec = secrets_loader.load_secrets(proj)
        result = spec_from_prompt(body.prompt, proj, catalog, manifest, sec,
                                  allow_local_fallback=body.allow_local_fallback)
        return result.to_dict()
    except NexoMapError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/nexomap/generate")
async def nexomap_generate(body: NexoMapGenerateBody):
    async def stream():
        for event in nexomap_generator.generate_stream(
            body.path, prompt=body.prompt, mapspec=body.mapspec
        ):
            yield _sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/nexomap/resultados")
def nexomap_resultados(path: str):
    try:
        return nexomap_generator.list_results(path)
    except NexoMapError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/nexomap/file")
def nexomap_file(path: str):
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="arquivo nao encontrado")
    return FileResponse(path)


@app.get("/api/nexomap/doctor")
def nexomap_doctor(path: str | None = None):
    try:
        result = nexomap_doctor_mod.run(path or None)
    except (NexoMapError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["python"] = sys.executable
    result["ui_dist"] = os.path.isdir(_DIST) if "_DIST" in globals() else False
    return result


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
