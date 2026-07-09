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
    """Soma das áreas (m²) das geometrias, assumindo projeção UTM."""
    total = 0.0
    for f in features:
        if f.geom.is_empty:
            continue
        total += f.geom.area
    return total


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


def resolver_tabela_calculada(spec_tabela: dict, drawn_layers: list,
                               recorte_geom, utm_epsg: int) -> dict:
    """Resolve uma tabela com ``fonte: "quantitativos"`` em linhas concretas.

    Devolve a tabela pronta para render (``colunas`` + ``linhas`` preenchidas
    com dados reais), preservando ``titulo`` e ``colunas_grupos``.
    """
    fonte = spec_tabela.get("fonte", "manual")
    if fonte != "quantitativos":
        return spec_tabela  # manual: já vem pronta

    config = spec_tabela.get("config") or {}
    classes = config.get("classes") or []
    percentual = bool(config.get("percentual", True))
    linha_total = bool(config.get("linha_total", True))

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
