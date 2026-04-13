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
      if (s) tag.style.cssText = `background:${isDark?s.dbg:s.bg};color:${isDark?s.dc:s.color};border-radius:4px;padding:.1rem .4rem;font-size:.82rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px;display:inline-block;`;
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

    // ── Energy filter bar ─────────────────────────────────────────────────
    document.querySelectorAll('.energy-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.energy-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const energy = btn.dataset.energy;
        document.querySelectorAll('#board .card').forEach(card => {
          if (energy === 'all') {
            card.style.display = '';
          } else {
            const hasTag = card.querySelector(`.etag-${energy}`);
            card.style.display = hasTag ? '' : 'none';
          }
        });
      });
    });

    // ── Backlog collapse (show top 3 by default) ───────────────────────────
    function collapseBacklog() {
      const backlogBody = document.querySelector('.column[data-status="backlog"] .column-body');
      if (!backlogBody) return;
      const cards = Array.from(backlogBody.querySelectorAll('.card'));
      const LIMIT = 3;
      if (cards.length <= LIMIT) return;

      const hidden = cards.slice(LIMIT);
      hidden.forEach(c => c.classList.add('backlog-hidden'));

      const toggle = document.createElement('button');
      toggle.className = 'backlog-show-more';
      toggle.textContent = `+ Show ${hidden.length} more`;
      toggle.onclick = () => {
        const isExpanded = toggle.dataset.expanded === '1';
        hidden.forEach(c => c.classList.toggle('backlog-hidden', isExpanded));
        toggle.textContent = isExpanded ? `+ Show ${hidden.length} more` : `− Hide ${hidden.length}`;
        toggle.dataset.expanded = isExpanded ? '0' : '1';
      };
      backlogBody.appendChild(toggle);
    }
    collapseBacklog();

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

// ─── PHASE 1 QUICK WINS ─────────────────────────────────────────────────────

// ── 1.2 Click-toggle for progressive disclosure on task rows ─────────────────
// Clicking a task row toggles .expanded, making metadata "sticky" instead of
// hover-only. The :hover CSS continues working for mouse users who prefer it.
document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', (e) => {
    const row = e.target.closest('.task-row');
    if (!row) return;
    // Don't toggle if clicking on an interactive element
    if (e.target.closest('button, a, form, input, select, textarea')) return;
    row.classList.toggle('expanded');
  });
});

// ── 1.4 Persist CoP accordion state in localStorage ─────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const copAccordion = document.querySelector('.cop-accordion');
  if (!copAccordion) return;
  try {
    const wasOpen = localStorage.getItem('myday-cop-open') === '1';
    if (wasOpen) copAccordion.setAttribute('open', '');
  } catch(e) {}
  copAccordion.addEventListener('toggle', () => {
    try {
      localStorage.setItem('myday-cop-open', copAccordion.open ? '1' : '0');
    } catch(e) {}
  });
});

// ── 1.6 Keyboard shortcuts (expanded in Track C) ─────────────────────────────
// Navigation: J/K = up/down task list, Enter = expand, Space = toggle
// Actions: 1/2/3 = focus state, D = done NOW task, N = quick-add, F = focus
// Pages: E = evening reset, M = morning checkin
// UI: Escape = close modal / deselect, ? = help

let _selectedTaskIdx = -1;

function _getNavTasks() {
  return Array.from(document.querySelectorAll('.task-card, .win-row, .task-row'));
}

