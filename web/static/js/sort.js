import { api } from './api.js';
import { state, CAT_COLORS, IMP_LABEL } from './state.js';
import { esc, calcScore } from './utils.js';

const IMP_CYCLE = { high: 'low', medium: 'high', low: 'medium' };

// ── Sort pane load ────────────────────────────────────────────────────
export async function loadSortPane() {
  const container = document.getElementById('sort-list');
  if (!container) return;
  container.innerHTML = '<div class="empty">読み込み中...</div>';
  try {
    const [tasksData, orderData] = await Promise.all([
      api('GET', '/api/tasks?status=todo'),
      api('GET', '/api/dashboard-order'),
    ]);
    const orderMap = {};
    (orderData.order || []).forEach((id, i) => { orderMap[id] = i; });
    const tasks = tasksData.tasks.slice().sort((a, b) => {
      const aPos = orderMap[a.id] ?? Infinity;
      const bPos = orderMap[b.id] ?? Infinity;
      if (aPos !== bPos) return aPos - bPos;
      return calcScore(b, []).score - calcScore(a, []).score;
    });
    if (!tasks.length) {
      container.innerHTML = '<div class="empty">Todo タスクがありません</div>';
      return;
    }
    container.innerHTML = tasks.map(t => {
      const imp = t.importance || 'medium';
      const catClass = CAT_COLORS[t.category] || 'cat-その他';
      const score = calcScore(t, []).score;
      return `<div class="sort-item" id="sorti-${t.id}" draggable="true"
        ondragstart="sortDragStart(event,'${t.id}')"
        ondragover="sortDragOver(event,'${t.id}')"
        ondragleave="sortDragLeave(event)"
        ondrop="sortDrop(event,'${t.id}')">
        <span class="sort-drag-handle">⠿</span>
        <span class="sort-text" title="${esc(t.text)}">${esc(t.text)}</span>
        <div style="display:flex;gap:4px;flex-shrink:0">
          <button class="imp-btn imp-high${imp==='high'?'':' btn-ghost'}" style="opacity:${imp==='high'?1:.35}" onclick="setImportanceDirect('${t.id}','high')" title="重要度: 高">🔴</button>
          <button class="imp-btn imp-medium${imp==='medium'?'':' btn-ghost'}" style="opacity:${imp==='medium'?1:.35}" onclick="setImportanceDirect('${t.id}','medium')" title="重要度: 中">🟡</button>
          <button class="imp-btn imp-low${imp==='low'?'':' btn-ghost'}" style="opacity:${imp==='low'?1:.35}" onclick="setImportanceDirect('${t.id}','low')" title="重要度: 低">🟢</button>
        </div>
        <span class="task-cat ${catClass}" style="flex-shrink:0">${esc(t.category||'未分類')}</span>
        <span class="sort-score">${score}pt</span>
      </div>`;
    }).join('');
  } catch(e) { container.innerHTML = '<div class="empty">エラー: ' + esc(e.message) + '</div>'; }
}
window.loadSortPane = loadSortPane;

// ── Importance ────────────────────────────────────────────────────────
export async function setImportanceDirect(id, level) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {importance: level});
    loadSortPane();
    if (state.activePane === 'dashboard') window.loadDashboard();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.setImportanceDirect = setImportanceDirect;

export async function cycleImportance(id, current) {
  const next = IMP_CYCLE[current] || 'high';
  try {
    await api('PATCH', `/api/tasks/${id}`, {importance: next});
    if (state.activePane === 'sort') loadSortPane();
    else if (state.activePane === 'dashboard') window.loadDashboard();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.cycleImportance = cycleImportance;

// ── Sort drag ─────────────────────────────────────────────────────────
let _sortDragId = null;

export function sortDragStart(event, id) {
  _sortDragId = id;
  event.dataTransfer.effectAllowed = 'move';
  setTimeout(() => { const el = document.getElementById('sorti-' + id); if (el) el.classList.add('dragging'); }, 0);
}
window.sortDragStart = sortDragStart;

export function sortDragOver(event, id) {
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  if (id === _sortDragId) return;
  document.querySelectorAll('.sort-item').forEach(el => el.classList.remove('drag-over'));
  const el = document.getElementById('sorti-' + id);
  if (el) el.classList.add('drag-over');
}
window.sortDragOver = sortDragOver;

export function sortDragLeave(event) { event.currentTarget.classList.remove('drag-over'); }
window.sortDragLeave = sortDragLeave;

export async function sortDrop(event, targetId) {
  event.preventDefault();
  document.querySelectorAll('.sort-item').forEach(el => el.classList.remove('drag-over', 'dragging'));
  if (!_sortDragId || _sortDragId === targetId) { _sortDragId = null; return; }
  const items = [...document.querySelectorAll('#sort-list .sort-item')];
  const ids = items.map(el => el.id.replace('sorti-', ''));
  const fromIdx = ids.indexOf(_sortDragId);
  const toIdx = ids.indexOf(targetId);
  if (fromIdx < 0 || toIdx < 0) { _sortDragId = null; return; }
  ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, _sortDragId);
  _sortDragId = null;
  try {
    await api('POST', '/api/dashboard-order', {order: ids});
    window.showStatus('並び順を保存しました', 'success', 1500);
    loadSortPane();
  } catch(e) { window.showStatus('並び替えエラー: ' + e.message, 'error'); }
}
window.sortDrop = sortDrop;
