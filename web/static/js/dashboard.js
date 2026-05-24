import { api } from './api.js';
import { state, WEEKDAY_NAMES, CAT_COLORS, IMP_LABEL } from './state.js';
import { esc, fmtDate, fmtDatetime, calcScore, scoreBadge, scoreLabel, isDue } from './utils.js';

// ── Dashboard state ───────────────────────────────────────────────────
let _dashAllTasks = [];

// ── Dashboard load ────────────────────────────────────────────────────
export async function loadDashboard() {
  const container = document.getElementById('dashboard-content');
  container.innerHTML = '<div class="empty">読み込み中...</div>';
  try {
    const [tasksData, clData, recData, inboxData, orderData] = await Promise.all([
      api('GET', '/api/tasks?status=todo'),
      api('GET', '/api/checklists'),
      api('GET', '/api/recurring'),
      api('GET', '/api/tasks?status=inbox'),
      api('GET', '/api/dashboard-order'),
    ]);
    container.innerHTML = '';

    const _inboxCount = inboxData.tasks.length;
    if (_inboxCount > 0) {
      container.innerHTML += `
      <div class="dash-section">
        <div style="padding:10px 14px;background:#1a2a10;border:1px solid #2e7d32;border-radius:8px;font-size:13px;display:flex;align-items:center;gap:10px">
          <span>📥</span>
          <span>Inbox に <strong>${_inboxCount} 件</strong> の未分類タスク</span>
          <button class="btn btn-warning btn-sm" style="margin-left:auto" onclick="switchTabByName('inbox')">整理する</button>
        </div>
      </div>`;
    }

    // ── 固定チェックリスト（フル表示） ──
    const pinnedIds = new Set((window.getPinnedChecklistIds ? window.getPinnedChecklistIds() : []));
    const pinnedCls = clData.checklists.filter(cl => pinnedIds.has(cl.id));
    if (pinnedCls.length) {
      const byId = new Map(clData.checklists.map(c => [c.id, c]));
      let html = `<div class="dash-section">
        <div class="dash-section-title"><h2>📌 固定チェックリスト</h2><span class="count">${pinnedCls.length}</span></div>`;
      pinnedCls.forEach(cl => html += renderPinnedChecklist(cl, byId));
      html += '</div>';
      container.innerHTML += html;
    }

    const activeCls = clData.checklists.filter(cl => cl.items.some(i => !i.done) && !pinnedIds.has(cl.id));
    const clWithDue  = activeCls.filter(cl => cl.due_date).sort((a,b) => new Date(a.due_date)-new Date(b.due_date));
    const clNoDue    = activeCls.filter(cl => !cl.due_date);
    const _orderMap = {};
    (orderData.order || []).forEach((id, i) => { _orderMap[id] = i; });
    const tasks = tasksData.tasks.slice().sort((a, b) => {
      const aPos = _orderMap[a.id] ?? Infinity;
      const bPos = _orderMap[b.id] ?? Infinity;
      if (aPos !== bPos) return aPos - bPos;
      return calcScore(b, clData.checklists).score - calcScore(a, clData.checklists).score;
    });
    _dashAllTasks = tasks;
    const hasAnything = activeCls.length || tasks.length || recData.recurring.length || inboxData.tasks.length;

    if (clWithDue.length) {
      let html = `<div class="dash-section">
        <div class="dash-section-title"><h2>📅 期日あり</h2><span class="count">${clWithDue.length}</span></div>`;
      clWithDue.forEach(cl => html += renderClDashItem(cl));
      html += '</div>';
      container.innerHTML += html;
    }

    const _spotlight = (() => {
      const cutoff = new Date(); cutoff.setDate(cutoff.getDate() + 2); cutoff.setHours(0,0,0,0);
      return tasks.filter(t => t.importance === 'high' || (t.due_date && new Date(t.due_date) < cutoff));
    })();
    const _spotIds = new Set(_spotlight.map(t => t.id));
    const _restTasks = tasks.filter(t => !_spotIds.has(t.id));

    if (_spotlight.length) {
      let html = `<div class="dash-section" style="border:1px solid #e65100;background:#1a0e00;border-radius:8px">
        <div class="dash-section-title"><h2 style="color:#ffb300">🔥 注目</h2><span class="count">${_spotlight.length}</span></div>`;
      _spotlight.forEach(t => { html += renderTaskDashItem(t, clData.checklists); });
      html += '</div>';
      container.innerHTML += html;
    }
    if (_restTasks.length) {
      let html = `<div class="dash-section">
        <div class="dash-section-title"><h2>📋 タスク</h2><span class="count">${_restTasks.length}</span></div>`;
      _restTasks.forEach(t => { html += renderTaskDashItem(t, clData.checklists); });
      html += '</div>';
      container.innerHTML += html;
    } else if (!_spotlight.length && tasks.length) {
      let html = `<div class="dash-section">
        <div class="dash-section-title"><h2>📋 タスク</h2><span class="count">${tasks.length}</span></div>`;
      tasks.forEach(t => { html += renderTaskDashItem(t, clData.checklists); });
      html += '</div>';
      container.innerHTML += html;
    }

    if (recData.recurring.length) {
      let html = `<div class="dash-section">
        <div class="dash-section-title"><h2>🔄 定期タスク</h2><span class="count">${recData.recurring.length}</span></div>`;
      recData.recurring.forEach(r => {
        const freq = r.frequency === 'daily' ? '毎日'
          : r.frequency === 'monthly' ? `毎月 ${r.day_of_month} 日`
          : '毎週 ' + (r.days_of_week.map(d => WEEKDAY_NAMES[d]).join('・') || '未設定');
        html += `<div class="dash-item type-recurring">
          <div class="dash-item-icon">🔄</div>
          <div class="dash-item-body">
            <div class="dash-item-text">${esc(r.text)}</div>
            <div class="dash-item-meta">${freq}${r.category?' · '+esc(r.category):''}${r.last_generated_date?' · 最終: '+r.last_generated_date:''}</div>
          </div>
        </div>`;
      });
      html += '</div>';
      container.innerHTML += html;
    }

    if (clNoDue.length) {
      let html = `<div class="dash-section">
        <div class="dash-section-title"><h2>📋 チェックリスト</h2><span class="count">${clNoDue.length}</span></div>`;
      clNoDue.forEach(cl => html += renderClDashItem(cl));
      html += '</div>';
      container.innerHTML += html;
    }

    if (!hasAnything) {
      container.innerHTML = '<div class="empty">すべてのタスクが完了しています 🎉</div>';
    }
  } catch(e) {
    container.innerHTML = `<div class="empty" style="color:#e53935">読み込みエラー: ${esc(e.message)}</div>`;
  }
}
window.loadDashboard = loadDashboard;

