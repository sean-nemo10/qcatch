import { api } from './api.js';
import { state, CAT_COLORS, IMP_LABEL } from './state.js';
import { esc, fmtDate, calcScore, scoreBadge, scoreLabel, getFoldState, setFoldState } from './utils.js';

const CATS = ['仕事','プライベート','買い物','学習','その他'];
const IMP_CYCLE = { high: 'low', medium: 'high', low: 'medium' };
const DEFAULT_CAT_ORDER = ['仕事','プライベート','買い物','学習','その他'];

function getTasksCatOrder() {
  try {
    const s = JSON.parse(localStorage.getItem('qcatch_tasks_cat_order') || 'null');
    if (Array.isArray(s) && s.length === DEFAULT_CAT_ORDER.length) return s;
  } catch(e) {}
  return [...DEFAULT_CAT_ORDER];
}

function saveTasksCatOrder(o) { localStorage.setItem('qcatch_tasks_cat_order', JSON.stringify(o)); }

// ── Tasks load ────────────────────────────────────────────────────────
export async function loadTasks() {
  const [taskData, clData, orderData] = await Promise.all([
    api('GET', '/api/tasks?status=todo'),
    api('GET', '/api/checklists'),
    api('GET', '/api/tasks-order'),
  ]);
  const tasks = taskData.tasks;
  const checklists = clData.checklists;
  state.currentTasks = tasks;
  const tasksOrder = orderData.order || [];
  const orderIdx = id => { const i = tasksOrder.indexOf(id); return i < 0 ? Infinity : i; };

  const groups = {};
  const ORDER = getTasksCatOrder();
  tasks.forEach(t => {
    const cat = t.category || 'その他';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(t);
  });
  ORDER.forEach(cat => {
    if (groups[cat]) groups[cat].sort((a, b) => {
      const oi = orderIdx(a.id) - orderIdx(b.id);
      if (oi !== 0) return oi;
      return calcScore(b, checklists).score - calcScore(a, checklists).score;
    });
  });

  const container = document.getElementById('tasks-list');
  if (!tasks.length) { container.innerHTML = '<div class="empty">タスクがありません</div>'; return; }

  function renderCatGroup(cat, catTasks) {
    const subgroups = {};
    catTasks.forEach(t => {
      const key = (t.tags && t.tags[0]) ? t.tags[0] : '';
      if (!subgroups[key]) subgroups[key] = [];
      subgroups[key].push(t);
    });
    const keys = Object.keys(subgroups).sort((a,b) => a === '' ? 1 : b === '' ? -1 : a.localeCompare(b));
    return keys.map(key => {
      const subTasks = subgroups[key];
      const header = key ? `<div style="font-size:12px;color:#a5d6a7;padding:6px 2px 2px;margin-top:10px;font-weight:600">📁 ${esc(key)}</div>` : '';
      return header + subTasks.map(t => {
        const badge = scoreBadge(t, checklists);
        const tip = scoreLabel(t, checklists);
        return `
        <div class="task-item ${state.selectedTaskIds.has(t.id)?'selected':''}" id="ti-${t.id}" draggable="true" data-cat="${esc(t.category||'その他')}"
          ondragstart="taskDragStart(event,'${t.id}')"
          ondragover="taskDragOver(event,'${t.id}')"
          ondragleave="taskDragLeave(event)"
          ondrop="taskDrop(event,'${t.id}','${esc(t.category||'その他')}')"
          onclick="toggleSelect('${t.id}', event)">
          <div class="task-drag-handle" title="ドラッグして並び替え">⠿</div>
          <input type="checkbox" ${state.selectedTaskIds.has(t.id)?'checked':''} onclick="toggleSelect('${t.id}', event)">
          <div class="task-text" id="txt-${t.id}" title="${esc(tip)}">${esc(t.text)}${t.tags&&t.tags[0]?`<span class="task-subtag" onclick="openSubfolderModal('${t.id}');event.stopPropagation()" title="📁 ${esc(t.tags[0])} — クリックで変更">📁 ${esc(t.tags[0])}</span><span onclick="clearSubtag('${t.id}');event.stopPropagation()" style="cursor:pointer;opacity:.4;font-size:10px;margin-left:1px" title="サブフォルダを外す">×</span>`:`<button class="subfolder-add" onclick="openSubfolderModal('${t.id}');event.stopPropagation()" title="サブフォルダに分類">📁+</button>`}${badge}</div>
          <input class="task-edit-input" id="edit-${t.id}" value="${esc(t.text)}" style="display:none;flex:1;padding:3px 8px;background:#0f2547;border:1px solid #4fc3f7;border-radius:4px;color:#e0e0e0;font-size:14px;font-family:inherit"
            onkeydown="if(event.key==='Enter')saveEdit('${t.id}');if(event.key==='Escape')cancelEdit('${t.id}')"
            onblur="saveEdit('${t.id}')">
          <div class="task-actions" onclick="e=>e.stopPropagation()">
            <div class="cat-change-wrap">
              <span class="task-cat ${CAT_COLORS[t.category]||'cat-その他'}" style="cursor:pointer" onclick="toggleCatMenu('${t.id}',event)">${esc(t.category||'未分類')}</span>
              <div class="cat-change-menu" id="catmenu-${t.id}">
                ${CATS.map(c=>`<button class="cat-change-item" onclick="changeTaskCat('${t.id}','${c}',event)">${c}</button>`).join('')}
              </div>
            </div>
            <button class="imp-btn imp-${t.importance||'medium'}" onclick="cycleImportance('${t.id}','${t.importance||'medium'}');event.stopPropagation()" title="重要度">${IMP_LABEL[t.importance||'medium']}</button>
            <button class="btn btn-ghost btn-sm" id="edit-btn-${t.id}" onclick="startEdit('${t.id}');event.stopPropagation()">編集</button>
            <button class="btn btn-ghost btn-sm" onclick="editTaskDue('${t.id}','${t.due_date||''}');event.stopPropagation()" title="期日を設定">📅</button>
            <button class="btn btn-ghost btn-sm" onclick="moveToLongterm('${t.id}');event.stopPropagation()" title="長期タスクに移動">🗂</button>
            <button class="btn btn-ghost btn-sm" onclick="backToInbox('${t.id}');event.stopPropagation()" title="Inbox に戻す">↩</button>
            <button class="btn btn-success btn-sm" onclick="completeOne('${t.id}');event.stopPropagation()">完了</button>
            <button class="btn btn-ghost btn-sm" onclick="moveToTrash('${t.id}');event.stopPropagation()">削除</button>
          </div>
        </div>`;
      }).join('');
    }).join('');
  }

  const foldState = getFoldState();
  container.innerHTML = ORDER.filter(c => groups[c]).map(cat => {
    const folded = foldState[cat] ? 'folded' : '';
    return `
    <div class="cat-section ${folded}" id="catsec-${cat}" draggable="true"
      ondragstart="catDragStart(event,'${cat}')"
      ondragover="catDragOver(event,'${cat}')"
      ondragleave="catDragLeave(event)"
      ondrop="catDrop(event,'${cat}')">
      <div class="cat-header" onclick="toggleCatFold('${cat}', document.getElementById('catsec-${cat}'))">
        <span class="cat-drag-handle" title="ドラッグしてカテゴリを並び替え" onclick="event.stopPropagation()">⠿</span>
        <h3>${esc(cat)}</h3>
        <span class="cat-count">${groups[cat].length}</span>
        <span class="cat-fold-icon">▾</span>
      </div>
      <div class="task-list">
        ${renderCatGroup(cat, groups[cat])}
      </div>
    </div>`;
  }).join('');

  updateSelectionCount();
}
window.loadTasks = loadTasks;

