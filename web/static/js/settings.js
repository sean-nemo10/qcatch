import { api } from './api.js';
import { esc } from './utils.js';

// ── API key ───────────────────────────────────────────────────────────
export function getApiKey() {
  return localStorage.getItem('qcatch_api_key') || '';
}
window.getApiKey = getApiKey;

export function loadApiKeyToChat() {
  const hint = document.getElementById('chat-key-hint');
  if (!hint) return;
  const key = localStorage.getItem('qcatch_api_key') || '';
  hint.textContent = key ? '🔑 API キー設定済み' : '⚠️ APIキー未設定（設定タブで登録してください）';
  hint.style.color = key ? '#4caf50' : '#ff9800';
}
window.loadApiKeyToChat = loadApiKeyToChat;

export function saveApiKey() {
  const val = document.getElementById('settings-api-key').value.trim();
  if (!val) return;
  localStorage.setItem('qcatch_api_key', val);
  window.showStatus('API キーを保存しました', 'success', 2000);
  loadApiKeyToChat();
}
window.saveApiKey = saveApiKey;

export function clearApiKey() {
  localStorage.removeItem('qcatch_api_key');
  document.getElementById('settings-api-key').value = '';
  const chatKey = document.getElementById('chat-api-key');
  if (chatKey) chatKey.value = '';
  window.showStatus('API キーを削除しました', 'info', 2000);
}
window.clearApiKey = clearApiKey;

// ── Settings load ─────────────────────────────────────────────────────
export async function loadSettings() {
  const cfg = await api('GET', '/api/config');
  document.getElementById('cfg-backend').value = cfg.sort_backend || 'auto';
  document.getElementById('cfg-ollama-model').value = cfg.ollama_model || '';
  document.getElementById('cfg-ollama-host').value = cfg.ollama_host || '';
  const saved = localStorage.getItem('qcatch_api_key') || '';
  document.getElementById('settings-api-key').value = saved;
  const intervalSel = document.getElementById('sync-interval');
  if (intervalSel && cfg.sync_interval_minutes != null) {
    intervalSel.value = String(cfg.sync_interval_minutes);
  }
  checkGoogleAuthStatus();
}
window.loadSettings = loadSettings;

