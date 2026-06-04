// ── Task Detail Panel ─────────────────────────────────────────────────────────
(function () {
  var _taskId = null;
  var _projects = [];
  var _dirty = false;
  var _expanded = false;
  var BASE = '/task-manager';

  // ── Open / Close ──────────────────────────────────────────────────────────
  window.openTaskPanel = function (taskId) {
    _taskId = taskId;
    _dirty = false;
    var panel = document.getElementById('task-panel');
    var backdrop = document.getElementById('panel-backdrop');
    if (!panel) return;

    panel.classList.add('open');
    backdrop.classList.add('open');

    var body = document.getElementById('panel-body');
    body.innerHTML = '<div class="panel-loading">Loading\u2026</div>';

    var editLink = document.getElementById('panel-edit-link');
    if (editLink) editLink.href = BASE + '/tasks/' + taskId + '/edit';

    var taskP = fetch(BASE + '/tasks/' + taskId).then(function(r){ return r.json(); });
    var projP = _projects.length
      ? Promise.resolve(_projects)
      : fetch(BASE + '/projects-api').then(function(r){ return r.json(); }).then(function(p){ _projects = p; return p; });

    Promise.all([taskP, projP])
      .then(function(results){ _renderPanel(results[0], results[1]); })
      .catch(function(){ body.innerHTML = '<div class="panel-loading">Error loading task.</div>'; });
  };

  window.closeTaskPanel = function () {
    if (_dirty) _autoSave();
    var panel = document.getElementById('task-panel');
    var backdrop = document.getElementById('panel-backdrop');
    if (panel) panel.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    _taskId = null;
    _expanded = false;
    if (panel) panel.classList.remove('expanded');
  };

  window.togglePanelExpand = function () {
    var panel = document.getElementById('task-panel');
    if (!panel) return;
    _expanded = !_expanded;
    panel.classList.toggle('expanded', _expanded);
    var btn = document.getElementById('panel-expand-btn');
    if (btn) btn.textContent = _expanded ? '\u22a1' : '\u26f6';
  };

  // ── Render ────────────────────────────────────────────────────────────────
  function _renderPanel(task, projects) {
    var tpl = document.getElementById('panel-content-tpl');
    if (!tpl) return;
    var content = tpl.content.cloneNode(true);
    var body = document.getElementById('panel-body');
    body.innerHTML = '';
    body.appendChild(content);

    // Title
    var titleEl = document.getElementById('panel-title');
    if (titleEl) { titleEl.value = task.title || ''; titleEl.addEventListener('input', _markDirty); }

    // Selects
    ['status','priority','focus_state','energy_tag','time_block'].forEach(function(field) {
      var el = document.querySelector('[data-field="' + field + '"]');
      if (!el) return;
      el.value = task[field] || '';
      el.addEventListener('change', _markDirty);
    });

    // Due date
    var ddEl = document.getElementById('panel-due-date');
    if (ddEl) { ddEl.value = task.due_date || ''; ddEl.addEventListener('change', _markDirty); }

    // Description
    var descEl = document.getElementById('panel-description');
    if (descEl) { descEl.value = task.description || ''; descEl.addEventListener('input', _markDirty); }

    // Assignee
    var assigneeEl = document.getElementById('panel-assignee');
    if (assigneeEl) { assigneeEl.value = task.assignee || ''; assigneeEl.addEventListener('input', _markDirty); }

    // Status note
    var snEl = document.getElementById('panel-status-note');
    if (snEl) { snEl.value = task.status_note || ''; snEl.addEventListener('input', _markDirty); }

    // Projects
    var projSel = document.getElementById('panel-project');
    if (projSel) {
      projects.forEach(function(p) {
        var opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        if (p.id === task.project_id) opt.selected = true;
        projSel.appendChild(opt);
      });
      projSel.addEventListener('change', _markDirty);
    }

    _renderSubtasks(task.subtasks || []);
  }

  // ── Subtasks ──────────────────────────────────────────────────────────────
  function _renderSubtasks(subtasks) {
    var list = document.getElementById('panel-subtask-list');
    var bar = document.getElementById('panel-sub-bar');
    var progressText = document.getElementById('panel-sub-progress-text');
    var barWrap = document.getElementById('panel-sub-bar-wrap');
    if (!list) return;

    list.innerHTML = '';
    var done = subtasks.filter(function(s){ return s.is_done; }).length;
    var total = subtasks.length;

    if (barWrap) barWrap.style.display = total ? 'block' : 'none';
    if (total && bar) bar.style.width = Math.round((done / total) * 100) + '%';
    if (progressText) progressText.textContent = total ? done + ' / ' + total : '';

    subtasks.forEach(function(sub) {
      var item = document.createElement('div');
      item.className = 'panel-subtask-item';
      item.dataset.subId = sub.id;

      var check = document.createElement('button');
      check.className = 'panel-subtask-check' + (sub.is_done ? ' done' : '');
      check.title = 'Toggle';
      check.textContent = sub.is_done ? '\u2713' : '';
      check.onclick = function(){ window.panelToggleSubtask(sub.id); };

      var title = document.createElement('span');
      title.className = 'panel-subtask-title' + (sub.is_done ? ' done' : '');
      title.textContent = sub.title;

      var del = document.createElement('button');
      del.className = 'panel-subtask-del';
      del.title = 'Delete';
      del.textContent = '\u2715';
      del.onclick = function(){ window.panelDeleteSubtask(sub.id); };

      item.appendChild(check);
      item.appendChild(title);
      item.appendChild(del);
      list.appendChild(item);
    });
  }

  function _refreshSubtasks() {
    if (!_taskId) return;
    fetch(BASE + '/tasks/' + _taskId)
      .then(function(r){ return r.json(); })
      .then(function(t){ _renderSubtasks(t.subtasks || []); });
  }

  window.panelToggleSubtask = function (subId) {
    if (!_taskId) return;
    fetch(BASE + '/tasks/' + _taskId + '/subtasks/' + subId + '/toggle', { method: 'POST' })
      .then(_refreshSubtasks);
  };

  window.panelDeleteSubtask = function (subId) {
    if (!_taskId) return;
    fetch(BASE + '/tasks/' + _taskId + '/subtasks/' + subId, { method: 'DELETE' })
      .then(_refreshSubtasks);
  };

  window.panelAddSubtask = function () {
    var input = document.getElementById('panel-sub-input');
    var title = input ? input.value.trim() : '';
    if (!title || !_taskId) return;
    var body = new FormData();
    body.append('title', title);
    fetch(BASE + '/tasks/' + _taskId + '/subtasks', { method: 'POST', body: body })
      .then(function(){ input.value = ''; _refreshSubtasks(); });
  };

  // ── Save ──────────────────────────────────────────────────────────────────
  function _markDirty() { _dirty = true; }

  function _gatherPayload() {
    var payload = {};
    var titleEl = document.getElementById('panel-title');
    if (titleEl && titleEl.value.trim()) payload.title = titleEl.value.trim();
    var descEl = document.getElementById('panel-description');
    payload.description = descEl ? (descEl.value || null) : null;
    var statusEl = document.getElementById('panel-status');
    if (statusEl) payload.status = statusEl.value || null;
    var priEl = document.getElementById('panel-priority');
    if (priEl) payload.priority = priEl.value || null;
    var focusEl = document.getElementById('panel-focus');
    if (focusEl) payload.focus_state = focusEl.value || null;
    var energyEl = document.getElementById('panel-energy');
    if (energyEl) payload.energy_tag = energyEl.value || null;
    var tbEl = document.getElementById('panel-timeblock');
    if (tbEl) payload.time_block = tbEl.value || null;
    var ddEl = document.getElementById('panel-due-date');
    payload.due_date = ddEl ? (ddEl.value || null) : null;
    var projEl = document.getElementById('panel-project');
    payload.project_id = (projEl && projEl.value) ? parseInt(projEl.value) : null;
    var assigneeEl = document.getElementById('panel-assignee');
    payload.assignee = assigneeEl ? (assigneeEl.value.trim() || null) : null;
    var snEl = document.getElementById('panel-status-note');
    payload.status_note = snEl ? (snEl.value || null) : null;
    return payload;
  }

  window.panelSave = function () {
    if (!_taskId) return;
    fetch(BASE + '/tasks/' + _taskId, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_gatherPayload())
    }).then(function(r){ return r.json(); }).then(function() {
      _dirty = false;
      var btn = document.getElementById('panel-save-btn');
      if (btn) {
        btn.textContent = 'Saved \u2713';
        btn.classList.add('saved');
        setTimeout(function(){ btn.textContent = 'Save'; btn.classList.remove('saved'); }, 1800);
      }
    });
  };

  function _autoSave() {
    if (!_taskId || !_dirty) return;
    fetch(BASE + '/tasks/' + _taskId, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_gatherPayload())
    });
    _dirty = false;
  }

  window.panelDelete = function () {
    if (!_taskId) return;
    var _confirm = window.showConfirm || function(msg, cb) { if (window.confirm(msg)) cb(); };
    _confirm('Delete this task?', function() {
      fetch(BASE + '/tasks/' + _taskId, { method: 'DELETE' })
        .then(function(){ closeTaskPanel(); location.reload(); });
    });
  };

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  document.addEventListener('keydown', function (e) {
    if (!_taskId) return;
    if (e.key === 'Escape') { closeTaskPanel(); return; }
    var tag = document.activeElement ? document.activeElement.tagName : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key === 'x' || e.key === 'X') togglePanelExpand();
  });
})();
