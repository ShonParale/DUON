/* ══════════════════════════════════════
   DUON Dashboard — Main Application JS
   WebSocket | Controls | Joysticks | Map
══════════════════════════════════════ */

// ── Theme ──────────────────────────────────────────────────
const root = document.documentElement;
let theme = localStorage.getItem('duon-theme') || 'light';
applyTheme(theme);

function applyTheme(t) {
  theme = t;
  root.setAttribute('data-theme', t);
  localStorage.setItem('duon-theme', t);
  document.getElementById('theme-icon').textContent = t === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';
  const settingsCb = document.getElementById('settings-theme-toggle');
  if (settingsCb) settingsCb.checked = (t === 'dark');
  try { if (typeof drawMap === 'function') drawMap(); } catch(e) {}
}
function toggleTheme() { applyTheme(theme === 'light' ? 'dark' : 'light'); }
function settingsToggleTheme(cb) { applyTheme(cb.checked ? 'dark' : 'light'); }

// ── Page Navigation ────────────────────────────────────────
let currentPage = 'home';
function navigate(pageId, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item, .mob-nav-item').forEach(n => n.classList.remove('active'));
  const page = document.getElementById('page-' + pageId);
  if (page) page.classList.add('active');
  document.querySelectorAll(`[data-page="${pageId}"]`).forEach(n => n.classList.add('active'));
  currentPage = pageId;
  if (pageId === 'mapper')  setTimeout(() => { resizeCanvas(); drawMap(); }, 60);
  if (pageId === 'mapping')  setTimeout(() => { if (typeof advInit === 'function') advInit(); }, 60);
  if (pageId === 'network') generateQR();
  // Auto-focus drive page so keyboard works immediately without clicking anything
  if (pageId === 'drive') {
    setTimeout(() => {
      const pg = document.getElementById('page-drive');
      if (pg) pg.focus({ preventScroll: true });
    }, 50);
  }
  return false;
}

// Set default active page
navigate('home', null);

// ── WebSocket ──────────────────────────────────────────────
const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
let ws, wsReady = false;
let pingInterval, wsPingStart = 0, wsLatencyMs = 0;

function initWS() {
  ws = new WebSocket(`${wsProto}//${location.host}/ws`);

  ws.onopen = () => {
    wsReady = true;
    setSBStatus(true);
    logAll('[SYS] Dashboard connected to server', 'ok');
    startPingLoop();
    // Populate mapping state as soon as WS is open (fixes race with advInit)
    send({ cmd: 'ADV_GET_STATE' });
    send({ cmd: 'ADV_MAP_LIST' });
  };
  ws.onclose = () => {
    wsReady = false;
    setSBStatus(false);
    clearInterval(pingInterval);
    logAll('[SYS] Server disconnected — retrying in 2s…', 'warn');
    setTimeout(initWS, 2000);
  };
  ws.onerror = () => { logAll('[SYS] WebSocket error', 'error'); };
  ws.onmessage = (evt) => {
    try { handleMsg(JSON.parse(evt.data)); } catch(e) { console.error('WS parse', e); }
  };
}