// ── Longterm ──────────────────────────────────────────────────────────
export async function loadLongterm() {
  const data = await api('GET', '/api/tasks?status=longterm');
  const container = document.getElementById('longterm-list');
  const tasks = data.tasks;
  if (!tasks.length) {
    container.innerHTML = '<div class="empty">長期タスクがありません<br><span style="font-size:12px;color:#555">タスクタブの 🗂 ボタンで追加できます</span></div>';
    return;
  }
  container.innerHTML = tasks.map(t => {
    const catClass = CAT_COLORS[t.category] || 'cat-その他';
    const due = t.due_date ? `<span class="task-due${new Date(t.due_date) <= new Date() ? ' overdue' : ''}" style="margin-left:6px">📅${fmtDate(t.due_date)}</span>` : '';
    const subtag = t.tags && t.tags[0] ? `<span class="task-subtag">📁 ${esc(t.tags[0])}</span>` : '';
    return `
    <div class="task-item" id="lti-${t.id}">
      <div class="task-text">${esc(t.text)}${subtag}${due}
        ${t.category ? `<span class="task-cat ${catClass}" style="margin-left:6px">${esc(t.category)}</span>` : ''}
      </div>
      <div class="task-actions">
        <button class="imp-btn imp-${t.importance||'medium'}" onclick="cycleImportance('${t.id}','${t.importance||'medium'}');event.stopPropagation()" title="重要度">${IMP_LABEL[t.importance||'medium']}</button>
        <button class="btn btn-ghost btn-sm" onclick="editTaskDue('${t.id}','${t.due_date||''}');event.stopPropagation()" title="期日を設定">📅</button>
        <button class="btn btn-primary btn-sm" onclick="backFromLongterm('${t.id}')">Todo に戻す</button>
        <button class="btn btn-ghost btn-sm" onclick="moveToTrash('${t.id}')">削除</button>
      </div>
    </div>`;
  }).join('');
}
window.loadLongterm = loadLongterm;

