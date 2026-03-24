import { api } from './api.js';
import { esc } from './utils.js';
import { getApiKey } from './settings.js';

let _langSubtab = 'practice';
let _langPracticeText = '';
let _langQState = {
  1: {correction: '', history: []},
  2: {correction: '', history: []},
  3: {correction: '', history: []},
};
let _reviewCards = [];
let _reviewIdx = 0;
let _reviewCardShown = false;

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
// expose for HTML onclick inline
window.todayStr = todayStr;

// ── Lang pane init ────────────────────────────────────────────────────
export function initLangPane() {
  const dateEl = document.getElementById('lang-date');
  if (!dateEl.value) dateEl.value = todayStr();
  setLangSubtab('practice');
}
window.initLangPane = initLangPane;

export function setLangSubtab(name) {
  _langSubtab = name;
  ['practice','review','cards'].forEach(t => {
    document.getElementById('lang-subtab-' + t).classList.toggle('active', t === name);
    document.getElementById('lang-' + t + '-pane').style.display = t === name ? '' : 'none';
  });
  if (name === 'review') initReview();
  else if (name === 'cards') loadAllCards();
}
window.setLangSubtab = setLangSubtab;

// ── Lang practice ─────────────────────────────────────────────────────
export async function loadLangPractice() {
  const dateStr = document.getElementById('lang-date').value || todayStr();
  const apiKey = getApiKey();
  const statusEl = document.getElementById('lang-practice-status');
  const outputBox = document.getElementById('lang-practice-output');
  const problemEl = document.getElementById('lang-problem-text');
  const answerSections = document.getElementById('lang-answer-sections');

  statusEl.textContent = '生成中…';
  outputBox.style.display = '';
  problemEl.textContent = '';
  answerSections.style.display = 'none';
  _langPracticeText = '';
  [1,2,3].forEach(n => {
    document.getElementById(`lang-answer-${n}`).value = '';
    document.getElementById(`lang-correction-${n}`).textContent = '';
    document.getElementById(`lang-correction-${n}`).classList.remove('show');
    document.getElementById(`lang-save-${n}`).style.display = 'none';
    document.getElementById(`lang-save-status-${n}`).textContent = '';
    document.getElementById(`lang-discuss-${n}`).style.display = 'none';
    document.getElementById(`lang-discuss-history-${n}`).innerHTML = '';
    _langQState[n] = {correction: '', history: []};
  });

  try {
    const response = await fetch('/api/lang/practice', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({date_str: dateStr, api_key: apiKey || null}),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({detail: response.statusText}));
      problemEl.textContent = 'エラー: ' + (err.detail || response.statusText);
      statusEl.textContent = '';
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(part.slice(6));
          if (ev.type === 'text') {
            _langPracticeText += ev.chunk;
            problemEl.textContent = _langPracticeText;
          } else if (ev.type === 'error') {
            problemEl.textContent = 'エラー: ' + ev.message;
          }
        } catch {}
      }
    }
    statusEl.textContent = '';
    if (_langPracticeText) answerSections.style.display = '';
  } catch(e) {
    problemEl.textContent = 'エラー: ' + e.message;
    statusEl.textContent = '';
  }
}
window.loadLangPractice = loadLangPractice;

