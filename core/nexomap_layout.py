# -*- coding: utf-8 -*-
"""Posicionamento de elementos do layout (plano 01).

Converte o modelo ``layout.elementos`` do MapSpec — ``ancora`` + ponto ``(x, y)``
em fracao da pagina (origem inferior-esquerda) + ``largura``/``altura`` opcionais —
no retangulo ``(x0, y0, w, h)`` em fracao da pagina que o renderer entrega ao
``fig.add_axes``. Sem ``layout`` no MapSpec, cada peca usa o default atual do
renderer (retrocompativel).

Ancoras ``in-map-*`` usam o quadro do mapa como referencia do ponto ``(x, y)``
(para elementos flutuantes sobre a imagem, ex.: tabela); ``largura``/``altura``
continuam em fracao da pagina.
"""
from __future__ import annotations

ANCORAS_BASE = (
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
)

# ids canonicos dos elementos posicionaveis (documentados no prompt do sistema)
ELEMENTOS_POSICIONAVEIS = (
    "titulo", "legenda", "tabela", "inset_tipologia", "minimapa",
    "rosa_dos_ventos", "escala", "metadados", "metadados_imagem", "logo",
)


def _split_anchor(ancora: str) -> tuple[str, str, bool]:
    """Normaliza a ancora -> (vertical, horizontal, in_map). Levanta ValueError."""
    a = (ancora or "bottom-left").strip().lower()
    in_map = a.startswith("in-map-")
    base = a[len("in-map-"):] if in_map else a
    if base not in ANCORAS_BASE:
        raise ValueError(f"ancora desconhecida: {ancora!r}")
    if base == "center":
        return "center", "center", in_map
    vert, _, horiz = base.partition("-")
    return vert, horiz, in_map


def anchor_alignment(ancora: str) -> tuple[str, str]:
    """(ha, va) de texto matplotlib equivalentes a ancora."""
    vert, horiz, _ = _split_anchor(ancora)
    ha = {"left": "left", "center": "center", "right": "right"}[horiz]
    va = {"top": "top", "center": "center", "bottom": "bottom"}[vert]
    return ha, va


def anchor_point(ancora: str, x: float, y: float,
                 map_rect: tuple | None = None) -> tuple[float, float]:
    """Ponto de ancoragem em fracao da PAGINA (resolve ``in-map-*`` via map_rect)."""
    _, _, in_map = _split_anchor(ancora)
    if in_map:
        if not map_rect:
            raise ValueError("ancora in-map-* requer map_rect")
        mx, my, mw, mh = map_rect
        return mx + float(x) * mw, my + float(y) * mh
    return float(x), float(y)


def resolve_rect(ancora: str, x: float, y: float, largura: float, altura: float,
                 map_rect: tuple | None = None) -> tuple[tuple, str]:
    """Resolve (ancora, x, y, largura, altura) -> ((x0, y0, w, h), aviso).

    O retangulo sai em fracao da pagina, clampado dentro dela; quando o clamp
    precisa agir, ``aviso`` descreve o ajuste (senao e string vazia).
    """
    vert, horiz, _ = _split_anchor(ancora)
    w = max(0.005, float(largura))
    h = max(0.005, float(altura))
    px, py = anchor_point(ancora, x, y, map_rect)
    dx = {"left": 0.0, "center": -w / 2.0, "right": -w}[horiz]
    dy = {"bottom": 0.0, "center": -h / 2.0, "top": -h}[vert]
    x0, y0 = px + dx, py + dy

    aviso = ""
    cx0 = min(max(x0, 0.0), max(0.0, 1.0 - w))
    cy0 = min(max(y0, 0.0), max(0.0, 1.0 - h))
    if abs(cx0 - x0) > 1e-9 or abs(cy0 - y0) > 1e-9 or w > 1.0 or h > 1.0:
        aviso = (f"elemento saiu da pagina (rect {x0:.3f},{y0:.3f},{w:.3f},{h:.3f}); "
                 "reposicionado para dentro")
        x0, y0 = cx0, cy0
        w, h = min(w, 1.0), min(h, 1.0)
    return (x0, y0, w, h), aviso


def element_rect(layout: dict, elemento: str, default_rect: tuple,
                 map_rect: tuple | None = None, avisos: list | None = None) -> tuple:
    """Rect do elemento: ``layout.elementos[elemento]`` quando presente, senao o default.

    Config invalida nunca derruba o render — vira aviso e cai no default.
    """
    cfg = ((layout or {}).get("elementos") or {}).get(elemento)
    if not isinstance(cfg, dict) or not cfg:
        return default_rect
    try:
        rect, aviso = resolve_rect(
            cfg.get("ancora", "bottom-left"),
            float(cfg.get("x", 0.0)), float(cfg.get("y", 0.0)),
            float(cfg.get("largura", default_rect[2])),
            float(cfg.get("altura", default_rect[3])),
            map_rect=map_rect,
        )
    except (TypeError, ValueError, KeyError) as e:
        if avisos is not None:
            avisos.append(f"layout.elementos.{elemento} invalido ({e}); usado o padrao")
        return default_rect
    if aviso and avisos is not None:
        avisos.append(f"layout.elementos.{elemento}: {aviso}")
    return rect


def element_text_anchor(layout: dict, elemento: str, map_rect: tuple,
                        default: tuple, avisos: list | None = None) -> tuple:
    """Ancora de TEXTO em fracao dos EIXOS do mapa: (x_axes, y_axes, ha, va).

    Usada por pecas desenhadas com ``ax.text``/``transAxes`` (ex.: caixa de
    titulo). ``default`` = (x_axes, y_axes, ha, va) atuais do renderer.
    """
    cfg = ((layout or {}).get("elementos") or {}).get(elemento)
    if not isinstance(cfg, dict) or not cfg:
        return default
    mx, my, mw, mh = map_rect
    try:
        ancora = cfg.get("ancora", "top-right")
        px, py = anchor_point(ancora, float(cfg.get("x", 0.0)),
                              float(cfg.get("y", 0.0)), map_rect)
        ha, va = anchor_alignment(ancora)
    except (TypeError, ValueError, KeyError) as e:
        if avisos is not None:
            avisos.append(f"layout.elementos.{elemento} invalido ({e}); usado o padrao")
        return default
    ax_x = (px - mx) / mw if mw else 0.5
    ax_y = (py - my) / mh if mh else 0.5
    clamped = (min(max(ax_x, 0.0), 1.0), min(max(ax_y, 0.0), 1.0))
    if avisos is not None and (clamped[0] != ax_x or clamped[1] != ax_y):
        avisos.append(f"layout.elementos.{elemento}: ponto fora do quadro do mapa; ajustado")
    return clamped[0], clamped[1], ha, va