function send(obj) {
  if (wsReady && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function startPingLoop() {
  clearInterval(pingInterval);
  pingInterval = setInterval(() => {
    wsPingStart = Date.now();
    send({ cmd: 'PING', ts: wsPingStart });
  }, 5000);
  // immediate first ping
  wsPingStart = Date.now();
  send({ cmd: 'PING', ts: wsPingStart });
}

// ── Message Handler ────────────────────────────────────────
let espState = { esp1: false, esp2: false };

function handleMsg(msg) {
  switch (msg.type) {
    case 'init':
      if (msg.ip1) document.getElementById('ip1').value = msg.ip1;
      if (msg.ip2) document.getElementById('ip2').value = msg.ip2;
      if (msg.conn) applyConnStatus(msg.conn);
      break;
    case 'conn':
      applyConnStatus(msg);
      break;
    case 'log':
      routeLog(msg.msg);
      break;
    case 'sonar':
      updateGauges(msg.L, msg.F, msg.R);
      updateSBSonar(msg.F);
      if (typeof handleAdvMsg === 'function') handleAdvMsg(msg);
      break;
    case 'map':
      mapState = msg;
      if (msg.bot) updatePose(msg.bot);
      drawMap();
      break;
    case 'adv_map':
    case 'adv_map_list':
      if (typeof handleAdvMsg === 'function') handleAdvMsg(msg);
      break;
    case 'status':
      handleStatus(msg);
      break;
    case 'estop':
      showEStopModal(msg.reason);
      break;
    case 'PONG':
      wsLatencyMs = Date.now() - msg.ts;
      updatePingDisplay(wsLatencyMs);
      break;
  }
}

function routeLog(msg) {
  let cls = '';
  if (msg.includes('[TX]'))                              cls = 'tx';
  else if (msg.includes('[NET]') || msg.includes('[CFG]')) cls = 'ok';
  else if (msg.includes('[ERROR]') || msg.includes('[ERR]')) cls = 'error';
  else if (msg.includes('[WARN]') || msg.includes('[ESTOP]') || msg.includes('[AUTO]')) cls = 'warn';
  logAll(msg, cls);
}

function logAll(msg, cls='') {
  logLine('conn-log', msg, cls);
  logLine('cmd-log',  msg, cls);
  logLine('auto-log', msg, cls);
}

// ── Status Message ─────────────────────────────────────────
let esp1Lag = -1, esp2Lag = -1;

function handleStatus(msg) {
  if (msg.mapping !== undefined) updateMapStatus(msg.mapping);
  if (msg.esp1_lag !== undefined) { esp1Lag = msg.esp1_lag; updatePingEsp(1, msg.esp1_lag); }
  if (msg.esp2_lag !== undefined) { esp2Lag = msg.esp2_lag; updatePingEsp(2, msg.esp2_lag); }
}

function updateMapStatus(running) {
  const el = document.getElementById('sb-map-status');
  el.textContent = running ? 'MAP: ON' : 'MAP: OFF';
  el.className = 'sb-map-status' + (running ? ' on' : '');
}

function updateSBSonar(f) {
  const el = document.getElementById('sb-sonar-f');
  if (f >= 380) { el.textContent = 'F: ---'; el.className = 'sb-telem'; return; }
  el.textContent = `F: ${f.toFixed(0)} cm`;
  el.className = 'sb-telem' + (f <= 10 ? ' alert' : '');
}

function updatePingDisplay(ms) {
  const pingEl = document.getElementById('sb-ping');
  const valEl  = document.getElementById('ping-ws-val');
  const barEl  = document.getElementById('ping-ws-bar');
  if (pingEl) pingEl.textContent = `${ms}ms`;
  if (valEl)  valEl.textContent = `${ms} ms`;
  if (barEl) {
    const pct = Math.min(100, ms / 3);
    barEl.style.width = pct + '%';
    barEl.style.background = ms < 50 ? 'var(--success)' : ms < 150 ? 'var(--warning)' : 'var(--danger)';
  }
}

function updatePingEsp(n, ms) {
  const valEl = document.getElementById(`ping-esp${n}-val`);
  const barEl = document.getElementById(`ping-esp${n}-bar`);
  if (!valEl) return;
  if (ms < 0) { valEl.textContent = 'No data'; return; }
  valEl.textContent = `${ms} ms`;
  if (barEl) {
    const pct = Math.min(100, ms / 50);
    barEl.style.width = pct + '%';
    barEl.style.background = ms < 500 ? 'var(--success)' : ms < 2000 ? 'var(--warning)' : 'var(--danger)';
  }
}

// ── WS Status Bar ──────────────────────────────────────────
function setSBStatus(connected) {
  const el = document.getElementById('sb-ws');
  el.textContent = connected ? '\u25CF LIVE' : '\u25CF DISCONNECTED';
  el.className   = 'sb-ws' + (connected ? ' live' : '');
}

// ── Connection ─────────────────────────────────────────────
function applyConnStatus(conn) {
  espState = { esp1: Boolean(conn.esp1), esp2: Boolean(conn.esp2) };
  setESPDot('sb-dot1', espState.esp1);
  setESPDot('sb-dot2', espState.esp2);
  setCardConn(1, espState.esp1);
  setCardConn(2, espState.esp2);
}

function setESPDot(id, online) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle('online', online);
}

function setCardConn(n, online) {
  const dot  = document.getElementById(`ci-dot${n}`);
  const txt  = document.getElementById(`ci-text${n}`);
  const btn  = document.getElementById(`cbtn${n}`);
  if (!dot) return;
  dot.classList.toggle('online', online);
  txt.textContent = online ? 'Online' : 'Offline';
  btn.textContent = online ? 'Disconnect' : 'Connect';
  if (online) btn.classList.add('disconnect'); else btn.classList.remove('disconnect');
}

function toggleConnect(n) {
  const online = n === 1 ? espState.esp1 : espState.esp2;
  if (online) {
    send({ cmd: 'DISCONNECT', esp: n });
  } else {
    saveIPs(false);
    setTimeout(() => send({ cmd: 'CONNECT', esp: n }), 150);
  }
}

function connectBoth() {
  saveIPs(false);
  setTimeout(() => send({ cmd: 'CONNECT', esp: 1 }), 150);
  setTimeout(() => send({ cmd: 'CONNECT', esp: 2 }), 600);
}

function disconnectBoth() {
  send({ cmd: 'DISCONNECT', esp: 1 });
  setTimeout(() => send({ cmd: 'DISCONNECT', esp: 2 }), 100);
}

function saveIPs(notify = true) {
  const ip1 = document.getElementById('ip1').value.trim();
  const ip2 = document.getElementById('ip2').value.trim();
  send({ cmd: 'SET_IPS', ip1, ip2 });
  if (notify) logLine('conn-log', `[CFG] IPs saved — ${ip1} | ${ip2}`, 'ok');
}

// ── QR Code ────────────────────────────────────────────────
let qrInstance = null;
function generateQR() {
  const container = document.getElementById('qr-container');
  const urlEl     = document.getElementById('qr-url-text');
  if (!container) return;
  const url = location.protocol + '//' + location.host;
  if (urlEl) urlEl.textContent = url;
  container.innerHTML = '';
  qrInstance = new QRCode(container, {
    text: url,
    width: 160, height: 160,
    colorDark:  '#000000',
    colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.M,
  });
}

// ── E-Stop ─────────────────────────────────────────────────
let autoEStopEnabled = false;

function manualEStop() {
  send({ cmd: 'X' });
  logAll('[ESTOP] *** MANUAL EMERGENCY STOP ***', 'error');
}

// Called from toggle switch in Drive page
function syncEStopToggle() {
  const cb = document.getElementById('estop-toggle');
  autoEStopEnabled = cb.checked;
  _applyAutoEStop(autoEStopEnabled);
}

// Called from status bar AUTO button
function sbToggleAutoEStop() {
  autoEStopEnabled = !autoEStopEnabled;
  const cb = document.getElementById('estop-toggle');
  if (cb) cb.checked = autoEStopEnabled;
  _applyAutoEStop(autoEStopEnabled);
}

function _applyAutoEStop(enabled) {
  send({ cmd: 'ESTOP_TOGGLE', enabled });
  const sbBtn = document.getElementById('sb-auto');
  sbBtn.classList.toggle('armed', enabled);
  sbBtn.textContent = enabled ? '\u26A1 AUTO: ON' : '\u26A1 AUTO';
  logAll(`[ESTOP] Auto E-Stop ${enabled ? 'ENABLED' : 'DISABLED'}`, enabled ? 'warn' : '');
}

function showEStopModal(reason) {
  document.getElementById('estop-reason').textContent = 'Reason: ' + reason;
  document.getElementById('estop-backdrop').classList.add('active');
}

function overrideEStop() {
  document.getElementById('estop-backdrop').classList.remove('active');
  send({ cmd: 'ESTOP_OVERRIDE' });
  logAll('[ESTOP] Override — 3s reverse window active', 'warn');
}

// ── Help ───────────────────────────────────────────────────
function showHelp() { document.getElementById('help-backdrop').classList.add('active'); }
function closeHelp(e) {
  if (!e || e.target === document.getElementById('help-backdrop')) {
    document.getElementById('help-backdrop').classList.remove('active');
  }
}

// ── Shutdown ───────────────────────────────────────────────
function shutdownServer() {
  if (!confirm('This will stop the Python server and close this tab. Continue?')) return;
  fetch('/shutdown', { method: 'POST' }).finally(() => {
    setTimeout(() => window.close(), 400);
  });
}

// ── D-Pad Buttons ──────────────────────────────────────────
document.querySelectorAll('.dpad-btn').forEach(btn => {
  const cmd = btn.dataset.cmd;
  const press   = (e) => { e.preventDefault(); btn.classList.add('pressed'); send({ cmd }); };
  const release = (e) => { e.preventDefault(); btn.classList.remove('pressed'); if (cmd !== 'X') send({ cmd: 'X' }); };
  btn.addEventListener('mousedown',   press);
  btn.addEventListener('mouseup',     release);
  btn.addEventListener('mouseleave',  () => btn.classList.remove('pressed'));
  btn.addEventListener('touchstart',  press,   { passive: false });
  btn.addEventListener('touchend',    release, { passive: false });
  btn.addEventListener('touchcancel', release, { passive: false });
});

// ── Numpad Buttons removed — keys handled globally in keyboard handler below ──

// ── Keyboard — works globally, no click required ──────────
// Both WASD/Arrows AND Numpad keys light up the D-Pad buttons
const keymap = {
  'w': 'W', 'arrowup': 'W',
  'a': 'A', 'arrowleft': 'A',
  's': 'S', 'arrowdown': 'S',
  'd': 'D', 'arrowright': 'D',
  ' ': 'X', 'x': 'X',
};
// Numpad codes are NumLock-independent via e.code
const numpadMap = {
  'Numpad8': 'W', 'Numpad4': 'A', 'Numpad6': 'D', 'Numpad2': 'S', 'Numpad5': 'X',
};
let heldKey = null;

document.addEventListener('keydown', e => {
  // Never intercept text fields
  const tag = document.activeElement?.tagName || '';
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;

  let cmd = null;

  // Check numpad first (NumLock-independent)
  if (numpadMap[e.code]) {
    cmd = numpadMap[e.code];
  } else {
    cmd = keymap[e.key.toLowerCase()];
  }

  if (!cmd || heldKey === cmd) return;
  e.preventDefault();
  heldKey = cmd;
  send({ cmd });
  highlightDpad(cmd, true); // numpad also lights up D-Pad keys
});

document.addEventListener('keyup', e => {
  const tag = document.activeElement?.tagName || '';
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;

  const cmd = numpadMap[e.code] || keymap[e.key.toLowerCase()];
  if (!cmd || heldKey !== cmd) return;
  heldKey = null;
  if (cmd !== 'X') send({ cmd: 'X' });
  document.querySelectorAll('.dpad-btn').forEach(b => b.classList.remove('pressed'));
});

function highlightDpad(cmd, on) {
  const btn = document.getElementById(`dbtn-${cmd}`);
  if (btn) btn.classList.toggle('pressed', on);
}

// ── Sonar Gauges ───────────────────────────────────────────
const ARC_LEN = 251;
const MAX_CM  = 200;

function updateGauges(L, F, R) {
  setGauge('L', L); setGauge('F', F); setGauge('R', R);
}

function setGauge(id, val) {
  const arc = document.getElementById('arc-' + id);
  const txt = document.getElementById('arcval-' + id);
  if (!arc || !txt) return;

  if (val >= 380) {
    arc.style.strokeDashoffset = ARC_LEN;
    arc.style.stroke = 'var(--text-3)';
    txt.textContent = '---'; return;
  }

  const pct    = Math.min(val, MAX_CM) / MAX_CM;
  const offset = ARC_LEN - pct * ARC_LEN;
  arc.style.strokeDashoffset = offset;
  txt.textContent = val.toFixed(0);

  if (val <= 10)  arc.style.stroke = 'var(--danger)';
  else if (val <= 30) arc.style.stroke = 'var(--warning)';
  else            arc.style.stroke = 'var(--success)';
}

// ── Terminal Logs ──────────────────────────────────────────
function logLine(id, msg, cls = '') {
  const el = document.getElementById(id);
  if (!el) return;
  const now = new Date();
  const ts  = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const p   = document.createElement('p');
  p.className = `log-line ${cls}`;
  p.textContent = `[${ts}] ${msg}`;
  el.appendChild(p);
  while (el.children.length > 300) el.removeChild(el.firstChild);
  el.scrollTop = el.scrollHeight;
}
function clearLog(id) { const el = document.getElementById(id); if (el) el.innerHTML = ''; }
const pad = n => String(n).padStart(2, '0');

// ══════════════════════════════════════════════════════════
// JOYSTICKS
// ══════════════════════════════════════════════════════════

// ── Omni Joystick ──────────────────────────────────────────
(function initOmni() {
  const zone  = document.getElementById('omni-zone');
  const knob  = document.getElementById('omni-knob');
  const label = document.getElementById('omni-cmd-lbl');
  if (!zone) return;

  const DEAD = 24; // px dead zone radius
  let active = false, lastCmd = null, rect, cx, cy;

  function refresh() {
    rect = zone.getBoundingClientRect();
    cx   = rect.width  / 2;
    cy   = rect.height / 2;
  }

  zone.addEventListener('pointerdown', e => {
    e.preventDefault();
    active = true;
    zone.setPointerCapture(e.pointerId);
    zone.classList.add('active');
    refresh();
    move(e.clientX - rect.left, e.clientY - rect.top);
  });
  zone.addEventListener('pointermove', e => {
    if (!active) return;
    e.preventDefault();
    move(e.clientX - rect.left, e.clientY - rect.top);
  });
  zone.addEventListener('pointerup',     () => { active = false; zone.classList.remove('active'); reset(); });
  zone.addEventListener('pointercancel', () => { active = false; zone.classList.remove('active'); reset(); });

  function move(px, py) {
    const dx   = px - cx, dy = py - cy;
    const dist = Math.sqrt(dx*dx + dy*dy);
    const maxR = cx - 28;
    const r    = dist > 0 ? Math.min(dist, maxR) / dist : 0;
    const kx   = dx * r, ky = dy * r;
    knob.style.transform = `translate(calc(-50% + ${kx}px), calc(-50% + ${ky}px))`;

    let cmd, lbl;
    if (dist < DEAD) {
      cmd = 'X'; lbl = '\u25CF Center';
    } else if (Math.abs(dx) >= Math.abs(dy)) {
      cmd = dx > 0 ? 'D' : 'A';
      lbl = cmd === 'D' ? '\u25B6 RIGHT' : '\u25C0 LEFT';
    } else {
      cmd = dy > 0 ? 'S' : 'W';
      lbl = cmd === 'S' ? '\u25BC BACK' : '\u25B2 FWD';
    }
    if (label) label.textContent = lbl;
    if (cmd !== lastCmd) { lastCmd = cmd; send({ cmd }); }
  }

  function reset() {
    knob.style.transform = 'translate(-50%, -50%)';
    if (label) label.textContent = '\u25CF Center';
    lastCmd = null;
    send({ cmd: 'X' });
  }
})();

// ── Vertical Joystick (Fwd/Back) ──────────────────────────
(function initVJ() {
  const track = document.getElementById('vj-zone');
  const knob  = document.getElementById('vj-knob');
  if (!track) return;

  const DEAD = 18;
  let active = false, lastCmd = null, rect;

  track.addEventListener('pointerdown', e => {
    e.preventDefault();
    active = true;
    track.setPointerCapture(e.pointerId);
    rect   = track.getBoundingClientRect();
    move(e.clientY - rect.top);
  });
  track.addEventListener('pointermove', e => {
    if (!active) return;
    e.preventDefault();
    move(e.clientY - rect.top);
  });
  track.addEventListener('pointerup',     () => { active = false; reset(); });
  track.addEventListener('pointercancel', () => { active = false; reset(); });

  function move(py) {
    const cy = rect.height / 2;
    const dy = py - cy;
    const maxR = cy - 26;
    const clamped = Math.max(-maxR, Math.min(maxR, dy));
    knob.style.transform = `translate(-50%, calc(-50% + ${clamped}px))`;
    const cmd = Math.abs(dy) < DEAD ? 'X' : (dy < 0 ? 'W' : 'S');
    if (cmd !== lastCmd) { lastCmd = cmd; send({ cmd }); }
  }

  function reset() {
    knob.style.transform = 'translate(-50%, -50%)';
    lastCmd = null;
    send({ cmd: 'X' });
  }
})();

// ── Horizontal Joystick (Left/Right) ──────────────────────
(function initHJ() {
  const track = document.getElementById('hj-zone');
  const knob  = document.getElementById('hj-knob');
  if (!track) return;

  const DEAD = 18;
  let active = false, lastCmd = null, rect;

  track.addEventListener('pointerdown', e => {
    e.preventDefault();
    active = true;
    track.setPointerCapture(e.pointerId);
    rect   = track.getBoundingClientRect();
    move(e.clientX - rect.left);
  });
  track.addEventListener('pointermove', e => {
    if (!active) return;
    e.preventDefault();
    move(e.clientX - rect.left);
  });
  track.addEventListener('pointerup',     () => { active = false; reset(); });
  track.addEventListener('pointercancel', () => { active = false; reset(); });

  function move(px) {
    const cx = rect.width / 2;
    const dx = px - cx;
    const maxR = cx - 26;
    const clamped = Math.max(-maxR, Math.min(maxR, dx));
    knob.style.transform = `translate(calc(-50% + ${clamped}px), -50%)`;
    const cmd = Math.abs(dx) < DEAD ? 'X' : (dx < 0 ? 'A' : 'D');
    if (cmd !== lastCmd) { lastCmd = cmd; send({ cmd }); }
  }

  function reset() {
    knob.style.transform = 'translate(-50%, -50%)';
    lastCmd = null;
    send({ cmd: 'X' });
  }
})();

// ══════════════════════════════════════════════════════════
// MAPPER
// ══════════════════════════════════════════════════════════
let mapRunning = false;
let mapState   = { walls: [], free: [], path: [], bot: { x:0, y:0, h:0 } };
let cmPerPixel = 2, panX = 0, panY = 0;
let isPanning  = false, lastPanX = 0, lastPanY = 0;

function toggleMap() {
  mapRunning = !mapRunning;
  const btn = document.getElementById('map-start-btn');
  if (mapRunning) {
    btn.textContent = '\u25A0 Stop Mapping';
    btn.className   = 'btn btn-danger';
    send({ cmd: 'MAP_START' });
  } else {
    btn.textContent = '\u25B6 Start Mapping';
    btn.className   = 'btn btn-primary';
    send({ cmd: 'MAP_STOP' });
  }
}

function clearMap() {
  send({ cmd: 'MAP_CLEAR' });
  mapState = { walls: [], free: [], path: [], bot: { x:0, y:0, h:0 } };
  updatePose(mapState.bot);
  drawMap();
}

function sendMapConfig() {
  send({
    cmd:       'MAP_CFG',
    mode:      document.getElementById('map-mode').value,
    pulse_ms:  +document.getElementById('sl-pulse').value,
    turn_ms:   +document.getElementById('sl-turn').value,
    front_thr: +document.getElementById('sl-ft').value,
    diag_thr:  +document.getElementById('sl-dt').value,
  });
}

function updatePose(bot) {
  document.getElementById('pose-x').textContent = bot.x.toFixed(0);
  document.getElementById('pose-y').textContent = bot.y.toFixed(0);
  document.getElementById('pose-h').textContent = (bot.h % 360).toFixed(0) + '\u00B0';
}

// Canvas
const canvas = document.getElementById('mapCanvas');
const ctx    = canvas.getContext('2d');

function resizeCanvas() {
  const wrap = document.getElementById('canvas-wrap');
  if (!wrap) return;
  canvas.width  = wrap.clientWidth  || 400;
  canvas.height = wrap.clientHeight || 400;
}
window.addEventListener('resize', () => { resizeCanvas(); drawMap(); });

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  cmPerPixel = e.deltaY > 0 ? cmPerPixel * 1.12 : cmPerPixel * 0.88;
  cmPerPixel = Math.max(0.3, Math.min(20, cmPerPixel));
  drawMap();
}, { passive: false });

