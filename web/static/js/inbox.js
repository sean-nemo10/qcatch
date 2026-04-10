import { api } from './api.js';
import { parseNaturalDate, esc } from './utils.js';
import { IMP_LABEL } from './state.js';

const CATS = ['仕事','プライベート','買い物','学習','その他'];
const IMP_CYCLE = { high: 'low', medium: 'high', low: 'medium' };

let _quickImp = 'medium';
let _quickLongterm = false;

// ── Quick add helpers ─────────────────────────────────────────────────
export function handleQuickAdd(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); addTask(); }
}
window.handleQuickAdd = handleQuickAdd;

export function setQuickDate(daysFromNow) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  document.getElementById('quick-due-date').value = d.toISOString().slice(0, 10);
}
window.setQuickDate = setQuickDate;

export function cycleQuickImp() {
  _quickImp = IMP_CYCLE[_quickImp] || 'medium';
  const btn = document.getElementById('imp-quick-btn');
  btn.className = `imp-btn imp-${_quickImp}`;
  btn.textContent = IMP_LABEL[_quickImp];
}
window.cycleQuickImp = cycleQuickImp;

export function toggleQuickLongterm() {
  _quickLongterm = !_quickLongterm;
  document.getElementById('longterm-quick-btn').classList.toggle('active', _quickLongterm);
}
window.toggleQuickLongterm = toggleQuickLongterm;

export function onQuickInput(text) {
  const hint = document.getElementById('quick-date-hint');
  const dateISO = parseNaturalDate(text);
  if (dateISO) {
    document.getElementById('quick-due-date').value = dateISO;
    hint.textContent = `📅 ${dateISO} を検出`;
    hint.style.display = 'block';
  } else {
    hint.style.display = 'none';
  }
}
window.onQuickInput = onQuickInput;

