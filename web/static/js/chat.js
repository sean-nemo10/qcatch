import { api } from './api.js';
import { esc } from './utils.js';
import { getApiKey, loadApiKeyToChat } from './settings.js';

export { loadApiKeyToChat };

// ── Chat helpers ──────────────────────────────────────────────────────
export function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
}
window.handleChatKey = handleChatKey;

export function autoResizeChat(el) {
  el.style.height = '44px';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}
window.autoResizeChat = autoResizeChat;

export function appendChatMsg(role, text) {
  const container = document.getElementById('chat-messages');
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const row = document.createElement('div');
  row.className = `chat-row ${role}`;
  row.innerHTML = `<div class="chat-bubble">${esc(text).replace(/\n/g,'<br>')}</div>
    <div class="chat-meta">${time}</div>`;
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
  return row;
}
window.appendChatMsg = appendChatMsg;

export function showTyping() {
  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'chat-row ai thinking';
  row.id = 'chat-typing';
  row.innerHTML = '<div class="chat-bubble">…</div>';
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
}
window.showTyping = showTyping;

export function hideTyping() {
  const el = document.getElementById('chat-typing');
  if (el) el.remove();
}
window.hideTyping = hideTyping;

// ── Send chat ─────────────────────────────────────────────────────────
export async function sendChat() {
  const inp = document.getElementById('chat-input');
  const text = inp.value.trim();
  if (!text) return;
  const apiKey = getApiKey();

  appendChatMsg('user', text);
  inp.value = '';
  inp.style.height = '44px';

  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'chat-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = '…';
  const now = new Date();
  const meta = document.createElement('div');
  meta.className = 'chat-meta';
  meta.textContent = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  row.appendChild(bubble);
  row.appendChild(meta);
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;

  let accumulated = '';

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, api_key: apiKey || null}),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({detail: response.statusText}));
      bubble.textContent = 'エラー: ' + (err.detail || response.statusText);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(part.slice(6));
          if (event.type === 'text') {
            accumulated += event.chunk;
            bubble.innerHTML = esc(accumulated).replace(/\n/g, '<br>');
            container.scrollTop = container.scrollHeight;
          } else if (event.type === 'done') {
            for (const action of event.actions || []) {
              if (action.type === 'refresh') { window.updateBadges(); window.reloadActivePane(); }
              else if (action.type === 'switch_tab') window.switchTabByName(action.tab);
              else if (action.type === 'calendar_confirm') showCalendarConfirm(action.event);
            }
          } else if (event.type === 'error') {
            bubble.textContent = 'エラー: ' + event.message;
          }
        } catch {}
      }
    }
    if (!accumulated) bubble.textContent = '（応答がありませんでした）';
  } catch(e) {
    bubble.textContent = 'エラー: ' + e.message;
  }
}
window.sendChat = sendChat;

