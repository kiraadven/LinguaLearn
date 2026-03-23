// Thin wrapper around fetch – auto-attaches auth header
const BASE = ''  // same origin

function authHeaders() {
  const tok = localStorage.getItem('ll_token') || ''
  return tok ? { Authorization: 'Bearer ' + tok } : {}
}

export async function apiFetch(path, opts = {}) {
  const headers = { ...authHeaders(), ...(opts.headers || {}) }
  const res = await fetch(BASE + path, { ...opts, headers })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const d = await res.clone().json(); msg = d.detail || d.message || msg } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export async function apiPost(path, formData) {
  return apiFetch(path, { method: 'POST', body: formData })
}

export async function apiDelete(path) {
  return apiFetch(path, { method: 'DELETE' })
}

export function buildForm(obj) {
  const fd = new FormData()
  Object.entries(obj).forEach(([k, v]) => {
    if (v !== undefined && v !== null) fd.append(k, v)
  })
  return fd
}
