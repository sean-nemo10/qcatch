const STORAGE_KEY = 'zzzmemo_voice_enabled';

export function isVoiceEnabled() {
  return localStorage.getItem(STORAGE_KEY) === 'true';
}

export function setVoiceEnabled(val) {
  localStorage.setItem(STORAGE_KEY, val ? 'true' : 'false');
  updateMicButtons();
  const label = document.getElementById('voice-toggle-label');
  if (label) label.textContent = val ? '有効' : '無効';
}
window.setVoiceEnabled = setVoiceEnabled;

export function updateMicButtons() {
  const enabled = isVoiceEnabled();
  document.querySelectorAll('.mic-btn').forEach(btn => {
    btn.style.display = enabled ? '' : 'none';
  });
  const toggle = document.getElementById('voice-enabled-toggle');
  if (toggle) toggle.checked = enabled;
  const label = document.getElementById('voice-toggle-label');
  if (label) label.textContent = enabled ? '有効' : '無効';
}
window.updateMicButtons = updateMicButtons;

export function startVoice(targetId) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    window.showStatus('このブラウザは音声入力に対応していません', 'error', 3000);
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = 'ja-JP';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  const btn = document.querySelector(`.mic-btn[data-target="${targetId}"]`);
  if (btn) btn.classList.add('mic-active');

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    const el = document.getElementById(targetId);
    if (el) {
      el.value += (el.value ? ' ' : '') + text;
      el.dispatchEvent(new Event('input'));
    }
  };
  recognition.onerror = () => {
    if (btn) btn.classList.remove('mic-active');
  };
  recognition.onend = () => {
    if (btn) btn.classList.remove('mic-active');
  };
  recognition.start();
}
window.startVoice = startVoice;