// ── Calendar confirmation card ─────────────────────────────────────────────
function fmtLocalDt(isoStr) {
  // ISO文字列をローカルdatetime-local input用フォーマットに変換
  const d = new Date(isoStr);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function showCalendarConfirm(ev) {
  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'chat-row ai';

  const startFmt = fmtLocalDt(ev.start_dt);
  const endFmt = fmtLocalDt(ev.end_dt);

  row.innerHTML = `
    <div class="chat-bubble" style="min-width:260px">
      <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">📅 カレンダー予定の確認</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div>
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:3px">タイトル</div>
          <input id="cal-title" type="text" value="${esc(ev.title)}"
            style="width:100%;padding:6px 8px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box">
        </div>
        <div style="display:flex;gap:6px">
          <div style="flex:1">
            <div style="font-size:11px;color:var(--text-dim);margin-bottom:3px">開始</div>
            <input id="cal-start" type="datetime-local" value="${startFmt}"
              style="width:100%;padding:6px 8px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:12px;font-family:inherit;box-sizing:border-box">
          </div>
          <div style="flex:1">
            <div style="font-size:11px;color:var(--text-dim);margin-bottom:3px">終了</div>
            <input id="cal-end" type="datetime-local" value="${endFmt}"
              style="width:100%;padding:6px 8px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:12px;font-family:inherit;box-sizing:border-box">
          </div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-dim);margin-bottom:3px">メモ（任意）</div>
          <input id="cal-desc" type="text" value="${esc(ev.description || '')}"
            style="width:100%;padding:6px 8px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:13px;font-family:inherit;box-sizing:border-box">
        </div>
        <div style="display:flex;gap:8px;margin-top:4px">
          <button id="cal-confirm-btn" class="btn btn-primary btn-sm" style="flex:1">追加する</button>
          <button id="cal-cancel-btn" class="btn btn-ghost btn-sm" style="flex:1">キャンセル</button>
        </div>
        <div id="cal-status" style="font-size:12px;color:var(--text-dim);min-height:16px"></div>
      </div>
    </div>
    <div class="chat-meta"></div>`;

  container.appendChild(row);
  container.scrollTop = container.scrollHeight;

  row.querySelector('#cal-cancel-btn').addEventListener('click', () => row.remove());

  row.querySelector('#cal-confirm-btn').addEventListener('click', async () => {
    const title = row.querySelector('#cal-title').value.trim();
    const startVal = row.querySelector('#cal-start').value;
    const endVal = row.querySelector('#cal-end').value;
    const desc = row.querySelector('#cal-desc').value.trim();
    const status = row.querySelector('#cal-status');

    if (!title || !startVal || !endVal) {
      status.textContent = 'タイトルと日時は必須です。';
      status.style.color = 'var(--danger, #e53935)';
      return;
    }
    if (new Date(endVal) <= new Date(startVal)) {
      status.textContent = '終了時刻は開始より後にしてください。';
      status.style.color = 'var(--danger, #e53935)';
      return;
    }

    row.querySelector('#cal-confirm-btn').disabled = true;
    row.querySelector('#cal-cancel-btn').disabled = true;
    status.textContent = '追加中…';
    status.style.color = 'var(--text-dim)';

    try {
      const res = await fetch('/api/calendar/add_event', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({title, start_dt: startVal, end_dt: endVal, description: desc}),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({detail: res.statusText}));
        status.textContent = 'エラー: ' + (err.detail || res.statusText);
        status.style.color = 'var(--danger, #e53935)';
        row.querySelector('#cal-confirm-btn').disabled = false;
        row.querySelector('#cal-cancel-btn').disabled = false;
        return;
      }
      status.textContent = '✓ カレンダーに追加しました';
      status.style.color = '#4caf50';
      row.querySelector('#cal-confirm-btn').remove();
      row.querySelector('#cal-cancel-btn').textContent = '閉じる';
      row.querySelector('#cal-cancel-btn').disabled = false;
    } catch(e) {
      status.textContent = 'エラー: ' + e.message;
      status.style.color = 'var(--danger, #e53935)';
      row.querySelector('#cal-confirm-btn').disabled = false;
      row.querySelector('#cal-cancel-btn').disabled = false;
    }
  });
}
window.showCalendarConfirm = showCalendarConfirm;

export async function clearChat() {
  try {
    await api('POST', '/api/chat/clear');
    const container = document.getElementById('chat-messages');
    container.innerHTML = '<div class="chat-row ai"><div class="chat-bubble">会話履歴をクリアしました。</div></div>';
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.clearChat = clearChat;

// ── Briefing ──────────────────────────────────────────────────────────
export async function sendBriefing() {
  const apiKey = getApiKey();
  window.switchTabByName('chat');

  appendChatMsg('user', 'AI 分析');

  const container = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'chat-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = '…';
  const now = new Date();
  const meta = document.createElement('div');
  meta.className = 'chat-meta';
  meta.textContent = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  row.appendChild(bubble);
  row.appendChild(meta);
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;

  let accumulated = '';
  try {
    const response = await fetch('/api/chat/briefing', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: '', api_key: apiKey || null}),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({detail: response.statusText}));
      bubble.textContent = 'エラー: ' + (err.detail || response.statusText);
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(part.slice(6));
          if (event.type === 'text') {
            accumulated += event.chunk;
            bubble.innerHTML = esc(accumulated).replace(/\n/g, '<br>');
            container.scrollTop = container.scrollHeight;
          } else if (event.type === 'error') {
            bubble.textContent = 'エラー: ' + event.message;
          }
        } catch {}
      }
    }
    if (!accumulated) bubble.textContent = '（応答がありませんでした）';
  } catch(e) {
    bubble.textContent = 'エラー: ' + e.message;
  }
}
window.sendBriefing = sendBriefing;
