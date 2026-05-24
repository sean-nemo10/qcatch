import { api } from './api.js';
import { esc, fmtDatetime, isDue } from './utils.js';
import { state } from './state.js';

let _dueClId = null;
let _dueTaskId = null;
let _allChecklists = [];  // 親セレクタ等で使うキャッシュ
// 展開済みID集合（デフォルト=全て閉じている）。
const _expanded = new Set(JSON.parse(localStorage.getItem('cl_expanded') || '[]'));
// 固定（ダッシュボードに展開表示）するチェックリストID集合
const _pinned = new Set(JSON.parse(localStorage.getItem('cl_pinned') || '[]'));

function _persistExpanded() {
  localStorage.setItem('cl_expanded', JSON.stringify([..._expanded]));
}

function _persistPinned() {
  localStorage.setItem('cl_pinned', JSON.stringify([..._pinned]));
}

function _ancestorChain(clId) {
  const chain = [];
  let cur = _allChecklists.find(c => c.id === clId);
  while (cur && cur.parent_id) {
    chain.push(cur.parent_id);
    cur = _allChecklists.find(c => c.id === cur.parent_id);
  }
  return chain;
}

function _toggleExpand(clId) {
  if (_expanded.has(clId)) {
    _expanded.delete(clId);
  } else {
    // アコーディオン: 開くときは祖先チェーン+自分以外を全て閉じる
    const keep = new Set([clId, ..._ancestorChain(clId)]);
    for (const id of [..._expanded]) if (!keep.has(id)) _expanded.delete(id);
    _expanded.add(clId);
  }
  _persistExpanded();
  loadChecklists();
}
window._toggleExpand = _toggleExpand;

window.togglePinChecklist = function(clId) {
  if (_pinned.has(clId)) _pinned.delete(clId);
  else _pinned.add(clId);
  _persistPinned();
  loadChecklists();
  if (window.loadDashboard) window.loadDashboard();
};

window.getPinnedChecklistIds = () => [..._pinned];

window.expandChecklistAndScroll = function(clId) {
  // 祖先チェーン+自分を展開、他は閉じる
  const keep = new Set([clId, ..._ancestorChain(clId)]);
  for (const id of [..._expanded]) if (!keep.has(id)) _expanded.delete(id);
  for (const id of keep) _expanded.add(id);
  _persistExpanded();
  window.switchTabByName('checklists');
  loadChecklists().then(() => {
    setTimeout(() => {
      const el = document.getElementById('cl-card-' + clId);
      if (el) {
        el.scrollIntoView({behavior: 'smooth', block: 'center'});
        el.style.transition = 'background 0.6s';
        el.style.background = '#2a3a1f';
        setTimeout(() => el.style.background = '', 1200);
      }
    }, 100);
  });
};

window.toggleClForm = function() {
  const body = document.getElementById('cl-form-body');
  const btn = document.getElementById('cl-form-toggle');
  const open = body.style.display === 'none';
  body.style.display = open ? 'block' : 'none';
  btn.textContent = open ? '▼ 閉じる' : '▶ 開く';
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
};

function _buildTree(checklists) {
  const byParent = new Map();
  for (const cl of checklists) {
    const key = cl.parent_id || '__root__';
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(cl);
  }
  for (const arr of byParent.values()) {
    arr.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name, 'ja'));
  }
  return byParent;
}

function _aggregateProgress(cl, byParent) {
  let done = cl.items.filter(i => i.done).length;
  let total = cl.items.length;
  for (const child of byParent.get(cl.id) || []) {
    const sub = _aggregateProgress(child, byParent);
    done += sub.done; total += sub.total;
  }
  return {done, total};
}

function _parentOptions(currentId, excludeId) {
  // 循環防止: excludeIdとその子孫は除外
  const descendants = new Set();
  const stack = [excludeId];
  while (stack.length) {
    const id = stack.pop();
    descendants.add(id);
    for (const cl of _allChecklists) if (cl.parent_id === id) stack.push(cl.id);
  }
  return _allChecklists
    .filter(cl => !descendants.has(cl.id))
    .map(cl => `<option value="${cl.id}"${cl.id === currentId ? ' selected' : ''}>${esc(cl.name)}</option>`)
    .join('');
}

