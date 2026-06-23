const BASE = '/api'

async function j(path, opts) {
  const r = await fetch(`${BASE}${path}`, opts)
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json()
}

export const getFiles = () => j('/files')
export const getPreview = (name) => j(`/file/${encodeURIComponent(name)}/preview`)
export const runReconcile = () => j('/reconcile', { method: 'POST' })
