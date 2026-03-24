// ── Entry point ───────────────────────────────────────────────────────
// Import all modules — side effects (window.X assignments) run on import.

import './state.js';
import './utils.js';
import './api.js';
import './settings.js';   // getApiKey must be available before chat/lang
import './chat.js';
import './dashboard.js';
import './inbox.js';
import './tasks.js';
import './checklists.js';
import './recurring.js';
import './sort.js';
import './diary.js';
import './lang.js';
import './import.js';
import './nav.js';        // nav last: sets up keydown handlers that call feature loaders

import { state } from './state.js';
import { updateHomeBadges, updateBadges, reloadActivePane, switchTab } from './nav.js';

// ── Service Worker ────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// ── Init ──────────────────────────────────────────────────────────────
state.activePane = 'home';
updateHomeBadges();
updateBadges();

// OAuth callback notifications
if (location.search.includes('auth=success')) {
  history.replaceState(null, '', location.pathname);
  window.showStatus('✅ Google 連携が完了しました', 'success', 4000);
} else if (location.search.includes('auth=error')) {
  const msg = new URLSearchParams(location.search).get('msg') || '不明なエラー';
  history.replaceState(null, '', location.pathname);
  window.showStatus('❌ Google 連携エラー: ' + msg, 'error', 8000);
}

// 60-second auto-refresh
setInterval(() => {
  updateBadges();
  if (state.activePane !== 'chat' && state.activePane !== 'settings') reloadActivePane();
}, 60000);
