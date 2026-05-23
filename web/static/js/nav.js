import { state } from './state.js';
import { api } from './api.js';
import { loadInbox, runSort } from './inbox.js';
import { loadTasks, loadLongterm } from './tasks.js';
import { loadChecklists } from './checklists.js';
import { loadRecurring } from './recurring.js';
import { loadWishlist, WISHLISTS } from './wishlist.js';
import { loadSettings } from './settings.js';
import { loadDashboard } from './dashboard.js';
import { initDiaryPane } from './diary.js';
import { initLangPane } from './lang.js';
import { loadApiKeyToChat } from './chat.js';

// ── Status display ────────────────────────────────────────────────────
export function showStatus(msg, type='info', duration=4000) {
  const bar = document.getElementById('status-bar');
  bar.textContent = msg;
  bar.className = 'status-bar show ' + type;
  if (duration) setTimeout(() => bar.classList.remove('show'), duration);
}
window.showStatus = showStatus;

// ── Tab switching ─────────────────────────────────────────────────────
export function switchTab(name) {
  if (name === 'inbox') { switchTab('home'); return; }
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.getElementById('pane-' + name).classList.add('active');
  state.activePane = name;
  window._activePane = name;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const navBtn = document.querySelector(`.nav-btn[data-tab="${name}"]`);
  if (navBtn) navBtn.classList.add('active');
  // FAB: ホーム以外で表示（オーバーレイは常に閉じる）
  const fab = document.getElementById('fab-add');
  const overlay = document.getElementById('quick-add-overlay');
  if (fab) fab.style.display = name === 'home' ? 'none' : 'flex';
  if (overlay) overlay.style.display = 'none';
  if (name === 'home') { loadInbox(); updateHomeBadges(); setTimeout(() => document.getElementById('quick-input')?.focus(), 50); }
  else if (name === 'chat') loadApiKeyToChat();
  else if (name === 'dashboard') loadDashboard();
  else if (name === 'tasks') loadTasks();
  else if (name === 'longterm') loadLongterm();
  else if (name === 'checklists') loadChecklists();
  else if (name === 'diary') initDiaryPane();
  else if (name === 'lang') initLangPane();
  else if (name === 'recurring') loadRecurring();
  else if (WISHLISTS[name]) loadWishlist(name);
  else if (name === 'settings') loadSettings();
}
window.switchTab = switchTab;

export function switchTabByName(name) {
  switchTab(name);
}
window.switchTabByName = switchTabByName;

export function reloadActivePane() {
  if (state.activePane === 'dashboard') loadDashboard();
  else if (state.activePane === 'home' || state.activePane === 'inbox') loadInbox();
  else if (state.activePane === 'longterm') loadLongterm();
  else if (state.activePane === 'checklists') loadChecklists();
}
window.reloadActivePane = reloadActivePane;

// ── Trash toggle ──────────────────────────────────────────────────────
let trashVisible = false;
export function toggleTrash() {
  trashVisible = !trashVisible;
  const sec = document.getElementById('trash-section');
  const btn = document.getElementById('trash-toggle-btn');
  if (sec) sec.style.display = trashVisible ? '' : 'none';
  if (btn) btn.style.color = trashVisible ? '#4fc3f7' : '';
  if (trashVisible) window.loadTrash();
}
window.toggleTrash = toggleTrash;

// ── Badges ────────────────────────────────────────────────────────────
export async function updateBadges() {
  try {
    const inbox = await api('GET', '/api/tasks?status=inbox');
    const hic = document.getElementById('home-inbox-count');
    if (hic) hic.textContent = inbox.tasks.length;
  } catch {}
}
window.updateBadges = updateBadges;

export async function updateHomeBadges() {
  try {
    const inbox = await api('GET', '/api/tasks?status=inbox');
    const ic = document.getElementById('home-inbox-count');
    if (ic) ic.textContent = inbox.tasks.length;
    const wl = await api('GET', '/api/tasks?status=wishlist');
    for (const [key, cfg] of Object.entries(WISHLISTS)) {
      const el = document.getElementById(`${key}-count`);
      if (el) el.textContent = wl.tasks.filter(t => t.category === cfg.category).length;
    }
  } catch(e) {}
}
window.updateHomeBadges = updateHomeBadges;

// ── Home screen keyboard nav ──────────────────────────────────────────
export const HOME_TABS = ['longterm','checklists','recurring','shopping','settings'];
let _homeFocusIdx = 0;

export function updateHomeFocus() {
  document.querySelectorAll('.home-card').forEach((card, i) => {
    card.classList.toggle('focused', i === _homeFocusIdx);
  });
}

document.addEventListener('keydown', e => {
  if (state.activePane !== 'home') return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    e.preventDefault();
    _homeFocusIdx = (_homeFocusIdx + 1) % HOME_TABS.length;
    updateHomeFocus();
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    e.preventDefault();
    _homeFocusIdx = (_homeFocusIdx - 1 + HOME_TABS.length) % HOME_TABS.length;
    updateHomeFocus();
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    switchTab(HOME_TABS[_homeFocusIdx]);
  }
});

// ── Global keyboard shortcuts ─────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
  if (document.querySelector('.modal-overlay.show')) return;
  if (e.key === 'n') {
    switchTab('home');
    setTimeout(() => document.getElementById('quick-input').focus(), 50);
  }
});
