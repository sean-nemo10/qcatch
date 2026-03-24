// ── BroadcastChannel setup ────────────────────────────────────────────
export const _tabId = Math.random().toString(36).slice(2);
export const _bc = ('BroadcastChannel' in window) ? new BroadcastChannel('qcatch_sync') : null;

if (_bc) {
  _bc.onmessage = (e) => {
    if (e.data.source === _tabId) return;  // 自タブのエコーは無視
    if (e.data.type === 'data_changed') {
      // Use window.X to avoid circular imports with nav.js
      if (typeof window.updateBadges === 'function') window.updateBadges();
      if (typeof window.reloadActivePane === 'function') window.reloadActivePane();
    }
  };
}

export function _bcBroadcast(method) {
  if (_bc && ['POST','PATCH','DELETE'].includes(method)) {
    _bc.postMessage({type: 'data_changed', source: _tabId});
  }
}

// ── API helper ────────────────────────────────────────────────────────
export async function api(method, path, body) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({detail: res.statusText}));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) { _bcBroadcast(method); return null; }
  const data = await res.json();
  _bcBroadcast(method);
  return data;
}