export function renderClDashItem(cl) {
  const done = cl.items.filter(i => i.done).length;
  const total = cl.items.length;
  const pct = total ? Math.round(done / total * 100) : 0;
  const remaining = cl.items.filter(i => !i.done);
  const overdue = cl.due_date && isDue(cl.due_date);
  return `<div class="dash-item type-checklist">
    <div class="dash-item-icon">📋</div>
    <div class="dash-item-body">
      <div class="dash-item-text">${esc(cl.name)}${cl.due_date?` <span style="font-size:11px;color:${overdue?'#ff7043':'var(--text-dim)'}">📅 ${fmtDatetime(cl.due_date)}</span>`:''}</div>
      <div class="cl-mini-bar"><div class="cl-mini-bar-fill" style="width:${pct}%"></div></div>
      <div class="dash-item-meta">${done}/${total} 完了 — 残り: ${remaining.slice(0,3).map(i=>esc(i.text)).join('、')}${remaining.length>3?'…':''}</div>
    </div>
    <div class="dash-item-actions">
      <button class="btn btn-success btn-sm" onclick="checklistToTasks('${cl.id}')" title="未完了アイテムをタスクとして追加">今日やる</button>
      <button class="btn btn-ghost btn-sm" onclick="expandChecklistAndScroll('${cl.id}')">開く</button>
    </div>
  </div>`;
}

export function renderPinnedChecklist(cl, byId) {
  // 自分の items + 祖先からの継承
  const ownTexts = new Set(cl.items.map(i => i.text));
  const inherited = [];
  let cur = cl;
  while (cur.parent_id) {
    const p = byId.get(cur.parent_id);
    if (!p) break;
    p.items.forEach((item, idx) => {
      if (!ownTexts.has(item.text)) inherited.push({srcClId: p.id, srcIdx: idx, srcName: p.name, item});
    });
    cur = p;
  }
  const allItems = inherited.length + cl.items.length;
  const allDone = inherited.filter(i=>i.item.done).length + cl.items.filter(i=>i.done).length;
  const inhRows = inherited.map(info => `
    <div class="cl-item ${info.item.done?'done':''}" style="opacity:.75">
      <input type="checkbox" ${info.item.done?'checked':''} onchange="toggleClItem('${info.srcClId}', ${info.srcIdx}, this.checked); loadDashboard()">
      <label style="cursor:default;font-style:italic" title="継承元: ${esc(info.srcName)}">↳ ${esc(info.item.text)}</label>
    </div>`).join('');
  const ownRows = cl.items.map((item, idx) => `
    <div class="cl-item ${item.done?'done':''}">
      <input type="checkbox" ${item.done?'checked':''} onchange="toggleClItem('${cl.id}', ${idx}, this.checked); loadDashboard()">
      <label style="cursor:text">${esc(item.text)}</label>
    </div>`).join('');
  return `<div class="checklist-card" style="margin-bottom:8px">
    <div class="checklist-head">
      <div style="flex:1;min-width:0"><h3>📌 ${esc(cl.name)}</h3></div>
      <span class="cl-progress">${allDone}/${allItems}</span>
      <button class="btn btn-ghost btn-sm" onclick="togglePinChecklist('${cl.id}')" title="固定を解除" style="color:#ffb300">📌</button>
      <button class="btn btn-ghost btn-sm" onclick="resetChecklist('${cl.id}').then(()=>loadDashboard())">リセット</button>
      <button class="btn btn-ghost btn-sm" onclick="expandChecklistAndScroll('${cl.id}')">編集</button>
    </div>
    <div class="checklist-items">${inhRows}${ownRows}</div>
  </div>`;
}
window.renderPinnedChecklist = renderPinnedChecklist;

