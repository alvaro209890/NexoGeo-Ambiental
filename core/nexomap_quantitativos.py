# -*- coding: utf-8 -*-
"""Motor de cálculo de quantitativos para tabelas do mapa IMAP.

Calcula áreas por classe/camada dentro de um recorte (perímetro da área base),
com sobreposição via shapely, conversão m²→ha, percentuais e formatação BR.

Usado pelo pipeline de geração ANTES do render, resolvendo ``fonte:
"quantitativos"`` no MapSpec e gravando as ``linhas`` calculadas.
"""
from __future__ import annotations

from core.normalize import br as _fmt_br
from core.overlay import FeatureGeo


def calcular_area_utm(features: list[FeatureGeo]) -> float:
    """Área (m²) da UNIÃO das geometrias (UTM), sem dupla contagem.

    Antes somava feição a feição; polígonos que se sobrepõem dentro da mesma
    classe (comum em recortes SIMCAR) eram contados 2x. A união via shapely
    resolve isso — a área da classe passa a ser a real ocupada no terreno.
    """
    from shapely.ops import unary_union
    geoms = [f.geom for f in features if not f.geom.is_empty]
    if not geoms:
        return 0.0
    try:
        return float(unary_union(geoms).area)
    except Exception:
        return float(sum(g.area for g in geoms))


def _union_geom(features: list[FeatureGeo]):
    """União (shapely) das geometrias de uma lista de feições — ou None."""
    from shapely.ops import unary_union
    geoms = [f.geom for f in features if not f.geom.is_empty]
    if not geoms:
        return None
    try:
        return unary_union(geoms)
    except Exception:
        return None


def intersecao_com_recorte(
    features: list[FeatureGeo], recorte_geom, utm_epsg: int
) -> list[FeatureGeo]:
    """Recorta as feições pela geometria de recorte (ex.: área base).

    Feições que não intersectam o recorte são descartadas.
    A interseção é calculada na projeção UTM (área métrica).
    """
    resultado = []
    for f in features:
        if f.geom.is_empty or recorte_geom.is_empty:
            continue
        try:
            intersec = f.geom.intersection(recorte_geom)
        except Exception:
            continue
        if intersec.is_empty:
            continue
        resultado.append(FeatureGeo(
            geom=intersec,
            props=dict(f.props),
            fonte=f.fonte,
            layer=f.layer,
        ))
    return resultado


def quantitativos_por_classe(
    classes: list[dict],
    drawn_layers: list,
    recorte_geom,
    utm_epsg: int,
) -> dict:
    """Calcula quantitativos por classe a partir das camadas desenhadas.

    Args:
        classes: Lista de specs, ex.:
            [{"rotulo": "Veg. Nativa", "camada": "vegetacao"},
             {"rotulo": "Desmatada", "camada": "auas"}]
        drawn_layers: Lista de ``DrawnLayer`` (já em UTM).
        recorte_geom: Geometria shapely do perímetro (UTM).
        utm_epsg: EPSG UTM (ex.: 31982).

    Returns:
        {"rotulos": [...], "areas_ha": [...], "percentuais": [...],
         "total_ha": float, "total_percentual": float}
    """
    # índice de camadas por id
    layer_map = {}
    for dl in drawn_layers:
        layer_map[dl.id] = dl

    areas = []
    rotulos = []
    for cls in classes:
        camada_id = cls.get("camada", "")
        dl = layer_map.get(camada_id)
        if dl is None or not dl.features:
            areas.append(0.0)
            rotulos.append(cls.get("rotulo", camada_id))
            continue

        recortadas = intersecao_com_recorte(dl.features, recorte_geom, utm_epsg)
        area_m2 = calcular_area_utm(recortadas)
        areas.append(area_m2)
        rotulos.append(cls.get("rotulo", camada_id))

    total_m2 = sum(areas)
    ha = [a / 10000.0 for a in areas]
    total_ha = total_m2 / 10000.0

    if total_ha > 0:
        pcts = [round(h / total_ha * 100.0, 1) for h in ha]
    else:
        pcts = [0.0] * len(ha)

    return {
        "rotulos": rotulos,
        "areas_ha": ha,
        "percentuais": pcts,
        "total_ha": total_ha,
        "total_percentual": round(sum(pcts), 1),
    }


def _norm_itens(itens: list) -> list[dict]:
    """Normaliza [str | {rotulo, camada}] -> [{rotulo, camada}]."""
    out = []
    for c in itens or []:
        if isinstance(c, str):
            out.append({"rotulo": c, "camada": c})
        elif isinstance(c, dict) and c.get("camada"):
            out.append({"rotulo": c.get("rotulo", c["camada"]), "camada": c["camada"]})
    return out


