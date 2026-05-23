import { api } from './api.js';
import { esc } from './utils.js';

export const WISHLISTS = {
  shopping: { category: '買い物', label: '買い物リスト', placeholder: '商品名（例：シャンプー）' },
};

const HISTORY_LIMIT = 20;
const CART_TAG = 'cart';

export async function loadWishlist(key) {
  const cfg = WISHLISTS[key];
  if (!cfg) return;
  const [wlData, doneData] = await Promise.all([
    api('GET', '/api/tasks?status=wishlist'),
    api('GET', '/api/tasks?status=done'),
  ]);
  const items = wlData.tasks.filter(t => t.category === cfg.category);
  renderItems(key, cfg, items);
  renderHistory(key, cfg, doneData.tasks);
  renderDatalist(key, doneData.tasks.concat(items), cfg);

  const countEl = document.getElementById(`${key}-count`);
  if (countEl) countEl.textContent = items.length;
}
window.loadWishlist = loadWishlist;

function renderItems(key, cfg, items) {
  const container = document.getElementById(`${key}-list`);
  if (!container) return;
  const cartCount = items.filter(t => t.tags.includes(CART_TAG)).length;
  const promoteBtn = document.getElementById(`${key}-promote-btn`);
  if (promoteBtn) {
    promoteBtn.textContent = cartCount > 0
      ? `🛒 カゴの${cartCount}件をダッシュボードへ`
      : '🛒 全部ダッシュボードへ';
    promoteBtn.dataset.mode = cartCount > 0 ? 'cart' : 'all';
  }
  if (!items.length) {
    container.innerHTML = '<div class="empty">アイテムがまだありません</div>';
    return;
  }
  items.sort((a, b) => {
    const aCart = a.tags.includes(CART_TAG) ? 0 : 1;
    const bCart = b.tags.includes(CART_TAG) ? 0 : 1;
    return aCart - bCart;
  });
  container.innerHTML = items.map(t => {
    const inCart = t.tags.includes(CART_TAG);
    return `
    <div class="wishlist-row${inCart ? ' in-cart' : ''}" data-id="${t.id}">
      <button class="cart-btn${inCart ? ' active' : ''}" title="${inCart ? 'カゴから外す' : 'カゴに入れる'}"
        onclick="toggleCart('${t.id}','${key}',${inCart})">🛒</button>
      <span class="wishlist-text">${esc(t.text)}</span>
      <button class="btn btn-success btn-sm" onclick="completeWishlistItem('${t.id}','${key}')" title="購入済み">✓</button>
      <button class="btn btn-ghost btn-sm" onclick="deleteWishlistItem('${t.id}','${key}')" title="削除">✕</button>
    </div>`;
  }).join('');
}

function renderHistory(key, cfg, allDone) {
  const container = document.getElementById(`${key}-history`);
  if (!container) return;
  const past = allDone
    .filter(t => t.category === cfg.category)
    .sort((a, b) => new Date(b.completed_at || 0) - new Date(a.completed_at || 0));
  const seen = new Set();
  const unique = [];
  for (const t of past) {
    if (seen.has(t.text)) continue;
    seen.add(t.text);
    unique.push(t);
    if (unique.length >= HISTORY_LIMIT) break;
  }
  if (!unique.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = `
    <div class="history-title">📜 最近の購入（タップで再追加）</div>
    <div class="history-chips">
      ${unique.map(t => `<button class="history-chip" onclick="reAddFromHistory('${key}','${esc(t.text).replace(/'/g, "\\'")}')"
        title="${t.completed_at ? new Date(t.completed_at).toLocaleDateString() : ''}">${esc(t.text)}</button>`).join('')}
    </div>`;
}

function renderDatalist(key, allItems, cfg) {
  const datalist = document.getElementById(`${key}-datalist`);
  if (!datalist) return;
  const texts = new Set();
  for (const t of allItems) {
    if (t.category === cfg.category && t.text) texts.add(t.text);
  }
  datalist.innerHTML = [...texts].map(t => `<option value="${esc(t)}">`).join('');
}

export async function addWishlistItem(key) {
  const cfg = WISHLISTS[key];
  if (!cfg) return;
  const input = document.getElementById(`${key}-input`);
  const text = input.value.trim();
  if (!text) return;
  try {
    await api('POST', '/api/tasks', {
      text,
      category: cfg.category,
      status: 'wishlist',
      importance: 'low',
      auto_classify: false,
    });
    input.value = '';
    loadWishlist(key);
  } catch (e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.addWishlistItem = addWishlistItem;

export async function reAddFromHistory(key, text) {
  const cfg = WISHLISTS[key];
  if (!cfg) return;
  try {
    await api('POST', '/api/tasks', {
      text,
      category: cfg.category,
      status: 'wishlist',
      importance: 'low',
      auto_classify: false,
    });
    window.showStatus(`「${text}」を追加しました`, 'success', 2000);
    loadWishlist(key);
  } catch (e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.reAddFromHistory = reAddFromHistory;

export async function toggleCart(id, key, currentlyInCart) {
  try {
    const data = await api('GET', '/api/tasks?status=wishlist');
    const task = data.tasks.find(t => t.id === id);
    if (!task) return;
    const tags = currentlyInCart
      ? task.tags.filter(t => t !== CART_TAG)
      : [...task.tags, CART_TAG];
    await api('PATCH', `/api/tasks/${id}`, { tags });
    loadWishlist(key);
  } catch (e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.toggleCart = toggleCart;

export async function completeWishlistItem(id, key) {
  try {
    await api('PATCH', `/api/tasks/${id}`, { status: 'done' });
    loadWishlist(key);
  } catch (e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.completeWishlistItem = completeWishlistItem;

export async function deleteWishlistItem(id, key) {
  if (!confirm('削除しますか？')) return;
  try {
    await api('DELETE', `/api/tasks/${id}`);
    loadWishlist(key);
  } catch (e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.deleteWishlistItem = deleteWishlistItem;

export async function promoteAllWishlist(key) {
  const cfg = WISHLISTS[key];
  if (!cfg) return;
  const btn = document.getElementById(`${key}-promote-btn`);
  const mode = btn?.dataset.mode || 'all';
  const confirmMsg = mode === 'cart'
    ? '🛒 カゴのアイテムをダッシュボードに昇格しますか？'
    : `「${cfg.label}」の全アイテムをダッシュボードに昇格しますか？`;
  if (!confirm(confirmMsg)) return;
  try {
    const url = mode === 'cart'
      ? `/api/tasks/promote-wishlist?category=${encodeURIComponent(cfg.category)}&only_tagged=${CART_TAG}`
      : `/api/tasks/promote-wishlist?category=${encodeURIComponent(cfg.category)}`;
    const r = await api('POST', url);
    window.showStatus(`${r.promoted}件を昇格しました`, 'success');
    loadWishlist(key);
  } catch (e) { window.showStatus('エラー: ' + e.message, 'error'); }
}
window.promoteAllWishlist = promoteAllWishlist;

export function handleWishlistEnter(event, key) {
  if (event.key === 'Enter') {
    event.preventDefault();
    addWishlistItem(key);
  }
}
window.handleWishlistEnter = handleWishlistEnter;
