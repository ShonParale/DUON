/* ══════════════════════════════════════════════════════
   DUON — Advanced Mapping Page  (mapping.js)
   Handles: map CRUD, obstacle draw/edit, heat map,
            bot pose, autonomous explore, canvas render.
   Uses the global `send()` and `ws` from main.js.
══════════════════════════════════════════════════════ */

// ── State ──────────────────────────────────────────────────
const advState = {
  active_map:  null,
  room_width:  400,
  room_height: 400,
  obstacles:   [],
  heat_map:    [],
  bot:         { x: 0, y: 0, h: 0 },
  exploring:   false,
  navigating:  false,
  nav_path:    [],
  nav_target:  null,
};
let advMapsList = [];

// Canvas / view
let advCvs, advCtx;
let advCmPx   = 1.2;
let advPanX   = 0, advPanY = 0;
let advPanning = false, advLastPx = 0, advLastPy = 0;

// Drawing new obstacle
let advDrawing   = false;
let advDrawStart = null;
let advDrawCur   = null;

// Selected/editing obstacle
let advEditId = null;

// Touch pan
let advT1 = null;

// Guard: canvas events bound only once
let advInitDone = false;

// Canvas interaction mode: 'draw' | 'set_pos' | 'set_target'
let advCanvasMode = 'draw';

// ── Init ───────────────────────────────────────────────────
function advInit() {
  advCvs = document.getElementById('advCanvas');
  if (!advCvs) return;
  advCtx = advCvs.getContext('2d');
  if (!advInitDone) {
    advBindCanvas();
    window.addEventListener('resize', () => { advResizeCanvas(); advDraw(); });
    advInitDone = true;
  }
  advResizeCanvas();
  advRefreshUI();
  advDraw();
  // Send state request — retry up to 10x if WS not ready yet
  let _tries = 0;
  const _tryGet = () => {
    if (typeof send === 'function' && typeof wsReady !== 'undefined' && wsReady) {
      send({ cmd: 'ADV_GET_STATE' });
    } else if (_tries++ < 10) {
      setTimeout(_tryGet, 200);
    }
  };
  _tryGet();
}

// ── Message handler (called from main.js handleMsg) ────────
function handleAdvMsg(msg) {
  if (msg.type === 'adv_map') {
    Object.assign(advState, {
      active_map:  msg.active_map !== undefined ? msg.active_map : advState.active_map,
      room_width:  msg.room_width !== undefined ? msg.room_width : advState.room_width,
      room_height: msg.room_height !== undefined ? msg.room_height : advState.room_height,
      resolution:  msg.resolution !== undefined ? msg.resolution : advState.resolution,
      obstacles:   msg.obstacles   || [],
      heat_map:    msg.heat_map    || [],
      bot:         msg.bot         || advState.bot,
      exploring:   msg.exploring !== undefined ? msg.exploring : false,
      navigating:  msg.navigating !== undefined ? msg.navigating : false,
      nav_path:    Array.isArray(msg.nav_path)   ? msg.nav_path   : advState.nav_path,
      nav_target:  msg.nav_target !== undefined  ? msg.nav_target : advState.nav_target,
    });
    // maps_list is included in lifecycle responses
    if (Array.isArray(msg.maps_list)) advApplyMapsList(msg.maps_list);
    advRefreshUI();
    advDraw();
  } else if (msg.type === 'adv_map_list') {
    advApplyMapsList(Array.isArray(msg.maps) ? msg.maps : []);
    advRefreshUI();
  } else if (msg.type === 'sonar') {
    const el = document.getElementById('adv-sonar-vals');
    if (el) el.textContent =
      `L: ${msg.L.toFixed(0)} cm\u2002|\u2002F: ${msg.F.toFixed(0)} cm\u2002|\u2002R: ${msg.R.toFixed(0)} cm`;
  }
}