canvas.addEventListener('mousedown', e => { isPanning = true; lastPanX = e.clientX; lastPanY = e.clientY; });
canvas.addEventListener('mousemove', e => {
  if (!isPanning) return;
  panX += e.clientX - lastPanX; panY += e.clientY - lastPanY;
  lastPanX = e.clientX; lastPanY = e.clientY; drawMap();
});
canvas.addEventListener('mouseup',    () => isPanning = false);
canvas.addEventListener('mouseleave', () => isPanning = false);
canvas.addEventListener('dblclick',   () => { panX=0; panY=0; cmPerPixel=2; drawMap(); });

// Touch panning
let t1 = null;
canvas.addEventListener('touchstart', e => { if (e.touches.length===1) t1={x:e.touches[0].clientX, y:e.touches[0].clientY}; }, { passive:true });
canvas.addEventListener('touchmove',  e => {
  if (!t1 || e.touches.length!==1) return;
  panX += e.touches[0].clientX - t1.x; panY += e.touches[0].clientY - t1.y;
  t1 = {x:e.touches[0].clientX, y:e.touches[0].clientY}; drawMap();
}, { passive:true });
canvas.addEventListener('touchend', () => t1=null, { passive:true });

function toCanvas(wx, wy) {
  return [canvas.width/2 + wx/cmPerPixel + panX,
          canvas.height/2 - wy/cmPerPixel + panY];
}

