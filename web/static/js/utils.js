import { _FOLD_KEY, CAT_WEIGHT, IMP_WEIGHT } from './state.js';

// ── HTML escape ───────────────────────────────────────────────────────
export function esc(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Date helpers ──────────────────────────────────────────────────────
export function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`;
}

export function fmtDatetime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const hasTime = d.getHours() !== 0 || d.getMinutes() !== 0;
  const base = `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`;
  return hasTime ? `${base} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}` : base;
}

export function isDue(isoStr) {
  if (!isoStr) return false;
  return new Date(isoStr) <= new Date();
}

// ── Natural language date parser ─────────────────────────────────────
export function parseNaturalDate(text) {
  const today = new Date(); today.setHours(0,0,0,0);
  const toISO = d => d.toISOString().slice(0,10);
  const addDays = n => { const d = new Date(today); d.setDate(d.getDate()+n); return d; };
  const WD = ['日','月','火','水','木','金','土'];

  if (/明後日|あさって/.test(text)) return toISO(addDays(2));
  if (/明日|あした/.test(text)) return toISO(addDays(1));
  if (/今日|本日/.test(text)) return toISO(today);
  if (/今週末/.test(text)) return toISO(addDays(6 - today.getDay() || 7));
  const nwd = text.match(/来週([月火水木金土日])曜?/);
  if (nwd) { const t = WD.indexOf(nwd[1]); const d = addDays(7); while (d.getDay()!==t) d.setDate(d.getDate()+1); return toISO(d); }
  if (/再来週/.test(text)) return toISO(addDays(14));
  if (/来週/.test(text)) return toISO(addDays(7));
  if (/月末|今月末/.test(text)) return toISO(new Date(today.getFullYear(), today.getMonth()+1, 0));
  const ml = text.match(/(\d+)[ヶか]月後/);
  if (ml) { const d = new Date(today); d.setMonth(d.getMonth()+parseInt(ml[1])); return toISO(d); }
  const wl = text.match(/(\d+)週間?後/);
  if (wl) return toISO(addDays(parseInt(wl[1])*7));
  const dl = text.match(/(\d+)日後/);
  if (dl) return toISO(addDays(parseInt(dl[1])));
  const md = text.match(/(\d{1,2})月(\d{1,2})日/);
  if (md) { const d = new Date(today.getFullYear(), parseInt(md[1])-1, parseInt(md[2])); if (d < today) d.setFullYear(d.getFullYear()+1); return toISO(d); }
  const iso = text.match(/(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/);
  if (iso) return `${iso[1]}-${iso[2].padStart(2,'0')}-${iso[3].padStart(2,'0')}`;
  return null;
}

// ── Category fold state ───────────────────────────────────────────────
export function getFoldState() {
  try { return JSON.parse(localStorage.getItem(_FOLD_KEY) || '{}'); } catch { return {}; }
}

export function setFoldState(cat, folded) {
  const s = getFoldState();
  s[cat] = folded;
  localStorage.setItem(_FOLD_KEY, JSON.stringify(s));
}

// ── Scoring ───────────────────────────────────────────────────────────
export function calcScore(t, checklists) {
  const base = CAT_WEIGHT[t.category] ?? 10;
  const impBonus = IMP_WEIGHT[t.importance] ?? 0;
  const days = t.created_at
    ? Math.floor((Date.now() - new Date(t.created_at)) / 86400000)
    : 0;
  const staleness = days * 2;
  const todayStr = new Date().toDateString();
  const taskDueBonus = t.due_date && new Date(t.due_date) <= new Date() ? 100 : 0;
  const clDueBonus = !taskDueBonus && checklists && checklists.some(cl =>
    cl.due_date && new Date(cl.due_date).toDateString() === todayStr &&
    cl.items.some(i => !i.done)
  ) ? 100 : 0;
  const dueBonus = taskDueBonus || clDueBonus;
  return { score: base + impBonus + staleness + dueBonus, base, impBonus, days, staleness, dueBonus, taskDue: t.due_date || null };
}

export function scoreLabel(t, checklists) {
  const { score, base, impBonus, days, staleness, dueBonus } = calcScore(t, checklists);
  const parts = [`カテゴリ: ${base}`];
  if (impBonus !== 0) parts.push(`重要度: ${impBonus > 0 ? '+' : ''}${impBonus}`);
  if (staleness > 0) parts.push(`滞留: ${staleness}`);
  if (dueBonus > 0) parts.push(`期日: ${dueBonus}`);
  return `スコア: ${score} (${parts.join(' + ')})`;
}

export function scoreBadge(t, checklists) {
  const { days, taskDue } = calcScore(t, checklists);
  if (taskDue) {
    const overdue = new Date(taskDue) <= new Date();
    const label = fmtDate(taskDue);
    return `<span class="score-badge badge-due" title="期日: ${label}">${overdue ? '⚠️ 期日超過' : '📅 ' + label}</span>`;
  }
  if (days >= 7) return `<span class="score-badge badge-hot" title="${days}日間 todo のまま">🔥 ${days}日経過</span>`;
  if (days >= 3) return `<span class="score-badge badge-warn" title="${days}日間 todo のまま">⏳ ${days}日</span>`;
  return '';
}
