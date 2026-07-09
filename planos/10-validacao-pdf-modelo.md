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

- [ ] Instalar pymupdf no venv
- [ ] Script `scripts/extrair_perfil_imap.py`: lê Mapas_unidos.pdf, extrai métricas
- [ ] Gerar `referencias/perfil_imap.json` com médias e tolerâncias
- [ ] `core/nexomap_validacao.py`: função `validar_contra_modelo(pdf, perfil)`
- [ ] Integrar no pipeline de geração (pós-render)
- [ ] Tool `validar_mapa` usa o resultado
- [ ] Testes com mapa gerado vs perfil
- [ ] Documentar o perfil extraído

## Dependências

- `pip install pymupdf` (já pode estar no venv)
- `referencias/Mapas_unidos.pdf` (já no repo)
- Plano 06 (validação QA) — estender com validação visual
- Plano 09 (mais tools) — tool `validar_mapa`
