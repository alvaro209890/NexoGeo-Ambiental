# -*- coding: utf-8 -*-
"""PDF and rendered-image validation for NexoMap AI."""
from __future__ import annotations

import json
import os

import fitz


def validate_pdf(pdf_path: str, png_path: str, expected_title: str,
                 map_region: tuple | None = None, layout_report: dict | None = None) -> dict:
    """Valida o PDF/PNG do mapa.

    Alem dos checks basicos (abre, titulo, pagina nao vazia), quando informados:
    - ``map_region`` = (x0, y0, w, h) em fracao da pagina -> confere que o quadro
      do mapa tem imagem/camadas (variancia de cor), i.e. nao esta em branco.
    - ``layout_report`` do renderer -> confere sem sobreposicao de elementos e
      sem texto cortado nas bordas.
    """
    checks = []
    result = {
        "ok": False,
        "pdf": pdf_path,
        "png_validacao": png_path,
        "checks": checks,
    }

    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("pdf_existe", os.path.exists(pdf_path), pdf_path)
    if not os.path.exists(pdf_path):
        return result
    size = os.path.getsize(pdf_path)
    add("pdf_tamanho_minimo", size > 1000, f"{size} bytes")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        add("pdf_abre", False, str(e))
        return result
    add("pdf_abre", True, f"{doc.page_count} pagina(s)")
    add("pdf_tem_pagina", doc.page_count > 0, str(doc.page_count))
    if doc.page_count <= 0:
        return result

    page = doc[0]
    text = page.get_text() or ""
    title_ok = expected_title.lower() in text.lower()
    add("titulo_presente", title_ok, expected_title)

    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    pix.save(png_path)
    add("png_validacao_salvo", os.path.exists(png_path), png_path)

    samples = pix.samples
    step = max(1, len(samples) // 30000)
    unique = len(set(samples[::step]))
    nonblank = unique > 8
    add("pagina_nao_vazia", nonblank, f"amostras_unicas={unique}")

    # imagem/camadas presentes no quadro do mapa (nao em branco)
    if map_region is not None:
        std, detalhe = _region_color_std(pix, map_region)
        add("mapa_tem_imagem", std > 6.0, f"std_cor={std:.1f} ({detalhe})")

    # relatorio de layout do renderer
    if layout_report is not None:
        overlaps = layout_report.get("sobreposicoes") or []
        add("sem_sobreposicao_elementos", not overlaps,
            "; ".join(overlaps) if overlaps else "ok")
        clipped = layout_report.get("texto_cortado") or []
        add("sem_texto_cortado", not clipped,
            (f"{len(clipped)} artefato(s): " + "; ".join(clipped[:3])) if clipped else "ok")

    result["ok"] = all(check["ok"] for check in checks)
    return result


def _region_color_std(pix, region: tuple) -> tuple[float, str]:
    """Desvio-padrao medio de cor numa regiao (fracao da pagina) do pixmap."""
    x0f, y0f, wf, hf = region
    W, H = pix.width, pix.height
    n = pix.n  # canais por pixel
    samples = pix.samples
    x0 = int(x0f * W); x1 = int((x0f + wf) * W)
    y0 = int((1 - y0f - hf) * H); y1 = int((1 - y0f) * H)  # fracao com origem embaixo -> topo
    x0, x1 = max(0, min(x0, W)), max(0, min(x1, W))
    y0, y1 = max(0, min(y0, H)), max(0, min(y1, H))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0, "regiao pequena"
    # amostra em grade para nao varrer tudo
    import statistics
    vals_r, vals_g, vals_b = [], [], []
    sx = max(1, (x1 - x0) // 40)
    sy = max(1, (y1 - y0) // 40)
    for yy in range(y0, y1, sy):
        row = yy * W * n
        for xx in range(x0, x1, sx):
            idx = row + xx * n
            vals_r.append(samples[idx])
            vals_g.append(samples[idx + 1] if n > 1 else samples[idx])
            vals_b.append(samples[idx + 2] if n > 2 else samples[idx])
    if len(vals_r) < 4:
        return 0.0, "poucas amostras"
    std = (statistics.pstdev(vals_r) + statistics.pstdev(vals_g) + statistics.pstdev(vals_b)) / 3
    return std, f"{len(vals_r)} amostras"


def write_validation_report(path: str, report: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Validacao contra o perfil do PDF-modelo IMAP (plano 10)
# --------------------------------------------------------------------------- #

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERFIL_IMAP_PADRAO = os.path.join(ROOT, "referencias", "perfil_imap.json")


def _page_spans(page) -> list[dict]:
    """Spans de texto nao-vazios de uma pagina (fitz)."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    out.append(span)
    return out


def _dentro(valor: float | None, stat: dict) -> bool:
    """True se ``valor`` esta dentro de media +/- tol do resumo (ou nada a checar)."""
    if valor is None or not stat or "media" not in stat:
        return False
    return abs(valor - stat["media"]) <= stat.get("tol", 0.0) + 1e-9


def _no_rodape(valor: float | None, stat: dict) -> bool:
    """True se ``valor`` (y0 em fracao) esta na faixa inferior ou abaixo dela.

    Limite inferior (nao simetrico): o elemento pode estar mais para baixo que a
    media do modelo sem reprovar — so nao pode estar acima da faixa.
    """
    if valor is None or not stat or "media" not in stat:
        return False
    return valor >= stat["media"] - stat.get("tol", 0.0) - 1e-9


def load_perfil_imap(perfil: str | dict | None = None) -> dict | None:
    """Carrega o perfil IMAP (caminho, dict ja carregado, ou default)."""
    if isinstance(perfil, dict):
        return perfil
    caminho = perfil or PERFIL_IMAP_PADRAO
    if not os.path.exists(caminho):
        return None
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def extrair_metricas_pagina(page) -> dict:
    """Extrai as metricas de estilo IMAP de uma pagina (fitz).

    Retorna posicoes em fracao da pagina (origem topo-esquerda). Chaves ausentes
    quando o elemento nao e encontrado. Usada tanto pela validacao de PDF gerado
    quanto pelo extrator de perfil (``scripts/extrair_perfil_imap.py``), para que
    perfil e medida sejam comparaveis.
    """
    w, h = page.rect.width, page.rect.height
    if w <= 0 or h <= 0:
        return {}
    spans = _page_spans(page)
    metr: dict = {"aspect": w / h}

    # Titulo = maior span de texto real (ignora glifos ESRI e fragmentos curtos).
    candidatos = [s for s in spans if "ESRI" not in s["font"] and len(s["text"].strip()) > 3]
    candidatos.sort(key=lambda s: -s["size"])
    if candidatos:
        s = candidatos[0]
        x0, y0, x1, y1 = s["bbox"]
        metr["titulo"] = {
            "size": s["size"],
            "cx_frac": ((x0 + x1) / 2) / w,
            "y0_frac": y0 / h,
            "largura_frac": (x1 - x0) / w,
            "fonte": s["font"],
            "cor": "#%06x" % (s["color"] & 0xFFFFFF),
            "texto": s["text"].strip(),
        }

    # Norte: fonte ESRINorth (glifo "µ" no modelo).
    norte = next((s for s in spans if "North" in s["font"]), None)
    if norte:
        x0, y0, x1, y1 = norte["bbox"]
        metr["norte"] = {"cx_frac": ((x0 + x1) / 2) / w, "cy_frac": ((y0 + y1) / 2) / h}

    # Legenda: cabecalho no rodape. Pode haver mini-legendas no corpo do mapa —
    # o header IMAP e o mais baixo na pagina (maior y0), na faixa inferior.
    legs = [s for s in spans if s["text"].strip().upper() == "LEGENDA"]
    if legs:
        s = max(legs, key=lambda s: s["bbox"][1])
        x0, y0, x1, y1 = s["bbox"]
        metr["legenda"] = {"cx_frac": ((x0 + x1) / 2) / w, "y0_frac": y0 / h}

    # Metadados da imagem: cabecalho na faixa inferior.
    metas = [s for s in spans if "METADADOS" in s["text"].upper()]
    if metas:
        s = max(metas, key=lambda s: s["bbox"][1])
        x0, y0, x1, y1 = s["bbox"]
        metr["metadados_imagem"] = {"cx_frac": ((x0 + x1) / 2) / w, "y0_frac": y0 / h}

    return metr


def extrair_metricas_pdf(pdf_path: str) -> dict:
    """Extrai as metricas de estilo IMAP da pagina 0 de um PDF gerado."""
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count <= 0:
            return {}
        return extrair_metricas_pagina(doc[0])
    finally:
        doc.close()


def _cor_escura(cor_hex: str) -> bool:
    """True se a cor (#rrggbb) e escura (luminancia baixa) — titulo IMAP e escuro."""
    try:
        v = int(cor_hex.lstrip("#"), 16)
    except (ValueError, AttributeError):
        return False
    r, g, b = (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF
    return (0.299 * r + 0.587 * g + 0.114 * b) < 110


def validar_contra_modelo(pdf_path: str, perfil: str | dict | None = None) -> dict:
    """Valida um PDF gerado contra o perfil visual do modelo IMAP (plano 10).

    Compara aspecto da pagina, posicao/tamanho/cor do titulo e presenca de norte,
    legenda e faixa inferior (metadados) com as metricas do PDF-modelo. Checks
    posicionais sao rigidos; fonte e informativa (o motor nativo usa outra fonte).

    Retorna ``{"ok", "checks": [...], "metricas": {...}, "perfil": <origem>}``.
    """
    checks: list[dict] = []
    result = {"ok": False, "pdf": pdf_path, "checks": checks}

    def add(name: str, ok: bool, detail: str = "", severidade: str = "hard"):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severidade": severidade})

    perfil_d = load_perfil_imap(perfil)
    if perfil_d is None:
        add("perfil_disponivel", False,
            "referencias/perfil_imap.json ausente — rode scripts/extrair_perfil_imap.py")
        return result
    result["perfil"] = perfil_d.get("gerado_de", "perfil_imap.json")

    if not os.path.exists(pdf_path):
        add("pdf_existe", False, pdf_path)
        return result

    metr = extrair_metricas_pdf(pdf_path)
    result["metricas"] = metr
    if not metr:
        add("pdf_legivel", False, "sem paginas/texto extraivel")
        return result

    # Aspecto da pagina (paisagem A4).
    pg = perfil_d.get("pagina", {}).get("aspect", {})
    add("aspecto_pagina", _dentro(metr.get("aspect"), pg),
        f"aspect={metr.get('aspect', 0):.3f} (modelo {pg.get('media')}±{pg.get('tol')})")

    # Titulo.
    tperf = perfil_d.get("titulo", {})
    tmetr = metr.get("titulo")
    if not tmetr:
        add("titulo_presente", False, "nenhum titulo detectado na pagina 0")
    else:
        add("titulo_presente", True, tmetr.get("texto", ""))
        add("titulo_no_topo", _dentro(tmetr["y0_frac"], tperf.get("y0_frac", {})),
            f"y0={tmetr['y0_frac']:.3f} (modelo {tperf.get('y0_frac', {}).get('media')})")
        add("titulo_centralizado", _dentro(tmetr["cx_frac"], tperf.get("cx_frac", {})),
            f"cx={tmetr['cx_frac']:.3f} (modelo {tperf.get('cx_frac', {}).get('media')})")
        add("titulo_tamanho", _dentro(tmetr["size"], tperf.get("size", {})),
            f"size={tmetr['size']:.1f} (modelo {tperf.get('size', {}).get('media')})",
            severidade="soft")
        add("titulo_cor_escura", _cor_escura(tmetr["cor"]),
            f"cor={tmetr['cor']}", severidade="soft")
        fontes_modelo = set(tperf.get("fontes", {}))
        add("titulo_fonte", tmetr["fonte"] in fontes_modelo,
            f"fonte={tmetr['fonte']} (modelo {sorted(fontes_modelo)})", severidade="soft")

    # Norte (topo-direita).
    add("norte_presente", metr.get("norte") is not None,
        _fmt_pos(metr.get("norte")), severidade="soft")

    # Faixa inferior: legenda + metadados no rodape.
    add("legenda_presente", metr.get("legenda") is not None, _fmt_pos(metr.get("legenda")))
    lmetr = metr.get("legenda")
    if lmetr:
        add("legenda_no_rodape",
            _no_rodape(lmetr["y0_frac"], perfil_d.get("faixa_inferior", {}).get("y0_frac", {})),
            f"y0={lmetr['y0_frac']:.3f} (faixa a partir de "
            f"{perfil_d.get('faixa_inferior', {}).get('y0_frac', {}).get('media')})")
    add("metadados_presente", metr.get("metadados_imagem") is not None,
        _fmt_pos(metr.get("metadados_imagem")), severidade="soft")

    # OK = todos os checks HARD passam (soft nao reprova).
    result["ok"] = all(c["ok"] for c in checks if c["severidade"] == "hard")
    result["hard_falhos"] = [c["name"] for c in checks if c["severidade"] == "hard" and not c["ok"]]
    result["soft_falhos"] = [c["name"] for c in checks if c["severidade"] == "soft" and not c["ok"]]
    return result


def _fmt_pos(pos: dict | None) -> str:
    if not pos:
        return "ausente"
    return f"cx={pos.get('cx_frac', 0):.3f} y0={pos.get('y0_frac', pos.get('cy_frac', 0)):.3f}"