function _selectTask(idx) {
  const tasks = _getNavTasks();
  if (!tasks.length) return;
  _selectedTaskIdx = Math.max(0, Math.min(idx, tasks.length - 1));
  tasks.forEach((t, i) => t.classList.toggle('kbd-selected', i === _selectedTaskIdx));
  tasks[_selectedTaskIdx]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function _clearTaskSelection() {
  _selectedTaskIdx = -1;
  _getNavTasks().forEach(t => t.classList.remove('kbd-selected'));
}

function _getBase() {
  const m = window.location.pathname.match(/^(\/[^/]+)\//);
  return (m ? m[1] : '') || '/task-manager';
}

document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('keydown', (e) => {
    // Don't fire shortcuts when typing in inputs
    if (e.target.closest('input, textarea, select, [contenteditable]')) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    const key = e.key;
    const keyL = key.toLowerCase();
    const base = _getBase();

    // ── Escape: close modal / deselect / exit focus mode
    if (key === 'Escape') {
      _clearTaskSelection();
      document.querySelectorAll('dialog[open]').forEach(d => { try { d.close(); } catch(ex) {} });
      const helpEl = document.getElementById('shortcuts-help');
      if (helpEl) helpEl.remove();
      return;
    }

    // ── J/K: navigate task list (only when tasks exist in DOM)
    const tasks = _getNavTasks();
    if (keyL === 'j' && tasks.length) {
      _selectTask(_selectedTaskIdx < 0 ? 0 : _selectedTaskIdx + 1);
      e.preventDefault();
      return;
    }
    if (keyL === 'k' && tasks.length) {
      _selectTask(_selectedTaskIdx <= 0 ? 0 : _selectedTaskIdx - 1);
      e.preventDefault();
      return;
    }

    // ── Enter / Space: expand selected task
    if ((key === 'Enter' || key === ' ') && _selectedTaskIdx >= 0 && tasks[_selectedTaskIdx]) {
      tasks[_selectedTaskIdx].click();
      e.preventDefault();
      return;
    }

    // ── 1/2/3: move selected task to NOW / NEXT / LATER
    if (['1','2','3'].includes(key) && _selectedTaskIdx >= 0) {
      const row = tasks[_selectedTaskIdx];
      const taskId = row?.dataset?.taskId || row?.id?.replace(/\D/g, '');
      const stateMap = { '1': 'now', '2': 'next', '3': 'later_today' };
      if (taskId && stateMap[key]) {
        fetch(`${base}/tasks/${taskId}/focus-state`, {
          method: 'POST',
          body: new URLSearchParams({ focus_state: stateMap[key] }),
        }).then(() => setTimeout(() => window.location.reload(), 250)).catch(() => {});
        e.preventDefault();
      }
      return;
    }

    // ── F → Focus mode
    if (keyL === 'f') {
      const link = document.querySelector('a[href*="/focus"]');
      if (link) { window.location.href = link.href; e.preventDefault(); }
      return;
    }

    // ── D → Done NOW task
    if (keyL === 'd') {
      const doneBtn = document.querySelector('.now-strip .btn-done-now, .now-strip .btn-check');
      if (doneBtn) { doneBtn.closest('form')?.submit(); e.preventDefault(); }
      return;
    }

    // ── N → Quick-add modal
    if (keyL === 'n') {
      const modal = document.querySelector('.quick-modal');
      if (modal && typeof modal.showModal === 'function' && !modal.open) {
        modal.showModal();
        const input = modal.querySelector('.quick-input');
        if (input) setTimeout(() => input.focus(), 50);
        e.preventDefault();
      }
      return;
    }

    // ── M → Morning Check-In
    if (keyL === 'm') {
      const link = document.querySelector('a[href*="/morning-checkin"]');
      if (link) { window.location.href = link.href; e.preventDefault(); }
      return;
    }

    // ── E → Evening Reset
    if (keyL === 'e') {
      const link = document.querySelector('a[href*="/close-day"]');
      if (link) { window.location.href = link.href; e.preventDefault(); }
      return;
    }

    // ── R → Weekly Review
    if (keyL === 'r') {
      const link = document.querySelector('a[href*="/weekly-review"]');
      if (link) { window.location.href = link.href; e.preventDefault(); }
      return;
    }

    // ── ? → Help overlay
    if (key === '?' || (e.shiftKey && keyL === '/')) {
      const existing = document.getElementById('shortcuts-help');
      if (existing) { existing.remove(); return; }
      const kbd = (k) => `<kbd style="background:var(--md-ctrl-bg,var(--ctrl-bg));padding:.15rem .45rem;border-radius:.28rem;font-weight:700;font-family:inherit;border:1px solid var(--md-border,var(--border));font-size:.82rem;">${k}</kbd>`;
      const help = document.createElement('div');
      help.id = 'shortcuts-help';
      help.style.cssText = 'position:fixed;bottom:2rem;right:2rem;z-index:9999;background:var(--md-surface,var(--surface));border:1px solid var(--md-border,var(--border));border-radius:.85rem;padding:1.35rem 1.5rem;box-shadow:0 8px 32px rgba(0,0,0,.22);font-size:.85rem;line-height:1.9;max-width:310px;font-family:var(--font-body,inherit);';
      help.innerHTML = `
        <div style="font-weight:800;margin-bottom:.6rem;color:var(--md-primary,var(--accent));">Keyboard Shortcuts</div>
        <div style="font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--md-text-faint,#9CA3AF);margin-bottom:.35rem;">Navigation</div>
        <div>${kbd('J')} / ${kbd('K')} &nbsp;Move down / up in task list</div>
        <div>${kbd('Enter')} / ${kbd('Space')} &nbsp;Expand selected task</div>
        <div style="margin-top:.5rem;font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--md-text-faint,#9CA3AF);margin-bottom:.35rem;">Actions</div>
        <div>${kbd('1')} / ${kbd('2')} / ${kbd('3')} &nbsp;Set selected → NOW / NEXT / LATER</div>
        <div>${kbd('D')} &nbsp;Mark NOW task as done</div>
        <div>${kbd('N')} &nbsp;Quick add task</div>
        <div style="margin-top:.5rem;font-size:.7rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--md-text-faint,#9CA3AF);margin-bottom:.35rem;">Pages</div>
        <div>${kbd('F')} &nbsp;Focus mode</div>
        <div>${kbd('M')} &nbsp;Morning Check-In</div>
        <div>${kbd('E')} &nbsp;Evening Reset</div>
        <div>${kbd('R')} &nbsp;Weekly Review</div>
        <div>${kbd('Esc')} &nbsp;Close / deselect</div>
        <div>${kbd('?')} &nbsp;Show this help</div>
        <div style="margin-top:.65rem;font-size:.78rem;color:var(--md-text-faint,#9CA3AF);cursor:pointer;" onclick="this.parentElement.remove()">Click anywhere to close</div>
      `;
      document.body.appendChild(help);
      setTimeout(() => {
        document.addEventListener('click', function handler(ev) {
          if (!help.contains(ev.target)) { help.remove(); document.removeEventListener('click', handler); }
        });
      }, 100);
    }
  });

  // Add data-task-id to task rows so 1/2/3 can find the task ID
  document.querySelectorAll('.task-card[id], .win-row[data-id], .task-row[data-task-id]').forEach(row => {
    if (!row.dataset.taskId) {
      const m = (row.id || row.dataset.id || '').match(/\d+/);
      if (m) row.dataset.taskId = m[0];
    }
  });
});

