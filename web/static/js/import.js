import { api } from './api.js';
import { esc, fmtDate } from './utils.js';
import { state } from './state.js';

const _IMPORT_CATS = ['仕事','プライベート','買い物','学習','その他'];
let _importTasks = [];

// called from inline onchange in preview HTML
function _setImportCat(idx, val) {
  if (_importTasks[idx]) _importTasks[idx].category = val || null;
}
window._setImportCat = _setImportCat;

export function openImportModal() {
  document.getElementById('import-preview-section').style.display = 'none';
  document.getElementById('import-exec-btn').style.display = 'none';
  _importTasks = [];
  document.getElementById('modal-import').classList.add('show');
  setTimeout(() => document.getElementById('import-textarea').focus(), 50);
}
window.openImportModal = openImportModal;

export function closeImportModal() {
  document.getElementById('modal-import').classList.remove('show');
  _importTasks = [];
}
window.closeImportModal = closeImportModal;

export function clearImport() {
  document.getElementById('import-textarea').value = '';
  document.getElementById('import-preview-section').style.display = 'none';
  document.getElementById('import-exec-btn').style.display = 'none';
  _importTasks = [];
}
window.clearImport = clearImport;

export function parseBulkText(rawText) {
  const lines = rawText.split('\n');
  const tasks = [];
  let sectionCategory = null;

  for (const rawLine of lines) {
    let line = rawLine.trim();
    if (!line) continue;

    if (!line.match(/^[-*•\d]/)) {
      const hm = line.match(/^#+\s+(.+)$/) ||
                 line.match(/^\*{1,2}(.+?)\*{1,2}[：:。]?\s*$/) ||
                 line.match(/^【(.+?)】\s*$/) ||
                 line.match(/^(.+?)[：:]\s*$/);
      if (hm) {
        const name = (hm[1] || '').trim().replace(/[。\.！!]$/, '');
        if (_IMPORT_CATS.includes(name)) { sectionCategory = name; continue; }
      }
    }

    line = line
      .replace(/^[-*•]\s*\[[ xX✓]\]\s*/, '')
      .replace(/^[-*•]\s+/, '')
      .replace(/^\d+[.)]\s+/, '')
      .replace(/^\*{1,2}(.+?)\*{1,2}$/, '$1')
      .trim();

    if (!line || line.startsWith('#')) continue;

    let category = sectionCategory;
    const catM = line.match(/\s*[(\[（【]([^\)）\]】]+)[)\]）】]\s*$/);
    if (catM && _IMPORT_CATS.includes(catM[1])) {
      category = catM[1];
      line = line.slice(0, catM.index).trim();
    }

    let due_date = null;
    const dueM = line.match(/\s*[\(（]?期日[：:]\s*(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})[\)）]?/);
    if (dueM) {
      try {
        due_date = new Date(dueM[1].replace(/\//g, '-') + 'T00:00:00').toISOString();
        line = line.replace(dueM[0], '').trim();
      } catch {}
    }

    if (line) tasks.push({ text: line, category: category || null, due_date });
  }
  return tasks;
}
window.parseBulkText = parseBulkText;

export function previewImport() {
  const raw = document.getElementById('import-textarea').value;
  if (!raw.trim()) { window.showStatus('テキストを貼り付けてください', 'info', 2000); return; }

  _importTasks = parseBulkText(raw);
  const section = document.getElementById('import-preview-section');
  const preview = document.getElementById('import-preview');
  const countEl = document.getElementById('import-count');
  const execBtn = document.getElementById('import-exec-btn');

  if (!_importTasks.length) {
    countEl.textContent = '解析できるタスクが見つかりませんでした';
    countEl.style.color = '#e53935';
    section.style.display = '';
    execBtn.style.display = 'none';
    preview.innerHTML = '<div style="font-size:13px;color:#666;padding:10px 0">テキストを確認してください。箇条書き（- / * / 1.）や1行1タスク形式に対応しています。</div>';
    return;
  }

  countEl.textContent = `${_importTasks.length} 件のタスクを検出`;
  countEl.style.color = '#4fc3f7';
  preview.innerHTML = _importTasks.map((t, i) => `
    <div class="import-item" id="iitem-${i}">
      <button class="import-item-remove" onclick="removeImportItem(${i})" title="このタスクを除外">✕</button>
      <div class="import-item-text" title="${esc(t.text)}">${esc(t.text)}</div>
      ${t.due_date ? `<span style="font-size:11px;color:#69f0ae;white-space:nowrap;flex-shrink:0">📅${fmtDate(t.due_date)}</span>` : ''}
      <select class="import-item-cat" onchange="_setImportCat(${i},this.value)" aria-label="カテゴリ">
        <option value="">未分類 (Inbox)</option>
        ${_IMPORT_CATS.map(c => `<option value="${c}"${t.category===c?' selected':''}>${c}</option>`).join('')}
      </select>
    </div>`).join('');

  execBtn.textContent = `${_importTasks.length} 件をすべて追加`;
  execBtn.style.display = '';
  section.style.display = '';
}
window.previewImport = previewImport;

export function removeImportItem(idx) {
  _importTasks[idx] = null;
  const el = document.getElementById('iitem-' + idx);
  if (el) el.remove();
  const remaining = _importTasks.filter(Boolean).length;
  document.getElementById('import-count').textContent = `${remaining} 件のタスクを検出`;
  const execBtn = document.getElementById('import-exec-btn');
  execBtn.textContent = `${remaining} 件をすべて追加`;
  if (!remaining) execBtn.style.display = 'none';
}
window.removeImportItem = removeImportItem;


export async function executeImport() {
  const items = _importTasks.filter(Boolean);
  if (!items.length) return;
  try {
    const res = await api('POST', '/api/tasks/bulk', items);
    closeImportModal();
    window.showStatus(`✓ ${res.added} 件のタスクを追加しました`, 'success');
    window.updateBadges();
    if (state.activePane === 'inbox') window.loadInbox();
    else if (state.activePane === 'tasks') window.loadTasks();
  } catch(e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.executeImport = executeImport;
