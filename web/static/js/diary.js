import { api } from './api.js';
import { esc } from './utils.js';
import { getApiKey } from './settings.js';

let _diaryDebounce = null;
let _blogDebounce = null;
let _editingBlogId = null;
let _writingMode = 'diary';

function _todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// ── Writing mode ──────────────────────────────────────────────────────
export function setWritingMode(mode) {
  _writingMode = mode;
  document.getElementById('writing-diary').style.display = mode === 'diary' ? '' : 'none';
  document.getElementById('writing-blog').style.display = mode === 'blog' ? '' : 'none';
  document.getElementById('mode-btn-diary').classList.toggle('active', mode === 'diary');
  document.getElementById('mode-btn-blog').classList.toggle('active', mode === 'blog');
  if (mode === 'blog') loadBlogList();
}
window.setWritingMode = setWritingMode;

export function initDiaryPane() {
  const picker = document.getElementById('diary-date');
  if (!picker.value) picker.value = _todayStr();
  loadDiary();
  loadDiaryHistory();
}
window.initDiaryPane = initDiaryPane;

// ── Diary ─────────────────────────────────────────────────────────────
export async function loadDiary() {
  const date = document.getElementById('diary-date').value;
  if (!date) return;
  document.getElementById('diary-save-status').textContent = '';
  closeSuggestPanel('diary');
  try {
    const entry = await api('GET', `/api/diary/${date}`);
    document.getElementById('diary-textarea').value = entry.content;
  } catch(e) {
    document.getElementById('diary-textarea').value = '';
  }
  document.querySelectorAll('#diary-history-list .diary-history-item').forEach(el => {
    el.classList.toggle('active-item', el.dataset.date === date);
  });
}
window.loadDiary = loadDiary;

export async function loadDiaryHistory() {
  const list = document.getElementById('diary-history-list');
  try {
    const res = await api('GET', '/api/diary');
    if (!res.dates.length) {
      list.innerHTML = '<div style="font-size:13px;color:#555;padding:8px 0">まだ日記がありません</div>';
      return;
    }
    const cur = document.getElementById('diary-date').value;
    list.innerHTML = res.dates.slice(0, 15).map(d => `
      <div class="diary-history-item${d === cur ? ' active-item' : ''}" data-date="${d}" onclick="jumpToDiary('${d}')">
        <span class="diary-history-date">${d}</span>
      </div>`).join('');
  } catch(e) { list.innerHTML = ''; }
}
window.loadDiaryHistory = loadDiaryHistory;

export function jumpToDiary(dateStr) {
  document.getElementById('diary-date').value = dateStr;
  loadDiary();
}
window.jumpToDiary = jumpToDiary;

export function diaryNavDay(delta) {
  const picker = document.getElementById('diary-date');
  const d = new Date((picker.value || _todayStr()) + 'T00:00:00');
  d.setDate(d.getDate() + delta);
  picker.value = d.toISOString().slice(0, 10);
  loadDiary();
}
window.diaryNavDay = diaryNavDay;

export function diaryGoToday() {
  document.getElementById('diary-date').value = _todayStr();
  loadDiary();
}
window.diaryGoToday = diaryGoToday;

export function onDiaryInput() {
  document.getElementById('diary-save-status').textContent = '未保存…';
  clearTimeout(_diaryDebounce);
  _diaryDebounce = setTimeout(saveDiaryNow, 1500);
}
window.onDiaryInput = onDiaryInput;

export async function saveDiaryNow() {
  clearTimeout(_diaryDebounce);
  const date = document.getElementById('diary-date').value;
  const content = document.getElementById('diary-textarea').value.trim();
  const statusEl = document.getElementById('diary-save-status');
  if (!date || !content) { statusEl.textContent = ''; return; }
  try {
    await api('POST', '/api/diary', { date_str: date, content, referenced_task_ids: [] });
    statusEl.textContent = '✓ 保存済み';
    setTimeout(() => { statusEl.textContent = ''; }, 2000);
    loadDiaryHistory();
  } catch(e) { statusEl.textContent = '保存エラー'; }
}
window.saveDiaryNow = saveDiaryNow;

// ── Blog ──────────────────────────────────────────────────────────────
export function newBlogPost() {
  _editingBlogId = null;
  document.getElementById('blog-title').value = '';
  document.getElementById('blog-tags').value = '';
  document.getElementById('blog-textarea').value = '';
  document.getElementById('blog-save-status').textContent = '';
  document.getElementById('blog-delete-btn').style.display = 'none';
  closeSuggestPanel('blog');
  document.querySelectorAll('#blog-list .blog-list-item').forEach(el => el.classList.remove('active-item'));
}
window.newBlogPost = newBlogPost;

export function onBlogInput() {
  document.getElementById('blog-save-status').textContent = '未保存…';
  clearTimeout(_blogDebounce);
  _blogDebounce = setTimeout(saveBlogPost, 1500);
}
window.onBlogInput = onBlogInput;