export async function submitLangAnswer(n) {
  const userEnglish = document.getElementById(`lang-answer-${n}`).value.trim();
  if (!userEnglish) { window.showStatus('英語を入力してください', 'error'); return; }
  const apiKey = getApiKey();
  const correctionEl = document.getElementById(`lang-correction-${n}`);
  const saveBtn = document.getElementById(`lang-save-${n}`);
  const discussWrap = document.getElementById(`lang-discuss-${n}`);

  correctionEl.classList.remove('show');
  correctionEl.textContent = '';
  saveBtn.style.display = 'none';
  saveBtn.className = 'btn btn-success btn-sm';
  saveBtn.textContent = '💾 カードに保存';
  discussWrap.style.display = 'none';
  document.getElementById(`lang-discuss-history-${n}`).innerHTML = '';
  _langQState[n] = {correction: '', history: []};

  try {
    const response = await fetch('/api/lang/correct', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        user_english: userEnglish,
        context: _langPracticeText,
        api_key: apiKey || null,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({detail: response.statusText}));
      correctionEl.textContent = 'エラー: ' + (err.detail || response.statusText);
      correctionEl.classList.add('show');
      return;
    }
    correctionEl.classList.add('show');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let corrText = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(part.slice(6));
          if (ev.type === 'text') {
            corrText += ev.chunk;
            correctionEl.textContent = corrText;
          } else if (ev.type === 'error') {
            correctionEl.textContent = 'エラー: ' + ev.message;
          }
        } catch {}
      }
    }
    if (corrText) {
      _langQState[n].correction = corrText;
      saveBtn.style.display = '';
      if (corrText.length > 150) {
        saveBtn.className = 'btn btn-warning btn-sm';
        saveBtn.textContent = '📌 重要: カードに保存';
      }
      discussWrap.style.display = '';
    }
  } catch(e) {
    correctionEl.textContent = 'エラー: ' + e.message;
    correctionEl.classList.add('show');
  }
}
window.submitLangAnswer = submitLangAnswer;

export async function saveLangCard(n) {
  const userEnglish = document.getElementById(`lang-answer-${n}`).value.trim();
  const front = `[問題${n}] ` + _langPracticeText.slice(0, 180);
  const back = userEnglish;
  const example = _langQState[n].correction.slice(0, 300);
  if (!front || !back) { window.showStatus('問題と回答が必要です', 'error'); return; }
  try {
    await api('POST', '/api/flashcards', {
      front, back, example,
      source: 'practice',
      source_ref: document.getElementById('lang-date').value || todayStr(),
    });
    const statusEl = document.getElementById(`lang-save-status-${n}`);
    statusEl.textContent = '✓ 保存済み';
    setTimeout(() => { statusEl.textContent = ''; }, 3000);
    document.getElementById(`lang-save-${n}`).style.display = 'none';
  } catch(e) {
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.saveLangCard = saveLangCard;

export async function sendLangDiscuss(n) {
  const inputEl = document.getElementById(`lang-discuss-input-${n}`);
  const followUp = inputEl.value.trim();
  if (!followUp) return;
  const apiKey = getApiKey();
  const historyEl = document.getElementById(`lang-discuss-history-${n}`);
  const userAnswer = document.getElementById(`lang-answer-${n}`).value.trim();

  const userDiv = document.createElement('div');
  userDiv.className = 'lang-discuss-msg lang-discuss-user';
  userDiv.textContent = followUp;
  historyEl.appendChild(userDiv);
  inputEl.value = '';

  const aiDiv = document.createElement('div');
  aiDiv.className = 'lang-discuss-msg lang-discuss-ai';
  aiDiv.textContent = '…';
  historyEl.appendChild(aiDiv);
  historyEl.scrollTop = historyEl.scrollHeight;

  const historySnapshot = [..._langQState[n].history];
  _langQState[n].history.push({role: 'user', content: followUp});

  let aiText = '';
  try {
    const response = await fetch('/api/lang/discuss', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        practice_text: _langPracticeText,
        user_answer: userAnswer,
        correction: _langQState[n].correction,
        follow_up: followUp,
        history: historySnapshot,
        api_key: apiKey || null,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({detail: response.statusText}));
      aiDiv.textContent = 'エラー: ' + (err.detail || response.statusText);
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream: true});
      const parts = buf.split('\n\n');
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        try {
          const ev = JSON.parse(part.slice(6));
          if (ev.type === 'text') {
            aiText += ev.chunk;
            aiDiv.textContent = aiText;
            historyEl.scrollTop = historyEl.scrollHeight;
          }
        } catch {}
      }
    }
    _langQState[n].history.push({role: 'model', content: aiText});
  } catch(e) {
    aiDiv.textContent = 'エラー: ' + e.message;
  }
}
window.sendLangDiscuss = sendLangDiscuss;

// ── Review ────────────────────────────────────────────────────────────
export async function initReview() {
  const data = await api('GET', '/api/flashcards/due');
  _reviewCards = data.cards || [];
  _reviewIdx = 0;
  _reviewCardShown = false;
  renderReviewCard();
}
window.initReview = initReview;