// ── Map list helpers ───────────────────────────────────────
function advApplyMapsList(list) {
  advMapsList = list;
  const sel = document.getElementById('adv-map-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Select Map --</option>';
  list.forEach(function(n) {
    const o = document.createElement('option');
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  });
  // Sync dropdown to whichever map is active
  if (advState.active_map) sel.value = advState.active_map;
}

function advRefreshUI() {
  var lbl = document.getElementById('adv-active-lbl');
  if (lbl) {
    lbl.textContent = advState.active_map ? 'Active: ' + advState.active_map : 'No map loaded';
    lbl.style.color = advState.active_map ? 'var(--success)' : 'var(--text-3)';
  }

  var sel = document.getElementById('adv-map-select');
  if (sel && advState.active_map && sel.value !== advState.active_map) {
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === advState.active_map) { sel.value = advState.active_map; break; }
    }
  }

  var rw = document.getElementById('adv-room-w');
  var rh = document.getElementById('adv-room-h');
  if (rw && document.activeElement !== rw) rw.value = advState.room_width;
  if (rh && document.activeElement !== rh) rh.value = advState.room_height;

  var eb = document.getElementById('adv-explore-btn');
  if (eb) {
    if (advState.exploring) {
      eb.textContent = '\u23f9 Stop Exploring';
      eb.className   = 'btn btn-danger';
    } else {
      eb.textContent = '\u25b6 Start Exploring';
      eb.className   = 'btn btn-primary';
    }
  }

  // Navigation status
  var ns = document.getElementById('adv-nav-status');
  if (ns) {
    if (advState.navigating) {
      ns.textContent = 'Status: Navigating to (' +
        (advState.nav_target ? advState.nav_target[0].toFixed(0) + ', ' + advState.nav_target[1].toFixed(0) : '?') + ') cm';
      ns.style.color = 'var(--accent)';
    } else {
      ns.textContent = 'Status: Idle';
      ns.style.color = 'var(--text-3)';
    }
  }

  var bx = document.getElementById('adv-pose-x');
  var by = document.getElementById('adv-pose-y');
  var bh = document.getElementById('adv-pose-h');
  if (bx) bx.textContent = advState.bot.x.toFixed(0);
  if (by) by.textContent = advState.bot.y.toFixed(0);
  if (bh) bh.textContent = advState.bot.h.toFixed(0) + '\u00b0';

  advRenderObsList();
}


// ── Obstacle list panel ────────────────────────────────────
function advRenderObsList() {
  const el = document.getElementById('adv-obs-list');
  if (!el) return;
  if (!advState.obstacles.length) {
    el.innerHTML = '<div class="adv-obs-empty">No obstacles added yet</div>';
    return;
  }
  el.innerHTML = advState.obstacles.map(o => `
    <div class="adv-obs-item" data-id="${o.id}">
      <div class="adv-obs-name">${o.name}</div>
      <div class="adv-obs-coords">(${o.x1.toFixed(0)},${o.y1.toFixed(0)}) → (${o.x2.toFixed(0)},${o.y2.toFixed(0)})</div>
      <div class="adv-obs-btns">
        <button class="btn btn-outline btn-sm" onclick="advStartEditObs('${o.id}')">✎ Edit</button>
        <button class="btn btn-danger-soft btn-sm" onclick="advRemoveObs('${o.id}')">✕</button>
      </div>
    </div>
  `).join('');
}

// ── Map lifecycle actions ──────────────────────────────────
function advMapNew() {
  // Mobile-safe: use inline input row instead of relying on prompt
  const inp = document.getElementById('adv-newmap-inp');
  if (inp) {
    inp.style.display = inp.style.display === 'none' ? 'flex' : 'none';
    if (inp.style.display !== 'none') document.getElementById('adv-newmap-name').focus();
    return;
  }
  // Fallback for browsers without the inline row
  const name = prompt('Enter map name:');
  if (!name || !name.trim()) return;
  send({ cmd: 'ADV_MAP_NEW', name: name.trim() });
}

function advMapNewConfirm() {
  const el = document.getElementById('adv-newmap-name');
  if (!el) return;
  const name = el.value.trim();
  if (!name) { el.focus(); return; }
  send({ cmd: 'ADV_MAP_NEW', name });
  el.value = '';
  const row = document.getElementById('adv-newmap-inp');
  if (row) row.style.display = 'none';
}