// ── Selection ─────────────────────────────────────────────────────────
export function toggleSelect(id, e) {
  if (e.target.tagName === 'BUTTON') return;
  if (state.selectedTaskIds.has(id)) state.selectedTaskIds.delete(id);
  else state.selectedTaskIds.add(id);
  const el = document.getElementById('ti-' + id);
  if (el) {
    el.classList.toggle('selected', state.selectedTaskIds.has(id));
    const cb = el.querySelector('input[type=checkbox]');
    if (cb) cb.checked = state.selectedTaskIds.has(id);
  }
  updateSelectionCount();
}
window.toggleSelect = toggleSelect;

function updateSelectionCount() {
  const el = document.getElementById('selected-count');
  if (el) el.textContent = state.selectedTaskIds.size ? `${state.selectedTaskIds.size} 件選択中` : '';
}

export function selectAll(tab) {
  document.querySelectorAll('#tasks-list .task-item').forEach(el => {
    const id = el.id.replace('ti-','');
    state.selectedTaskIds.add(id);
    el.classList.add('selected');
    const cb = el.querySelector('input[type=checkbox]');
    if (cb) cb.checked = true;
  });
  updateSelectionCount();
}
window.selectAll = selectAll;

export function clearSelection() {
  state.selectedTaskIds.clear();
  document.querySelectorAll('#tasks-list .task-item').forEach(el => {
    el.classList.remove('selected');
    const cb = el.querySelector('input[type=checkbox]');
    if (cb) cb.checked = false;
  });
  updateSelectionCount();
}
window.clearSelection = clearSelection;

export async function bulkComplete() {
  if (!state.selectedTaskIds.size) { window.showStatus('タスクを選択してください', 'info', 2000); return; }
  try {
    const res = await api('POST', '/api/tasks/bulk-complete', [...state.selectedTaskIds]);
    state.selectedTaskIds.clear();
    window.showStatus(`✓ ${res.updated.length} 件を完了しました`, 'success');
    loadTasks();
    window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.bulkComplete = bulkComplete;

export async function completeOne(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status:'done'});
    state.selectedTaskIds.delete(id);
    window.showStatus('✓ 完了しました', 'success', 2000);
    loadTasks();
    window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.completeOne = completeOne;

export async function backToInbox(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status: 'inbox', category: null});
    window.showStatus('Inbox に戻しました', 'info', 2000);
    loadTasks(); window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.backToInbox = backToInbox;