function _collectInherited(cl, byId) {
  // 祖先のアイテムを root → 直接親 の順で集める。子に同テキストの own item があれば override として除外。
  const ownTexts = new Set(cl.items.map(i => i.text));
  const chain = [];
  let cur = cl;
  while (cur.parent_id) {
    const p = byId.get(cur.parent_id);
    if (!p) break;
    chain.unshift(p);
    cur = p;
  }
  const inherited = [];
  for (const anc of chain) {
    anc.items.forEach((item, idx) => {
      if (ownTexts.has(item.text)) return;  // override
      inherited.push({srcClId: anc.id, srcIdx: idx, srcName: anc.name, item});
    });
  }
  return inherited;
}

function _renderNode(cl, byParent, byId, depth) {
  const children = byParent.get(cl.id) || [];
  const hasChildren = children.length > 0;
  const inherited = _collectInherited(cl, byId);
  const hasInherited = inherited.length > 0;
  const isFolder = cl.items.length === 0 && hasChildren && !hasInherited;
  const expanded = _expanded.has(cl.id);
  const hasToggle = hasChildren || cl.items.length > 0 || hasInherited;
  const agg = _aggregateProgress(cl, byParent);
  const dueColor = cl.due_date && isDue(cl.due_date) ? '#ff7043' : 'var(--text-dim)';

  const headerToggle = hasToggle
    ? `<button class="btn btn-ghost btn-sm" style="padding:2px 6px;font-size:14px;min-width:24px" onclick="_toggleExpand('${cl.id}')" title="${expanded?'折りたたみ':'展開'}">${expanded?'▼':'▶'}</button>`
    : `<span style="width:24px;display:inline-block"></span>`;

  const inheritedHtml = (expanded && hasInherited) ? inherited.map(info => `
        <div class="cl-item cl-inherited ${info.item.done?'done':''}" style="opacity:.75">
          <input type="checkbox" ${info.item.done?'checked':''}
            onchange="toggleClItem('${info.srcClId}', ${info.srcIdx}, this.checked)">
          <label style="cursor:default;font-style:italic" title="継承元: ${esc(info.srcName)}（同名で自分のアイテムを追加すると上書きできます）">↳ ${esc(info.item.text)}</label>
        </div>`).join('') : '';

  const ownItemsHtml = (expanded && !isFolder) ? cl.items.map((item, idx) => `
        <div class="cl-item ${item.done?'done':''}">
          <input type="checkbox" id="cli-${cl.id}-${idx}" ${item.done?'checked':''}
            onchange="toggleClItem('${cl.id}', ${idx}, this.checked)">
          <label for="cli-${cl.id}-${idx}" ondblclick="startClItemEdit('${cl.id}',${idx},this)" style="cursor:text">${esc(item.text)}</label>
          <button class="btn btn-ghost btn-sm" style="opacity:.4;padding:2px 6px;font-size:11px" onclick="deleteClItem('${cl.id}',${idx})">×</button>
        </div>`).join('') : '';

  const itemsHtml = (expanded && !isFolder) ? `
    <div class="checklist-items">
      ${inheritedHtml}
      ${ownItemsHtml}
    </div>
    <div class="checklist-footer">
      <input placeholder="アイテムを追加…" class="form-input" style="margin:0;flex:1" id="cl-add-${cl.id}"
        onkeydown="if(event.key==='Enter')addClItem('${cl.id}')">
      <button class="btn btn-ghost btn-sm" onclick="addClItem('${cl.id}')">追加</button>
    </div>` : '';

  const childrenHtml = (hasChildren && expanded)
    ? `<div class="cl-children">${children.map(c => _renderNode(c, byParent, byId, depth + 1)).join('')}</div>`
    : '';

  const icon = isFolder ? '📁' : (hasChildren ? '📂' : '📋');
  const childBadge = hasChildren ? `<span style="font-size:11px;color:var(--text-dim);margin-left:6px">▸${children.length}</span>` : '';
  const ownDone = cl.items.filter(i=>i.done).length;
  const inhDone = inherited.filter(i=>i.item.done).length;
  const visibleDone = ownDone + inhDone;
  const visibleTotal = cl.items.length + inherited.length;
  const progressLabel = isFolder
    ? `${agg.done}/${agg.total}`
    : (hasChildren ? `${visibleDone}/${visibleTotal} · 全${agg.done}/${agg.total}` : `${visibleDone}/${visibleTotal}`);
  const pinned = _pinned.has(cl.id);
  const pinBtn = `<button class="btn btn-ghost btn-sm" onclick="togglePinChecklist('${cl.id}')" title="${pinned?'ダッシュボード固定を解除':'ダッシュボードに固定'}" style="color:${pinned?'#ffb300':'var(--text-dim)'}">${pinned?'📌':'📍'}</button>`;

  return `
    <div id="cl-card-${cl.id}" class="checklist-card ${isFolder?'cl-folder':''}" style="margin-left:${depth * 20}px">
      <div class="checklist-head">
        ${headerToggle}
        <div style="flex:1;min-width:0">
          <h3 ondblclick="startClNameEdit('${cl.id}',this)" style="cursor:text" title="ダブルクリックで名前を編集">${icon} ${esc(cl.name)}${childBadge}</h3>
          ${cl.due_date ? `<div style="font-size:11px;color:${dueColor};margin-top:2px">📅 ${fmtDatetime(cl.due_date)}</div>` : ''}
        </div>
        <span class="cl-progress">${progressLabel}</span>
        ${pinBtn}
        <select class="form-select" style="margin:0;font-size:11px;padding:2px 4px;max-width:120px" onchange="setClParent('${cl.id}', this.value)" title="親を変更">
          <option value="">(ルート)</option>
          ${_parentOptions(cl.parent_id || '', cl.id)}
        </select>
        ${isFolder?'':`<button class="btn btn-ghost btn-sm" onclick="editClDue('${cl.id}','${cl.due_date||''}')">期日</button>`}
        ${isFolder?'':`<button class="btn btn-ghost btn-sm" onclick="resetChecklist('${cl.id}')">リセット</button>`}
        <button class="btn btn-ghost btn-sm" onclick="addChildChecklist('${cl.id}')" title="子リストを追加">＋子</button>
        <button class="btn btn-danger btn-sm" onclick="deleteChecklist('${cl.id}')">削除</button>
      </div>
      ${childrenHtml}
      ${itemsHtml}
    </div>`;
}

