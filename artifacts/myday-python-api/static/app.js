// ─── MyDay shared: theme + brown noise ──────────────────────────────────────

// Dark-mode CSS variable values applied directly to <html> as inline style.
// Inline style has the highest cascade priority, guaranteeing they override
// any hardcoded values in inline <style> blocks or external stylesheets.
const DARK_VARS = {
  '--bg':             '#1A1A1A',
  '--surface':        '#242424',
  '--border':         '#3A3A3A',
  '--border-subtle':  '#333333',
  '--border-focus':   '#FFCC00',
  '--text':           '#F5F5F0',
  '--text-muted':     '#A3A3A3',
  '--muted':          '#A3A3A3',
  '--text-faint':     '#6B7280',
  '--accent':         '#FFCC00',
  '--accent-hover':   '#F0BB00',
  '--accent-soft':    '#2D2800',
  '--accent-light':   '#2D2800',
  '--accent-text':    '#FFDD55',
  '--focus-now':      '#FFDD55',
  '--success':        '#2DD4BF',
  '--success-soft':   '#0A2929',
  '--success-light':  '#0A2929',
  '--success-border': '#2DD4BF',
  '--warning':        '#F97316',
  '--warning-soft':   '#2D1200',
  '--warning-light':  '#2D1200',
  '--warning-border': '#F97316',
  '--warning-text':   '#FDBA74',
  '--danger':         '#EF4444',
  '--danger-light':   '#2D0A0A',
  '--danger-border':  '#EF4444',
  '--focus-bg':       '#1A1A00',
  '--focus-ring':     '#FFCC00',
  '--ctrl-bg':        '#333333',
  '--ctrl-hover':     '#444444',
};

function applyTheme(isDark) {
  const root = document.documentElement;
  if (isDark) {
    root.classList.add('dark');
    for (const [prop, val] of Object.entries(DARK_VARS)) {
      root.style.setProperty(prop, val);
    }
  } else {
    root.classList.remove('dark');
    for (const prop of Object.keys(DARK_VARS)) {
      root.style.removeProperty(prop);
    }
  }
}

function toggleTheme() {
  const isDark = !document.documentElement.classList.contains('dark');
  applyTheme(isDark);
  try { localStorage.setItem('myday-theme', isDark ? 'dark' : 'light'); } catch(e) {}
  updateThemeBtn();
}

function updateThemeBtn() {
  const btn = document.getElementById('theme-btn');
  if (!btn) return;
  const isDark = document.documentElement.classList.contains('dark');
  btn.innerHTML = isDark ? '&#9728;&#65039; Light' : '&#127769; Dark';
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
  btn.innerHTML = _noiseActive ? '&#127911; On' : '&#127911; Noise';
  btn.classList.toggle('active', _noiseActive);
}

// ── Init on every page ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Re-apply full theme (CSS vars + class) from saved preference.
  // The anti-flicker script in <head> adds the class, but this sets the
  // CSS variables which are the actual mechanism for all element colors.
  try {
    applyTheme(localStorage.getItem('myday-theme') === 'dark');
  } catch(e) {}

  updateThemeBtn();
  updateNoiseBtn();

  // Auto-resume noise preference on first interaction
  try {
    if (localStorage.getItem('myday-noise') === '1') {
      const resume = () => { startNoise(); updateNoiseBtn(); document.removeEventListener('click', resume); };
      document.addEventListener('click', resume, { once: true });
    }
  } catch(e) {}
});