export async function addTask() {
  const inp = document.getElementById('quick-input');
  const text = inp.value.trim();
  if (!text) return;
  const dueEl = document.getElementById('quick-due-date');
  const due_date = dueEl && dueEl.value ? dueEl.value + 'T00:00:00' : undefined;
  const body = { text, importance: _quickImp };
  if (due_date) body.due_date = due_date;
  if (_quickLongterm) body.status = 'longterm';
  try {
    await api('POST', '/api/tasks', body);
    inp.value = '';
    if (dueEl) dueEl.value = '';
    document.getElementById('quick-date-hint').style.display = 'none';
    loadInbox();
    window.showStatus('追加しました: ' + text.slice(0,30), 'success', 3000);
    runSort();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.addTask = addTask;

// ── Inbox load ────────────────────────────────────────────────────────
export async function loadInbox() {
  const data = await api('GET', '/api/tasks?status=inbox');
  const list = document.getElementById('inbox-list');
  const tasks = data.tasks;
  const countEl = document.getElementById('home-inbox-count');
  if (countEl) countEl.textContent = tasks.length;
  if (!tasks.length) { list.innerHTML = '<div class="empty">inbox は空です ✓</div>'; return; }
  const header = `<div class="inbox-list-header">
    <span style="font-size:12px;color:var(--text-dim)">未分類 ${tasks.length}件 — カテゴリを選ぶか AI に一括分類させてください</span>
    <button class="btn btn-warning btn-sm" onclick="runSort()" style="margin-left:auto;flex-shrink:0">✨ AI一括分類</button>
  </div>`;
  list.innerHTML = header + tasks.map(t => `
    <div class="task-item" id="ti-${t.id}" style="flex-direction:column;align-items:flex-start;gap:6px">
      <div style="display:flex;align-items:center;gap:10px;width:100%">
        <div class="task-text" style="flex:1">${esc(t.text)}</div>
        <button class="btn btn-ghost btn-sm" onclick="moveToTrash('${t.id}')">削除</button>
      </div>
      <div class="cat-btns">
        ${CATS.map(c => `<button class="cat-btn cat-btn-${c}" onclick="classifyInbox('${t.id}','${c}')">${c}</button>`).join('')}
      </div>
    </div>`).join('');
}
window.loadInbox = loadInbox;

export async function classifyInbox(taskId, category) {
  try {
    await api('PATCH', `/api/tasks/${taskId}`, {status: 'todo', category});
    const el = document.getElementById('ti-' + taskId);
    if (el) { el.style.opacity = '0.4'; el.style.pointerEvents = 'none'; }
    setTimeout(() => loadInbox(), 300);
    window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.classifyInbox = classifyInbox;

export async function runSort() {
  const el = document.getElementById('sort-status');
  if (el) el.textContent = 'AI が分類中...';
  window.showStatus('AI が Inbox を分類しています...', 'info', 0);
  try {
    const res = await api('POST', '/api/sort');
    if (el) el.textContent = '';
    if (res.sorted > 0) {
      window.showStatus(`✓ ${res.sorted} 件を分類しました`, 'success');
      // サブフォルダ提案を再実行（タスクページにいる場合）
      sessionStorage.removeItem('splits_auto_done');
      setTimeout(() => window.autoSuggestSplits?.(), 500);
    } else {
      window.showStatus(res.message || 'inbox は空です', 'success', 2000);
    }
    loadInbox();
    window.updateBadges();
  } catch(e) {
    if (el) el.textContent = '';
    window.showStatus('分類エラー: ' + e.message, 'error');
  }
}
window.runSort = runSort;

// ── オーバーレイ（FAB から開くクイック追加）────────────────────────────
let _overlayImp = 'medium';

export function openQuickAddOverlay() {
  document.getElementById('quick-add-overlay').style.display = 'block';
  document.getElementById('fab-add').style.display = 'none';
  setTimeout(() => document.getElementById('overlay-input')?.focus(), 50);
}
window.openQuickAddOverlay = openQuickAddOverlay;

export function closeQuickAddOverlay() {
  document.getElementById('quick-add-overlay').style.display = 'none';
  const fab = document.getElementById('fab-add');
  if (fab) fab.style.display = (window._activePane !== 'home') ? 'flex' : 'none';
}
window.closeQuickAddOverlay = closeQuickAddOverlay;

export function onOverlayInput(text) {
  const hint = document.getElementById('overlay-date-hint');
  if (!hint) return;
  const dateISO = parseNaturalDate(text);
  if (dateISO) {
    document.getElementById('overlay-due-date').value = dateISO;
    hint.textContent = `📅 ${dateISO} を検出`;
    hint.style.display = 'block';
  } else {
    hint.style.display = 'none';
  }
}
window.onOverlayInput = onOverlayInput;

export function handleOverlayAdd(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); addTaskFromOverlay(); }
}
window.handleOverlayAdd = handleOverlayAdd;

export function setOverlayDate(daysFromNow) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  document.getElementById('overlay-due-date').value = d.toISOString().slice(0, 10);
}
window.setOverlayDate = setOverlayDate;

export function cycleOverlayImp() {
  _overlayImp = IMP_CYCLE[_overlayImp] || 'medium';
  const btn = document.getElementById('overlay-imp-btn');
  btn.className = `imp-btn imp-${_overlayImp}`;
  btn.textContent = IMP_LABEL[_overlayImp];
}
window.cycleOverlayImp = cycleOverlayImp;

export async function addTaskFromOverlay() {
  const inp = document.getElementById('overlay-input');
  const text = inp.value.trim();
  if (!text) return;
  const dueEl = document.getElementById('overlay-due-date');
  const due_date = dueEl && dueEl.value ? dueEl.value + 'T00:00:00' : undefined;
  const body = { text, importance: _overlayImp };
  if (due_date) body.due_date = due_date;
  try {
    await api('POST', '/api/tasks', body);
    inp.value = '';
    if (dueEl) dueEl.value = '';
    window.showStatus('追加しました: ' + text.slice(0, 30), 'success', 3000);
    window.updateBadges();
    closeQuickAddOverlay();
    // アクティブペインを更新
    if (window._activePane === 'dashboard') window.loadDashboard?.();
    runSortFromOverlay();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.addTaskFromOverlay = addTaskFromOverlay;

export async function runSortFromOverlay() {
  const el = document.getElementById('overlay-sort-status');
  if (el) el.textContent = 'AI が分類中...';
  try {
    const res = await api('POST', '/api/sort');
    if (el) el.textContent = '';
    if (res.sorted > 0) {
      window.showStatus(`✓ ${res.sorted} 件を分類しました`, 'success');
      // サブフォルダ提案を再実行
      sessionStorage.removeItem('splits_auto_done');
      setTimeout(() => window.autoSuggestSplits?.(), 500);
    }
    window.updateBadges();
  } catch(e) {
    if (el) el.textContent = '';
    window.showStatus('分類エラー: ' + e.message, 'error');
  }
}
window.runSortFromOverlay = runSortFromOverlay;