// ── Checklists ────────────────────────────────────────────────────────
export async function loadChecklists() {
  const data = await api('GET', '/api/checklists');
  _allChecklists = data.checklists;
  _refreshParentSelector();
  const container = document.getElementById('checklists-list');
  if (!data.checklists.length) {
    container.innerHTML = '<div class="empty">チェックリストがまだありません</div>'; return;
  }
  const byParent = _buildTree(data.checklists);
  const byId = new Map(data.checklists.map(c => [c.id, c]));
  const roots = byParent.get('__root__') || [];
  // 親IDが存在しないorphanもルートに混ぜる
  const knownIds = new Set(data.checklists.map(c => c.id));
  const orphans = data.checklists.filter(c => c.parent_id && !knownIds.has(c.parent_id));
  const allRoots = [...roots, ...orphans];
  container.innerHTML = allRoots.map(cl => _renderNode(cl, byParent, byId, 0)).join('');
}
window.loadChecklists = loadChecklists;

function _refreshParentSelector() {
  const sel = document.getElementById('cl-parent');
  if (!sel) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">(ルート)</option>' +
    _allChecklists.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  sel.value = cur;
}

export async function setClParent(clId, parentId) {
  try {
    await api('PATCH', `/api/checklists/${clId}`, {parent_id: parentId || null});
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); loadChecklists(); }
}
window.setClParent = setClParent;

