# 01 — Mover e posicionar cada elemento do mapa

## Objetivo

Permitir que a IA (e o usuário via chat) **posicione, redimensione e reordene qualquer elemento do
layout**: título, legenda, tabela, inset de tipologia, minimapa de localização, rosa-dos-ventos,
barra de escala, bloco de metadados, metadados-imagem e logo. Hoje cada peça tem posição **fixa no
código**; o alvo é torná-las **objetos posicionáveis no MapSpec**.

## Estado atual

- `core/nexomap_renderer.py` desenha cada peça em retângulos fixos (`map_rect`, `panel_rect`,
  `band_rect`) e âncoras cravadas dentro de `_flagship_furniture` / `_standard_furniture`.
- `elementos_layout` só liga/desliga (booleano). **Não há posição/tamanho por elemento.**

## Escopo

**Inclui**
- Modelo de **posicionamento por elemento** no MapSpec (`layout.elementos[]`).
- Renderer lê posição/tamanho/âncora e desenha ali (com defaults = layout atual).
- Tool `mover_elemento` e `editar_estilo_elemento` (plano 00).
- Detecção de sobreposição continua no validador (plano 06).

**Não inclui**
- Editor visual drag-and-drop na UI (fica como evolução; a UI envia comandos de texto/tool).

## Design / contrato

### Modelo de posição (page-fraction + âncora)

Cada elemento posicionável ganha um objeto:

```json
"layout": {
  "elementos": {
    "titulo":            {"ancora": "top-right",    "x": 0.985, "y": 0.985, "largura": 0.30},
    "legenda":           {"ancora": "bottom-right", "x": 0.80,  "y": 0.02,  "largura": 0.28},
    "tabela":            {"ancora": "in-map-bottom-right", "x": 0.99, "y": 0.02, "largura": 0.46},
    "inset_tipologia":   {"ancora": "top-left",     "x": 0.01,  "y": 0.99,  "largura": 0.20},
    "minimapa":          {"ancora": "bottom-left",  "x": 0.02,  "y": 0.02,  "largura": 0.11},
    "rosa_dos_ventos":   {"ancora": "top-right",    "x": 0.99,  "y": 0.99,  "largura": 0.045},
    "escala":            {"ancora": "bottom-left",  "x": 0.035, "y": 0.035},
    "metadados_imagem":  {"ancora": "bottom-center","x": 0.31,  "y": 0.02,  "largura": 0.24},
    "logo":              {"ancora": "bottom-right", "x": 0.98,  "y": 0.02,  "largura": 0.12}
  }
}
```

- **Coordenadas** em fração da página `[0..1]` (origem inferior-esquerda), + `ancora` para o ponto de
  referência do elemento. Alternativa aceitável: `ancora` + `offset_mm`.
- **`in-map-*`**: âncora relativa ao quadro do mapa (para tabela/insets flutuantes sobre a imagem).
- **Defaults**: quando ausente, usa a posição atual do layout (retrocompatível — nada quebra).
- **`z`** opcional para ordem de empilhamento entre elementos flutuantes.

### Elementos posicionáveis (ids canônicos)

`titulo`, `subtitulo`(segue o título), `legenda`, `tabela`, `inset_tipologia`, `minimapa`,
`rosa_dos_ventos`, `escala`, `grade`(sem posição), `metadados`, `metadados_imagem`, `logo`,
`creditos`, `rotulos`(seguem feições).

### Renderer

- Criar `core/nexomap_layout.py` com `resolve_rect(ancora, x, y, largura, altura, page, map_rect)`
  → converte para retângulo `fig.add_axes`.
- `_flagship_furniture`/`_standard_furniture` passam a **ler `spec.layout.elementos[id]`** com
  fallback para os defaults atuais.
- Manter `elementos_layout` (visibilidade) ortogonal a `layout.elementos` (posição/tamanho).

## Checklist de implementação

- [x] Adicionar `layout.elementos{}` ao `MapSpec` (dataclass + `to_dict`/`from_dict`), opcional. (2026-07-08)
- [x] `core/nexomap_layout.py`: âncoras (`top-left`…`bottom-right`, `*-center`, `in-map-*`) → rect. (2026-07-08)
- [x] Refatorar as peças do renderer para consultar `layout.elementos[id]` com defaults atuais. (2026-07-08)
- [ ] Tool `mover_elemento(elemento, posicao, tamanho?)` (plano 00) escreve em `layout.elementos`.
- [ ] Tool `editar_estilo_elemento(elemento, props)` (fonte, cor, fundo, borda). *(renderer já lê `titulo.estilo {fundo,cor,tamanho}` — caixa branca IMAP)*
- [x] Clamping: manter elemento dentro da página; avisar se sair. (2026-07-08)
- [x] Documentar ids e âncoras no prompt do sistema (`nexomap_ai._system_prompt`). (2026-07-08)

## Plano de testes

**Unit (`tests/test_layout.py`)**
- [x] `resolve_rect` para cada âncora devolve retângulo esperado. (2026-07-08)
- [x] MapSpec sem `layout` renderiza idêntico ao atual (retrocompatível). (2026-07-08)
- [x] Mover legenda de `bottom-right` para `bottom-left` muda o rect e não sobrepõe o logo. (2026-07-08)

**Visual/manual**
- [ ] Gerar o flagship, mover título para `top-left`, conferir PNG.
- [ ] Mover tabela para fora do mapa (faixa) e conferir que não corta.

**Validação (plano 06)**
- [ ] `sem_sobreposicao_elementos` continua passando após mover; falha proposital quando encostam.

## Critérios de aceite

- A IA consegue reposicionar qualquer elemento por instrução ("mova a legenda para o rodapé").
- Sem `layout`, o resultado é idêntico ao layout IMAP atual.
- Validação detecta sobreposição introduzida por um mau posicionamento.

## Riscos e decisões abertas

- **Sistema de coordenadas**: page-fraction+âncora (recomendado) vs mm absolutos. Decidir e fixar.
- **Colisão**: auto-empurrar elementos que colidem, ou apenas avisar? v1 = avisar (plano 06).

## Dependências

- Plano 00 (tools) usa este modelo em `mover_elemento`.
- Plano 06 (validação) checa sobreposição/corte após reposicionamento.
