// ─── MyDay shared: theme + brown noise ──────────────────────────────────────

// ── Theme toggle ────────────────────────────────────────────────────────────
function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  try { localStorage.setItem('myday-theme', isDark ? 'dark' : 'light'); } catch(e) {}
  updateThemeBtn();
}
function updateThemeBtn() {
  const btn = document.getElementById('theme-btn');
  if (!btn) return;
  const isDark = document.documentElement.classList.contains('dark');
  btn.innerHTML = isDark ? '☀️ Light' : '🌙 Dark';
  btn.classList.toggle('active', isDark);
}

// ── Brown Noise ──────────────────────────────────────────────────────────────
let _audioCtx = null, _noiseSource = null, _gainNode = null, _noiseActive = false;

function _buildBrownNoise(ctx) {
  const sz = 2 * ctx.sampleRate;
  const buf = ctx.createBuffer(1, sz, ctx.sampleRate);
  const out = buf.getChannelData(0);
  let last = 0;
  for (let i = 0; i < sz; i++) {
    const w = Math.random() * 2 - 1;
    out[i] = (last + (0.02 * w)) / 1.02;
    last = out[i];
    out[i] *= 3.5;
  }
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.loop = true;
  return src;
}

function startNoise() {
  if (!_audioCtx) {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    _gainNode = _audioCtx.createGain();
    _gainNode.gain.value = 0.22;
    _gainNode.connect(_audioCtx.destination);
  }
  if (_audioCtx.state === 'suspended') _audioCtx.resume();
  _noiseSource = _buildBrownNoise(_audioCtx);
  _noiseSource.connect(_gainNode);
  _noiseSource.start();
  _noiseActive = true;
}

function stopNoise() {
  if (_noiseSource) { try { _noiseSource.stop(); } catch(e) {} _noiseSource = null; }
  _noiseActive = false;
}

function toggleNoise() {
  _noiseActive ? stopNoise() : startNoise();
  try { localStorage.setItem('myday-noise', _noiseActive ? '1' : '0'); } catch(e) {}
  updateNoiseBtn();
}

function updateNoiseBtn() {
  const btn = document.getElementById('noise-btn');
  if (!btn) return;
  btn.innerHTML = _noiseActive ? '🎧 On' : '🎧 Noise';
  btn.classList.toggle('active', _noiseActive);
}

// ── Init on every page ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateThemeBtn();
  updateNoiseBtn();
  try {
    if (localStorage.getItem('myday-noise') === '1') {
      const resume = () => { startNoise(); updateNoiseBtn(); document.removeEventListener('click', resume); };
      document.addEventListener('click', resume, { once: true });
    }
  } catch(e) {}
});