export async function saveConfig() {
  const body = {
    sort_backend: document.getElementById('cfg-backend').value,
    ollama_model: document.getElementById('cfg-ollama-model').value,
    ollama_host: document.getElementById('cfg-ollama-host').value,
  };
  try {
    await api('POST', '/api/config', body);
    window.showStatus('設定を保存しました', 'success', 2000);
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.saveConfig = saveConfig;

// ── Google integration ────────────────────────────────────────────────
export async function checkGoogleAuthStatus() {
  try {
    const data = await api('GET', '/api/auth/status');
    const indicator = document.getElementById('google-auth-indicator');
    const label = document.getElementById('google-auth-label');
    const loginBtn = document.getElementById('google-login-btn');
    const syncBtn = document.getElementById('google-sync-btn');
    const pushBtn = document.getElementById('google-push-btn');
    const pullBtn = document.getElementById('google-pull-btn');
    const logoutBtn = document.getElementById('google-logout-btn');
    if (data.authenticated) {
      indicator.textContent = '✅';
      label.textContent = 'Google に接続済み';
      label.style.color = '#4caf50';
      loginBtn.style.display = 'none';
      syncBtn.style.display = '';
      pushBtn.style.display = '';
      pullBtn.style.display = '';
      logoutBtn.style.display = '';
      document.getElementById('google-autosync-section').style.display = 'flex';
      loadTasklistMapUI();
    } else if (!data.has_client_secrets) {
      indicator.textContent = '⚠️';
      label.textContent = 'client_secret.json が見つかりません';
      label.style.color = '#ff9800';
      loginBtn.style.display = 'none';
      syncBtn.style.display = 'none';
      pushBtn.style.display = 'none';
      pullBtn.style.display = 'none';
      logoutBtn.style.display = 'none';
    } else {
      indicator.textContent = '🔒';
      label.textContent = '未接続';
      label.style.color = 'var(--text-dim)';
      loginBtn.style.display = '';
      syncBtn.style.display = 'none';
      pushBtn.style.display = 'none';
      pullBtn.style.display = 'none';
      logoutBtn.style.display = 'none';
    }
  } catch(e) {
    document.getElementById('google-auth-label').textContent = 'ステータス取得失敗';
  }
}
window.checkGoogleAuthStatus = checkGoogleAuthStatus;

export async function runGoogleSync() {
  const log = document.getElementById('google-sync-log');
  log.textContent = '同期中…';
  try {
    const res = await api('POST', '/api/sync');
    log.textContent = `✓ Push: ${res.pushed} 件 / Pull: ${res.pulled} 件`;
  } catch(e) {
    log.textContent = 'エラー: ' + e.message;
  }
}
window.runGoogleSync = runGoogleSync;

export async function runGooglePush() {
  const log = document.getElementById('google-sync-log');
  log.textContent = 'Push 中…';
  try {
    const res = await api('POST', '/api/sync/push');
    log.textContent = `✓ ${res.pushed} 件を Google に送信しました`;
  } catch(e) {
    log.textContent = 'エラー: ' + e.message;
  }
}
window.runGooglePush = runGooglePush;

export async function runGooglePull() {
  const log = document.getElementById('google-sync-log');
  log.textContent = 'Pull 中…';
  try {
    const res = await api('POST', '/api/sync/pull');
    log.textContent = `✓ ${res.pulled} 件の完了状態を取り込みました`;
  } catch(e) {
    log.textContent = 'エラー: ' + e.message;
  }
}
window.runGooglePull = runGooglePull;

export async function googleLogout() {
  if (!confirm('Google 連携を解除しますか？')) return;
  try {
    await api('POST', '/api/auth/logout');
    document.getElementById('google-sync-log').textContent = '';
    document.getElementById('google-tasklist-map-section').style.display = 'none';
    checkGoogleAuthStatus();
  } catch(e) {
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.googleLogout = googleLogout;

export async function loadTasklistMapUI() {
  const section = document.getElementById('google-tasklist-map-section');
  const table = document.getElementById('tasklist-map-table');
  section.style.display = '';
  const CATEGORIES = ['仕事', 'プライベート', '買い物', '学習', 'その他'];
  try {
    const [listsRes, cfg] = await Promise.all([
      api('GET', '/api/auth/tasklists'),
      api('GET', '/api/config'),
    ]);
    const lists = listsRes.lists || [];
    const currentMap = cfg.google_tasklist_map || {};
    const opts = lists.map(l => `<option value="${esc(l.title)}">${esc(l.title)}</option>`).join('');
    table.innerHTML = CATEGORIES.map(cat => `
      <tr>
        <td style="padding:5px 10px 5px 0;color:var(--text-muted);white-space:nowrap">${esc(cat)}</td>
        <td style="padding:5px 0">
          <select id="tlmap-${esc(cat)}" style="background:var(--surface);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:4px 8px;font-size:12px;width:100%">
            <option value="">(カテゴリ名で新規作成)</option>
            ${opts}
          </select>
        </td>
      </tr>`).join('');
    CATEGORIES.forEach(cat => {
      const sel = document.getElementById('tlmap-' + cat);
      if (sel && currentMap[cat]) sel.value = currentMap[cat];
    });
  } catch(e) {
    section.style.display = 'none';
  }
}
window.loadTasklistMapUI = loadTasklistMapUI;

export async function saveTasklistMap() {
  const CATEGORIES = ['仕事', 'プライベート', '買い物', '学習', 'その他'];
  const map = {};
  CATEGORIES.forEach(cat => {
    const sel = document.getElementById('tlmap-' + cat);
    if (sel && sel.value) map[cat] = sel.value;
  });
  try {
    await api('POST', '/api/config', {google_tasklist_map: map});
    window.showStatus('✓ リスト対応を保存しました', 'success', 2000);
  } catch(e) {
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.saveTasklistMap = saveTasklistMap;

export async function saveSyncInterval() {
  const val = parseInt(document.getElementById('sync-interval').value);
  try {
    await api('POST', '/api/config', {sync_interval_minutes: val});
    window.showStatus(val === 0 ? '自動同期を無効にしました（再起動で反映）' : `自動同期を ${val} 分ごとに設定しました（再起動で反映）`, 'success', 3000);
  } catch(e) {
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.saveSyncInterval = saveSyncInterval;
