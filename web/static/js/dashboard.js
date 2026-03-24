import { api } from './api.js';
import { state, WEEKDAY_NAMES, CAT_COLORS, IMP_LABEL } from './state.js';
import { esc, fmtDate, fmtDatetime, calcScore, scoreBadge, scoreLabel, isDue } from './utils.js';

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

    container.innerHTML += `
      <div class="dash-section">
        <div style="padding:10px 14px;background:#0d1f2d;border:1px solid #0f3460;border-radius:8px;font-size:13px;display:flex;align-items:center;gap:10px">
          <span>☀️</span>
          <span style="color:#888">AI が今日のフォーカスを分析します</span>
          <button class="btn btn-ghost btn-sm" style="margin-left:auto" onclick="sendBriefing()">朝のブリーフィング</button>
        </div>
      </div>`;

    const _inboxCount = inboxData.tasks.length;
    container.innerHTML += `
      <div class="dash-section">
        <div style="padding:10px 14px;background:${_inboxCount > 0 ? '#1a2a10' : '#0d1f2d'};border:1px solid ${_inboxCount > 0 ? '#2e7d32' : '#0f3460'};border-radius:8px;font-size:13px;display:flex;align-items:center;gap:10px">
          <span>📥</span>
          <span>${_inboxCount > 0 ? `Inbox に <strong>${_inboxCount} 件</strong> の未分類タスク` : 'Inbox は空です'}</span>
          <span style="margin-left:auto;display:flex;gap:6px">
            <button class="btn btn-ghost btn-sm" onclick="switchTabByName('tasks')">✅ タスク</button>
            <button class="btn ${_inboxCount > 0 ? 'btn-warning' : 'btn-ghost'} btn-sm" onclick="switchTabByName('inbox')">📥 Inbox へ</button>
          </span>
        </div>
      </div>`;

    const activeCls = clData.checklists.filter(cl => cl.items.some(i => !i.done));
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
      <div class="dash-item-text">${esc(cl.name)}${cl.due_date?` <span style="font-size:11px;color:${overdue?'#ff7043':'#888'}">📅 ${fmtDatetime(cl.due_date)}</span>`:''}</div>
      <div class="cl-mini-bar"><div class="cl-mini-bar-fill" style="width:${pct}%"></div></div>
      <div class="dash-item-meta">${done}/${total} 完了 — 残り: ${remaining.slice(0,3).map(i=>esc(i.text)).join('、')}${remaining.length>3?'…':''}</div>
    </div>
    <div class="dash-item-actions">
      <button class="btn btn-ghost btn-sm" onclick="switchTabByName('checklists')">開く</button>
    </div>
  </div>`;
}

export function renderTaskDashItem(t, checklists) {
  const catClass = CAT_COLORS[t.category] || 'cat-その他';
  const subtag = t.tags && t.tags[0] ? `<span class="task-subtag">📁 ${esc(t.tags[0])}</span>` : '';
  const badge = scoreBadge(t, checklists || []);
  const tip = scoreLabel(t, checklists || []);
  return `<div class="dash-item type-task" id="dash-${t.id}" draggable="true"
    ondragstart="dashDragStart(event,'${t.id}')"
    ondragover="dashDragOver(event,'${t.id}')"
    ondragleave="dashDragLeave(event)"
    ondrop="dashDrop(event,'${t.id}')">
    <div class="dash-drag-handle" title="ドラッグして並び替え">⠿</div>
    <div class="dash-item-body">
      <div class="dash-item-text" title="${esc(tip)}">${esc(t.text)}${subtag}${badge}</div>
      <div class="dash-item-meta">${t.category?`<span class="task-cat ${catClass}">${esc(t.category)}</span> `:''}${t.due_date?`<span style="color:${new Date(t.due_date)<=new Date()?'#ff7043':'#69f0ae'}">📅${fmtDate(t.due_date)}</span> `:''}${fmtDate(t.created_at)}</div>
    </div>
    <div class="dash-item-actions">
      <button class="imp-btn imp-${t.importance||'medium'}" onclick="cycleImportance('${t.id}','${t.importance||'medium'}')" title="重要度">${IMP_LABEL[t.importance||'medium']}</button>
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