function advMapLoad() {
  const sel = document.getElementById('adv-map-select');
  if (!sel || !sel.value) { alert('Select a map first.'); return; }
  send({ cmd: 'ADV_MAP_LOAD', name: sel.value });
}

function advMapSave() {
  if (!advState.active_map) { alert('No active map. Load or create one first.'); return; }
  send({ cmd: 'ADV_MAP_SAVE' });
}

function advMapClose() {
  if (!advState.active_map) return;
  if (!confirm(`Close map "${advState.active_map}"? (File is kept on disk)`)) return;
  send({ cmd: 'ADV_MAP_CLOSE' });
}

function advMapDelete() {
  const sel = document.getElementById('adv-map-select');
  const name = (sel && sel.value) ? sel.value : advState.active_map;
  if (!name) { alert('Select a map to delete.'); return; }
  if (!confirm(`Delete map "${name}" from disk? This cannot be undone.`)) return;
  send({ cmd: 'ADV_MAP_DELETE', name });
}

function advRefreshList() {
  send({ cmd: 'ADV_MAP_LIST' });
}

// ── Room size ──────────────────────────────────────────────
function advSetRoom() {
  if (!advState.active_map) { alert('Load or create a map first.'); return; }
  const w = parseFloat(document.getElementById('adv-room-w').value);
  const h = parseFloat(document.getElementById('adv-room-h').value);
  if (!w || !h || w < 50 || h < 50) { alert('Enter valid dimensions (min 50 cm).'); return; }
  send({ cmd: 'ADV_SET_ROOM', width: w, height: h });
}

// ── Obstacle actions ───────────────────────────────────────
function advAddObs() {
  if (!advState.active_map) { alert('Load or create a map first.'); return; }
  const name = (document.getElementById('adv-obs-name').value || 'Obstacle').trim();
  const x1 = parseFloat(document.getElementById('adv-obs-x1').value);
  const y1 = parseFloat(document.getElementById('adv-obs-y1').value);
  const x2 = parseFloat(document.getElementById('adv-obs-x2').value);
  const y2 = parseFloat(document.getElementById('adv-obs-y2').value);
  if ([x1,y1,x2,y2].some(isNaN)) { alert('Enter all four coordinates.'); return; }
  send({ cmd: 'ADV_OBS_ADD', name, x1, y1, x2, y2 });
  ['adv-obs-name','adv-obs-x1','adv-obs-y1','adv-obs-x2','adv-obs-y2']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
}

function advStartEditObs(id) {
  const obs = advState.obstacles.find(o => o.id === id);
  if (!obs) return;
  advEditId = id;
  document.getElementById('adv-obs-name').value = obs.name;
  document.getElementById('adv-obs-x1').value   = obs.x1;
  document.getElementById('adv-obs-y1').value   = obs.y1;
  document.getElementById('adv-obs-x2').value   = obs.x2;
  document.getElementById('adv-obs-y2').value   = obs.y2;
  const addBtn = document.getElementById('adv-obs-add-btn');
  if (addBtn) { addBtn.textContent = '✔ Update Obstacle'; addBtn.onclick = advUpdateObs; }
  document.getElementById('adv-obs-name').focus();
}

function advUpdateObs() {
  if (!advEditId) return;
  const name = (document.getElementById('adv-obs-name').value || 'Obstacle').trim();
  const x1 = parseFloat(document.getElementById('adv-obs-x1').value);
  const y1 = parseFloat(document.getElementById('adv-obs-y1').value);
  const x2 = parseFloat(document.getElementById('adv-obs-x2').value);
  const y2 = parseFloat(document.getElementById('adv-obs-y2').value);
  if ([x1,y1,x2,y2].some(isNaN)) { alert('Enter all four coordinates.'); return; }
  send({ cmd: 'ADV_OBS_UPDATE', id: advEditId, name, x1, y1, x2, y2 });
  advCancelEdit();
}