// ─── Day Flow Bar (injected below nav on flow pages) ─────────────────────────
(function() {
  const flowPages = ['/my-day', '/morning-checkin', '/focus', '/close-day'];
  const onFlow = flowPages.some(p => window.location.pathname.includes(p));
  if (!onFlow) return;

  const base = (window._MYDAY_BASE || window.location.pathname.split('/my-day')[0].split('/morning')[0].split('/focus')[0].split('/close')[0]).replace(/\/$/, '');
  const apiBase = base || '/task-manager';

  fetch(apiBase + '/api/today-status')
    .then(r => r.json())
    .then(s => {
      const steps = [
        { key: 'checkin',  label: '✦ Check-In',  done: s.has_checkin, href: apiBase + '/morning-checkin' },
        { key: 'my-day',   label: '☀ My Day',    done: s.started,     href: apiBase + '/my-day' },
        { key: 'focus',    label: '⏱ Focus',     done: false,         href: apiBase + '/focus' },
        { key: 'close',    label: '🌙 Close Day', done: s.day_closed,  href: apiBase + '/close-day' },
      ];
      const path = window.location.pathname;
      let activeIdx = 1;
      if (path.includes('/morning')) activeIdx = 0;
      else if (path.includes('/focus'))  activeIdx = 2;
      else if (path.includes('/close'))  activeIdx = 3;

      const bar = document.createElement('div');
      bar.className = 'day-flow-bar';
      bar.setAttribute('role', 'navigation');
      bar.setAttribute('aria-label', 'Daily flow progress');

      steps.forEach((step, i) => {
        if (i > 0) {
          const arrow = document.createElement('span');
          arrow.className = 'dfb-arrow';
          arrow.textContent = '›';
          bar.appendChild(arrow);
        }
        const el = document.createElement('a');
        el.href = step.href;
        el.className = 'dfb-step';
        if (i === activeIdx) el.classList.add('active');
        else if (step.done)  el.classList.add('done');
        else                 el.classList.add('pending');
        el.textContent = (step.done && i !== activeIdx ? '✓ ' : '') + step.label;
        bar.appendChild(el);
      });

      const nav = document.querySelector('nav');
      if (nav) nav.insertAdjacentElement('afterend', bar);
    })
    .catch(() => {}); // silent fail — not critical
})();

