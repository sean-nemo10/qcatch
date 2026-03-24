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

  appendChatMsg('user', '☀️ 朝のブリーフィング');

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