export async function addChildChecklist(parentId) {
  const name = prompt('子リストの名前:');
  if (!name || !name.trim()) return;
  try {
    await api('POST', '/api/checklists', {name: name.trim(), items: [], parent_id: parentId});
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.addChildChecklist = addChildChecklist;

export function addClItemInput() {
  const c = document.getElementById('cl-items-inputs');
  const count = c.querySelectorAll('input').length + 1;
  const row = document.createElement('div');
  row.className = 'form-row';
  row.innerHTML = `<input name="cl-item" aria-label="チェックリストアイテム" placeholder="アイテム ${count}" class="cl-item-input" style="flex:1">`;
  c.appendChild(row);
}
window.addClItemInput = addClItemInput;

export async function createChecklist() {
  const name = document.getElementById('cl-name').value.trim();
  if (!name) { window.showStatus('チェックリスト名を入力してください', 'error', 2000); return; }
  const items = [...document.querySelectorAll('.cl-item-input')]
    .map(i => i.value.trim()).filter(Boolean);
  const due_date = buildDueDate('cl-due-date', 'cl-due-time');
  const parent_id = document.getElementById('cl-parent')?.value || null;
  try {
    await api('POST', '/api/checklists', {name, items, due_date, parent_id});
    document.getElementById('cl-name').value = '';
    document.getElementById('cl-due-date').value = '';
    document.getElementById('cl-due-time').value = '';
    const ps = document.getElementById('cl-parent'); if (ps) ps.value = '';
    document.getElementById('cl-items-inputs').innerHTML = '<div class="form-row"><input name="cl-item" aria-label="チェックリストアイテム" placeholder="アイテム 1" class="cl-item-input" style="flex:1"></div><div class="form-row"><input name="cl-item" aria-label="チェックリストアイテム" placeholder="アイテム 2" class="cl-item-input" style="flex:1"></div>';
    window.showStatus('チェックリストを作成しました', 'success');
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.createChecklist = createChecklist;

export function buildDueDate(dateId, timeId) {
  const d = document.getElementById(dateId).value;
  if (!d) return null;
  const t = document.getElementById(timeId).value;
  return new Date(t ? `${d}T${t}` : `${d}T00:00`).toISOString();
}
window.buildDueDate = buildDueDate;

// ── Due date modal ────────────────────────────────────────────────────
export function editTaskDue(taskId, currentDue) {
  _dueTaskId = taskId;
  _dueClId = null;
  if (currentDue) {
    const dt = new Date(currentDue);
    document.getElementById('modal-due-date').value = dt.toISOString().slice(0,10);
    const h = String(dt.getHours()).padStart(2,'0');
    const m = String(dt.getMinutes()).padStart(2,'0');
    document.getElementById('modal-due-time').value = (h === '00' && m === '00') ? '' : `${h}:${m}`;
  } else {
    document.getElementById('modal-due-date').value = '';
    document.getElementById('modal-due-time').value = '';
  }
  document.getElementById('modal-due').classList.add('show');
  setTimeout(() => document.getElementById('modal-due-date').focus(), 50);
}
window.editTaskDue = editTaskDue;

export function editClDue(clId, currentDue) {
  _dueTaskId = null;
  _dueClId = clId;
  if (currentDue) {
    const dt = new Date(currentDue);
    document.getElementById('modal-due-date').value = dt.toISOString().slice(0,10);
    const h = String(dt.getHours()).padStart(2,'0');
    const m = String(dt.getMinutes()).padStart(2,'0');
    document.getElementById('modal-due-time').value = (h === '00' && m === '00') ? '' : `${h}:${m}`;
  } else {
    document.getElementById('modal-due-date').value = '';
    document.getElementById('modal-due-time').value = '';
  }
  document.getElementById('modal-due').classList.add('show');
  setTimeout(() => document.getElementById('modal-due-date').focus(), 50);
}
window.editClDue = editClDue;

export function closeDueModal() {
  document.getElementById('modal-due').classList.remove('show');
  _dueClId = null;
  _dueTaskId = null;
}
window.closeDueModal = closeDueModal;

export function setDueQuick(daysFromNow) {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  document.getElementById('modal-due-date').value = d.toISOString().slice(0, 10);
  document.getElementById('modal-due-time').value = '';
}
window.setDueQuick = setDueQuick;

export async function saveDue(clear) {
  if (!_dueClId && !_dueTaskId) return;
  const due_date = clear ? null : buildDueDate('modal-due-date', 'modal-due-time');
  try {
    if (_dueTaskId) {
      await api('PATCH', `/api/tasks/${_dueTaskId}`, {due_date});
      window.showStatus(clear ? '期日をクリアしました' : '期日を保存しました', 'success', 2000);
      closeDueModal();
      if (state.activePane === 'longterm') window.loadLongterm(); else window.loadTasks();
    } else {
      await api('PATCH', `/api/checklists/${_dueClId}`, {due_date});
      window.showStatus(clear ? '期日をクリアしました' : '期日を保存しました', 'success', 2000);
      closeDueModal();
      loadChecklists();
      if (document.getElementById('pane-dashboard').classList.contains('active')) window.loadDashboard();
    }
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.saveDue = saveDue;

// ── Checklist items ───────────────────────────────────────────────────
export async function toggleClItem(clId, idx, done) {
  try {
    await api('PATCH', `/api/checklists/${clId}/items`, {item_index: idx, done});
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.toggleClItem = toggleClItem;

export async function resetChecklist(clId) {
  try {
    await api('POST', `/api/checklists/${clId}/reset`);
    window.showStatus('リセットしました', 'success', 2000);
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.resetChecklist = resetChecklist;

export async function addClItem(clId) {
  const inp = document.getElementById('cl-add-' + clId);
  const text = inp.value.trim();
  if (!text) return;
  try {
    await api('POST', `/api/checklists/${clId}/items`, {text});
    inp.value = '';
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.addClItem = addClItem;

export function startClItemEdit(clId, idx, labelEl) {
  const orig = labelEl.textContent;
  const inp = document.createElement('input');
  inp.value = orig;
  inp.style.cssText = 'flex:1;padding:2px 6px;background:var(--surface-deep);border:1px solid var(--accent);border-radius:4px;color:var(--text);font-size:14px;font-family:inherit';
  labelEl.replaceWith(inp);
  inp.focus(); inp.select();
  const finish = async () => {
    const text = inp.value.trim() || orig;
    const lbl = document.createElement('label');
    lbl.textContent = text;
    lbl.style.cursor = 'text';
    lbl.setAttribute('for', `cli-${clId}-${idx}`);
    lbl.ondblclick = () => startClItemEdit(clId, idx, lbl);
    inp.replaceWith(lbl);
    if (text !== orig) {
      try { await api('PATCH', `/api/checklists/${clId}/items`, {item_index: idx, text}); }
      catch(e) { window.showStatus('エラー: ' + e.message, 'error'); loadChecklists(); }
    }
  };
  inp.onblur = finish;
  inp.onkeydown = e => { if (e.key === 'Enter') inp.blur(); if (e.key === 'Escape') { inp.value = orig; inp.blur(); } };
}
window.startClItemEdit = startClItemEdit;

export function startClNameEdit(clId, h3El) {
  const orig = h3El.textContent;
  const inp = document.createElement('input');
  inp.value = orig;
  inp.style.cssText = 'font-size:15px;font-weight:600;background:transparent;border:none;border-bottom:1px solid var(--accent);color:var(--text);width:100%;font-family:inherit;outline:none';
  h3El.replaceWith(inp);
  inp.focus(); inp.select();
  const finish = async () => {
    const name = inp.value.trim() || orig;
    const newH3 = document.createElement('h3');
    newH3.textContent = name;
    newH3.style.cursor = 'text';
    newH3.title = 'ダブルクリックで名前を編集';
    newH3.ondblclick = () => startClNameEdit(clId, newH3);
    inp.replaceWith(newH3);
    if (name !== orig) {
      try { await api('PATCH', `/api/checklists/${clId}`, {name}); }
      catch(e) { window.showStatus('エラー: ' + e.message, 'error'); loadChecklists(); }
    }
  };
  inp.onblur = finish;
  inp.onkeydown = e => { if (e.key === 'Enter') inp.blur(); if (e.key === 'Escape') { inp.value = orig; inp.blur(); } };
}
window.startClNameEdit = startClNameEdit;

export async function deleteClItem(clId, idx) {
  try {
    await api('DELETE', `/api/checklists/${clId}/items/${idx}`);
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.deleteClItem = deleteClItem;

export async function deleteChecklist(clId) {
  if (!confirm('このチェックリストを削除しますか？')) return;
  try {
    await api('DELETE', `/api/checklists/${clId}`);
    window.showStatus('削除しました', 'info', 2000);
    loadChecklists();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.deleteChecklist = deleteChecklist;