export function renderReviewCard() {
  const area = document.getElementById('review-card-area');
  const progressEl = document.getElementById('review-progress');
  const emptyEl = document.getElementById('review-empty');

  if (_reviewCards.length === 0) {
    area.innerHTML = '';
    area.appendChild(emptyEl);
    emptyEl.style.display = '';
    progressEl.textContent = '';
    return;
  }

  emptyEl.style.display = 'none';
  const total = _reviewCards.length;
  progressEl.textContent = `残り ${total - _reviewIdx} / ${total} 枚`;

  if (_reviewIdx >= total) {
    area.innerHTML = '<div class="empty">復習完了！お疲れ様でした 🎉</div>';
    return;
  }

  const card = _reviewCards[_reviewIdx];
  area.innerHTML = `
    <div class="flashcard-item">
      <div class="flashcard-front">${esc(card.front)}</div>
      <div class="flashcard-back" id="rv-back">${esc(card.back)}</div>
      <div class="flashcard-example" id="rv-example">${esc(card.example || '')}</div>
      <div class="flashcard-meta">次回: ${card.next_review} | 間隔: ${card.interval}日 | 正解連続: ${card.repetitions}</div>
      <div id="rv-reveal-row" style="margin-top:10px">
        <button class="btn btn-ghost btn-sm" onclick="revealCard()">答えを見る</button>
      </div>
      <div id="rv-rate-row" class="review-rate-btns" style="display:none">
        <button class="review-rate-btn btn-forget" onclick="rateCard(0)">😵 忘れた</button>
        <button class="review-rate-btn btn-hard" onclick="rateCard(1)">😅 難しい</button>
        <button class="review-rate-btn btn-perfect" onclick="rateCard(2)">😊 完璧</button>
      </div>
    </div>`;
}
window.renderReviewCard = renderReviewCard;

export function revealCard() {
  document.getElementById('rv-back').classList.add('show');
  const ex = document.getElementById('rv-example');
  if (ex && ex.textContent) ex.classList.add('show');
  document.getElementById('rv-reveal-row').style.display = 'none';
  document.getElementById('rv-rate-row').style.display = '';
}
window.revealCard = revealCard;

export async function rateCard(quality) {
  if (_reviewIdx >= _reviewCards.length) return;
  const card = _reviewCards[_reviewIdx];
  try {
    await api('PATCH', `/api/flashcards/${card.id}/review`, {quality});
    _reviewIdx++;
    renderReviewCard();
  } catch(e) {
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.rateCard = rateCard;

// ── All cards ─────────────────────────────────────────────────────────
export async function loadAllCards() {
  const data = await api('GET', '/api/flashcards');
  const cards = data.cards || [];
  const listEl = document.getElementById('all-cards-list');
  if (!cards.length) {
    listEl.innerHTML = '<div class="empty">フラッシュカードがありません</div>';
    return;
  }
  listEl.innerHTML = cards.map(c => `
    <div class="flashcard-item">
      <div style="display:flex;align-items:flex-start;gap:8px">
        <div style="flex:1">
          <div class="flashcard-front">${esc(c.front)}</div>
          <div style="font-size:13px;color:#aaa;margin-top:4px">${esc(c.back)}</div>
          ${c.example ? `<div style="font-size:12px;color:#69f0ae;font-style:italic;margin-top:3px">${esc(c.example)}</div>` : ''}
        </div>
        <button class="btn btn-danger btn-sm" onclick="deleteCard('${esc(c.id)}')">🗑</button>
      </div>
      <div class="flashcard-meta">次回: ${c.next_review} | 間隔: ${c.interval}日 | ミス: ${c.lapses} | 出典: ${esc(c.source)}</div>
    </div>`).join('');
}
window.loadAllCards = loadAllCards;

export async function deleteCard(cardId) {
  if (!confirm('このカードを削除しますか？')) return;
  try {
    await api('DELETE', `/api/flashcards/${cardId}`);
    window.showStatus('削除しました', 'success', 2000);
    loadAllCards();
  } catch(e) {
    window.showStatus('エラー: ' + e.message, 'error');
  }
}
window.deleteCard = deleteCard;