function advCancelEdit() {
  advEditId = null;
  ['adv-obs-name','adv-obs-x1','adv-obs-y1','adv-obs-x2','adv-obs-y2']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const addBtn = document.getElementById('adv-obs-add-btn');
  if (addBtn) { addBtn.textContent = '+ Add Obstacle'; addBtn.onclick = advAddObs; }
}

function advRemoveObs(id) {
  if (!confirm('Delete this obstacle?')) return;
  send({ cmd: 'ADV_OBS_REMOVE', id });
}

// ── Heat map ───────────────────────────────────────────────
function advHeatClear() {
  if (!confirm('Clear all sonar heat map points?')) return;
  send({ cmd: 'ADV_HEAT_CLEAR' });
}

// ── Explore ────────────────────────────────────────────────
function advToggleExplore() {
  if (!advState.active_map) { alert('Load or create a map before exploring.'); return; }
  if (advState.exploring) {
    send({ cmd: 'ADV_EXPLORE_STOP' });
  } else {
    send({ cmd: 'ADV_EXPLORE_START' });
  }
}

// ══════════════════════════════════════════════════════════
// CANVAS
// ══════════════════════════════════════════════════════════

function advResizeCanvas() {
  const wrap = document.getElementById('adv-canvas-wrap');
  if (!wrap || !advCvs) return;
  const w = wrap.clientWidth  || 600;
  const h = wrap.clientHeight || Math.max(360, window.innerHeight - 260);
  if (advCvs.width !== w || advCvs.height !== h) {
    advCvs.width  = w;
    advCvs.height = h;
  }
  advDraw();
}

// Convert world cm → canvas px
function advW2C(wx, wy) {
  const cx = advCvs.width  / 2 + advPanX;
  const cy = advCvs.height / 2 + advPanY;
  return [
    cx + wx / advCmPx,
    cy - wy / advCmPx,
  ];
}

// Convert canvas px → world cm
function advC2W(px, py) {
  const cx = advCvs.width  / 2 + advPanX;
  const cy = advCvs.height / 2 + advPanY;
  return [
    (px - cx) * advCmPx,
    (cy - py) * advCmPx,
  ];
}

