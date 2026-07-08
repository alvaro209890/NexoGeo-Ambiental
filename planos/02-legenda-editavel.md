# 02 — Legenda editável

## Objetivo

Tornar a **legenda um objeto de primeira classe no MapSpec**, totalmente editável pela IA: título
da legenda, itens (rótulo + símbolo), ordem, agrupamento, número de colunas, posição e estilo.
Hoje a legenda é **derivada automaticamente** das camadas e não pode ser ajustada finamente.

## Estado atual

- `nexomap_renderer.py` monta `legend_entries` a partir das camadas desenhadas (Patch/Line2D) e do
  perímetro, com rótulo = `layer.nome + (contagem)`. Posição fixa (painel ou faixa).
- O usuário **não** consegue: renomear um item, reordenar, esconder um item, mudar o símbolo, o
  título "Legenda", nem o nº de colunas.

## Escopo

**Inclui**
- Bloco `legenda` no MapSpec com itens explícitos e estilo.
- Renderer usa a `legenda` do MapSpec quando presente; senão, gera automática (atual).
- Tool `editar_legenda` (plano 00).

**Não inclui**
- Legenda com gráficos/escala de cores contínua (evolução futura).

## Design / contrato

```json
"legenda": {
  "titulo": "LEGENDA",
  "posicao": {"ancora": "bottom-right", "x": 0.80, "y": 0.02},
  "colunas": 1,
  "fonte_tamanho": 8,
  "itens": [
    {"rotulo": "Área total da propriedade", "tipo": "linha", "cor": "#ff2d00", "largura": 2.4},
    {"rotulo": "Área de Vegetação Nativa (AVN)", "tipo": "poligono", "cor": "#1a7d1a",
     "preenchimento": "none", "hachura": "----"},
    {"rotulo": "Área desmatada (AD)", "tipo": "poligono", "cor": "#e0b400", "hachura": "////"},
    {"rotulo": "CAR", "tipo": "poligono", "cor": "#1d4ed8", "opacidade": 0.2, "camada": "car_sema"}
  ]
}
```

- **`tipo`**: `linha` | `poligono` | `ponto` | `imagem`(swatch de raster).
- **`camada`** (opcional): vincula o item a uma camada do MapSpec — permite "auto-preencher" o
  símbolo a partir do estilo da camada e manter contagem de feições.
- **Modos**: `auto` (deriva das camadas, comportamento atual) vs `manual` (usa `itens`) vs `misto`
  (auto + overrides por `camada`). Campo `legenda.modo` decide; default `auto`.
- **Posição/tamanho**: reaproveita o modelo do plano 01.

## Checklist de implementação

- [ ] Adicionar `legenda{}` ao MapSpec (dataclass + serialização), opcional.
- [ ] `nexomap_renderer`: função `_montar_legenda(spec, drawn_layers)` que resolve `auto`/`manual`/`misto`.
- [ ] Suporte a `tipo` linha/polígono/ponto/imagem nos swatches (Patch/Line2D/marker/mini-imshow).
- [ ] Respeitar `colunas`, `titulo`, `fonte_tamanho`, `posicao`.
- [ ] Tool `editar_legenda` (adicionar/remover/renomear/reordenar item, mudar título/colunas/posição).
- [ ] Vincular item↔camada (`camada`) e auto-símbolo a partir do estilo da camada.
- [ ] Documentar no prompt do sistema como editar a legenda.

## Plano de testes

**Unit (`tests/test_legenda.py`)**
- [ ] `modo:auto` reproduz a legenda atual (baseline).
- [ ] `modo:manual` respeita itens/ordem/rótulos.
- [ ] Renomear item via `editar_legenda` altera só aquele rótulo.
- [ ] Remover item some da legenda mas mantém a camada no mapa.

**Visual/manual**
- [ ] Gerar flagship, renomear "Area desmatada (AUAS)" → "Desmatamento" e reordenar; conferir PNG.

## Critérios de aceite

- IA edita título, itens, ordem, colunas e posição da legenda por instrução.
- Sem bloco `legenda`, a legenda automática atual é preservada.
- Itens vinculados a camadas refletem o estilo/contagem corretos.

## Riscos e decisões abertas

- **Sincronismo item↔camada**: ao remover uma camada, remover item vinculado? v1: avisar e manter.
- **Símbolo de hachura** na legenda deve casar exatamente com o do mapa (mesmo `hatch`/cor).

## Dependências

- Plano 01 (posição) para `legenda.posicao`.
- Plano 00 (tools) para `editar_legenda`.
- Plano 03 (camadas) para itens vinculados a camadas WMS/WFS.
