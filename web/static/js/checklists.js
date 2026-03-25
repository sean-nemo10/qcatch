import { api } from './api.js';
import { esc, fmtDatetime, isDue } from './utils.js';
import { state } from './state.js';

let _dueClId = null;
let _dueTaskId = null;

// ── Checklists ────────────────────────────────────────────────────────
export async function loadChecklists() {
  const data = await api('GET', '/api/checklists');
  const container = document.getElementById('checklists-list');
  if (!data.checklists.length) {
    container.innerHTML = '<div class="empty">チェックリストがまだありません</div>'; return;
  }
  container.innerHTML = data.checklists.map(cl => {
    const done = cl.items.filter(i => i.done).length;
    const total = cl.items.length;
    return `
    <div class="checklist-card">
      <div class="checklist-head">
        <div style="flex:1;min-width:0">
          <h3 ondblclick="startClNameEdit('${cl.id}',this)" style="cursor:text" title="ダブルクリックで名前を編集">${esc(cl.name)}</h3>
          ${cl.due_date ? `<div style="font-size:11px;color:${isDue(cl.due_date)?'#ff7043':'var(--text-dim)'};margin-top:2px">📅 ${fmtDatetime(cl.due_date)}</div>` : ''}
        </div>
        <span class="cl-progress">${done}/${total}</span>
        <button class="btn btn-ghost btn-sm" onclick="editClDue('${cl.id}','${cl.due_date||''}')">期日</button>
        <button class="btn btn-ghost btn-sm" onclick="resetChecklist('${cl.id}')">リセット</button>
        <button class="btn btn-danger btn-sm" onclick="deleteChecklist('${cl.id}')">削除</button>
      </div>
      <div class="checklist-items">
        ${cl.items.map((item, idx) => `
          <div class="cl-item ${item.done?'done':''}">
            <input type="checkbox" id="cli-${cl.id}-${idx}" ${item.done?'checked':''}
              onchange="toggleClItem('${cl.id}', ${idx}, this.checked)">
            <label for="cli-${cl.id}-${idx}" ondblclick="startClItemEdit('${cl.id}',${idx},this)" style="cursor:text">${esc(item.text)}</label>
            <button class="btn btn-ghost btn-sm" style="opacity:.4;padding:2px 6px;font-size:11px" onclick="deleteClItem('${cl.id}',${idx})">×</button>
          </div>`).join('')}
      </div>
      <div class="checklist-footer">
        <input placeholder="アイテムを追加…" class="form-input" style="margin:0;flex:1" id="cl-add-${cl.id}"
          onkeydown="if(event.key==='Enter')addClItem('${cl.id}')">
        <button class="btn btn-ghost btn-sm" onclick="addClItem('${cl.id}')">追加</button>
      </div>
    </div>`;
  }).join('');
}
window.loadChecklists = loadChecklists;

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
  if (items.length < 2) { window.showStatus('アイテムを2つ以上入力してください', 'error', 2000); return; }
  const due_date = buildDueDate('cl-due-date', 'cl-due-time');
  try {
    await api('POST', '/api/checklists', {name, items, due_date});
    document.getElementById('cl-name').value = '';
    document.getElementById('cl-due-date').value = '';
    document.getElementById('cl-due-time').value = '';
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
