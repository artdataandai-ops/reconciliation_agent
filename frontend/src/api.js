// Dev: VITE_API_BASE_URL unset → '/api', proxied to FastAPI :8000 (see vite.config.js).
// Prod build: VITE_API_BASE_URL (frontend/.env.production) points at the backend behind the
// edge nginx, e.g. https://ai.arttechgroup.com:7777/reconciliation-agent → calls
// https://ai.arttechgroup.com:7777/reconciliation-agent/api/* (baked in at build time).
const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '') + '/api'

async function j(path, opts) {
  const r = await fetch(`${BASE}${path}`, opts)
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json()
}

export const getFiles = () => j('/files')
export const getActivity = () => j('/activity')
export const getPreview = (name) => j(`/file/${encodeURIComponent(name)}/preview`)
export const runReconcile = () => j('/reconcile', { method: 'POST' })