export async function moveToLongterm(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status: 'longterm'});
    window.showStatus('長期タスクに移動しました', 'info', 2000);
    loadTasks(); window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.moveToLongterm = moveToLongterm;

export async function backFromLongterm(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status: 'todo'});
    window.showStatus('Todo に移動しました', 'success', 2000);
    loadLongterm(); window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.backFromLongterm = backFromLongterm;

export async function moveToTrash(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status:'trashed'});
    if (typeof window.loadInbox === 'function') window.loadInbox();
    loadTasks(); window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.moveToTrash = moveToTrash;

export function filterTasks(query) {
  const q = query.trim().toLowerCase();
  document.querySelectorAll('#tasks-list .task-item').forEach(el => {
    const txt = (el.querySelector('.task-text')?.textContent || '').toLowerCase();
    el.style.display = (!q || txt.includes(q)) ? '' : 'none';
  });
  document.querySelectorAll('#tasks-list .cat-section').forEach(sec => {
    const visible = [...sec.querySelectorAll('.task-item')].some(i => i.style.display !== 'none');
    sec.style.display = visible ? '' : 'none';
    sec.classList.toggle('folded', q ? false : getFoldState()[sec.id.replace('catsec-', '')] || false);
  });
}
window.filterTasks = filterTasks;

// ── Trash ─────────────────────────────────────────────────────────────
export async function loadTrash() {
  const data = await api('GET', '/api/tasks?status=done,trashed');
  const tasks = data.tasks;
  const list = document.getElementById('trash-list');
  if (!tasks.length) { list.innerHTML = '<div class="empty">ゴミ箱は空です</div>'; return; }
  list.innerHTML = tasks.map(t => `
    <div class="task-item" id="ti-${t.id}">
      <div class="task-text" style="color:${t.status==='done'?'#aaa':'#666'};${t.status==='trashed'?'text-decoration:line-through':''}">
        ${t.status==='done'?'<span class="done-mark">✓</span> ':'🗑 '}${esc(t.text)}
        ${t.category?`<span class="task-cat ${CAT_COLORS[t.category]||''}" style="margin-left:6px">${esc(t.category)}</span>`:''}
      </div>
      <div class="task-actions">
        <button class="btn btn-ghost btn-sm" onclick="restoreTask('${t.id}')">元に戻す</button>
        <button class="btn btn-danger btn-sm" onclick="deleteForever('${t.id}')">完全削除</button>
      </div>
    </div>`).join('');
}
window.loadTrash = loadTrash;

export async function restoreTask(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status:'todo'});
    window.showStatus('タスクを復元しました', 'success', 2000);
    loadTrash(); window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.restoreTask = restoreTask;

