# Deploy — NexoGeo Ambiental (web)

Arquitetura da versao web:

```
Navegador (Vercel)  ──HTTPS──>  Cloudflare Tunnel  ──>  uvicorn 127.0.0.1:8000
https://ui-kappa-eight-82.vercel.app     nexogeo-api.cursar.space        (esta maquina)
```

- **Frontend**: Vite/React na Vercel (projeto `ui`). Env `VITE_API_URL=https://nexogeo-api.cursar.space`.
  Domínio público: `https://ui-kappa-eight-82.vercel.app`.
  Build: `cd ui && VITE_API_URL=https://nexogeo-api.cursar.space npm run build`; deploy `npx vercel --prod`.
- **Backend**: FastAPI/uvicorn na porta 8000 (CORS `*`), exposto pelo Cloudflare Tunnel.

## Persistencia (correcao do "load failed")

O "load failed" acontecia porque (a) o backend rodava manualmente e caia quando a sessao
terminava, e (b) o conector do tunnel usava um **ingress remoto** sem a rota `nexogeo-api`,
enquanto o `saldopro-config.yml` local tinha a rota — conectores divergentes no mesmo tunnel
davam 404 intermitente. Correcao:

### 1. Backend como servico systemd (persistente, auto-restart)

```bash
cp deploy/nexogeo-backend.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nexogeo-backend.service
loginctl enable-linger "$USER"     # sobrevive a logout
systemctl --user status nexogeo-backend.service
```

### 2. Tunnel usando o ingress LOCAL (que inclui nexogeo-api -> :8000)

O `~/.config/systemd/user/saldopro-cloudflared.service` deve rodar o tunnel pelo **UUID**
(usa o ingress do `saldopro-config.yml`), nao pelo nome (que puxa ingress remoto):

```
ExecStart=/usr/local/bin/cloudflared tunnel --config /home/acer/.cloudflared/saldopro-config.yml run 0a219227-e2a4-424c-8cd0-2b90a77ba877
```

`~/.cloudflared/saldopro-config.yml` (ingress; nexogeo-api e a ultima rota util):

```yaml
tunnel: 0a219227-e2a4-424c-8cd0-2b90a77ba877
credentials-file: /home/acer/.cloudflared/0a219227-...json
ingress:
  - hostname: saldopro-api.cursar.space   { service: http://127.0.0.1:10000 }
  - hostname: saldopro.cursar.space        { service: http://127.0.0.1:5173 }
  - hostname: saldopro-admin.cursar.space  { service: http://127.0.0.1:5174 }
  - hostname: nexogeo-api.cursar.space     { service: http://127.0.0.1:8000 }
  - service: http_status:404
```

```bash
systemctl --user daemon-reload && systemctl --user restart saldopro-cloudflared.service
curl -s https://nexogeo-api.cursar.space/api/health     # -> {"ok":true}
```

## Checagem rapida

```bash
systemctl --user is-active nexogeo-backend.service saldopro-cloudflared.service
curl -s https://nexogeo-api.cursar.space/api/nexomap/modelos | head -c 80
```