// ─── Task-row click toggle (sticky meta expansion) ───────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.task-row').forEach(row => {
    row.addEventListener('click', e => {
      if (e.target.closest('button, a, form, input')) return;
      row.classList.toggle('expanded');
    });
  });

  // CoP accordion: persist open/closed state in localStorage
  const cop = document.querySelector('.cop-accordion');
  if (cop) {
    const stored = localStorage.getItem('myday-cop-open');
    if (stored === 'true') cop.setAttribute('open', '');
    else if (stored === 'false') cop.removeAttribute('open');
    cop.addEventListener('toggle', () => {
      localStorage.setItem('myday-cop-open', cop.open ? 'true' : 'false');
    });
  }
});

// ─── Subtask helpers (NOW strip, Phase 3.5) ──────────────────────────────────
const _SUBTASK_BASE = (function() {
  const m = window.location.pathname.match(/^(\/[^/]+)\/my-day/);
  return m ? m[1] : '/task-manager';
})();

function addSubtask(taskId, input) {
  const title = input.value.trim();
  if (!title) return;
  const body = new FormData();
  body.append('title', title);
  fetch(`${_SUBTASK_BASE}/tasks/${taskId}/subtasks`, { method: 'POST', body })
    .then(r => r.json())
    .then(sub => {
      input.value = '';
      let list = document.getElementById(`subtask-list-${taskId}`);
      if (!list) {
        list = document.createElement('div');
        list.className = 'subtask-list';
        list.id = `subtask-list-${taskId}`;
        list.innerHTML = '<div class="subtask-progress"><div class="subtask-progress-bar" style="width:0%"></div></div><div class="subtask-count">0/0 steps</div>';
        input.closest('.subtask-add-row').insertAdjacentElement('beforebegin', list);
      }
      const row = document.createElement('div');
      row.className = 'subtask-row';
      row.id = `subrow-${sub.id}`;
      row.innerHTML = `
        <button class="subtask-check" onclick="toggleSubtask(${taskId},${sub.id},this)"></button>
        <span class="subtask-title">${sub.title.replace(/</g,'&lt;')}</span>
        <button class="subtask-del" onclick="deleteSubtask(${taskId},${sub.id},this)" title="Remove">×</button>`;
      list.appendChild(row);
      _updateSubtaskProgress(taskId);
    })
    .catch(() => {});
}

function toggleSubtask(taskId, subId, btn) {
  fetch(`${_SUBTASK_BASE}/tasks/${taskId}/subtasks/${subId}/toggle`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      const row = document.getElementById(`subrow-${subId}`);
      if (!row) return;
      row.classList.toggle('done', data.is_done);
      btn.classList.toggle('checked', data.is_done);
      btn.textContent = data.is_done ? '✓' : '';
      _updateSubtaskProgress(taskId);
    })
    .catch(() => {});
}

