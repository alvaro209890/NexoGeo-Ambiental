# PLANO_NEXOMAP_AI.md

## Resumo

NexoMap AI e o modulo de geracao cartografica por chat derivado do NexoGeo. Ele agora fica
como a aba **Mapas IA** dentro do sistema de analise, nao como aplicativo separado. O fluxo
implementado e:

`chat -> MapSpec JSON validado -> preparacao geoespacial -> PDF/PNG validado -> ponte ArcGIS para MXD quando disponivel`.

O backend ja expoe endpoints `/api/nexomap/*`, o frontend integra a aba ao projeto de analise
ativo, e os contratos ficam em `schema/`, `catalogo/`, `templates/` e `exemplos/`.

Handoff tecnico para outro agente: `docs/NEXOMAP_AGENT_HANDOFF.md`.

## Checklist de Implementacao

### M0 - Fundacao

- [x] Estrutura base preservada no repo atual
- [x] `requirements.txt` compativel com o motor geo/PDF existente
- [x] Pastas `core/`, `api/`, `ui/`, `catalogo/`, `templates/`, `exemplos/`
- [x] `secrets.example.json` sem credenciais reais
- [x] Doctor ArcGIS/API configurado

### M1 - Schema e Catalogo

- [x] Schema do projeto NexoMap em `schema/nexomap_project.schema.json`
- [x] Schema do `MapSpec` em `schema/mapspec.schema.json`
- [x] Catalogo de camadas em `catalogo/camadas.json`
- [x] Manifesto de templates MXD em `templates/mxd/MANIFEST.json`
- [x] Removida chave DeepSeek hardcoded do codigo

### M2 - Chat e IA

- [x] Endpoint `/api/nexomap/chat`
- [x] Prompt de sistema para retorno em `MapSpec`
- [x] Validador que bloqueia camadas/templates inexistentes
- [x] Fallback local deterministico quando IA nao esta configurada
- [x] Historico `chat_history.jsonl` por projeto

### M3 - Motor Geoespacial

- [x] Leitura de shapefile zipado
- [x] Reprojecao automatica via `.prj`
- [x] Area, bbox, centroide e escala sugerida
- [ ] Download/recorte real de WFS por bbox
- [x] Base para arquivos temporarios compativeis com ArcMap

### M4 - Ponte MXD/PDF

- [x] `core/arcgis_bridge.py`
- [x] JSON UTF-8 via variavel de ambiente, sem argv com caminhos acentuados
- [x] Script ArcPy em `templates/mxd/scripts/export_mxd.py`
- [x] Export PDF pelo caminho ArcGIS quando template/ArcMap existirem
- [x] Saidas em `Resultados/Mapas/<job_id>/`
- [ ] Adicionar templates `.mxd` reais

### M5 - Validacao Visual

- [x] Render PDF -> PNG com PyMuPDF
- [x] Checagem de PDF valido, tamanho minimo e pagina nao vazia
- [x] Checagem de titulo extraivel
- [x] Relatorio `validacao.json`
- [ ] Checagem visual avancada de legenda/norte/perimetro por coordenadas de tela

### M6 - Interface

- [x] Tela de projetos recentes
- [x] Aba Mapas IA dentro do app de analise
- [x] Chat principal na aba integrada
- [x] Painel `MapSpec`
- [x] Preview PNG do mapa gerado
- [x] Galeria de resultados
- [x] Tela Config/Doctor

### M7 - Testes e Release

- [x] Testes unitarios iniciais de projeto, catalogo e `MapSpec`
- [ ] Testes com fixture shapefile real
- [ ] Smoke test ArcGIS com template real
- [ ] Empacotar com PyInstaller

## Pendencias Criticas

- Adicionar templates `.mxd` reais ao manifesto para habilitar MXD verdadeiro.
- Implementar download/recorte WFS por bbox para desenhar camadas externas no render proprio.
- Rodar smoke test ArcGIS em maquina com ArcMap 10.x instalado.
