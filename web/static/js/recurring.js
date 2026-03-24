import { api } from './api.js';
import { esc } from './utils.js';
import { WEEKDAY_NAMES } from './state.js';

let _editingRecurringId = null;
let _recurringRules = [];

// ── Recurring load ────────────────────────────────────────────────────
export async function loadRecurring() {
  const data = await api('GET', '/api/recurring');
  _recurringRules = data.recurring;
  const container = document.getElementById('recurring-list');
  if (!data.recurring.length) {
    container.innerHTML = '<div class="empty">定期タスクがまだありません</div>'; return;
  }
  container.innerHTML = data.recurring.map(r => {
    let freqLabel = r.frequency === 'daily' ? '毎日'
      : r.frequency === 'monthly' ? `毎月 ${r.day_of_month} 日`
      : '毎週 ' + (r.days_of_week.map(d => WEEKDAY_NAMES[d]).join('・') || '(曜日未設定)');
    return `
    <div class="recurring-card">
      <div class="recurring-info">
        <div class="text">${esc(r.text)}</div>
        <div class="meta">${freqLabel}${r.category?' · '+esc(r.category):''}${r.last_generated_date?' · 最終: '+r.last_generated_date:''}</div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost btn-sm" onclick="openRecurringEditById('${r.id}')">編集</button>
        <button class="btn btn-danger btn-sm" onclick="deleteRecurring('${r.id}')">削除</button>
      </div>
    </div>`;
  }).join('');
}
window.loadRecurring = loadRecurring;

export async function createRecurring() {
  const text = document.getElementById('rec-text').value.trim();
  if (!text) { window.showStatus('タスクのテキストを入力してください', 'error', 2000); return; }
  const freq = document.getElementById('rec-freq').value;
  const cat = document.getElementById('rec-cat').value || null;
  const days_of_week = freq === 'weekly'
    ? [...document.querySelectorAll('.wd-btn.active')].map(b => parseInt(b.dataset.wd))
    : [];
  const day_of_month = freq === 'monthly'
    ? parseInt(document.getElementById('rec-dom').value) || null
    : null;
  try {
    await api('POST', '/api/recurring', {text, category:cat, frequency:freq, days_of_week, day_of_month});
    document.getElementById('rec-text').value = '';
    document.querySelectorAll('.wd-btn').forEach(b => b.classList.remove('active'));
    window.showStatus('定期タスクを登録しました', 'success');
    loadRecurring();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.createRecurring = createRecurring;

export async function deleteRecurring(id) {
  if (!confirm('この定期タスクを削除しますか？')) return;
  try {
    await api('DELETE', `/api/recurring/${id}`);
    window.showStatus('削除しました', 'info', 2000);
    loadRecurring();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.deleteRecurring = deleteRecurring;

export function openRecurringEditById(id) {
  const r = _recurringRules.find(x => x.id === id);
  if (r) openRecurringEdit(r);
}
window.openRecurringEditById = openRecurringEditById;

export function openRecurringEdit(r) {
  _editingRecurringId = r.id;
  document.getElementById('redit-text').value = r.text;
  document.getElementById('redit-cat').value = r.category || '';
  document.getElementById('redit-freq').value = r.frequency;
  document.querySelectorAll('.redit-wd-btn').forEach(b => {
    b.classList.toggle('active', r.days_of_week.includes(parseInt(b.dataset.wd)));
  });
  document.getElementById('redit-dom').value = r.day_of_month || '';
  updateReditFreqUI();
  document.getElementById('modal-recurring-edit').classList.add('show');
}
window.openRecurringEdit = openRecurringEdit;

export function closeRecurringEdit() {
  _editingRecurringId = null;
  document.getElementById('modal-recurring-edit').classList.remove('show');
}
window.closeRecurringEdit = closeRecurringEdit;

export async function saveRecurringEdit() {
  const text = document.getElementById('redit-text').value.trim();
  if (!text) { window.showStatus('テキストを入力してください', 'error'); return; }
  const freq = document.getElementById('redit-freq').value;
  const days_of_week = freq === 'weekly'
    ? [...document.querySelectorAll('.redit-wd-btn.active')].map(b => parseInt(b.dataset.wd))
    : [];
  const day_of_month = freq === 'monthly'
    ? parseInt(document.getElementById('redit-dom').value) || null
    : null;
  const body = {
    text, frequency: freq, days_of_week, day_of_month,
    category: document.getElementById('redit-cat').value || null,
  };
  try {
    await api('PATCH', `/api/recurring/${_editingRecurringId}`, body);
    closeRecurringEdit();
    window.showStatus('更新しました', 'success', 2000);
    loadRecurring();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.saveRecurringEdit = saveRecurringEdit;

export function updateFreqUI() {
  const freq = document.getElementById('rec-freq').value;
  document.getElementById('rec-weekly-ui').style.display = freq === 'weekly' ? '' : 'none';
  document.getElementById('rec-monthly-ui').style.display = freq === 'monthly' ? '' : 'none';
}
window.updateFreqUI = updateFreqUI;

export function updateReditFreqUI() {
  const freq = document.getElementById('redit-freq').value;
  document.getElementById('redit-weekly-ui').style.display = freq === 'weekly' ? '' : 'none';
  document.getElementById('redit-monthly-ui').style.display = freq === 'monthly' ? '' : 'none';
}
window.updateReditFreqUI = updateReditFreqUI;

// ── Weekday button click listeners (setup at module load) ─────────────
document.querySelectorAll('.wd-btn').forEach(btn => {
  btn.addEventListener('click', () => btn.classList.toggle('active'));
});

document.querySelectorAll('.redit-wd-btn').forEach(btn => {
  btn.addEventListener('click', () => btn.classList.toggle('active'));
});
