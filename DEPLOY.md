# Reconciliation Exception Agent — Production Deployment

Same deployment pattern as the FinOps reference: a Dockerized FastAPI backend + a bundled
nginx, sitting behind the server's **system (edge) nginx** on `:7777` under a path prefix.
The frontend is a static site on Cloudflare Pages.

```
Frontend (React/Vite)  ──►  Cloudflare Pages
                            https://reconciliation-agent-arttechgroup.pages.dev/

Browser ──https──► edge nginx :7777 ──/reconciliation-agent/──► 127.0.0.1:4775 ──► backend:8000
        (TLS here)                     (prefix stripped)        (bundled nginx)    (uvicorn)
```

- **Backend API base (public):** `https://ai.arttechgroup.com:7777/reconciliation-agent/api`
- **Bundled stack host port:** `127.0.0.1:4775` (the edge's upstream target)
- **Lyzr key** lives only in `backend/.env`, never in the frontend bundle.

---

## Part A — Backend (Docker, on `ai.arttechgroup.com`)

### Prerequisites
- Docker + Docker Compose v2.
- `backend/.env` populated (gitignored, injected at runtime — never baked into the image):
  ```bash
  cp backend/.env.example backend/.env
  # then set LYZR_API_KEY and LYZR_AGENT_ID (CORS_ALLOWED_ORIGINS is already pre-filled)
  ```
  Without a configured agent the dashboard shows the deterministic numbers and *where* the
  differences are, but not the classification / narrative / routing (by design — no stub fallback).

### Deploy
```bash
bash /var/www/apps/reconciliation-agent/deploy.sh   # git pull + compose up --build + nginx reload
```
Manual equivalent:
```bash
docker compose up -d --build
docker compose ps
docker compose logs -f
docker compose down
```

### Edge (system) nginx wiring — once
Add the block from [deploy/nginx/system-reconciliation-agent.conf](deploy/nginx/system-reconciliation-agent.conf)
to the edge `server { listen 7777 ssl ...; }` on `ai.arttechgroup.com`, then:
```bash
sudo nginx -t && sudo systemctl reload nginx
```
It strips `/reconciliation-agent/` and forwards to `127.0.0.1:4775` (the bundled nginx, which
serves `/api/*` and `/` at its root — see [deploy/nginx/reconciliation.conf](deploy/nginx/reconciliation.conf)).

### Smoke test
```bash
# Direct to the bundled nginx (prefix already stripped):
curl http://127.0.0.1:4775/                 # -> {"ok":true,...,"lyzr_configured":true}
curl http://127.0.0.1:4775/api/files        # -> the day's files JSON

# Through the edge (the real public path the frontend uses):
curl https://ai.arttechgroup.com:7777/reconciliation-agent/          # -> health JSON
curl https://ai.arttechgroup.com:7777/reconciliation-agent/api/files # -> 200
```

### Configuration (`docker-compose.yml` `environment:`)
| Var | Value | Purpose |
|-----|-------|---------|
| `DATA_DIR` | `/app/data` | container path for the generated dataset (volume-mounted) |
| `AUTO_REGEN` | `1` | regenerate the synthetic dataset for "today" on startup |
| `CORS_ALLOWED_ORIGINS` | the Pages URL | allow the Cloudflare frontend to call the API cross-origin |

`backend/.env` adds the secrets (`LYZR_API_KEY`, `LYZR_AGENT_ID`, …) and is read via `env_file`;
the `environment:` block above overrides any conflicting key (e.g. the Windows `DATA_DIR`).

---

## Part B — Frontend (Cloudflare Pages)

Build base lives in [frontend/.env.production](frontend/.env.production):
```
VITE_API_BASE_URL=https://ai.arttechgroup.com:7777/reconciliation-agent
```
`api.js` appends `/api`, so requests go to `…/reconciliation-agent/api/*`. In local dev this var
is unset, so `api.js` falls back to `/api` and Vite proxies to `http://localhost:8000` (unchanged).

```bash
npm --prefix frontend install
npm --prefix frontend run build      # outputs frontend/dist (uses .env.production)
# deploy frontend/dist to Cloudflare Pages (dashboard upload, or):
npx wrangler pages deploy frontend/dist --project-name reconciliation-agent-arttechgroup
```

> The backend URL is compiled into the static bundle — change `VITE_API_BASE_URL`, **rebuild**, and
> redeploy if the URL/port/prefix moves.

## Gotchas
- **CORS origin must match exactly.** `CORS_ALLOWED_ORIGINS` (backend) must equal the Pages origin.
- **Prefix must match in three places.** The edge nginx `location` prefix, the `/reconciliation-agent`
  segment of `VITE_API_BASE_URL`, and the rewrite rule must all be the same string.
- **Single worker.** The app regenerates dataset files on startup / first request of a new day;
  one uvicorn worker avoids write races. Fine for a demo's traffic.
- **TLS.** The container serves plain HTTP on `127.0.0.1:4775`; TLS terminates at the edge nginx
  (`listen 7777 ssl`). Both ends of the browser↔backend path are HTTPS, so no mixed content.