export async function saveBlogPost() {
  clearTimeout(_blogDebounce);
  const title = document.getElementById('blog-title').value.trim();
  const content = document.getElementById('blog-textarea').value.trim();
  const tagsRaw = document.getElementById('blog-tags').value;
  const tags = tagsRaw.split(',').map(t => t.trim()).filter(Boolean);
  const statusEl = document.getElementById('blog-save-status');
  if (!title && !content) { statusEl.textContent = ''; return; }
  try {
    if (_editingBlogId) {
      await api('PATCH', `/api/blog/${_editingBlogId}`, { title: title || '（無題）', tags, content });
    } else {
      const post = await api('POST', '/api/blog', { title: title || '（無題）', tags, content });
      _editingBlogId = post.id;
      document.getElementById('blog-delete-btn').style.display = '';
    }
    statusEl.textContent = '✓ 保存済み';
    setTimeout(() => { statusEl.textContent = ''; }, 2000);
    loadBlogList();
  } catch(e) { statusEl.textContent = '保存エラー'; }
}
window.saveBlogPost = saveBlogPost;

export async function loadBlogList() {
  const list = document.getElementById('blog-list');
  try {
    const res = await api('GET', '/api/blog');
    if (!res.posts.length) {
      list.innerHTML = '<div style="font-size:13px;color:#555;padding:8px 0">まだブログ記事がありません</div>';
      return;
    }
    list.innerHTML = res.posts.map(p => `
      <div class="blog-list-item${p.id === _editingBlogId ? ' active-item' : ''}" onclick="loadBlogPost('${p.id}')">
        <div style="flex:1;min-width:0">
          <div class="blog-list-title">${esc(p.title)}</div>
          <div class="blog-list-meta">${(p.updated_at||'').slice(0,10)}</div>
          ${p.tags&&p.tags.length ? `<div class="blog-list-tags">${p.tags.map(t=>`<span class="blog-tag">${esc(t)}</span>`).join('')}</div>` : ''}
          ${p.preview ? `<div class="blog-list-preview">${esc(p.preview)}</div>` : ''}
        </div>
      </div>`).join('');
  } catch(e) { list.innerHTML = ''; }
}
window.loadBlogList = loadBlogList;

export async function loadBlogPost(id) {
  try {
    const post = await api('GET', `/api/blog/${id}`);
    _editingBlogId = post.id;
    document.getElementById('blog-title').value = post.title;
    document.getElementById('blog-tags').value = (post.tags||[]).join(', ');
    document.getElementById('blog-textarea').value = post.content;
    document.getElementById('blog-save-status').textContent = '';
    document.getElementById('blog-delete-btn').style.display = '';
    closeSuggestPanel('blog');
    loadBlogList();
  } catch(e) { window.showStatus('読み込みエラー', 'error'); }
}
window.loadBlogPost = loadBlogPost;

export async function deleteBlogPost() {
  if (!_editingBlogId) return;
  if (!confirm('この記事を削除しますか？')) return;
  try {
    await api('DELETE', `/api/blog/${_editingBlogId}`);
    newBlogPost();
    loadBlogList();
    window.showStatus('削除しました', 'success');
  } catch(e) { window.showStatus('削除エラー', 'error'); }
}
window.deleteBlogPost = deleteBlogPost;

// ── AI suggest panel ──────────────────────────────────────────────────
export function closeSuggestPanel(mode) {
  document.getElementById(`suggest-panel-${mode}`).style.display = 'none';
  document.getElementById(`suggest-output-${mode}`).textContent = '';
  const splitArea = document.getElementById(`${mode}-split-area`);
  if (splitArea) splitArea.classList.remove('split');
  const splitBtn = document.getElementById(`split-btn-${mode}`);
  if (splitBtn) { splitBtn.style.display = 'none'; splitBtn.classList.remove('active'); splitBtn.textContent = '⬜ 並べて表示'; }
}
window.closeSuggestPanel = closeSuggestPanel;

export function toggleSplitView(mode) {
  const splitArea = document.getElementById(`${mode}-split-area`);
  const splitBtn = document.getElementById(`split-btn-${mode}`);
  const isSplit = splitArea.classList.toggle('split');
  splitBtn.classList.toggle('active', isSplit);
  splitBtn.textContent = isSplit ? '▣ 並列解除' : '⬜ 並べて表示';
}
window.toggleSplitView = toggleSplitView;

export async function requestWritingSuggest(mode) {
  const taId = mode === 'diary' ? 'diary-textarea' : 'blog-textarea';
  const content = document.getElementById(taId).value.trim();
  if (!content && mode === 'blog') { window.showStatus('まず文章を書いてください', 'info', 2000); return; }

  const panel = document.getElementById(`suggest-panel-${mode}`);
  const output = document.getElementById(`suggest-output-${mode}`);
  const splitBtn = document.getElementById(`split-btn-${mode}`);
  panel.style.display = '';
  splitBtn.style.display = 'none';
  output.textContent = '提案を生成中…';

  const extra = mode === 'diary'
    ? { date: document.getElementById('diary-date').value }
    : { title: document.getElementById('blog-title').value, tags: document.getElementById('blog-tags').value };

  const apiKey = localStorage.getItem('gemini_api_key') || '';
  output.textContent = '';

  try {
    const res = await fetch('/api/writing/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, mode, extra, api_key: apiKey }),
    });
    if (!res.ok) throw new Error(await res.text());
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data:')) continue;
        const ev = JSON.parse(part.slice(5).trim());
        if (ev.type === 'text') output.textContent += ev.chunk;
      }
    }
    splitBtn.style.display = '';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch(e) {
    output.textContent = 'エラー: ' + e.message;
  }
}
window.requestWritingSuggest = requestWritingSuggest;
