# -*- coding: utf-8 -*-
"""Testes do motor de quantitativos (plano 04)."""
from __future__ import annotations

import pytest
from shapely.geometry import box, Polygon

from core.nexomap_quantitativos import (
    calcular_area_utm,
    intersecao_com_recorte,
    quantitativos_por_classe,
    resolver_tabela_calculada,
)
from core.overlay import FeatureGeo


# ── fixtures ────────────────────────────────────────────────────────────────

def _feat(geom, fonte="teste", layer="l1", props=None):
    return FeatureGeo(geom=geom, props=props or {}, fonte=fonte, layer=layer)


def _drawn_layer(id, features):
    """Simula uma DrawnLayer com o minimo necessario para os testes."""
    from unittest.mock import MagicMock
    dl = MagicMock()
    dl.id = id
    dl.features = features
    return dl


# ── calcular_area_utm ───────────────────────────────────────────────────────

def test_area_quadrado_1km2():
    """Quadrado de 1 km² = 1.000.000 m²."""
    quadrado = box(0, 0, 1000, 1000)
    feats = [_feat(quadrado)]
    assert calcular_area_utm(feats) == pytest.approx(1_000_000, rel=0.001)


def test_area_soma_multiplas_feicoes():
    """Soma de areas de multiplas feicoes."""
    feats = [
        _feat(box(0, 0, 1000, 1000)),
        _feat(box(2000, 0, 2500, 500)),
    ]
    total = calcular_area_utm(feats)
    # 1.000.000 + 250.000 = 1.250.000
    assert total == pytest.approx(1_250_000, rel=0.001)


def test_area_vazia():
    assert calcular_area_utm([]) == 0.0


def test_area_geometria_vazia():
    feats = [_feat(Polygon())]
    assert calcular_area_utm(feats) == 0.0


# ── intersecao_com_recorte ──────────────────────────────────────────────────

def test_intersecao_totalmente_dentro():
    recorte = box(0, 0, 1000, 1000)
    feats = [_feat(box(200, 200, 800, 800))]
    result = intersecao_com_recorte(feats, recorte, 31982)
    assert len(result) == 1
    assert result[0].geom.area == pytest.approx(360_000, rel=0.01)


def test_intersecao_parcial():
    recorte = box(0, 0, 1000, 1000)
    feats = [_feat(box(500, 500, 1500, 1500))]
    result = intersecao_com_recorte(feats, recorte, 31982)
    assert len(result) == 1
    assert result[0].geom.area == pytest.approx(250_000, rel=0.01)


def test_intersecao_fora_descartada():
    recorte = box(0, 0, 100, 100)
    feats = [_feat(box(200, 200, 300, 300))]
    result = intersecao_com_recorte(feats, recorte, 31982)
    assert len(result) == 0


# ── quantitativos_por_classe ────────────────────────────────────────────────

def test_quantitativos_classes_basicas():
    """Duas classes com areas conhecidas dentro de um quadrado de 1 km²."""
    recorte = box(0, 0, 1000, 1000)  # 1 km² = 100 ha

    # Veg. Nativa: 400x1000 = 400.000 m² = 40 ha (40%)
    veg = _drawn_layer("vegetacao", [_feat(box(0, 0, 400, 1000))])
    # Desmatada: 600x1000 = 600.000 m² = 60 ha (60%)
    desm = _drawn_layer("auas", [_feat(box(400, 0, 1000, 1000))])

    classes = [
        {"rotulo": "Veg. Nativa", "camada": "vegetacao"},
        {"rotulo": "Desmatada", "camada": "auas"},
    ]

    q = quantitativos_por_classe(classes, [veg, desm], recorte, 31982)

    assert q["areas_ha"] == pytest.approx([40.0, 60.0], rel=0.01)
    assert q["percentuais"] == pytest.approx([40.0, 60.0], rel=0.1)
    assert q["total_ha"] == pytest.approx(100.0, rel=0.01)
    assert q["total_percentual"] == pytest.approx(100.0, abs=0.5)


def test_quantitativos_classe_sem_features():
    """Classe sem camada → area zero."""
    recorte = box(0, 0, 1000, 1000)
    classes = [{"rotulo": "Inexistente", "camada": "nao_existe"}]
    q = quantitativos_por_classe(classes, [], recorte, 31982)
    assert q["areas_ha"] == [0.0]
    assert q["total_ha"] == 0.0


def test_quantitativos_recorte_parcial():
    """Feições que só parcialmente intersectam o recorte."""
    recorte = box(0, 0, 1000, 1000)  # 100 ha
    veg = _drawn_layer("veg", [_feat(box(-500, 0, 500, 1000))])  # metade dentro
    classes = [{"rotulo": "Veg", "camada": "veg"}]
    q = quantitativos_por_classe(classes, [veg], recorte, 31982)
    # 500 x 1000 = 500.000 m² = 50 ha
    assert q["areas_ha"][0] == pytest.approx(50.0, rel=0.01)
    assert q["total_ha"] == pytest.approx(50.0, rel=0.01)


