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

/* ═══════════════════════════════════════════════════════════════
   KANBAN v2 — Project colors · Move collapse · Quick-add
   ═══════════════════════════════════════════════════════════════ */
(function () {
  // Derive the app base path from the current URL (e.g. "/task-manager")
  const _BASE = window.location.pathname.split('/').slice(0, 2).join('/');

  const PROJECT_COLORS = {
    'My Day improvements':                        {bg:'#EDE9FE',color:'#5B21B6',dbg:'#2D1A5E',dc:'#C4B5FD'},
    'Business Development and Marketing Efforts': {bg:'#DBEAFE',color:'#1E40AF',dbg:'#0F2240',dc:'#93C5FD'},
    'Other tasks':                                {bg:'#F1F5F9',color:'#475569',dbg:'#1E293B',dc:'#94A3B8'},
    'Cardinal Health':                            {bg:'#D1FAE5',color:'#065F46',dbg:'#052E16',dc:'#6EE7B7'},
    'AI to dos':                                  {bg:'#FEF3C7',color:'#92400E',dbg:'#2D1800',dc:'#FDE68A'},
    'CoP Work':                                   {bg:'#FCE7F3',color:'#9D174D',dbg:'#2D0A1E',dc:'#F9A8D4'},
    'Rizek':                                      {bg:'#ECFDF5',color:'#047857',dbg:'#042018',dc:'#34D399'},
  };

  function colorizeProjectTags() {
    const isDark = document.documentElement.classList.contains('dark');
    document.querySelectorAll('.card-project').forEach(tag => {
      const s = PROJECT_COLORS[tag.textContent.trim()];
      if (s) tag.style.cssText = `background:${isDark?s.dbg:s.bg};color:${isDark?s.dc:s.color};border-radius:4px;padding:.1rem .4rem;font-size:.68rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px;display:inline-block;`;
    });
  }

  const STATUS_ORDER = ['backlog','todo','doing','waiting','done'];

  function collapseMoveButtons() {
    document.querySelectorAll('.card').forEach(card => {
      const actions = card.querySelector('.card-actions');
      if (!actions || actions.dataset.collapsed === '1') return;
      const colStatus = card.closest('.column')?.dataset.status;
      const next = STATUS_ORDER[STATUS_ORDER.indexOf(colStatus) + 1] || null;
      const forms = Array.from(actions.querySelectorAll('form'));
      if (!forms.length) return;
      const nextForm = forms.find(f => f.querySelector('input[name="status"]')?.value === next);
      const others = forms.filter(f => f !== nextForm);
      actions.innerHTML = '';
      actions.dataset.collapsed = '1';
      if (nextForm) {
        nextForm.querySelector('.move-btn').classList.add('move-btn-primary');
        actions.appendChild(nextForm);
      }
      if (others.length) {
        const wrap = document.createElement('div'); wrap.className = 'move-more-wrapper';
        const btn = document.createElement('button'); btn.className = 'move-btn move-btn-more'; btn.type = 'button'; btn.textContent = '···'; btn.title = 'Move to…';
        const drop = document.createElement('div'); drop.className = 'move-dropdown';
        others.forEach(f => drop.appendChild(f));
        btn.onclick = e => { e.stopPropagation(); drop.classList.toggle('move-dropdown-open'); };
        document.addEventListener('click', () => drop.classList.remove('move-dropdown-open'));
        wrap.appendChild(btn); wrap.appendChild(drop); actions.appendChild(wrap);
      }
    });
  }

  function addQuickAddButtons() {
    document.querySelectorAll('.column').forEach(col => {
      if (col.querySelector('.col-quick-add')) return;
      const status = col.dataset.status;
      if (!status) return;
      const btn = document.createElement('button');
      btn.className = 'col-quick-add'; btn.type = 'button'; btn.textContent = '+ Add task';
      btn.onclick = () => {
        document.querySelectorAll('.col-quick-form').forEach(f => f.remove());
        document.querySelectorAll('.col-quick-add').forEach(b => b.style.display = '');
        btn.style.display = 'none';
        const form = document.createElement('form');
        form.className = 'col-quick-form'; form.method = 'post';
        form.action = `${_BASE}/tasks-page`;
        form.innerHTML = `
          <input type="text" name="title" class="col-quick-input" placeholder="Task title…" autocomplete="off" required>
          <input type="hidden" name="status" value="${status}">
          <input type="hidden" name="priority" value="medium">
          <input type="hidden" name="redirect_to" value="${_BASE}/kanban">
          <div class="col-quick-row">
            <button type="submit" class="col-quick-submit">Add</button>
            <button type="button" class="col-quick-cancel">Cancel</button>
          </div>`;
        form.querySelector('.col-quick-cancel').onclick = () => { form.remove(); btn.style.display = ''; };
        col.appendChild(form);
        form.querySelector('.col-quick-input').focus();
      };
      col.appendChild(btn);
    });
  }

  function init() { colorizeProjectTags(); collapseMoveButtons(); addQuickAddButtons(); }
  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);

  // Re-colorize project tags after theme toggle
  const _origToggle = window.toggleTheme;
  if (_origToggle) window.toggleTheme = function () { _origToggle.apply(this, arguments); setTimeout(colorizeProjectTags, 60); };

  // ── Celebratory burst + wins counter when moving a card to Done ─────────
  const board = document.getElementById('board');
  if (board) {
    board.addEventListener('submit', function (e) {
      const form = e.target;
      const statusInput = form.querySelector('input[name="status"]');
      if (!statusInput || statusInput.value !== 'done') return;
      const card = form.closest('.card');
      if (!card) return;
      e.preventDefault();

      // Burst animation on card
      card.classList.add('card-completing');

      // Increment wins counter
      const winsBar  = document.getElementById('kanban-wins');
      const winsNum  = document.getElementById('kanban-wins-num');
      if (winsBar && winsNum) {
        const current = parseInt(winsNum.textContent || '0', 10);
        const next    = current + 1;
        winsNum.textContent = next;
        winsBar.classList.add('has-wins');
        // Bounce the counter
        winsNum.classList.remove('count-bump');
        void winsNum.offsetWidth; // force reflow to restart animation
        winsNum.classList.add('count-bump');
      }

      setTimeout(() => form.submit(), 450);
    });

    // ── NOW task: Set NOW / Clear NOW buttons ──────────────────────────────
    board.addEventListener('click', function (e) {
      const setBtn   = e.target.closest('.btn-set-now');
      const clearBtn = e.target.closest('.btn-clear-now');
      if (!setBtn && !clearBtn) return;
      e.stopPropagation();

      const taskId = (setBtn || clearBtn).dataset.taskId;
      const isSet  = !!setBtn;
      const url    = _BASE + '/tasks/' + taskId + (isSet ? '/set-now' : '/clear-now');

      fetch(url, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
          if (!data.ok) return;
          // Clear data-now from all cards
          document.querySelectorAll('.card[data-now="true"]').forEach(c => {
            c.removeAttribute('data-now');
            c.querySelector('.card-now-badge')?.remove();
            c.querySelector('.btn-clear-now')?.remove();
          });
          if (isSet) {
            const card = document.querySelector('.card[data-task-id="' + taskId + '"]');
            if (!card) return;
            card.setAttribute('data-now', 'true');
            // Insert badge above title
            const preview = card.querySelector('.card-preview');
            const title   = card.querySelector('.card-title');
            if (preview && title) {
              const badge = document.createElement('div');
              badge.className = 'card-now-badge';
              badge.textContent = '▶ NOW';
              preview.insertBefore(badge, title);
            }
            // Add "Clear" button next to the (still-hidden) Set NOW button
            const sBtn = card.querySelector('.btn-set-now');
            if (sBtn && !card.querySelector('.btn-clear-now')) {
              const cBtn = document.createElement('button');
              cBtn.className = 'btn-clear-now';
              cBtn.type = 'button';
              cBtn.dataset.taskId = taskId;
              cBtn.textContent = '✕ Clear';
              sBtn.insertAdjacentElement('afterend', cBtn);
            }
          }
        })
        .catch(() => {});
    });
  }
})();