export async function checklistToTasks(clId) {
  try {
    const data = await api('GET', '/api/checklists');
    const byId = new Map(data.checklists.map(c => [c.id, c]));
    const cl = byId.get(clId);
    if (!cl) { window.showStatus('チェックリストが見つかりません', 'error'); return; }
    // 自分の未完了 + 継承（祖先）未完了 を集める
    const seen = new Set();
    const texts = [];
    cl.items.forEach(i => { if (!i.done && !seen.has(i.text)) { texts.push(i.text); seen.add(i.text); } });
    let cur = cl;
    while (cur.parent_id) {
      const p = byId.get(cur.parent_id);
      if (!p) break;
      p.items.forEach(i => { if (!i.done && !seen.has(i.text)) { texts.push(i.text); seen.add(i.text); } });
      cur = p;
    }
    if (!texts.length) { window.showStatus('未完了アイテムがありません', 'info', 2000); return; }
    for (const text of texts) {
      await api('POST', '/api/tasks', {text: `${cl.name}: ${text}`, auto_classify: true});
    }
    window.showStatus(`${texts.length}件のタスクを追加しました`, 'success');
    loadDashboard();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.checklistToTasks = checklistToTasks;

export function renderTaskDashItem(t, checklists) {
  const catClass = CAT_COLORS[t.category] || 'cat-その他';
  const catBadge = t.category ? `<span class="task-cat ${catClass}" style="font-size:10px;padding:1px 7px">${esc(t.category)}</span>` : '';
  const subtag = t.tags && t.tags[0] ? `<span class="task-subtag">📁 ${esc(t.tags[0])}</span>` : '';
  const badge = scoreBadge(t, checklists || []);
  const tip = scoreLabel(t, checklists || []);
  const dueColor = t.due_date && new Date(t.due_date) <= new Date() ? '#ff7043' : '#69f0ae';
  const duePart = t.due_date ? `<span style="color:${dueColor}">📅${fmtDate(t.due_date)}</span>` : '';
  return `<div class="dash-item type-task" id="dash-${t.id}" draggable="true"
    ondragstart="dashDragStart(event,'${t.id}')"
    ondragover="dashDragOver(event,'${t.id}')"
    ondragleave="dashDragLeave(event)"
    ondrop="dashDrop(event,'${t.id}')">
    <div class="dash-drag-handle" title="ドラッグして並び替え">⠿</div>
    <div class="dash-item-body">
      <div class="dash-item-text" title="${esc(tip)}">${catBadge} ${esc(t.text)}${subtag}${badge}</div>
      <div class="dash-item-meta">${duePart}${duePart?' · ':''}${fmtDate(t.created_at)}</div>
    </div>
    <div class="dash-item-actions">
      <button class="imp-btn imp-${t.importance||'medium'}" onclick="cycleImportance('${t.id}','${t.importance||'medium'}')" title="重要度">${IMP_LABEL[t.importance||'medium']}</button>
      <button class="btn btn-ghost btn-sm" onclick="openTaskEditModal('${t.id}')">編集</button>
      <button class="btn btn-success btn-sm" onclick="dashComplete('${t.id}')">完了</button>
      <button class="btn btn-ghost btn-sm" onclick="dashTrash('${t.id}')">削除</button>
    </div>
  </div>`;
}

export function groupByDate(tasks) {
  const now = new Date();
  const todayStr = now.toDateString();
  const yest = new Date(now); yest.setDate(yest.getDate() - 1);
  const yestStr = yest.toDateString();
  const weekAgo = new Date(now); weekAgo.setDate(weekAgo.getDate() - 7);

  const groups = {'今日':[], '昨日':[], '今週':[], 'それ以前':[]};
  tasks.forEach(t => {
    const d = new Date(t.created_at);
    const ds = d.toDateString();
    if (ds === todayStr) groups['今日'].push(t);
    else if (ds === yestStr) groups['昨日'].push(t);
    else if (d >= weekAgo) groups['今週'].push(t);
    else groups['それ以前'].push(t);
  });
  return groups;
}

// ── Dashboard complete/trash ──────────────────────────────────────────
export async function dashComplete(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status:'done'});
    const el = document.getElementById('dash-' + id);
    if (el) el.remove();
    window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.dashComplete = dashComplete;

export async function dashTrash(id) {
  try {
    await api('PATCH', `/api/tasks/${id}`, {status:'trashed'});
    const el = document.getElementById('dash-' + id);
    if (el) el.remove();
    window.updateBadges();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.dashTrash = dashTrash;

// ── Dashboard drag ────────────────────────────────────────────────────
let _dashDragId = null;

export function dashDragStart(event, id) {
  _dashDragId = id;
  event.dataTransfer.effectAllowed = 'move';
  setTimeout(() => {
    const el = document.getElementById('dash-' + id);
    if (el) el.classList.add('dragging');
  }, 0);
}
window.dashDragStart = dashDragStart;

export function dashDragOver(event, id) {
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  if (id === _dashDragId) return;
  document.querySelectorAll('.dash-item.type-task').forEach(el => el.classList.remove('drag-over'));
  const el = document.getElementById('dash-' + id);
  if (el) el.classList.add('drag-over');
}
window.dashDragOver = dashDragOver;

export function dashDragLeave(event) {
  event.currentTarget.classList.remove('drag-over');
}
window.dashDragLeave = dashDragLeave;

export async function dashDrop(event, targetId) {
  event.preventDefault();
  document.querySelectorAll('.dash-item.type-task').forEach(el => {
    el.classList.remove('drag-over', 'dragging');
  });
  if (!_dashDragId || _dashDragId === targetId) { _dashDragId = null; return; }

  const items = [...document.querySelectorAll('#dashboard-content .dash-item.type-task')];
  const ids = items.map(el => el.id.replace('dash-', ''));
  const fromIdx = ids.indexOf(_dashDragId);
  const toIdx = ids.indexOf(targetId);
  if (fromIdx < 0 || toIdx < 0) { _dashDragId = null; return; }

  ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, _dashDragId);
  _dashDragId = null;

  try {
    await api('POST', '/api/dashboard-order', {order: ids});
    loadDashboard();
  } catch(e) { window.showStatus('並び替えエラー: ' + e.message, 'error'); }
}
window.dashDrop = dashDrop;

// ── タスク編集モーダル ────────────────────────────────────────────────
export function openTaskEditModal(taskId) {
  const task = _dashAllTasks.find(t => t.id === taskId);
  if (!task) return;
  document.getElementById('edit-task-id').value = taskId;
  document.getElementById('edit-task-text').value = task.text;
  document.getElementById('edit-task-cat').value = task.category || '';
  document.getElementById('edit-task-imp').value = task.importance || 'medium';
  document.getElementById('edit-task-due').value = task.due_date
    ? task.due_date.slice(0, 10)
    : '';
  const modal = document.getElementById('task-edit-modal');
  modal.classList.add('show');
  setTimeout(() => document.getElementById('edit-task-text')?.focus(), 50);
}
window.openTaskEditModal = openTaskEditModal;

export function closeTaskEditModal() {
  document.getElementById('task-edit-modal').classList.remove('show');
}
window.closeTaskEditModal = closeTaskEditModal;

export async function saveTaskEdit() {
  const id = document.getElementById('edit-task-id').value;
  const text = document.getElementById('edit-task-text').value.trim();
  const category = document.getElementById('edit-task-cat').value || null;
  const importance = document.getElementById('edit-task-imp').value;
  const dueVal = document.getElementById('edit-task-due').value;
  const due_date = dueVal ? dueVal + 'T00:00:00' : null;

  if (!text) { window.showStatus('タスク内容を入力してください', 'error'); return; }

  try {
    const patch = { text, importance };
    if (category !== undefined) patch.category = category;
    // due_date: null でも送って上書きできるように model_fields_set を活用
    patch.due_date = due_date;
    await api('PATCH', `/api/tasks/${id}`, patch);
    closeTaskEditModal();
    loadDashboard();
    window.showStatus('タスクを更新しました', 'success', 2000);
  } catch(e) { window.showStatus('更新エラー: ' + e.message, 'error'); }
}
window.saveTaskEdit = saveTaskEdit;