function drawMap() {
  const W = canvas.width, H = canvas.height;
  if (!W || !H) return;
  const dark = root.getAttribute('data-theme') === 'dark';
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = dark ? '#0a0a14' : '#f7f8fc';
  ctx.fillRect(0, 0, W, H);

  // Grid
  const ox = W/2 + panX, oy = H/2 + panY;
  const sp = 50 / cmPerPixel;

  ctx.lineWidth = 1;
  ctx.strokeStyle = dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)';
  for (let x = ox % sp - sp; x < W; x += sp) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }
  for (let y = oy % sp - sp; y < H; y += sp) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }

  // Axes
  ctx.strokeStyle = dark ? 'rgba(14,165,233,0.18)' : 'rgba(14,165,233,0.2)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(ox,0); ctx.lineTo(ox,H); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0,oy); ctx.lineTo(W,oy); ctx.stroke();

  // Free
  ctx.fillStyle = dark ? '#103a1f' : '#dcfce7';
  (mapState.free||[]).forEach(p => {
    const [cx,cy] = toCanvas(p[0], p[1]);
    if (cx>-4 && cx<W+4 && cy>-4 && cy<H+4) ctx.fillRect(cx-2, cy-2, 4, 4);
  });

  // Path
  ctx.fillStyle = '#00d4ff';
  (mapState.path||[]).forEach(p => {
    const [cx,cy] = toCanvas(p[0], p[1]);
    if (cx>-4 && cx<W+4 && cy>-4 && cy<H+4) ctx.fillRect(cx-2.5, cy-2.5, 5, 5);
  });

  // Walls
  ctx.fillStyle = '#ef4444';
  (mapState.walls||[]).forEach(p => {
    const [cx,cy] = toCanvas(p[0], p[1]);
    if (cx>-6 && cx<W+6 && cy>-6 && cy<H+6) ctx.fillRect(cx-3.5, cy-3.5, 7, 7);
  });

  // Bot
  const {x:bx, y:by, h:bh} = mapState.bot;
  const [bcx, bcy] = toCanvas(bx, by);
  const hr = bh * Math.PI / 180;

  ctx.shadowColor = dark ? '#f1c40f' : 'transparent';
  ctx.shadowBlur  = dark ? 12 : 0;
  ctx.fillStyle   = '#f1c40f';
  ctx.beginPath();
  ctx.moveTo(bcx, bcy-8); ctx.lineTo(bcx+8, bcy+4);
  ctx.lineTo(bcx, bcy+2); ctx.lineTo(bcx-8, bcy+4);
  ctx.closePath(); ctx.fill();
  ctx.shadowBlur = 0;

  // Heading line
  const hl = Math.max(15, 25 / cmPerPixel);
  ctx.strokeStyle = '#f1c40f'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(bcx, bcy);
  ctx.lineTo(bcx + hl*Math.sin(hr), bcy - hl*Math.cos(hr));
  ctx.stroke();
}

// ── Init ───────────────────────────────────────────────────
initWS();
setTimeout(() => { resizeCanvas(); drawMap(); }, 400);
