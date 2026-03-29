import { state } from './state.js';
import { api } from './api.js';
import { loadInbox, runSort } from './inbox.js';
import { loadTasks, loadLongterm } from './tasks.js';
import { loadChecklists } from './checklists.js';
import { loadRecurring } from './recurring.js';
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
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const navBtn = document.querySelector(`.nav-btn[data-tab="${name}"]`);
  if (navBtn) navBtn.classList.add('active');
  if (name === 'home') { loadInbox(); updateHomeBadges(); setTimeout(() => document.getElementById('quick-input')?.focus(), 50); }
  else if (name === 'chat') loadApiKeyToChat();
  else if (name === 'dashboard') loadDashboard();
  else if (name === 'tasks') loadTasks();
  else if (name === 'longterm') loadLongterm();
  else if (name === 'checklists') loadChecklists();
  else if (name === 'diary') initDiaryPane();
  else if (name === 'lang') initLangPane();
  else if (name === 'recurring') loadRecurring();
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
  else if (state.activePane === 'tasks') loadTasks();
  else if (state.activePane === 'longterm') loadLongterm();
  else if (state.activePane === 'checklists') loadChecklists();
}
window.reloadActivePane = reloadActivePane;

// ── Trash toggle ──────────────────────────────────────────────────────
let trashVisible = false;
export function toggleTrash() {
  trashVisible = !trashVisible;
  document.getElementById('trash-section').style.display = trashVisible ? '' : 'none';
  document.getElementById('trash-toggle-btn').style.color = trashVisible ? '#4fc3f7' : '';
  if (trashVisible) window.loadTrash();
}
window.toggleTrash = toggleTrash;

// ── Badges ────────────────────────────────────────────────────────────
export async function updateBadges() {
  try {
    const [inbox, tasks] = await Promise.all([
      api('GET', '/api/tasks?status=inbox'),
      api('GET', '/api/tasks?status=todo'),
    ]);
    const ic = inbox.tasks.length;
    const tc = tasks.tasks.length;
    const hic = document.getElementById('home-inbox-count');
    const hbt = document.getElementById('home-badge-tasks');
    if (hic) hic.textContent = ic;
    if (hbt) hbt.textContent = tc;
  } catch {}
}
window.updateBadges = updateBadges;

export async function updateHomeBadges() {
  try {
    const [inbox, tasks] = await Promise.all([
      api('GET', '/api/tasks?status=inbox'),
      api('GET', '/api/tasks?status=todo'),
    ]);
    const ic = document.getElementById('home-inbox-count');
    const tb = document.getElementById('home-badge-tasks');
    if (ic) ic.textContent = inbox.tasks.length;
    if (tb) tb.textContent = tasks.tasks.length;
  } catch(e) {}
}
window.updateHomeBadges = updateHomeBadges;

// ── Home screen keyboard nav ──────────────────────────────────────────
export const HOME_TABS = ['tasks','longterm','checklists','recurring','settings'];
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
  } else if (e.key === '/') {
    e.preventDefault();
    const searchMap = { tasks: 'task-search' };
    const searchId = searchMap[state.activePane];
    if (searchId) {
      const el = document.getElementById(searchId);
      if (el) el.focus();
    }
  }
});