# ── resolver_tabela_calculada ───────────────────────────────────────────────

def test_resolver_tabela_calculada():
    recorte = box(0, 0, 1000, 1000)
    veg = _drawn_layer("vegetacao", [_feat(box(0, 0, 400, 1000))])
    desm = _drawn_layer("auas", [_feat(box(400, 0, 1000, 1000))])

    tabela = {
        "titulo": "Quantitativo (ha)",
        "fonte": "quantitativos",
        "config": {
            "classes": [
                {"rotulo": "Veg. Nativa", "camada": "vegetacao"},
                {"rotulo": "Desmatada", "camada": "auas"},
            ],
            "percentual": True,
            "linha_total": True,
        },
    }

    resolved = resolver_tabela_calculada(tabela, [veg, desm], recorte, 31982)

    assert resolved["colunas"] == ["Classe", "Área (ha)", "%"]
    assert len(resolved["linhas"]) == 3  # 2 classes + total
    # primeira linha: Veg. Nativa
    assert resolved["linhas"][0][0] == "Veg. Nativa"
    # deve ter numeros formatados BR (com virgula)
    assert "," in str(resolved["linhas"][0][1])  # 40,00
    # ultima linha: Total
    assert resolved["linhas"][-1][0] == "Total"


def test_resolver_tabela_manual_nao_altera():
    """Tabela manual (sem fonte ou fonte:manual) nao e modificada."""
    tabela = {
        "titulo": "Dados",
        "colunas": ["A", "B"],
        "linhas": [["x", "1"], ["y", "2"]],
    }
    resolved = resolver_tabela_calculada(tabela, [], box(0, 0, 1, 1), 31982)
    assert resolved == tabela  # identico


def test_resolver_tabela_sem_classes():
    """Sem classes no config → sem alteracao."""
    tabela = {
        "titulo": "Vazio",
        "fonte": "quantitativos",
        "config": {"classes": []},
    }
    resolved = resolver_tabela_calculada(tabela, [], box(0, 0, 1, 1), 31982)
    assert resolved == tabela


# ── dedup (uniao) em calcular_area_utm ──────────────────────────────────────

def test_area_dedup_sobreposicao():
    """Feicoes sobrepostas nao devem contar 2x (uniao, nao soma)."""
    feats = [_feat(box(0, 0, 1000, 1000)), _feat(box(500, 0, 1500, 1000))]
    # soma seria 2.000.000; a uniao real = 1.500 x 1.000 = 1.500.000
    assert calcular_area_utm(feats) == pytest.approx(1_500_000, rel=0.001)


# ── matriz propriedade x classe ─────────────────────────────────────────────

def test_quantitativos_matriz_por_propriedade():
    from core.nexomap_quantitativos import quantitativos_matriz
    lote_a = _drawn_layer("lote_a", [_feat(box(0, 0, 1000, 1000))])       # 100 ha
    lote_b = _drawn_layer("lote_b", [_feat(box(1000, 0, 2000, 1000))])    # 100 ha
    # classe que cobre metade de cada lote
    veg = _drawn_layer("veg", [_feat(box(0, 0, 500, 1000)), _feat(box(1000, 0, 1500, 1000))])
    q = quantitativos_matriz(
        [{"rotulo": "A", "camada": "lote_a"}, {"rotulo": "B", "camada": "lote_b"}],
        [{"rotulo": "Veg", "camada": "veg"}],
        [lote_a, lote_b, veg], 31982)
    assert q["linhas"][0]["area_total_ha"] == pytest.approx(100, rel=0.001)
    assert q["linhas"][0]["classes_ha"][0] == pytest.approx(50, rel=0.001)   # metade do lote A
    assert q["linhas"][1]["classes_ha"][0] == pytest.approx(50, rel=0.001)   # metade do lote B
    assert q["total_classes_ha"][0] == pytest.approx(100, rel=0.001)


def test_resolver_tabela_matriz():
    from core.nexomap_quantitativos import resolver_tabela_calculada
    lote_a = _drawn_layer("lote_a", [_feat(box(0, 0, 1000, 1000))])
    veg = _drawn_layer("veg", [_feat(box(0, 0, 500, 1000))])
    tabela = {"fonte": "quantitativos_matriz", "config": {
        "propriedades": [{"rotulo": "Lote A", "camada": "lote_a"}],
        "classes": [{"rotulo": "Veg", "camada": "veg"}],
        "area_total_col": True, "linha_total": True}}
    resolved = resolver_tabela_calculada(tabela, [lote_a, veg], box(0, 0, 1, 1), 31982)
    assert resolved["colunas"][0] == "Propriedade"
    assert "Veg (ha)" in resolved["colunas"]
    assert resolved["linhas"][0][0] == "Lote A"
    assert resolved["linhas"][-1][0] == "TOTAL"
