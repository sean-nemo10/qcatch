// ── Shared mutable state ──────────────────────────────────────────────
export const state = {
  activePane: 'home',
  selectedTaskIds: new Set(),
  pendingSuggestions: [],
  pendingSplits: [],
  currentTasks: [],
  subfolderTaskId: null,
};

// ── Constants ─────────────────────────────────────────────────────────
export const _FOLD_KEY = 'qcatch_cat_fold';

export const WEEKDAY_NAMES = ['月','火','水','木','金','土','日'];

export const CAT_COLORS = {
  '仕事':'cat-仕事','プライベート':'cat-プライベート',
  '買い物':'cat-買い物','学習':'cat-学習','その他':'cat-その他'
};

export const CAT_WEIGHT = { '仕事': 50, '学習': 30, 'プライベート': 10, '買い物': 10, 'その他': 10 };
export const IMP_WEIGHT = { high: 60, medium: 0, low: -30 };
export const IMP_LABEL  = { high: '🔴 高', medium: '🟡 中', low: '🟢 低' };
