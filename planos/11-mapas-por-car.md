# 11 — Mapas por CAR (cards de modelo + busca no SIMCAR digital)

## Objetivo

Fluxo web direto: o usuario escolhe um **modelo de mapa** (card) e informa o
**numero do CAR estadual**; o sistema busca a propriedade (ATP) no WFS da SEMA,
**cruza** com as camadas do **SIMCAR digital** (uso consolidado, tipologia, APP,
ARL, AVN, AUAS...) e monta o mapa no padrao IMAP — sem precisar de shapefile.

## Implementado (2026-07-09)

### Backend
- `core/nexomap_car.py` — `buscar_car(numero, secrets)`: consulta `Geoportal:CAR_ATP`
  por `NUMEROESTADUAL` (ex. `MT313839/2025`) ou `CAR_FEDERAL` (SICAR) via CQL_FILTER;
  devolve poligono + `AREA_HA`/`NOMEPROPRIEDADE`/`SITUACAO_CAR`. `escrever_area_zip`
  grava a ATP como shapefile-zip (area_base). `utm_epsg_from_bbox` -> 31981 (21S) / 31982 (22S).
- Catalogo: camadas SIMCAR digital novas em `catalogo/camadas.json` —
  `uso_consolidado` (Geoportal:USO_CONSOLIDADO), `area_consolidada_simcar`,
  `simcar_avn/app/arl/auas/nascente`, `areas_uso_restrito`.
- `catalogo/modelos_mapas.json` + `core/nexomap_modelos.py` — 7 modelos derivados dos
  24 mapas IMAP reais: **car, uso_consolidado, tipologia, dinamica, embargos, alertas,
  areas_protegidas**. `aplicar_modelo` monta um MapSpec flagship (faixa inferior IMAP)
  com camadas do catalogo, estilos (hachuras/opacidade) e tabela de quantitativos.
- `core/nexomap_generator.py` — `gerar_mapa_por_car(numero, modelo)` e `_stream`:
  busca CAR -> area_base -> aplica modelo -> `_run_pipeline` (recorta camadas na ATP +
  quantitativos por overlay = o "cruzamento") -> render + conformidade IMAP.
- Projeto scaffold `projetos/car_web/projeto.json` (paths relativos ao repo; secrets
  da raiz). Zips gerados em `projetos/*/Shapes/*.zip` (gitignored).
- API: `GET /api/nexomap/modelos` (lista cards) e `POST /api/nexomap/car-mapa` (SSE).

### Frontend
- `ui/src/CarMapaView.jsx` — grade de cards (icone/categoria/descricao), campo do CAR,
  geracao via SSE, previa do mapa, badge "Conforme IMAP", download do PDF e tabela de
  quantitativos. Acessivel no lobby ("Mapa por CAR").
- `API = import.meta.env.VITE_API_URL || ''` em `App.jsx`/`ChatView.jsx` (Vercel aponta
  para o tunnel `https://nexogeo-api.cursar.space`; dev usa o proxy do vite).

### Correcao de layout
- `_layout_report` (renderer) nao marca mais rotulos de grade UTM/DMS como "texto
  cortado" (falso-positivo no layout full-bleed flagship) — `_e_rotulo_grade`.

## Testes
- Offline: `tests/test_car_modelos.py` (detec. de formato, escrita de shapefile,
  aplicar_modelo x 7, camadas do catalogo). Suite: **114 passando + 8 skipped**.
- Rede (opt-in `NEXO_NET=1`): `tests/net/test_car_net.py` (busca estadual ao vivo).
  Validado ao vivo: CAR `MT313839/2025` -> Fazenda Boa Vista V (253,97 ha), modelos
  `car`/`tipologia` gerados com camadas recortadas + quantitativos, conformidade IMAP ok.

## Ajustes 2026-07-09 (2ª rodada)

- **Cadastro/login vem ANTES dos mapas**: `ui/src/AuthScreen.jsx` + `ui/src/auth.js`
  (localStorage `nexogeo_auth`); `App.jsx` bloqueia tudo até autenticar. Logout no lobby e no
  CarMapaView. ChatView reusa a mesma sessão (mesma chave) — sem duplo login.
- **"Load failed" corrigido (raiz = infra)**:
  1. Backend virou serviço systemd persistente (`deploy/nexogeo-backend.service`, `Restart=always`,
     `loginctl enable-linger`) — antes rodava manual e caía ao fim da sessão.
  2. Tunnel: `saldopro-cloudflared.service` passou a rodar pelo **UUID** (usa o ingress LOCAL do
     `saldopro-config.yml`, que tem `nexogeo-api -> :8000`); antes rodava pelo nome e usava ingress
     remoto SEM a rota → 404 intermitente / round-robin entre conectores divergentes.
  Ver `deploy/README.md`. Validado: 6/6 `200` via tunnel; saldopro inalterado.
- **UX resiliente**: CarMapaView mostra erro amigável + "Tentar novamente" ao falhar o fetch dos
  modelos; `authError()` traduz "Load failed"/"Failed to fetch" para PT.

## Ajustes 2026-07-09 (3ª rodada)

- **Busca da ATP no requerimento do SIMCAR**: `buscar_car` agora consulta `CAR_ATP` (validado) E
  `MVW_REQUERIMENTO_ATP` (requerimento — campo federal e `CODIGO_CAR_FEDERAL`, situacao `SITUACAO`).
  Muitos CARs recentes so existem como requerimento. Resultado traz `origem` (car_digital|requerimento),
  exibido no front.
- **Fix "nao conectou no servidor"**: o render bloqueava o SSE por 30-90s sem enviar bytes → o
  Cloudflare cortava a conexao ociosa (~100s). Agora `gerar_mapa_por_car_stream` roda o render numa
  thread e emite **heartbeats** a cada 4s (`stage=renderizando`, com segundos decorridos); teto de 240s.
  Front mostra "Cruzando camadas e montando o mapa… (Ns)". Validado: modelo `car`+basemap via tunnel,
  4 heartbeats, `ok:True`.

## Proximos passos
- Tipologia por **classe de vegetacao** (atributo), nao a camada inteira como 1 classe.
- Cache da ATP por numero de CAR; desambiguacao quando ha >1 registro (PRA antigo + atual).
- Basemap Planet/satelite full-bleed (plano 08) para casar 100% com o gabarito IMAP.
- Tool `aplicar_modelo` na IA (chat) reusando `nexomap_modelos`.
