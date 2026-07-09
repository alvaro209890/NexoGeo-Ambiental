# Padrão visual IMAP — renderer flagship

Referência do layout "flagship" (padrão IMAP oficial do cliente) produzido pelo motor nativo
(`core/nexomap_renderer.py`). Calibrado em 2026-07-09 **contra os PDFs-modelo reais** gerados
no ArcMap (série Dinâmica, Tipologia, Embargos, Alertas — A4 paisagem). O objetivo é que um
mapa gerado pelo NexoGeo seja visualmente indistinguível do mapa feito à mão no ArcMap.

Os PDFs-modelo estão **versionados no repo** em
[`referencias/pdf_modelo_imap/`](../referencias/pdf_modelo_imap/README.md) (26 mapas, com
índice comentado) — use-os como gabarito em qualquer ajuste de layout. O modelo principal da
calibração foi `Dinamica_2026.pdf` (+ `Dinamica_2026_quantitativos.pdf` para a tabela).

O layout flagship é ativado automaticamente quando o MapSpec traz `metadados_imagem`,
`tabela` ou `marca`.

## Anatomia da página (A4 paisagem)

```
┌─────────────────────────────────────────────────────────────┐
│  52°15'0"W          [ Título em caixa branca ]   52°13'0"W   │ ← rótulos DMS + ticks
│ ┌───────────────────────────────────────────────────────┐   │
│ │                                              N▲       │   │ ← seta norte ArcMap
│ │              MAPA (satélite full-bleed)                │   │   moldura preta 2.0
│ │        lotes rotulados (branco + halo escuro)          │   │
│ │                          ┌───────────────────────────┐ │   │
│ │                          │ tabela branca, grade preta│ │   │
│ └──────────────────────────┴───────────────────────────┘─┘   │
│  [minimapa       ]  METADADOS IMAGEM   Legenda      [logo]   │ ← faixa inferior (20%)
│  [municípios IBGE]  Satélite: ...      ▭ Lote 65    IMAP     │
└─────────────────────────────────────────────────────────────┘
```

Geometria (frações da página): `map_rect=(0.022, 0.245, 0.956, 0.725)`,
faixa inferior `(0, 0, 1, 0.20)`. Template padrão: **`dinamica_a4_paisagem`**
(297×210 mm — o padrão do cliente é A4, não A3).

## Defaults do flagship (o que muda vs. layout "standard")

Tudo continua ligável/desligável por `elementos_layout` — estes são apenas os **defaults**,
escolhidos para bater com o PDF-modelo:

| Elemento | Default flagship | Observação |
|---|---|---|
| `grade` | on | Rótulos DMS `52°15'0"W` (sempre g°m's") + ticks pretos na moldura |
| `grade_linhas` | **off** | O modelo IMAP não tem linhas de grade dentro do mapa |
| `norte` | on | Seta ArcMap: triângulo dividido preto/branco + "N" com halo |
| `rosa_dos_ventos` | **off** | Liga a rosa de 8 pontas no lugar da seta |
| `escala_grafica` | **off** | O modelo não tem barra de escala |
| `creditos` | **off** | Sem rodapé "Fontes: ..." |
| `inset_tipologia` | **off** | Ligar só em mapas de Tipologia Vegetal |
| `minimapa` | on | Municípios IBGE (ver abaixo); fallback = tiles |
| `titulo_caixa` | on | Caixa branca, borda **preta** fina, topo-centro, fonte 20-22 |
| `tabela` | on | Branca, grade preta, cabeçalho + linha TOTAL em negrito |
| `metadados_imagem` | on | Bloco centralizado com acentos, sem linha de escala |
| `logo` | on | `assets/logo_imap.png` automático quando `marca.logo` ausente |

### Grade DMS

- Formato ArcMap: sempre `g°m's"H` (`52°15'0"W`, `12°33'10"S`), sem zero à esquerda.
- ~3 rótulos por eixo (`_nice_dms_step(alvo=3)`), laterais rotacionados 90°.
- Ticks pretos de 4 pt cruzando a moldura em cada rótulo.
- `grade_linhas: true` volta a desenhar as linhas tracejadas brancas (fora do padrão).

### Tabela

- Fundo branco opaco, grade preta 0.6, texto preto.
- Cabeçalho em negrito com altura 1.7× (suporta 2 linhas, ex. "Área total da\npropriedade (ha)").
- Se a primeira célula da última linha for `TOTAL`, a linha inteira sai em negrito.
- Larguras: 1ª coluna peso 2.0, 2ª peso 1.5, demais 1.0.
- Posição default: canto inferior-direito, flutuando sobre o mapa.

### METADADOS IMAGEM

Bloco centralizado na faixa inferior, rótulos em negrito e valores normais:

```
        METADADOS IMAGEM
       Satélite: PLANET
   Órbita/Ponto: Não se aplica
 Data da imagem: Maio/2026
          Datum: SIRGAS 2000 UTM 22S
```

Chaves aceitas no MapSpec: `satelite_sensor`, `orbita_ponto`, `data_aquisicao`, `datum`.

### Minimapa de localização (municípios IBGE)

`_draw_minimap_municipios()` reproduz o inset do ArcMap:

- Municípios da UF em bege (`#fdf3d7`) com contorno preto fino; o município do projeto
  em laranja (`#f59a4b`) com o nome rotulado (halo branco).
- Caixinha da UF no canto (estado em verde-claro, município em laranja, selo "MT").
- Retângulo vermelho na posição do imóvel + linha-guia vermelha até a moldura do mapa.
- **Dados:** API de malhas do IBGE v3 (`qualidade=minima&intrarregiao=municipio`),
  identificação pelo código `municipio.ibge` do projeto (fallback: contém o centroide).
- **Cache:** `~/.nexogeo/malhas/municipios_<UF>.geojson` — o download acontece uma única vez.
- **Fallback:** sem internet/sem código IBGE → minimapa antigo de tiles.

### Escalas

`NICE_SCALES` inclui 20.000/30.000/40.000 (o modelo do cliente usa ~1:22.000; antes o motor
pulava de 15.000 direto para 25.000).

## Estilos oficiais das camadas (validados contra o modelo)

| Camada | Estilo |
|---|---|
| Lote/ATP principal | contorno `#c00000`, largura 2.8, sem preenchimento, rótulo branco com halo |
| Lote secundário | contorno `#00b0f0`, largura 2.8, sem preenchimento |
| AVN | hachura `xxx` verde `#00b050`, vazada, largura 0.7 |
| AC (consolidada) | contorno magenta `#ff00ff`, vazado, largura 1.6 |
| AUAS (desmate pós-2008) | hachura `///` laranja `#ffa500`, vazada, largura 0.7 |

Na **legenda**, os lotes entram como `tipo: "poligono"` com `preenchimento: "none"` e
`largura` — o swatch sai como retângulo vazado grosso (igual ao ArcMap), não como linha.
`_legend_swatch` respeita `largura` na borda do patch.

Rótulo dos lotes: `estilo.rotulo_texto` (ex.: `"Fazenda Trevisol (Lote 65)\nMatrícula 13.533"`),
desenhado no centroide em branco com halo escuro, zorder acima das sub-áreas.

## Edição via chat (IA)

O system prompt do agente (`core/nexomap_agent.py`) conhece esses padrões. Pedidos típicos
que funcionam de ponta a ponta (validado ao vivo com DeepSeek):

- *"muda a cor da ATP para amarelo"* → `editar_camada` (linha) + `editar_legenda` + `validar_mapa`
- *"tira a tabela"* / *"liga a barra de escala"* → `alternar_elemento`
- *"título maior"* / *"move a legenda pra esquerda"* → `editar_estilo_elemento` / `mover_elemento`

Cada edição gera **nova versão** do job (`parent_job_id` + `versao`), nunca sobrescreve.

## Exemplos determinísticos

- `projetos/lauri_teste/gerar_dinamica_imap.py` — Dinâmica 2026 fiel ao PDF-modelo.
- `projetos/lauri_teste/gerar_serie_imap.py` — série (Dinâmica, Uso Consolidado, Tipologia)
  com tabela-matriz propriedade×classe calculada por overlay.

## Paridade pendente (conhecida)

- **Basemap PLANET**: hoje o fundo satélite é Esri World Imagery; com `planet_api_key`
  o fundo fica idêntico ao do cliente.
- **Tipologia Vegetal**: o modelo do cliente usa o WMS da SEMA (Radam Brasil) como fundo
  verde temático; o exemplo atual usa satélite + hachura (pedir "fundo WMS SEMA" no chat).
- Rótulos do inset `_draw_tipologia_inset` podem truncar (bug cosmético conhecido).