export async function deleteForever(id) {
  if (!confirm('完全に削除しますか？この操作は取り消せません。')) return;
  try {
    await api('DELETE', `/api/tasks/${id}`);
    window.showStatus('完全削除しました', 'info', 2000);
    loadTrash(); window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.deleteForever = deleteForever;

// ── Inline edit ───────────────────────────────────────────────────────
export function startEdit(id) {
  document.getElementById('txt-' + id).style.display = 'none';
  const inp = document.getElementById('edit-' + id);
  inp.style.display = 'inline-block';
  inp.focus();
  inp.select();
  document.getElementById('edit-btn-' + id).textContent = '✕';
  document.getElementById('edit-btn-' + id).onclick = (e) => { e.stopPropagation(); cancelEdit(id); };
}
window.startEdit = startEdit;

export function cancelEdit(id) {
  document.getElementById('txt-' + id).style.display = '';
  document.getElementById('edit-' + id).style.display = 'none';
  document.getElementById('edit-btn-' + id).textContent = '編集';
  document.getElementById('edit-btn-' + id).onclick = (e) => { e.stopPropagation(); startEdit(id); };
}
window.cancelEdit = cancelEdit;

export async function saveEdit(id) {
  const inp = document.getElementById('edit-' + id);
  if (!inp || inp.style.display === 'none') return;
  const text = inp.value.trim();
  if (!text) { cancelEdit(id); return; }
  try {
    await api('PATCH', `/api/tasks/${id}`, {text});
    loadTasks();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.saveEdit = saveEdit;

// ── Subfolder ─────────────────────────────────────────────────────────
export async function clearSubtag(taskId) {
  try {
    await api('PATCH', `/api/tasks/${taskId}`, {tags: []});
    loadTasks();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.clearSubtag = clearSubtag;

export function openSubfolderModal(taskId) {
  const task = state.currentTasks.find(t => t.id === taskId);
  if (!task) return;
  state.subfolderTaskId = taskId;
  const category = task.category || '未分類';
  const currentFolder = (task.tags && task.tags[0]) || null;

  const folders = [...new Set(
    state.currentTasks
      .filter(t => t.category === task.category && t.tags && t.tags[0])
      .map(t => t.tags[0])
  )];

  document.getElementById('modal-subfolder-info').textContent =
    `カテゴリ: ${category}${currentFolder ? ' ／ 現在: 📁 ' + currentFolder : ' ／ サブフォルダなし'}`;

  const list = document.getElementById('modal-subfolder-list');
  if (folders.length) {
    list.innerHTML = `<div style="font-size:11px;color:#888;margin-bottom:6px">既存のサブフォルダ:</div>` +
      folders.map(f => `
        <button class="subfolder-item${f === currentFolder ? ' active' : ''}" onclick="saveSubfolder('${esc(f)}')">
          ${f === currentFolder ? '✓ ' : ''}📁 ${esc(f)}
        </button>`).join('');
  } else {
    list.innerHTML = '<div style="font-size:12px;color:#555;text-align:center;padding:6px 0">このカテゴリに既存のサブフォルダがありません</div>';
  }

  document.getElementById('modal-subfolder-new').value = '';
  document.getElementById('modal-subfolder').classList.add('show');
  setTimeout(() => document.getElementById('modal-subfolder-new').focus(), 50);
}
window.openSubfolderModal = openSubfolderModal;

export function closeSubfolderModal() {
  document.getElementById('modal-subfolder').classList.remove('show');
  state.subfolderTaskId = null;
}
window.closeSubfolderModal = closeSubfolderModal;

export async function saveSubfolder(folderName) {
  if (state.subfolderTaskId === null) return;
  if (folderName === '') return;
  const tags = folderName ? [folderName] : [];
  try {
    await api('PATCH', `/api/tasks/${state.subfolderTaskId}`, {tags});
    closeSubfolderModal();
    window.showStatus(folderName ? `📁 "${folderName}" に設定しました` : 'サブフォルダを外しました', 'success', 2000);
    loadTasks();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.saveSubfolder = saveSubfolder;

// ── Category change menu ──────────────────────────────────────────────
export function toggleCatMenu(id, e) {
  e.stopPropagation();
  const menu = document.getElementById('catmenu-' + id);
  const isOpen = menu.classList.contains('open');
  document.querySelectorAll('.cat-change-menu.open').forEach(m => m.classList.remove('open'));
  if (!isOpen) menu.classList.add('open');
}
window.toggleCatMenu = toggleCatMenu;

export async function changeTaskCat(id, cat, e) {
  e.stopPropagation();
  document.querySelectorAll('.cat-change-menu.open').forEach(m => m.classList.remove('open'));
  try {
    await api('PATCH', `/api/tasks/${id}`, {category: cat});
    loadTasks();
  } catch(e2) { window.showStatus('エラー: ' + e2.message, 'error'); }
}
window.changeTaskCat = changeTaskCat;

document.addEventListener('click', () => {
  document.querySelectorAll('.cat-change-menu.open').forEach(m => m.classList.remove('open'));
});

// ── Category fold ─────────────────────────────────────────────────────
export function toggleCatFold(cat, sectionEl) {
  const folded = !sectionEl.classList.contains('folded');
  sectionEl.classList.toggle('folded', folded);
  setFoldState(cat, folded);
}
window.toggleCatFold = toggleCatFold;

// ── Drag: tasks ───────────────────────────────────────────────────────
let _taskDragId = null;
let _taskDragCat = null;

export function taskDragStart(event, id) {
  event.stopPropagation();
  _taskDragId = id;
  const el = document.getElementById('ti-' + id);
  _taskDragCat = el ? el.dataset.cat : null;
  event.dataTransfer.effectAllowed = 'move';
  setTimeout(() => { if (el) el.classList.add('dragging'); }, 0);
}
window.taskDragStart = taskDragStart;

export function taskDragOver(event, id) {
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  if (id === _taskDragId) return;
  const el = document.getElementById('ti-' + id);
  if (!el || el.dataset.cat !== _taskDragCat) return;
  document.querySelectorAll('#tasks-list .task-item').forEach(e => e.classList.remove('drag-over'));
  el.classList.add('drag-over');
}
window.taskDragOver = taskDragOver;

export function taskDragLeave(event) {
  event.currentTarget.classList.remove('drag-over');
}
window.taskDragLeave = taskDragLeave;

export async function taskDrop(event, targetId, targetCat) {
  event.preventDefault();
  document.querySelectorAll('#tasks-list .task-item').forEach(el => el.classList.remove('drag-over', 'dragging'));
  if (!_taskDragId || _taskDragId === targetId || _taskDragCat !== targetCat) {
    _taskDragId = null; return;
  }
  const allItems = [...document.querySelectorAll('#tasks-list .task-item')];
  const ids = allItems.map(el => el.id.replace('ti-', ''));
  const fromIdx = ids.indexOf(_taskDragId);
  const toIdx = ids.indexOf(targetId);
  if (fromIdx < 0 || toIdx < 0) { _taskDragId = null; return; }
  ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, _taskDragId);
  _taskDragId = null;
  try {
    await api('POST', '/api/tasks-order', {order: ids});
    loadTasks();
  } catch(e) { window.showStatus('並び替えエラー: ' + e.message, 'error'); }
}
window.taskDrop = taskDrop;

// ── Drag: categories ──────────────────────────────────────────────────
let _catDragCat = null;

export function catDragStart(event, cat) {
  event.stopPropagation();
  _catDragCat = cat;
  event.dataTransfer.effectAllowed = 'move';
  setTimeout(() => { document.getElementById('catsec-' + cat)?.classList.add('cat-dragging'); }, 0);
}
window.catDragStart = catDragStart;

export function catDragOver(event, cat) {
  if (!_catDragCat || cat === _catDragCat) return;
  event.preventDefault(); event.stopPropagation();
  document.querySelectorAll('.cat-section').forEach(e => e.classList.remove('drag-over-cat'));
  document.getElementById('catsec-' + cat)?.classList.add('drag-over-cat');
}
window.catDragOver = catDragOver;

export function catDragLeave(event) { event.currentTarget.classList.remove('drag-over-cat'); }
window.catDragLeave = catDragLeave;

export function catDrop(event, targetCat) {
  event.preventDefault(); event.stopPropagation();
  document.querySelectorAll('.cat-section').forEach(el => el.classList.remove('drag-over-cat','cat-dragging'));
  if (!_catDragCat || _catDragCat === targetCat) { _catDragCat = null; return; }
  const order = getTasksCatOrder();
  const fi = order.indexOf(_catDragCat), ti = order.indexOf(targetCat);
  if (fi < 0 || ti < 0) { _catDragCat = null; return; }
  order.splice(fi, 1); order.splice(ti, 0, _catDragCat);
  _catDragCat = null;
  saveTasksCatOrder(order);
  loadTasks();
}
window.catDrop = catDrop;

// ── Tag suggestion modal ──────────────────────────────────────────────
export async function suggestTags() {
  window.showStatus('AI がタグを分析中…', 'info', 0);
  try {
    const data = await api('POST', '/api/suggest-tags', {api_key: window.getApiKey ? window.getApiKey() : (localStorage.getItem('qcatch_api_key') || null)});
    document.getElementById('status-bar').classList.remove('show');
    if (!data.suggestions.length) {
      window.showStatus('変更提案はありません（全て適切なカテゴリです）', 'success'); return;
    }
    state.pendingSuggestions = data.suggestions;
    const list = document.getElementById('suggestions-list');
    list.innerHTML = data.suggestions.map((s, i) => `
      <div class="suggestion-item">
        <input type="checkbox" id="sug-${i}" checked>
        <div class="suggestion-text">
          <strong>${esc(s.text)}</strong><br>
          <span style="color:#888">${esc(s.current)}</span>
          <span class="suggestion-arrow">→</span>
          <span style="color:#4fc3f7">${esc(s.suggested)}</span>
        </div>
      </div>`).join('');
    document.getElementById('modal-tags').classList.add('show');
  } catch(e) {
    document.getElementById('status-bar').classList.remove('show');
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.suggestTags = suggestTags;

export async function applyTags() {
  const checked = state.pendingSuggestions.filter((_, i) =>
    document.getElementById('sug-' + i)?.checked
  );
  if (!checked.length) { closeModal(); return; }
  try {
    const res = await api('POST', '/api/apply-tags', {
      suggestions: checked.map(s => ({id: s.id, suggested: s.suggested}))
    });
    closeModal();
    window.showStatus(`✓ ${res.applied} 件のタグを変更しました`, 'success');
    loadTasks();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.applyTags = applyTags;

export function closeModal() {
  document.getElementById('modal-tags').classList.remove('show');
}
window.closeModal = closeModal;

// ── Split suggestion modal ────────────────────────────────────────────
export async function suggestSplits() {
  window.showStatus('AI がサブフォルダを分析中…', 'info', 0);
  try {
    const data = await api('POST', '/api/suggest-splits', {api_key: window.getApiKey ? window.getApiKey() : (localStorage.getItem('qcatch_api_key') || null)});
    document.getElementById('status-bar').classList.remove('show');
    if (!data.suggestions.length) {
      window.showStatus('AI のサブフォルダ提案はありません（各カテゴリ5件未満 or グループが見当たらない）', 'success'); return;
    }
    state.pendingSplits = data.suggestions;
    const byTag = {};
    data.suggestions.forEach((s, i) => {
      if (!byTag[s.suggested_tag]) byTag[s.suggested_tag] = [];
      byTag[s.suggested_tag].push({...s, _idx: i});
    });
    const list = document.getElementById('splits-list');
    list.innerHTML = Object.entries(byTag).map(([tag, items]) => `
      <div style="margin-bottom:14px">
        <div style="font-size:12px;color:#4fc3f7;font-weight:700;margin-bottom:6px">› ${esc(tag)}</div>
        ${items.map(s => `
          <div class="suggestion-item">
            <input type="checkbox" id="spl-${s._idx}" checked>
            <div class="suggestion-text">
              <span style="font-size:13px">${esc(s.text)}</span>
              <span style="font-size:11px;color:#666;margin-left:6px">${esc(s.category)}</span>
            </div>
          </div>`).join('')}
      </div>`).join('');
    document.getElementById('modal-splits').classList.add('show');
  } catch(e) {
    document.getElementById('status-bar').classList.remove('show');
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.suggestSplits = suggestSplits;

export async function applySplits() {
  const checked = state.pendingSplits.filter((_, i) =>
    document.getElementById('spl-' + i)?.checked
  );
  if (!checked.length) { closeSplitsModal(); return; }
  try {
    const res = await api('POST', '/api/apply-splits', {
      splits: checked.map(s => ({task_id: s.task_id, suggested_tag: s.suggested_tag}))
    });
    closeSplitsModal();
    window.showStatus(`✓ ${res.applied} 件にサブフォルダを設定しました`, 'success');
    loadTasks();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.applySplits = applySplits;

export function closeSplitsModal() {
  document.getElementById('modal-splits').classList.remove('show');
}
window.closeSplitsModal = closeSplitsModal;
