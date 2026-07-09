# -*- coding: utf-8 -*-
"""Tools atomicas da IA cartografica (plano 00 — function calling).

Cada tool e uma funcao pura sobre o dict do MapSpec:
``tool(spec_dict, ctx, **args) -> (spec_dict_novo, mensagem)``. O orquestrador
(`core/nexomap_agent.py`) expoe ``TOOL_SCHEMAS`` ao provedor (campo ``tools`` da
API OpenAI-compativel) e executa cada ``tool_call`` aqui. Nenhuma tool derruba o
loop: argumento invalido vira mensagem de erro devolvida a IA (role ``tool``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from core.mapspec import mapspec_from_dict
from core.nexomap_catalog import layer_index, template_index
from core.nexomap_layout import ANCORAS_BASE, ELEMENTOS_POSICIONAVEIS, resolve_rect

# chaves aceitas em elementos_layout (visibilidade) — espelha o renderer
ELEMENTOS_VISIBILIDADE = (
    "grade", "norte", "rosa_dos_ventos", "escala_grafica", "legenda", "metadados",
    "minimapa", "titulo_caixa", "inset_tipologia", "tabela", "metadados_imagem", "logo",
)

_ANCORAS_TODAS = list(ANCORAS_BASE) + [f"in-map-{a}" for a in ANCORAS_BASE]


class ToolError(Exception):
    """Erro de argumento/estado de uma tool — volta como mensagem para a IA."""


@dataclass
class ToolContext:
    catalog: dict
    manifest: dict
    secrets: dict = field(default_factory=dict)
    project_name: str = ""


def _copia(spec: dict) -> dict:
    return json.loads(json.dumps(spec, ensure_ascii=False))


def _validar(spec: dict) -> dict:
    """Confere que o dict continua um MapSpec parseavel (barato, sem rede)."""
    mapspec_from_dict(spec)
    return spec


# --------------------------------------------------------------------------- #
# Tools de leitura
# --------------------------------------------------------------------------- #

def tool_estado_atual(spec: dict, ctx: ToolContext) -> tuple[dict, str]:
    estado = {
        "mapspec": spec,
        "elementos_posicionaveis": list(ELEMENTOS_POSICIONAVEIS),
        "elementos_visibilidade": list(ELEMENTOS_VISIBILIDADE),
        "ancoras": _ANCORAS_TODAS,
    }
    return spec, json.dumps(estado, ensure_ascii=False)


def tool_listar_camadas(spec: dict, ctx: ToolContext) -> tuple[dict, str]:
    linhas = []
    for cid, cfg in layer_index(ctx.catalog).items():
        linhas.append({
            "id": cid,
            "nome": cfg.get("nome", cid),
            "tema": cfg.get("tema"),
            "tipo": cfg.get("tipo"),
            "auth": cfg.get("auth"),
            "descricao": cfg.get("descricao", ""),
        })
    return spec, json.dumps({"camadas": linhas}, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Tools de escrita
# --------------------------------------------------------------------------- #

def tool_criar_mapa(spec: dict, ctx: ToolContext, titulo: str, tipo: str = "geral",
                    template: str = "", basemap: str = "satellite",
                    grade_tipo: str = "dms") -> tuple[dict, str]:
    if not titulo or not str(titulo).strip():
        raise ToolError("titulo obrigatorio")
    templates = template_index(ctx.manifest)
    if template and template not in templates:
        raise ToolError(f"template inexistente: {template}; validos: {sorted(templates)}")
    if not template:
        template = next(iter(templates), "tematico_a3_retrato")
    novo = {
        "titulo": str(titulo).strip(),
        "tipo": tipo or "geral",
        "area_base": "projeto.area_base",
        "layout_template": template,
        "escala": "auto",
        "basemap": basemap or "satellite",
        "grade_tipo": grade_tipo or "dms",
        "camadas": [{
            "id": "perimetro", "fonte": "area_base", "filtro": "",
            "estilo": {"linha": "#ff2d00", "largura": 2.4, "preenchimento": "transparente"},
            "rotulo": True,
        }],
        "elementos_layout": {"legenda": True, "escala_grafica": True, "norte": True,
                             "grade": True, "minimapa": True, "metadados": True},
        "saidas": ["pdf", "png_validacao", "geojson"],
    }
    return _validar(novo), f"mapa criado: '{titulo}' (template {template})"


def tool_definir_titulo(spec: dict, ctx: ToolContext, titulo: str = "",
                        subtitulo: str = "") -> tuple[dict, str]:
    if not titulo and not subtitulo:
        raise ToolError("informe titulo e/ou subtitulo")
    novo = _copia(spec)
    if titulo:
        novo["titulo"] = str(titulo).strip()
    if subtitulo:
        novo["subtitulo"] = str(subtitulo).strip()
    return _validar(novo), "titulo atualizado"


def tool_mover_elemento(spec: dict, ctx: ToolContext, elemento: str, posicao: dict,
                        tamanho: dict | None = None) -> tuple[dict, str]:
    if elemento not in ELEMENTOS_POSICIONAVEIS:
        raise ToolError(f"elemento invalido: {elemento}; validos: {list(ELEMENTOS_POSICIONAVEIS)}")
    if not isinstance(posicao, dict) or "ancora" not in posicao:
        raise ToolError("posicao deve ser um objeto {ancora, x, y}")
    ancora = str(posicao.get("ancora"))
    x = float(posicao.get("x", 0.0))
    y = float(posicao.get("y", 0.0))
    largura = float((tamanho or {}).get("largura", 0.2) or 0.2)
    altura = float((tamanho or {}).get("altura", 0.1) or 0.1)
    # valida a ancora/rect (levanta ValueError -> ToolError)
    try:
        map_rect = (0.035, 0.155, 0.935, 0.80) if ancora.startswith("in-map-") else None
        _, aviso = resolve_rect(ancora, x, y, largura, altura, map_rect=map_rect)
    except ValueError as e:
        raise ToolError(str(e)) from e
    novo = _copia(spec)
    elementos = novo.setdefault("layout", {}).setdefault("elementos", {})
    cfg = dict(elementos.get(elemento) or {})
    cfg.update({"ancora": ancora, "x": x, "y": y})
    if tamanho:
        if "largura" in tamanho:
            cfg["largura"] = float(tamanho["largura"])
        if "altura" in tamanho:
            cfg["altura"] = float(tamanho["altura"])
    elementos[elemento] = cfg
    msg = f"elemento '{elemento}' ancorado em {ancora} ({x:.3f}, {y:.3f})"
    if aviso:
        msg += f" [aviso: {aviso}]"
    return _validar(novo), msg


def tool_alternar_elemento(spec: dict, ctx: ToolContext, elemento: str,
                           visivel: bool) -> tuple[dict, str]:
    if elemento not in ELEMENTOS_VISIBILIDADE:
        raise ToolError(f"elemento invalido: {elemento}; validos: {list(ELEMENTOS_VISIBILIDADE)}")
    novo = _copia(spec)
    novo.setdefault("elementos_layout", {})[elemento] = bool(visivel)
    return _validar(novo), f"elemento '{elemento}' {'ligado' if visivel else 'desligado'}"


def tool_editar_estilo_elemento(spec: dict, ctx: ToolContext, elemento: str,
                                props: dict) -> tuple[dict, str]:
    if elemento not in ELEMENTOS_POSICIONAVEIS:
        raise ToolError(f"elemento invalido: {elemento}; validos: {list(ELEMENTOS_POSICIONAVEIS)}")
    if not isinstance(props, dict) or not props:
        raise ToolError("props deve ser um objeto com fundo/cor/tamanho/fonte/borda")
    novo = _copia(spec)
    elementos = novo.setdefault("layout", {}).setdefault("elementos", {})
    cfg = dict(elementos.get(elemento) or {})
    estilo = dict(cfg.get("estilo") or {})
    estilo.update({k: v for k, v in props.items() if v is not None})
    cfg["estilo"] = estilo
    elementos[elemento] = cfg
    return _validar(novo), f"estilo de '{elemento}' atualizado: {sorted(estilo)}"


def _layer_ids(spec: dict) -> list[str]:
    return [c.get("id") for c in spec.get("camadas") or []]


def tool_adicionar_camada(spec: dict, ctx: ToolContext, fonte: str,
                          estilo: dict | None = None, rotulo: bool = False) -> tuple[dict, str]:
    layers = layer_index(ctx.catalog)
    if fonte == "area_base":
        cid = "perimetro"
    elif isinstance(fonte, str) and fonte.startswith("catalogo."):
        cid = fonte.split(".", 1)[1]
        if cid not in layers:
            raise ToolError(f"camada inexistente no catalogo: {cid}; use listar_camadas")
    else:
        raise ToolError("fonte deve ser 'area_base' ou 'catalogo.<id>'")
    novo = _copia(spec)
    if cid in _layer_ids(novo):
        return novo, f"camada '{cid}' ja esta no mapa"
    novo.setdefault("camadas", []).append({
        "id": cid, "fonte": fonte,
        "filtro": "intersecta_area_base" if cid != "perimetro" else "",
        "estilo": estilo or {}, "rotulo": bool(rotulo),
    })
    aviso = ""
    auth = layers.get(cid, {}).get("auth")
    if auth and not ctx.secrets.get(auth):
        aviso = f" [aviso: requer segredo '{auth}' — sem ele a camada sai do mapa com aviso]"
    return _validar(novo), f"camada '{cid}' adicionada{aviso}"


def tool_remover_camada(spec: dict, ctx: ToolContext, id: str) -> tuple[dict, str]:
    novo = _copia(spec)
    antes = _layer_ids(novo)
    if id not in antes:
        raise ToolError(f"camada '{id}' nao esta no mapa; atuais: {antes}")
    novo["camadas"] = [c for c in novo["camadas"] if c.get("id") != id]
    if not novo["camadas"]:
        raise ToolError("nao e possivel remover a ultima camada do mapa")
    aviso = ""
    itens = ((novo.get("legenda") or {}).get("itens")) or []
    if any(i.get("camada") == id for i in itens if isinstance(i, dict)):
        aviso = " [aviso: ha item de legenda vinculado a essa camada; mantido]"
    return _validar(novo), f"camada '{id}' removida{aviso}"


def tool_editar_camada(spec: dict, ctx: ToolContext, id: str, estilo: dict | None = None,
                       rotulo: bool | None = None, filtro: str | None = None) -> tuple[dict, str]:
    novo = _copia(spec)
    alvo = next((c for c in novo.get("camadas") or [] if c.get("id") == id), None)
    if alvo is None:
        raise ToolError(f"camada '{id}' nao esta no mapa; atuais: {_layer_ids(novo)}")
    if estilo:
        alvo.setdefault("estilo", {}).update(estilo)
    if rotulo is not None:
        alvo["rotulo"] = bool(rotulo)
    if filtro is not None:
        alvo["filtro"] = str(filtro)
    return _validar(novo), f"camada '{id}' atualizada"


def tool_editar_legenda(spec: dict, ctx: ToolContext, titulo: str | None = None,
                        itens: list | None = None, posicao: dict | None = None,
                        colunas: int | None = None, modo: str | None = None,
                        fonte_tamanho: float | None = None) -> tuple[dict, str]:
    novo = _copia(spec)
    leg = dict(novo.get("legenda") or {})
    if modo is not None:
        if modo not in ("auto", "manual", "misto"):
            raise ToolError("modo deve ser auto|manual|misto")
        leg["modo"] = modo
    if titulo is not None:
        leg["titulo"] = str(titulo)
    if itens is not None:
        if not isinstance(itens, list):
            raise ToolError("itens deve ser uma lista de objetos {rotulo, tipo, cor, ...}")
        leg["itens"] = itens
    if posicao is not None:
        if not isinstance(posicao, dict) or "ancora" not in posicao:
            raise ToolError("posicao deve ser um objeto {ancora, x, y}")
        try:
            resolve_rect(str(posicao["ancora"]), float(posicao.get("x", 0)),
                         float(posicao.get("y", 0)), float(posicao.get("largura", 0.3)), 0.1,
                         map_rect=(0.035, 0.155, 0.935, 0.80))
        except ValueError as e:
            raise ToolError(str(e)) from e
        leg["posicao"] = posicao
    if colunas is not None:
        leg["colunas"] = max(1, int(colunas))
    if fonte_tamanho is not None:
        leg["fonte_tamanho"] = float(fonte_tamanho)
    novo["legenda"] = leg
    return _validar(novo), "legenda atualizada"


def tool_criar_tabela(spec: dict, ctx: ToolContext, titulo: str, colunas: list | None = None,
                      linhas: list | None = None, fonte: str = "manual",
                      config: dict | None = None) -> tuple[dict, str]:
    if fonte == "manual":
        if not colunas or linhas is None:
            raise ToolError("tabela manual exige colunas[] e linhas[][]")
        tabela = {"titulo": titulo, "colunas": colunas, "linhas": linhas}
        msg = f"tabela manual '{titulo}' criada ({len(linhas)} linha(s))"
    elif fonte in ("quantitativos", "sigef_sobreposicao"):
        tabela = {"titulo": titulo, "fonte": fonte, "config": config or {}}
        if colunas:
            tabela["colunas"] = colunas
        msg = (f"tabela calculada '{titulo}' registrada (fonte {fonte}); "
               "as linhas sao calculadas por overlay no render")
    else:
        raise ToolError("fonte deve ser manual|quantitativos|sigef_sobreposicao")
    novo = _copia(spec)
    novo["tabela"] = tabela
    novo.setdefault("elementos_layout", {}).setdefault("tabela", True)
    return _validar(novo), msg


def tool_definir_metadados_imagem(spec: dict, ctx: ToolContext, satelite_sensor: str = "",
                                  data_aquisicao: str = "", orbita_ponto: str = "",
                                  datum: str = "") -> tuple[dict, str]:
    novo = _copia(spec)
    meta = dict(novo.get("metadados_imagem") or {})
    for k, v in (("satelite_sensor", satelite_sensor), ("data_aquisicao", data_aquisicao),
                 ("orbita_ponto", orbita_ponto), ("datum", datum)):
        if v:
            meta[k] = str(v)
    if not meta:
        raise ToolError("informe ao menos um campo de metadados")
    novo["metadados_imagem"] = meta
    return _validar(novo), "metadados de imagem atualizados"


def tool_definir_raster_fundo(spec: dict, ctx: ToolContext, caminho: str) -> tuple[dict, str]:
    if not caminho or not str(caminho).strip():
        raise ToolError("caminho do raster obrigatorio")
    novo = _copia(spec)
    novo["raster_fundo"] = str(caminho).strip()
    return _validar(novo), f"raster de fundo definido: {caminho}"


def tool_definir_escala(spec: dict, ctx: ToolContext, escala) -> tuple[dict, str]:
    novo = _copia(spec)
    if isinstance(escala, str) and escala.strip().lower() == "auto":
        novo["escala"] = "auto"
    else:
        try:
            valor = int(escala)
        except (TypeError, ValueError):
            raise ToolError("escala deve ser um inteiro (ex.: 25000) ou 'auto'")
        if valor <= 0:
            raise ToolError("escala deve ser positiva")
        novo["escala"] = valor
    return _validar(novo), f"escala definida: {novo['escala']}"


def tool_finalizar(spec: dict, ctx: ToolContext, resumo: str = "") -> tuple[dict, str]:
    return spec, resumo or "finalizado"


# --------------------------------------------------------------------------- #
# Registro + JSON Schemas (campo `tools` da API OpenAI-compativel)
# --------------------------------------------------------------------------- #

TOOLS: dict[str, Callable] = {
    "estado_atual": tool_estado_atual,
    "listar_camadas": tool_listar_camadas,
    "criar_mapa": tool_criar_mapa,
    "definir_titulo": tool_definir_titulo,
    "mover_elemento": tool_mover_elemento,
    "alternar_elemento": tool_alternar_elemento,
    "editar_estilo_elemento": tool_editar_estilo_elemento,
    "adicionar_camada": tool_adicionar_camada,
    "remover_camada": tool_remover_camada,
    "editar_camada": tool_editar_camada,
    "editar_legenda": tool_editar_legenda,
    "criar_tabela": tool_criar_tabela,
    "definir_metadados_imagem": tool_definir_metadados_imagem,
    "definir_raster_fundo": tool_definir_raster_fundo,
    "definir_escala": tool_definir_escala,
    "finalizar": tool_finalizar,
}

_POSICAO_SCHEMA = {
    "type": "object",
    "properties": {
        "ancora": {"type": "string", "enum": _ANCORAS_TODAS},
        "x": {"type": "number", "minimum": 0, "maximum": 1},
        "y": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["ancora", "x", "y"],
}

_ESTILO_CAMADA_SCHEMA = {
    "type": "object",
    "properties": {
        "linha": {"type": "string", "description": "cor da linha (hex)"},
        "preenchimento": {"type": "string", "description": "cor de preenchimento (hex), 'transparente' ou 'none'"},
        "opacidade": {"type": "number", "minimum": 0, "maximum": 1},
        "largura": {"type": "number"},
        "hachura": {"type": "string", "description": "padrao matplotlib: ////, ----, ...."},
    },
}

_ITEM_LEGENDA_SCHEMA = {
    "type": "object",
    "properties": {
        "rotulo": {"type": "string"},
        "tipo": {"type": "string", "enum": ["linha", "poligono", "ponto", "imagem"]},
        "cor": {"type": "string"},
        "preenchimento": {"type": "string"},
        "hachura": {"type": "string"},
        "opacidade": {"type": "number"},
        "largura": {"type": "number"},
        "camada": {"type": "string", "description": "id de camada do mapa para herdar estilo/contagem"},
    },
}


def _schema(nome: str, descricao: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {"type": "object", "properties": props, "required": required or []},
        },
    }


TOOL_SCHEMAS: list[dict] = [
    _schema("estado_atual", "Le o MapSpec atual, os elementos posicionaveis e as ancoras validas.", {}),
    _schema("listar_camadas", "Lista as camadas disponiveis no catalogo (id, nome, tema, auth, descricao).", {}),
    _schema("criar_mapa", "Cria um MapSpec base novo (perimetro + elementos padrao).", {
        "titulo": {"type": "string"},
        "tipo": {"type": "string"},
        "template": {"type": "string"},
        "basemap": {"type": "string", "enum": ["satellite", "light", "osm", "none"]},
        "grade_tipo": {"type": "string", "enum": ["dms", "utm"]},
    }, ["titulo"]),
    _schema("definir_titulo", "Define titulo e/ou subtitulo do mapa.", {
        "titulo": {"type": "string"}, "subtitulo": {"type": "string"},
    }),
    _schema("mover_elemento", "Reposiciona um elemento do layout (titulo, legenda, tabela, "
            "inset_tipologia, minimapa, rosa_dos_ventos, escala, metadados, metadados_imagem, logo). "
            "x,y em fracao da pagina [0..1], origem inferior-esquerda; ancoras in-map-* usam o quadro do mapa.", {
        "elemento": {"type": "string", "enum": list(ELEMENTOS_POSICIONAVEIS)},
        "posicao": _POSICAO_SCHEMA,
        "tamanho": {"type": "object", "properties": {
            "largura": {"type": "number", "minimum": 0, "maximum": 1},
            "altura": {"type": "number", "minimum": 0, "maximum": 1}}},
    }, ["elemento", "posicao"]),
    _schema("alternar_elemento", "Liga/desliga a visibilidade de um elemento do layout.", {
        "elemento": {"type": "string", "enum": list(ELEMENTOS_VISIBILIDADE)},
        "visivel": {"type": "boolean"},
    }, ["elemento", "visivel"]),
    _schema("editar_estilo_elemento", "Edita o estilo visual de um elemento (ex.: titulo: "
            "{fundo: 'white', cor: '#111827', tamanho: 15} = caixa branca padrao IMAP).", {
        "elemento": {"type": "string", "enum": list(ELEMENTOS_POSICIONAVEIS)},
        "props": {"type": "object", "properties": {
            "fundo": {"type": "string"}, "cor": {"type": "string"},
            "tamanho": {"type": "number"}, "fonte": {"type": "string"},
            "borda": {"type": "string"}}},
    }, ["elemento", "props"]),
    _schema("adicionar_camada", "Adiciona uma camada ao mapa. fonte = 'catalogo.<id>' (use "
            "listar_camadas) ou 'area_base' (perimetro).", {
        "fonte": {"type": "string"},
        "estilo": _ESTILO_CAMADA_SCHEMA,
        "rotulo": {"type": "boolean"},
    }, ["fonte"]),
    _schema("remover_camada", "Remove uma camada do mapa pelo id.", {
        "id": {"type": "string"},
    }, ["id"]),
    _schema("editar_camada", "Edita estilo/rotulo/filtro de uma camada existente.", {
        "id": {"type": "string"},
        "estilo": _ESTILO_CAMADA_SCHEMA,
        "rotulo": {"type": "boolean"},
        "filtro": {"type": "string"},
    }, ["id"]),
    _schema("editar_legenda", "Edita a legenda: titulo, itens (ordem/rotulos/simbolos), modo "
            "(auto|manual|misto), colunas, fonte_tamanho e posicao.", {
        "titulo": {"type": "string"},
        "modo": {"type": "string", "enum": ["auto", "manual", "misto"]},
        "itens": {"type": "array", "items": _ITEM_LEGENDA_SCHEMA},
        "posicao": _POSICAO_SCHEMA,
        "colunas": {"type": "integer", "minimum": 1},
        "fonte_tamanho": {"type": "number"},
    }),
    _schema("criar_tabela", "Cria a tabela do mapa. fonte 'manual' exige colunas+linhas; "
            "'quantitativos'/'sigef_sobreposicao' calculam as linhas por overlay no render.", {
        "titulo": {"type": "string"},
        "fonte": {"type": "string", "enum": ["manual", "quantitativos", "sigef_sobreposicao"]},
        "colunas": {"type": "array", "items": {"type": "string"}},
        "linhas": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "config": {"type": "object"},
    }, ["titulo"]),
    _schema("definir_metadados_imagem", "Preenche o bloco METADADOS IMAGEM da faixa inferior.", {
        "satelite_sensor": {"type": "string"}, "data_aquisicao": {"type": "string"},
        "orbita_ponto": {"type": "string"}, "datum": {"type": "string"},
    }),
    _schema("definir_raster_fundo", "Define um GeoTIFF local como fundo do mapa.", {
        "caminho": {"type": "string"},
    }, ["caminho"]),
    _schema("definir_escala", "Define a escala do mapa (inteiro, ex.: 25000) ou 'auto'.", {
        "escala": {"type": ["integer", "string"]},
    }, ["escala"]),
    _schema("finalizar", "Encerra o turno de edicao e dispara o render. Chame quando o pedido "
            "do usuario estiver atendido.", {
        "resumo": {"type": "string", "description": "resumo curto do que foi feito"},
    }),
]


def execute_tool(nome: str, spec: dict, ctx: ToolContext, args: dict) -> tuple[dict, str, bool]:
    """Executa uma tool. Devolve (spec_novo, mensagem, finalizou).

    Erros de argumento NUNCA levantam para fora: viram mensagem 'erro: ...'
    devolvida a IA, mantendo o spec anterior.
    """
    fn = TOOLS.get(nome)
    if fn is None:
        return spec, f"erro: tool desconhecida '{nome}'", False
    try:
        novo, msg = fn(spec, ctx, **(args or {}))
    except ToolError as e:
        return spec, f"erro: {e}", False
    except TypeError as e:  # argumentos faltando/sobrando do provedor
        return spec, f"erro: argumentos invalidos para {nome}: {e}", False
    except Exception as e:  # validacao do mapspec etc.
        return spec, f"erro: {type(e).__name__}: {e}", False
    return novo, msg, nome == "finalizar"
