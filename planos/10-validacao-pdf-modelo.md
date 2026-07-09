# 10 — Validação com PDFs de referência (modelo IMAP)

## Objetivo

Usar os **24 mapas reais do IMAP** em `referencias/Mapas_unidos.pdf` como **gabarito visual**
para validar automaticamente os mapas gerados pelo NexoGeo. Extrair métricas de estilo
(cor, posição, fonte, espaçamento) e comparar com a saída.

## Estado atual

- `referencias/Mapas_unidos.pdf`: 24 mapas IMAP reais (commitado)
- `templates/mxd/*.mxd`: 4 arquivos ArcMap legacy com simbologia (LOCAIS, gitignored, têm credenciais)
- Validação atual (`validacao.json`): checks básicos (PDF existe, não vazio, sem sobreposição)
- Renderer já produz PDFs no padrão IMAP (título branco centro, faixa inferior)

## Abordagem

### Fase 1 — Extrair padrões do PDF-modelo

Usar `pymupdf` (fitz) ou `pdfplumber` para extrair:
- Posição do título (x, y, largura, altura) em cada página
- Cores dominantes (título, legenda, faixa inferior)
- Tamanhos de fonte
- Presença e posição de: minimapa, metadados, legenda, logo, escala, norte
- Proporções dos elementos (faixa inferior ~13.5% da altura)

Gerar um **perfil de estilo** (`referencias/perfil_imap.json`) com as métricas extraídas.

### Fase 2 — Validar mapa gerado contra o perfil

Nova função `validar_contra_modelo(pdf_path, perfil)` que compara:
- [ ] Título na posição esperada (centro-topo, ±5% de tolerância)
- [ ] Faixa inferior presente (se flagship mode)
- [ ] Cores do título dentro da paleta IMAP (branco, #111827)
- [ ] Elementos obrigatórios presentes (escala, norte)
- [ ] Sem texto cortado ou sobreposição
- [ ] Resolução mínima (300 DPI equivalente)

### Fase 3 — Integrar na IA

- Tool `validar_mapa` (plano 09) usa esta validação
- Auto-correção: se falhar, IA ajusta e re-valida

## Checklist

- [x] Instalar pymupdf no venv (PyMuPDF 1.28.0)
- [x] Script `scripts/extrair_perfil_imap.py`: lê Mapas_unidos.pdf, extrai métricas
- [x] Gerar `referencias/perfil_imap.json` com médias e tolerâncias (24 páginas)
- [x] `core/nexomap_validation.py`: função `validar_contra_modelo(pdf, perfil)`
- [x] Integrar no pipeline de geração (pós-render → `validacao.json > conformidade_modelo`)
- [ ] Tool `validar_mapa` usa o resultado (plano 09)
- [x] Testes com mapa gerado vs perfil (`tests/test_validacao_modelo.py`, 6 testes)
- [x] Documentar o perfil extraído (ver abaixo)

## Perfil extraído (2026-07-09) — `referencias/perfil_imap.json`

Métricas médias dos 24 mapas IMAP reais (posições em fração da página, origem topo-esquerda):

| Elemento | Métrica | Valor | Presente em |
|----------|---------|-------|-------------|
| Página | aspect | 1.413 (A4 paisagem) | 24/24 |
| Título | fonte / cor | Tahoma-Bold / #000000 | 24/24 |
| Título | size · cx · y0 | ~24.9 · 0.480 · 0.017 | 24/24 |
| Norte | cx · cy | 0.957 · 0.077 (topo-direita) | 23/24 |
| Legenda | cx · y0 | 0.612 · 0.807 (faixa) | 24/24 |
| Metadados | cx · y0 | 0.398 · 0.798 (faixa) | 24/24 |
| Faixa inferior | y0 (topo) | 0.788 | — |

### Como `validar_contra_modelo` classifica os checks

- **HARD** (estrutura IMAP, reprovam): `aspecto_pagina`, `titulo_presente`, `titulo_no_topo`,
  `titulo_centralizado`, `legenda_presente`, `legenda_no_rodape`.
- **SOFT** (estilo, só informam): `titulo_tamanho`, `titulo_cor_escura`, `titulo_fonte`,
  `norte_presente`, `metadados_presente`.

Um mapa em modo **flagship** (faixa inferior — quando o MapSpec traz `metadados_imagem`/`tabela`/`marca`)
passa todos os checks HARD. Um mapa em **painel-direito** reprova `legenda_no_rodape` (correto: não
segue a faixa inferior IMAP). Regenerar o perfil: `.venv/bin/python scripts/extrair_perfil_imap.py`.

### Gaps de estilo detectados (soft) — candidatos ao renderer / plano 09

- **Título menor** que o modelo (native ~16-17pt vs IMAP ~25pt) → aumentar fonte do título.
- **Norte não detectado por texto**: matplotlib desenha a seta como vetor, não como fonte
  ESRINorth → validação por texto sempre soft-falha; futuro = detectar por região desenhada.
- **Fonte do título** DejaVuSans-Bold (nativo) vs Tahoma-Bold (modelo) — esperado, não bloqueia.

## Dependências

- `pip install pymupdf` (já pode estar no venv)
- `referencias/Mapas_unidos.pdf` (já no repo)
- Plano 06 (validação QA) — estender com validação visual
- Plano 09 (mais tools) — tool `validar_mapa`