function deleteSubtask(taskId, subId, btn) {
  fetch(`${_SUBTASK_BASE}/tasks/${taskId}/subtasks/${subId}`, { method: 'DELETE' })
    .then(() => {
      document.getElementById(`subrow-${subId}`)?.remove();
      _updateSubtaskProgress(taskId);
    })
    .catch(() => {});
}

function _updateSubtaskProgress(taskId) {
  const list = document.getElementById(`subtask-list-${taskId}`);
  if (!list) return;
  const rows = list.querySelectorAll('.subtask-row');
  const done = [...rows].filter(r => r.classList.contains('done')).length;
  const total = rows.length;
  const bar = list.querySelector('.subtask-progress-bar');
  const count = list.querySelector('.subtask-count');
  if (bar) bar.style.width = total ? `${Math.round(done/total*100)}%` : '0%';
  if (count) count.textContent = `${done}/${total} steps`;
}

// ─── Progressive form submission (3.6) ────────────────────────────────────────
// Usage: onsubmit="return progressiveSubmit(this, pDone|pDismiss|pSoftReload)"
// All backend routes work as-is — fetch() follows their 303 redirect to My Day.

function progressiveSubmit(form, onSuccess) {
  const fd = new FormData(form);
  fetch(form.action, {
    method: 'POST',
    body: fd,
    headers: { 'X-Requested-With': 'fetch' },
  })
    .then(r => { if (r.ok || r.redirected) onSuccess(form); })
    .catch(() => form.submit());
  return false;
}

// "✓ Done" — confetti flash then slide out
function pDone(form) {
  const btn = form.querySelector('button');
  if (btn && typeof fireConfettiAt === 'function') fireConfettiAt(btn);
  const row = form.closest('.win-row, .nice-row, .task-row');
  if (!row) { setTimeout(() => window.location.reload(), 300); return; }
  // Brief strikethrough before removing
  const titleEl = row.querySelector('.win-title, .task-row-title');
  if (titleEl) { titleEl.style.textDecoration = 'line-through'; titleEl.style.color = 'var(--text-faint)'; }
  setTimeout(() => _pSlideOut(row, _pUpdateCounters), 550);
}

// "Move to Later / Park" — silent slide out
function pDismiss(form) {
  const row = form.closest('.win-row, .nice-row, .task-row');
  _pSlideOut(row, _pUpdateCounters);
}

// "Set as Now / focus-state change" — needs NOW strip refresh so soft-reload
function pSoftReload(_form) {
  setTimeout(() => window.location.reload(), 260);
}

function _pSlideOut(el, cb) {
  if (!el) { setTimeout(() => window.location.reload(), 300); return; }
  el.style.overflow = 'hidden';
  el.style.maxHeight = el.scrollHeight + 'px';
  el.style.transition = 'opacity .32s ease, max-height .38s ease, margin .38s ease, padding .38s ease';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      el.style.opacity = '0';
      el.style.maxHeight = '0';
      el.style.marginTop = '0';
      el.style.marginBottom = '0';
      el.style.paddingTop = '0';
      el.style.paddingBottom = '0';
      setTimeout(() => { el.remove(); if (cb) cb(); }, 400);
    });
  });
}

function _pUpdateCounters() {
  // Wins counter
  const winsSection = document.querySelector('.wins-section');
  if (winsSection) {
    const left = winsSection.querySelectorAll('.win-row:not(.is-done)').length;
    const done = winsSection.querySelectorAll('.win-row.is-done').length;
    const wcEl = winsSection.querySelector('.wcount');
    if (wcEl) wcEl.textContent = `${left} left · ${done} done`;
  }
  // Plan count
  const planCount = document.querySelector('.section .count');
  if (planCount) {
    const rows = document.querySelectorAll('.focus-panel .task-row');
    planCount.textContent = rows.length;
  }
}