function advDraw() {
  if (!advCvs || !advCtx) return;
  const W = advCvs.width, H = advCvs.height;
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  const ctx  = advCtx;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = dark ? '#0a0a14' : '#f7f8fc';
  ctx.fillRect(0, 0, W, H);

  // Grid
  const ox = W / 2 + advPanX, oy = H / 2 + advPanY;
  const sp = Math.max(10, 50) / advCmPx;
  ctx.lineWidth   = 1;
  ctx.strokeStyle = dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.07)';
  for (let x = ox % sp - sp; x < W; x += sp) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }
  for (let y = oy % sp - sp; y < H; y += sp) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }

  // Axes
  ctx.strokeStyle = dark ? 'rgba(14,165,233,0.15)' : 'rgba(14,165,233,0.18)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(ox,0); ctx.lineTo(ox,H); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0,oy); ctx.lineTo(W,oy); ctx.stroke();

  // Room boundary
  if (advState.room_width && advState.room_height) {
    const [rx0,ry0] = advW2C(0, 0);
    const [rx1,ry1] = advW2C(advState.room_width, advState.room_height);
    ctx.strokeStyle = dark ? 'rgba(14,165,233,0.5)' : 'rgba(14,165,233,0.6)';
    ctx.lineWidth   = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(rx0, ry1, rx1 - rx0, ry0 - ry1);
    ctx.setLineDash([]);
  }

  // Heat map (amber dots)
  ctx.fillStyle = 'rgba(251,191,36,0.75)';
  (advState.heat_map || []).forEach(p => {
    const [cx, cy] = advW2C(p[0], p[1]);
    if (cx > -6 && cx < W+6 && cy > -6 && cy < H+6) {
      ctx.beginPath(); ctx.arc(cx, cy, 3.5, 0, Math.PI*2); ctx.fill();
    }
  });

  // Obstacles
  (advState.obstacles || []).forEach(obs => {
    const [ax, ay] = advW2C(obs.x1, obs.y1);
    const [bx, by] = advW2C(obs.x2, obs.y2);
    const rx = Math.min(ax, bx), ry = Math.min(ay, by);
    const rw = Math.abs(bx - ax), rh = Math.abs(by - ay);
    const isEditing = (obs.id === advEditId);

    ctx.fillStyle   = isEditing
      ? (dark ? 'rgba(139,92,246,0.35)' : 'rgba(139,92,246,0.25)')
      : (dark ? 'rgba(239,68,68,0.35)'  : 'rgba(239,68,68,0.20)');
    ctx.strokeStyle = isEditing ? '#8b5cf6' : '#ef4444';
    ctx.lineWidth   = isEditing ? 2.5 : 2;
    ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeRect(rx, ry, rw, rh);

    // Label
    ctx.fillStyle  = dark ? '#f8f8f8' : '#111';
    ctx.font       = `bold ${Math.max(10, Math.min(14, rw/6))}px Inter, sans-serif`;
    ctx.textAlign  = 'center';
    ctx.textBaseline = 'middle';
    if (rw > 20 && rh > 12) {
      ctx.fillText(obs.name, rx + rw/2, ry + rh/2);
    }
  });
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';

  // In-progress draw rectangle
  if (advDrawing && advDrawStart && advDrawCur) {
    const rx = Math.min(advDrawStart.px, advDrawCur.px);
    const ry = Math.min(advDrawStart.py, advDrawCur.py);
    const rw = Math.abs(advDrawCur.px - advDrawStart.px);
    const rh = Math.abs(advDrawCur.py - advDrawStart.py);
    ctx.fillStyle   = 'rgba(14,165,233,0.18)';
    ctx.strokeStyle = '#0ea5e9';
    ctx.lineWidth   = 2;
    ctx.setLineDash([5,3]);
    ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeRect(rx, ry, rw, rh);
    ctx.setLineDash([]);
  }

  // Nav path (cyan dashed line)
  if (advState.nav_path && advState.nav_path.length > 1) {
    ctx.strokeStyle = '#0ea5e9';
    ctx.lineWidth   = 2.5;
    ctx.setLineDash([8, 4]);
    ctx.beginPath();
    for (var pi = 0; pi < advState.nav_path.length; pi++) {
      var pp = advState.nav_path[pi];
      var pxy = advW2C(pp[0], pp[1]);
      if (pi === 0) ctx.moveTo(pxy[0], pxy[1]);
      else          ctx.lineTo(pxy[0], pxy[1]);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Target B point
  if (advState.nav_target) {
    var txy = advW2C(advState.nav_target[0], advState.nav_target[1]);
    ctx.fillStyle   = 'rgba(239,68,68,0.85)';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.arc(txy[0], txy[1], 10, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle    = '#fff';
    ctx.font         = 'bold 11px Inter,sans-serif';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('B', txy[0], txy[1]);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  }

  // Bot
  const bot = advState.bot;
  const [bcx, bcy] = advW2C(bot.x, bot.y);
  const hr = bot.h * Math.PI / 180;

  ctx.shadowColor = dark ? '#f1c40f' : 'transparent';
  ctx.shadowBlur  = dark ? 12 : 0;
  ctx.fillStyle   = '#f1c40f';
  ctx.beginPath();
  ctx.moveTo(bcx, bcy-10);
  ctx.lineTo(bcx+9, bcy+5);
  ctx.lineTo(bcx, bcy+3);
  ctx.lineTo(bcx-9, bcy+5);
  ctx.closePath(); ctx.fill();
  ctx.shadowBlur = 0;

  // Heading line
  const hl = Math.max(16, 28 / advCmPx);
  ctx.strokeStyle = '#f1c40f'; ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(bcx, bcy);
  ctx.lineTo(bcx + hl*Math.sin(hr), bcy - hl*Math.cos(hr));
  ctx.stroke();

  // Zoom label
  ctx.fillStyle    = dark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.25)';
  ctx.font         = '11px Inter, sans-serif';
  ctx.textAlign    = 'right';
  ctx.textBaseline = 'bottom';
  ctx.fillText(`${advCmPx.toFixed(1)} cm/px`, W-8, H-6);
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
}

// ── Canvas event binding ───────────────────────────────────
function advBindCanvas() {
  // Zoom
  advCvs.addEventListener('wheel', e => {
    e.preventDefault();
    advCmPx = e.deltaY > 0 ? advCmPx * 1.12 : advCmPx * 0.88;
    advCmPx = Math.max(0.2, Math.min(30, advCmPx));
    advDraw();
  }, { passive: false });

  // Double-click: reset view
  advCvs.addEventListener('dblclick', () => {
    advPanX = 0; advPanY = 0; advCmPx = 1.2; advDraw();
  });

  // Mouse: draw obstacle or pan
  advCvs.addEventListener('mousedown', function(e) {
    if (e.button !== 0) return;
    var rect = advCvs.getBoundingClientRect();
    var mx = e.clientX - rect.left, my = e.clientY - rect.top;

    // Ctrl+drag = pan always
    if (e.ctrlKey || e.metaKey) {
      advPanning = true; advLastPx = e.clientX; advLastPy = e.clientY;
      advCvs.style.cursor = 'grabbing'; return;
    }

    if (!advState.active_map) {
      advPanning = true; advLastPx = e.clientX; advLastPy = e.clientY;
      advCvs.style.cursor = 'grabbing'; return;
    }

    // Mode: Set Bot Position
    if (advCanvasMode === 'set_pos') {
      var wp = advC2W(mx, my);
      var bpx = document.getElementById('adv-botpos-x');
      var bpy = document.getElementById('adv-botpos-y');
      if (bpx) bpx.value = Math.round(wp[0]);
      if (bpy) bpy.value = Math.round(wp[1]);
      advApplyBotPos();
      advSetCanvasMode('draw');
      return;
    }

    // Mode: Set Navigation Target
    if (advCanvasMode === 'set_target') {
      var wt = advC2W(mx, my);
      var ntx = document.getElementById('adv-nav-tx');
      var nty = document.getElementById('adv-nav-ty');
      if (ntx) ntx.value = Math.round(wt[0]);
      if (nty) nty.value = Math.round(wt[1]);
      advState.nav_target = [wt[0], wt[1]];
      advDraw();
      advSetCanvasMode('draw');
      return;
    }

    // Mode: Draw obstacle
    var hit = advObsAtCanvas(mx, my);
    if (hit) { advStartEditObs(hit.id); return; }
    advDrawing   = true;
    advDrawStart = { px: mx, py: my };
    advDrawCur   = { px: mx, py: my };
  });

  advCvs.addEventListener('mousemove', e => {
    const rect = advCvs.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    if (advPanning) {
      advPanX += e.clientX - advLastPx; advPanY += e.clientY - advLastPy;
      advLastPx = e.clientX; advLastPy = e.clientY; advDraw(); return;
    }
    if (advDrawing) { advDrawCur = { px: mx, py: my }; advDraw(); }

    // Cursor hint
    if (advState.active_map && !advPanning && !advDrawing) {
      advCvs.style.cursor = advObsAtCanvas(mx, my) ? 'pointer' : 'crosshair';
    }
  });

  advCvs.addEventListener('mouseup', e => {
    if (advPanning) { advPanning = false; advCvs.style.cursor = advState.active_map ? 'crosshair' : 'grab'; return; }
    if (!advDrawing) return;
    advDrawing = false;
    const rect = advCvs.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const dx = Math.abs(mx - advDrawStart.px), dy = Math.abs(my - advDrawStart.py);
    if (dx < 8 && dy < 8) { advDrawStart = advDrawCur = null; advDraw(); return; }
    // Convert to world coords
    const [wx1, wy1] = advC2W(advDrawStart.px, advDrawStart.py);
    const [wx2, wy2] = advC2W(mx, my);
    const name = prompt('Obstacle name:', 'Obstacle') || 'Obstacle';
    send({ cmd: 'ADV_OBS_ADD', name: name.trim(),
      x1: Math.min(wx1,wx2), y1: Math.min(wy1,wy2),
      x2: Math.max(wx1,wx2), y2: Math.max(wy1,wy2) });
    advDrawStart = advDrawCur = null; advDraw();
  });

  advCvs.addEventListener('mouseleave', () => {
    advPanning = false; advDrawing = false;
    advDrawStart = advDrawCur = null; advDraw();
  });

  // Touch pan
  advCvs.addEventListener('touchstart', e => {
    if (e.touches.length === 1) advT1 = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  }, { passive: true });
  advCvs.addEventListener('touchmove', e => {
    if (!advT1 || e.touches.length !== 1) return;
    advPanX += e.touches[0].clientX - advT1.x;
    advPanY += e.touches[0].clientY - advT1.y;
    advT1 = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    advDraw();
  }, { passive: true });
  advCvs.addEventListener('touchend', () => advT1 = null, { passive: true });
}

// ── Hit-test obstacle at canvas coords ────────────────────
function advObsAtCanvas(px, py) {
  for (let i = advState.obstacles.length - 1; i >= 0; i--) {
    const obs = advState.obstacles[i];
    const [ax, ay] = advW2C(obs.x1, obs.y1);
    const [bx, by] = advW2C(obs.x2, obs.y2);
    const rx = Math.min(ax,bx), ry = Math.min(ay,by);
    const rw = Math.abs(bx-ax), rh = Math.abs(by-ay);
    if (px >= rx && px <= rx+rw && py >= ry && py <= ry+rh) return obs;
  }
  return null;
}

// ══════════════════════════════════════════════════════════
// CANVAS MODE SYSTEM
// ══════════════════════════════════════════════════════════

function advSetCanvasMode(mode) {
  advCanvasMode = mode;
  var labels = {
    'draw':       'Mode: Draw Obstacle \u2014 Drag on canvas to draw',
    'set_pos':    'Mode: Set Bot Pos \u2014 Click on canvas to place bot (A)',
    'set_target': 'Mode: Set Target \u2014 Click on canvas to place target (B)',
  };
  var lbl = document.getElementById('adv-canvas-mode-lbl');
  if (lbl) lbl.textContent = (labels[mode] || '') + ' \u00a0|\u00a0 Scroll=Zoom \u00a0|\u00a0 Ctrl+Drag=Pan';

  // Highlight active mode button
  ['draw','setpos','settgt'].forEach(function(id) {
    var btn = document.getElementById('adv-mode-' + id);
    if (btn) btn.style.borderColor = '';
  });
  var activeMap = { 'draw': 'adv-mode-draw', 'set_pos': 'adv-mode-setpos', 'set_target': 'adv-mode-settgt' };
  var activeBtn = document.getElementById(activeMap[mode]);
  if (activeBtn) activeBtn.style.borderColor = 'var(--accent)';

  // Update cursor
  if (advCvs) {
    advCvs.style.cursor = mode === 'draw' ? 'crosshair' : 'cell';
  }
}

// ══════════════════════════════════════════════════════════
// NAVIGATION FUNCTIONS
// ══════════════════════════════════════════════════════════

function advApplyBotPos() {
  var x = parseFloat(document.getElementById('adv-botpos-x').value);
  var y = parseFloat(document.getElementById('adv-botpos-y').value);
  var h = parseFloat(document.getElementById('adv-botpos-h').value);
  if (isNaN(x) || isNaN(y)) { alert('Enter X and Y coordinates.'); return; }
  send({ cmd: 'ADV_SET_BOT_POS', x: x, y: y, heading: isNaN(h) ? 0 : h });
}

function advNavTo() {
  if (!advState.active_map) { alert('Load or create a map first.'); return; }
  var tx = parseFloat(document.getElementById('adv-nav-tx').value);
  var ty = parseFloat(document.getElementById('adv-nav-ty').value);
  if (isNaN(tx) || isNaN(ty)) { alert('Enter target X and Y coordinates, or click "Click on Map".'); return; }
  if (advState.navigating) { alert('Already navigating. Stop first.'); return; }
  advState.nav_target = [tx, ty];
  advDraw();
  send({ cmd: 'ADV_NAV_TO', tx: tx, ty: ty });
}

function advNavStop() {
  send({ cmd: 'ADV_NAV_STOP' });
}