def quantitativos_matriz(propriedades: list[dict], classes: list[dict],
                         drawn_layers: list, utm_epsg: int) -> dict:
    """Matriz PROPRIEDADE × CLASSE (o cruzamento dos mapas IMAP).

    Para cada propriedade (ex.: Lote 65, Lote 66-A) intersecta cada classe
    (AVN, AC, AUAS...) e devolve a área (ha) ocupada, com dedup por união.
    ``propriedades``/``classes`` = [{"rotulo","camada"}], onde ``camada`` e o id
    de um DrawnLayer. Devolve linhas por propriedade + totais por classe.
    """
    layer_map = {dl.id: dl for dl in drawn_layers}
    linhas = []
    tot_classes = [0.0] * len(classes)
    tot_area = 0.0
    for prop in propriedades:
        pdl = layer_map.get(prop.get("camada"))
        pgeom = _union_geom(pdl.features) if pdl else None
        if pgeom is None or pgeom.is_empty:
            continue
        area_prop_ha = pgeom.area / 10000.0
        vals_ha = []
        for cls in classes:
            cdl = layer_map.get(cls.get("camada"))
            if cdl is None or not cdl.features:
                vals_ha.append(0.0)
                continue
            partes = []
            for f in cdl.features:
                if f.geom.is_empty or not f.geom.intersects(pgeom):
                    continue
                try:
                    inter = f.geom.intersection(pgeom)
                except Exception:
                    continue
                if not inter.is_empty:
                    partes.append(inter)
            from shapely.ops import unary_union
            a_ha = (unary_union(partes).area / 10000.0) if partes else 0.0
            vals_ha.append(a_ha)
        linhas.append({"rotulo": prop.get("rotulo", prop.get("camada", "")),
                       "area_total_ha": area_prop_ha, "classes_ha": vals_ha})
        tot_area += area_prop_ha
        for i, v in enumerate(vals_ha):
            tot_classes[i] += v
    return {"linhas": linhas, "total_area_ha": tot_area, "total_classes_ha": tot_classes,
            "rotulos_classes": [c.get("rotulo", c.get("camada", "")) for c in classes]}


def _matriz_para_tabela(spec_tabela: dict, q: dict, area_total_col: bool,
                        linha_total: bool) -> dict:
    """Monta colunas/linhas da tabela IMAP a partir do resultado da matriz."""
    colunas = ["Propriedade"]
    if area_total_col:
        colunas.append("Área total da\npropriedade (ha)")
    colunas += [f"{r} (ha)" for r in q["rotulos_classes"]]
    linhas = []
    for ln in q["linhas"]:
        row = [ln["rotulo"]]
        if area_total_col:
            row.append(_fmt_br(ln["area_total_ha"], 4))
        row += [_fmt_br(v, 4) for v in ln["classes_ha"]]
        linhas.append(row)
    if linha_total and q["linhas"]:
        row = ["TOTAL"]
        if area_total_col:
            row.append(_fmt_br(q["total_area_ha"], 4))
        row += [_fmt_br(v, 4) for v in q["total_classes_ha"]]
        linhas.append(row)
    resolved = dict(spec_tabela)
    resolved["colunas"] = colunas
    resolved["linhas"] = linhas
    resolved["_resolved"] = True
    return resolved


def resolver_tabela_calculada(spec_tabela: dict, drawn_layers: list,
                               recorte_geom, utm_epsg: int) -> dict:
    """Resolve uma tabela com ``fonte: "quantitativos"`` em linhas concretas.

    Devolve a tabela pronta para render (``colunas`` + ``linhas`` preenchidas
    com dados reais), preservando ``titulo`` e ``colunas_grupos``.
    """
    fonte = spec_tabela.get("fonte", "manual")
    if fonte == "quantitativos_matriz":
        cfg = spec_tabela.get("config") or {}
        props = _norm_itens(cfg.get("propriedades") or [])
        classes = _norm_itens(cfg.get("classes") or [])
        if not props or not classes:
            return spec_tabela
        q = quantitativos_matriz(props, classes, drawn_layers, utm_epsg)
        return _matriz_para_tabela(spec_tabela, q,
                                   area_total_col=bool(cfg.get("area_total_col", True)),
                                   linha_total=bool(cfg.get("linha_total", True)))
    if fonte != "quantitativos":
        return spec_tabela  # manual: já vem pronta

    config = spec_tabela.get("config") or {}
    classes_raw = config.get("classes") or []
    percentual = bool(config.get("percentual", True))
    linha_total = bool(config.get("linha_total", True))

    # Normaliza classes: aceita strings simples ou dicts {rotulo, camada}
    classes = []
    for c in classes_raw:
        if isinstance(c, str):
            classes.append({"rotulo": c, "camada": c})
        elif isinstance(c, dict):
            classes.append({
                "rotulo": c.get("rotulo", c.get("camada", "")),
                "camada": c.get("camada", ""),
            })

    if not classes:
        return spec_tabela  # sem classes → sem cálculo

    q = quantitativos_por_classe(classes, drawn_layers, recorte_geom, utm_epsg)

    # monta colunas
    colunas = ["Classe", "Área (ha)"]
    if percentual:
        colunas.append("%")

    # monta linhas
    linhas = []
    for i, rotulo in enumerate(q["rotulos"]):
        row = [rotulo, _fmt_br(q["areas_ha"][i], 2)]
        if percentual:
            row.append(_fmt_br(q["percentuais"][i], 1))
        linhas.append(row)

    if linha_total:
        total_row = ["Total", _fmt_br(q["total_ha"], 2)]
        if percentual:
            total_row.append(_fmt_br(q["total_percentual"], 1))
        linhas.append(total_row)

    resolved = dict(spec_tabela)
    resolved["colunas"] = colunas
    resolved["linhas"] = linhas
    resolved["_resolved"] = True
    return resolved
