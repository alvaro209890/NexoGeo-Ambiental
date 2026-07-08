# 04 — Tabelas com dados reais

## Objetivo

Permitir que a IA **crie tabelas** no mapa (quantitativos por classe, parcelas SIGEF sobrepostas,
áreas por matrícula etc.) com **dados calculados de verdade** — não digitados pela IA — e com estilo
IMAP (cabeçalho azul, zebra, multinível quando preciso).

## Estado atual

- `nexomap_renderer._draw_table(fig, rect, tabela)` já renderiza `tabela = {titulo, colunas, linhas}`
  com cabeçalho azul e zebra. **Mas as linhas vêm prontas** (a IA digita os números).
- Não há **cálculo automático** de quantitativos a partir das geometrias/camadas.
- Não há **tabela multinível** (ex.: Matrícula × Cerrado/Floresta × AD/AVN, como no mapa referência).

## Escopo

**Inclui**
- Modelo de tabela estendido: `fonte: "manual" | "quantitativos" | "sigef_sobreposicao" | ...`.
- Motor de **cálculo de quantitativos** por overlay (área por classe, por camada, por feição).
- Suporte a **cabeçalho multinível** (grupos de colunas).
- Formatação **BR** de números (milhar `.`, decimal `,`) reaproveitando `core/normalize.py`.
- Tool `criar_tabela` (plano 00).

**Não inclui**
- Tabelas dinâmicas interativas (é um mapa estático/PDF).

## Design / contrato

### Tabela manual (atual, mantém)

```json
"tabela": {"titulo": "Quantitativo (ha)", "colunas": ["Classe","Área (ha)","%"],
           "linhas": [["Veg. Nativa","2.145,30","32,8"], ["Total","6.545,56","100,0"]]}
```

### Tabela calculada (novo)

```json
"tabela": {
  "titulo": "Quantitativo por classe (ha)",
  "fonte": "quantitativos",
  "config": {
    "classes": [
      {"rotulo": "Veg. Nativa", "camada": "vegetacao"},
      {"rotulo": "Desmatada",   "camada": "auas"}
    ],
    "recorte": "area_base",       // calcula dentro do perímetro
    "percentual": true,
    "linha_total": true
  }
}
```

O renderer/generator resolve `fonte:"quantitativos"` **antes** de desenhar: interseção de cada
camada com o recorte, soma de área (m²→ha em UTM), % sobre o total, linha de total. As `linhas`
finais entram no MapSpec resolvido (auditável) e na tabela.

### Cabeçalho multinível (novo)

```json
"colunas_grupos": [
  {"titulo": "Cerrado", "sub": ["AD ha","AD %","AVN ha","AVN %","Total ha"]},
  {"titulo": "Floresta","sub": ["AD ha","AD %","AVN ha","AVN %","Total ha"]},
  {"titulo": "", "sub": ["Total ha"]}
]
```

Renderer desenha duas linhas de cabeçalho (grupo + subcolunas), como no mapa "Dinâmica 2000".

### Módulos

- `core/nexomap_quantitativos.py` (novo) — cálculo de área por classe/camada/feição via shapely
  (reaproveita `core/overlay.py` e `core/geo.py`).
- `nexomap_renderer._draw_table` — suporte a `colunas_grupos` (multinível).

## Checklist de implementação

- [ ] Estender o modelo `tabela` (fonte, config, colunas_grupos) no MapSpec.
- [ ] `core/nexomap_quantitativos.py`: área por classe dentro de um recorte (UTM, ha, %).
- [ ] Resolver `fonte:"quantitativos"`/`"sigef_sobreposicao"` no pipeline antes do render.
- [ ] Formatação BR dos números (usar `core/normalize.br`).
- [ ] `_draw_table`: cabeçalho multinível + total em negrito + larguras por coluna.
- [ ] Tool `criar_tabela` (manual ou calculada) e `editar_tabela`.
- [ ] Escrever no MapSpec resolvido as `linhas` calculadas (rastreabilidade).

## Plano de testes

**Unit (`tests/test_quantitativos.py`)**
- [ ] Área por classe bate com área conhecida (fixture: quadrado 1 km² → 100 ha).
- [ ] % soma 100% com `linha_total`.
- [ ] Recorte por `area_base` ignora feições fora do perímetro.
- [ ] Números formatados em padrão BR.

**Visual/manual**
- [ ] Reproduzir a tabela multinível (Matrícula × Cerrado/Floresta × AD/AVN) do mapa referência.

## Critérios de aceite

- IA cria tabela calculada e os números **conferem** com a geometria (não são inventados).
- Cabeçalho multinível renderiza como no padrão IMAP.
- Tabela manual continua funcionando (retrocompatível).

## Riscos e decisões abertas

- **De onde vêm as classes** (Cerrado/Floresta, AD/AVN)? De camadas WMS/WFS (plano 03), de shapes
  locais da análise, ou de uma classificação futura? v1: de camadas/shapes fornecidos.
- **Áreas grandes**: performance do overlay → simplificar geometrias antes do cálculo.

## Dependências

- Plano 03 (camadas) fornece as feições por classe.
- Plano 01 (posição) para posicionar/rediimensionar a tabela.
- Plano 00 (tools) para `criar_tabela`.