// ─── Inline Quick-Capture (iqSubmit) ─────────────────────────────────────────
function iqSubmit(form) {
  const input = form.querySelector('.iqa-input');
  const title = input.value.trim();
  if (!title) return false;

  const data = new FormData(form);
  fetch(form.action, { method: 'POST', body: data })
    .then(r => {
      if (r.ok || r.redirected) {
        input.value = '';
        // Show brief ✓ confirmation
        let msg = form.querySelector('.iqa-success');
        if (!msg) { msg = document.createElement('span'); msg.className = 'iqa-success'; form.appendChild(msg); }
        msg.textContent = '✓ Added';
        setTimeout(() => { msg.textContent = ''; }, 1800);
        // Soft-reload just the wins / plan sections after a short delay
        setTimeout(() => window.location.reload(), 1000);
      }
    })
    .catch(() => { form.submit(); }); // fallback: normal submit
  return false; // prevent default form submit
}

// ─── Quick-Add: energy type toggle ──────────────────────────────────────────
function setQuickEnergy(btn) {
  const alreadyActive = btn.classList.contains('active');
  document.querySelectorAll('#quick-energy-row .quick-pri').forEach(b => b.classList.remove('active'));
  document.getElementById('quick-energy-val').value = alreadyActive ? '' : btn.dataset.energy;
  if (!alreadyActive) btn.classList.add('active');
}

// ─── E2: Collapsible sections ─────────────────────────────────────────────────
function toggleSection(headerEl, name) {
  const body = document.getElementById('sb-' + name);
  if (!body) return;
  const isCollapsed = headerEl.classList.toggle('collapsed');
  if (isCollapsed) {
    body.style.maxHeight = body.scrollHeight + 'px';
    requestAnimationFrame(() => body.classList.add('collapsed'));
  } else {
    body.classList.remove('collapsed');
    body.style.maxHeight = body.scrollHeight + 'px';
    setTimeout(() => { body.style.maxHeight = ''; }, 300);
  }
  try { localStorage.setItem('myday_section_' + name, isCollapsed ? 'closed' : 'open'); } catch(e) {}
}

function _initSections() {
  const defaults = { wins: 'open', nice: null, plan: 'open', timeblocks: 'closed' };
  document.querySelectorAll('[data-section]').forEach(header => {
    const name = header.dataset.section;
    const body = document.getElementById('sb-' + name);
    if (!body) return;
    let saved;
    try { saved = localStorage.getItem('myday_section_' + name); } catch(e) {}
    let shouldClose;
    if (saved === 'open') shouldClose = false;
    else if (saved === 'closed') shouldClose = true;
    else {
      // default logic
      if (name === 'nice') {
        const defClosed = header.dataset.defaultClosed === 'true';
        shouldClose = defClosed;
      } else {
        shouldClose = defaults[name] === 'closed';
      }
    }
    if (shouldClose) {
      header.classList.add('collapsed');
      body.classList.add('collapsed');
      body.style.maxHeight = '0';
    } else {
      body.style.maxHeight = '';
    }
  });
}
document.addEventListener('DOMContentLoaded', _initSections);

// ─── E1: Inline section add ──────────────────────────────────────────────────
function inlineAdd(inputEl, opts) {
  const title = inputEl.value.trim();
  if (!title) return;
  const _base = (typeof BASE !== 'undefined') ? BASE : '';
  fetch(_base + '/tasks/inline-add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, ...opts }),
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) return;
      // Insert a new row above the input container
      const container = inputEl.closest('.section-inline-add');
      const row = document.createElement('div');
      row.className = 'win-row';
      row.style.cssText = 'opacity:0;transition:opacity .25s;';
      row.innerHTML = `<div class="win-body"><div class="win-title">${data.title}</div></div>`;
      container.parentNode.insertBefore(row, container);
      requestAnimationFrame(() => { row.style.opacity = '1'; });
      inputEl.value = '';
      inputEl.focus();
      // Show brief confirmation
      let msg = container.querySelector('.iqa-success');
      if (!msg) { msg = document.createElement('span'); msg.className = 'iqa-success'; container.appendChild(msg); }
      msg.textContent = '✓ Added';
      setTimeout(() => { msg.textContent = ''; }, 1800);
    })
    .catch(() => {});
}
