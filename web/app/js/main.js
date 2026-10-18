// ESP32 CTF player app: Connect and Play screens, driven by the board over
// the machine channel (SPEC "v0.2.0: Machine channel"). Names, points, kit,
// mode, solved state and hint texts come from the board; briefs and tools
// come from content/challenges.json.

import { BoardLink, debug } from './link.js';
import { SerialTransport, serialSupported } from './serial.js';
import { DemoTransport } from './demo.js';
import { ConsolePane } from './terminal.js';
import { renderMarkdown, escapeHtml as esc } from './markdown.js';
import { TabCoordinator } from './tabs.js';

const params = new URLSearchParams(location.search);
const DEMO = params.has('demo');

const TRACKS = { BLE: 'Bluetooth LE', BTC: 'Bluetooth Classic', WEB: 'Wi-Fi and web', SER: 'Serial', HW: 'Hardware pins', RE: 'Firmware', CRY: 'Crypto' };
const TRACK_ORDER = ['BLE', 'BTC', 'WEB', 'SER', 'HW', 'RE', 'CRY'];
const PRIMER_FILE = { BLE: 'ble', BTC: 'btc', WEB: 'web', SER: 'serial', HW: 'hw', RE: 're', CRY: 'crypto' };
const LEVELS = { 100: ['Easy', 1, 'lv-easy'], 200: ['Medium', 2, 'lv-medium'], 300: ['Hard', 3, 'lv-hard'] };
const HINT_META = [['Nudge', 'A push in the right direction'], ['Hint', 'Names the technique you need'], ['Walkthrough', 'Step by step, without the flag']];
const DEMO_BODY = 'DEMO00000000';
const POLL_MS = 5000;
const RESTART_WAIT_MS = 8000;
const BANNER = 'type `help`';
const MSG_BUSY = 'This board is already open in another tab or program. Close it there, or press Disconnect in that tab, then connect again.';
const MSG_FREE = 'Disconnected. The port is free for other tools.';
const MSG_MOVED = 'Connection moved to another tab.';
// Challenges whose tools need the USB port, or that use another port.
const PORT_NOTE = {
  RE: { text: 'This one needs <span class="mono">esptool</span>, which can\'t share the port with this page. Press Disconnect, run your tool, then connect again. Your points stay on the board.', disconnect: true },
  'SER-02': { text: 'This one uses the board\'s second serial port (pins 17/16) with a USB-UART adapter or a logic analyzer, not this USB port. Keep this page connected.', disconnect: false },
};

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const trackOf = (c) => (c.id.split('-')[0] in TRACKS ? c.id.split('-')[0] : String(c.track || '').toUpperCase());
const levelOf = (pts) => LEVELS[pts] || (pts >= 300 ? LEVELS[300] : pts >= 200 ? LEVELS[200] : LEVELS[100]);
const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

const S = {
  link: null,
  transport: null,
  info: null,
  list: [],
  content: {},
  tab: params.get('tab') ? params.get('tab').toUpperCase() : null,
  selId: params.get('sel') ? params.get('sel').toUpperCase() : null,
  shownFree: new Set(),
  hintText: new Map(),   // "ID:tier" -> text
  hintBusy: new Set(),   // "ID:tier" requests in flight
  hintTried: new Set(),  // "ID:tier" texts fetched automatically since the last selection
  hintError: null,       // { id, tier, text }
  result: null,          // { text, ok }
  submitting: false,
  answer: null,          // { id, ok, flag?, text? }
  answering: false,
  copied: false,
  consoleOpen: params.get('console') === '1',
  primer: null,          // track key while the primer view is open
  restarting: false,
  pollTimer: null,
  peer: null,            // another tab of this app holding the board
  takingOver: false,
};

// Demo tabs coordinate among themselves only, so a demo tab never blocks a real one.
const tabs = TabCoordinator.create(DEMO ? 'esp32-ctf-demo' : 'esp32-ctf', {
  onRelease: async () => {
    await teardown();
    showScreen('connect');
    setConnectState('idle', MSG_MOVED);
  },
  onPeer: (peer) => { S.peer = peer; renderTabNotice(); },
});

let consolePane = null;

/* ---------- Content ---------- */

const contentReady = fetch('content/challenges.json')
  .then((r) => (r.ok ? r.json() : {}))
  .then((j) => { S.content = j; })
  .catch(() => { S.content = {}; });

/* ---------- Board requests ---------- */

async function ask(cmd, opts = {}) {
  const { retries = 0, ...rest } = opts;
  for (let i = 0; ; i++) {
    try {
      return await S.link.request(cmd, rest);
    } catch (e) {
      if (e.message !== 'timeout' || i >= retries) throw e;
    }
  }
}

function applyInfo(info) {
  const prev = S.info;
  S.info = info;
  return !prev || prev.points !== info.points || prev.solved !== info.solved || prev.mode !== info.mode;
}

function applyList(list) {
  if (!list || !Array.isArray(list.challenges) || !list.challenges.length) return;
  S.list = list.challenges;
  const ids = new Set(S.list.map((c) => c.id));
  if (!S.selId || !ids.has(S.selId)) {
    const first = S.list.find((c) => !c.solved) || S.list[0];
    S.selId = first.id;
  }
  const tracks = new Set(S.list.map(trackOf));
  if (!S.tab || (S.tab !== 'ALL' && !tracks.has(S.tab))) S.tab = trackOf(S.list.find((c) => c.id === S.selId));
}

async function sync({ retries = 0 } = {}) {
  const info = await ask('api info', { retries });
  if (!info.ok) throw new Error(info.error || 'info failed');
  applyInfo(info);
  const list = await ask('api list', { retries });
  if (!list.ok) throw new Error(list.error || 'list failed');
  applyList(list);
}

function startPolling() {
  stopPolling();
  S.pollTimer = setInterval(async () => {
    if (!S.link || S.restarting || S.link.current || S.link.queue.length) return;
    try {
      const info = await S.link.request('api info', { background: true });
      if (!info.ok) return;
      if (applyInfo(info)) {
        applyList(await S.link.request('api list', { background: true }));
      }
      renderPlay();
    } catch { /* skipped (player typing) or no answer: try again next round */ }
  }, POLL_MS);
}

function stopPolling() {
  if (S.pollTimer) clearInterval(S.pollTimer);
  S.pollTimer = null;
}

/* ---------- Connect screen ---------- */

function setConnectState(state, message = '') {
  const btn = $('connect-btn');
  const status = $('connect-status');
  const ok = $('connect-ok');
  btn.hidden = state === 'busy' || state === 'ok';
  ok.hidden = state !== 'ok';
  status.hidden = !(state === 'busy' || state === 'error' || state === 'unsupported' || (state === 'idle' && message));
  status.className = 'status-line' + (state === 'error' ? ' bad' : state === 'unsupported' ? ' warn' : '');
  status.setAttribute('role', state === 'error' ? 'alert' : 'status');
  if (state === 'busy') status.textContent = 'Reading the board…';
  else if (state === 'error' || state === 'unsupported') status.innerHTML = message;
  else if (state === 'idle' && message) status.textContent = message;
  btn.disabled = state === 'unsupported';
  if (state === 'ok') {
    const i = S.info;
    const name = DEMO ? 'the demo board' : `<span class="mono">${esc(i.board)}</span>`;
    const pts = i.solved === 0 && i.spent === 0 && i.points === i.start
      ? `You start with ${i.start} points.` : `You have ${i.points} points.`;
    $('connect-ok-text').innerHTML = `Connected to ${name}. ${pts}`;
    $('start-btn').focus();
  }
  S.connectState = state;
  renderTabNotice();
}

// While another tab holds the board, the Connect button gives way to a notice
// that can move the connection here.
function renderTabNotice() {
  const st = S.connectState;
  const show = !!S.peer && !S.link && (st === 'idle' || st === 'error');
  $('tab-notice').hidden = !show;
  $('tab-takeover').setAttribute('aria-disabled', String(S.takingOver));
  $('tab-takeover').textContent = S.takingOver ? 'Waiting for the other tab…' : 'Use this tab instead';
  if (st === 'idle' || st === 'error') $('connect-btn').hidden = show;
}

async function takeOver() {
  if (S.takingOver) return;
  S.takingOver = true;
  renderTabNotice();
  await tabs.requestRelease();
  S.takingOver = false;
  S.peer = null;
  setConnectState('idle', DEMO ? '' : 'The other tab let go of the board. Press Connect board and choose its port.');
  $('connect-btn').focus();
}

function showScreen(which) {
  $('connect-screen').hidden = which !== 'connect';
  $('play-screen').hidden = which !== 'play';
  document.title = which === 'play' ? 'ESP32 CTF: challenges' : 'ESP32 CTF: connect your board';
}

function initConnect() {
  if (!DEMO && (!serialSupported() || params.has('fallback'))) {
    const msg = window.isSecureContext || params.has('fallback')
      ? 'This browser can\'t open serial ports. Use desktop Chrome or Edge, or <a href="?demo">try the demo board</a>.'
      : 'Serial ports need a secure page. Open this app over HTTPS or from <span class="mono">localhost</span>.';
    setConnectState('unsupported', msg);
  } else {
    setConnectState('idle');
  }
  $('connect-btn').addEventListener('click', connect);
  $('start-btn').addEventListener('click', enterPlay);
  $('tab-takeover').addEventListener('click', takeOver);
}

const portBusy = (e) => !!e && (e.name === 'InvalidStateError' || e.name === 'NetworkError');

async function connect() {
  if (S.link) return;
  if (S.peer) { renderTabNotice(); return; } // another tab holds the board: offer to move it
  let transport;
  if (DEMO) {
    transport = new DemoTransport();
  } else {
    try {
      transport = await SerialTransport.pick();
    } catch (e) {
      if (e && e.name === 'NotFoundError') return; // picker closed: stay idle
      setConnectState('error', 'The browser could not list serial ports. Reload the page and try again.');
      return;
    }
    setConnectState('busy');
    try {
      await transport.open();
    } catch (e) {
      console.warn('[ctf] port open failed:', e && e.name, e && e.message);
      setConnectState('error', portBusy(e) ? esc(MSG_BUSY)
        : 'The port could not be opened. Close any other program using it (a serial terminal or <span class="mono">idf.py monitor</span>), then try again.');
      return;
    }
  }
  setConnectState('busy');
  attachLink(transport);
  try {
    await contentReady;
    await sync({ retries: 2 });
  } catch (e) {
    await teardown();
    setConnectState('error', e.message === 'timeout'
      ? 'The board did not answer. It needs the CTF firmware 0.2.0 or newer: flash it in step 1, press its EN button, then connect again.'
      : 'The board answered, but not as expected. Flash the latest CTF firmware in step 1, then connect again.');
    return;
  }
  tabs.announceConnected(S.info && S.info.board);
  if (DEMO && params.get('screen') !== 'connect') enterPlay();
  else setConnectState('ok');
}

function attachLink(transport) {
  S.transport = transport;
  S.link = new BoardLink(transport);
  if (!consolePane) consolePane = new ConsolePane($('term'), (d) => S.link && S.link.sendUser(d));
  consolePane.clear();
  S.link.onText((t) => consolePane.write(t));
  transport.onLost = async () => {
    await teardown();
    showScreen('connect');
    setConnectState('error', 'Lost the connection to the board. If it is still plugged in, close any other program using its port (a serial terminal, <span class="mono">idf.py monitor</span>, PulseView), then connect again. Otherwise plug it back in.');
  };
}

async function teardown() {
  stopPolling();
  const link = S.link;
  S.link = null;
  S.transport = null;
  S.info = null;
  S.list = [];
  S.hintText.clear();
  S.hintBusy.clear();
  S.hintTried.clear();
  S.shownFree.clear();
  S.hintError = null;
  S.result = null;
  S.answer = null;
  S.restarting = false;
  hideOverlay();
  tabs.announceDisconnected();
  if (link) { try { await link.close(); } catch { /* port already gone */ } }
}

// pagehide / beforeunload: no awaiting, no dialog. Start closing the port and
// tell the other tabs it is free.
function releaseOnLeave() {
  const t = S.transport;
  tabs.announceDisconnected();
  if (!t) return;
  stopPolling();
  if (t.closeNow) t.closeNow();
  if (S.link) S.link.close().catch(() => {}); // rejects pending requests; the port is already closing
  S.link = null;
  S.transport = null;
}

async function disconnect() {
  await teardown();
  showScreen('connect');
  if (DEMO || serialSupported()) setConnectState('idle', MSG_FREE);
  else setConnectState('unsupported');
  $('connect-btn').focus();
}

/* ---------- Play screen ---------- */

function enterPlay() {
  showScreen('play');
  renderPlay();
  setConsole(S.consoleOpen, false);
  if (params.get('primer')) {
    const key = Object.keys(PRIMER_FILE).find((k) => PRIMER_FILE[k] === params.get('primer')) || params.get('primer').toUpperCase();
    if (key in TRACKS) openPrimer(key, false);
  }
  startPolling();
}

function selected() { return S.list.find((c) => c.id === S.selId) || S.list[0]; }

// Re-render keeps keyboard focus on the element with the same data-key.
function withFocus(fn) {
  const key = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.key : null;
  fn();
  if (key) {
    const el = document.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (el && el !== document.activeElement) el.focus({ preventScroll: true });
  }
}

function renderPlay() {
  if (!S.info || !S.list.length) return;
  withFocus(() => {
    renderHeader();
    renderTabs();
    renderList();
    renderPanel();
  });
}

function renderHeader() {
  const i = S.info;
  $('points').textContent = i.points;
  for (const b of document.querySelectorAll('.seg')) b.setAttribute('aria-pressed', String(b.dataset.mode === i.mode));
  $('pill-text').innerHTML = DEMO ? 'Demo board' : `Connected to <span class="mono">${esc(i.board)}</span>`;
  $('solved-total').textContent = `${i.solved} of ${i.total} solved`;
}

function renderTabs() {
  const present = TRACK_ORDER.filter((k) => S.list.some((c) => trackOf(c) === k));
  const tabs = ['ALL', ...present];
  $('tabs').innerHTML = tabs.map((k) => {
    const items = k === 'ALL' ? S.list : S.list.filter((c) => trackOf(c) === k);
    const done = items.filter((c) => c.solved).length;
    const sel = S.tab === k;
    return `<button type="button" role="tab" class="tab" id="tab-${k}" data-tab="${k}" data-key="tab-${k}" aria-selected="${sel}" aria-controls="list" tabindex="${sel ? 0 : -1}">${k === 'ALL' ? 'All' : esc(TRACKS[k])} <span class="tab-count">${done}/${items.length}</span></button>`;
  }).join('');
  $('list').setAttribute('aria-labelledby', `tab-${S.tab}`);
}

function renderList() {
  const items = S.tab === 'ALL' ? S.list : S.list.filter((c) => trackOf(c) === S.tab);
  if (!items.length) { $('list').innerHTML = '<li class="list-empty">No challenges in this track.</li>'; return; }
  $('list').innerHTML = items.map((c) => {
    const [word, n, cls] = levelOf(c.pts);
    const cur = c.id === S.selId;
    const sub = S.tab === 'ALL' ? TRACKS[trackOf(c)] || '' : (c.kit ? 'needs a ' + c.kit : '');
    const icon = c.solved
      ? '<svg width="18" height="18" viewBox="0 0 18 18" role="img" aria-label="Solved"><circle cx="9" cy="9" r="9" fill="#b4f04a"></circle><path d="M5 9.5l2.6 2.5L13 6.5" fill="none" stroke="#13111b" stroke-width="2"></path></svg>'
      : '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="8" fill="none" stroke="#4a4360" stroke-width="2"></circle></svg>';
    const pips = [1, 2, 3].map((p) => `<span class="pip${p <= n ? ' on' : ''}"></span>`).join('');
    return `<li><button type="button" class="row" data-id="${esc(c.id)}" data-key="row-${esc(c.id)}" aria-current="${cur}">` +
      `<span class="row-status">${icon}</span>` +
      `<span class="row-main"><span class="row-name">${esc(c.name)}</span>` +
      `<span class="row-sub"><span class="mono">${esc(c.id)}</span>${sub ? '&nbsp;&nbsp;' + esc(sub) : ''}</span></span>` +
      `<span class="row-level ${cls}"><span class="pips" aria-hidden="true">${pips}</span><span class="level-word">${word}</span></span>` +
      `<span class="row-pts">${c.pts}<span class="sr-only"> points</span></span></button></li>`;
  }).join('');
}

function renderPanel() {
  const c = selected();
  if (!c) return;
  const tk = trackOf(c);
  const [word, , cls] = levelOf(c.pts);
  const info = S.content[c.id] || {};
  $('ch-id').textContent = c.id;
  $('ch-name').textContent = c.name;
  $('ch-chips').innerHTML =
    `<span class="chip">${esc(TRACKS[tk] || tk)}</span>` +
    `<span class="chip ${cls}">${word}</span>` +
    `<span class="chip chip-pts">${c.pts} points</span>` +
    (c.kit ? `<span class="chip chip-kit">Needs a ${esc(c.kit)}</span>` : '');
  $('ch-brief').textContent = info.brief || '';
  $('ch-brief').hidden = !info.brief;

  const need = c.mode === 'radio' || c.mode === 'net' ? c.mode : '';
  const wrong = need && need !== S.info.mode;
  $('ch-mode').hidden = !wrong;
  if (wrong) {
    $('ch-mode-text').textContent = `This challenge needs the board in ${need} mode. Switching restarts the board; your points stay.`;
    $('ch-mode-btn').textContent = `Switch to ${need} mode`;
    $('ch-mode-btn').dataset.mode = need;
  }

  const note = PORT_NOTE[c.id] || PORT_NOTE[tk];
  $('ch-port').hidden = !note;
  if (note) {
    $('ch-port-text').innerHTML = note.text;
    $('ch-port-btn').hidden = !note.disconnect;
  }

  const tools = info.tools || [];
  $('ch-tools').innerHTML = tools.map((t) => `<span class="tool">${esc(t)}</span>`).join('');
  $('ch-tools').parentElement.querySelector('.label').hidden = !tools.length;
  $('primer-link').textContent = `New to ${TRACKS[tk] || tk}? Read the short primer`;
  $('primer-link').href = `content/primers/${PRIMER_FILE[tk] || 'serial'}.md`;
  $('primer-link').dataset.track = tk;

  renderHints(c);
  renderAnswer(c);

  const r = $('result');
  r.hidden = !S.result;
  if (S.result) { r.textContent = S.result.text; r.className = 'result ' + (S.result.ok ? 'ok' : 'bad'); }
  $('submit-btn').setAttribute('aria-disabled', String(S.submitting));
  if (S.transport && S.transport.select) S.transport.select(c.id);
}

function renderHints(c) {
  const owned = Math.max(1, Number(c.tier) || 1);
  const prices = Array.isArray(c.prices) && c.prices.length === 3 ? c.prices : [0, Math.round(c.pts * 0.2), Math.round(c.pts * 0.5)];
  const points = S.info.points;
  $('hints').innerHTML = [1, 2, 3].map((tier) => {
    const key = `${c.id}:${tier}`;
    const p = prices[tier - 1];
    const open = owned >= tier;
    const next = tier === owned + 1;
    const afford = points >= p;
    const can = next && afford;
    const shown = open && (tier > 1 || S.shownFree.has(c.id));
    const showBtn = !open || (tier === 1 && !S.shownFree.has(c.id));
    let label;
    if (tier === 1) label = 'Show';
    else if (!next) label = `Unlock hint ${tier - 1} first`;
    else if (!afford) label = `Need ${p} points`;
    else label = `Unlock for ${p}`;
    const enabled = tier === 1 || can;
    const desc = open ? (tier === 1 ? 'Free' : 'Unlocked') : `${HINT_META[tier - 1][1]}${tier === 1 ? ', free' : `, ${p} points`}`;
    const busy = S.hintBusy.has(key);
    const text = S.hintText.get(key);
    if (shown && text === undefined && !busy && !S.hintTried.has(key)) {
      S.hintTried.add(key);
      queueMicrotask(() => fetchHint(c.id, tier, { background: true }));
    }
    let body = '';
    if (shown) {
      body = text !== undefined
        ? `<p class="hint-text">${esc(text)}</p>`
        : `<p class="hint-text is-loading">${busy ? 'Getting the text from the board…' : 'The board did not send this text yet. Select the challenge again to retry.'}</p>`;
    } else if (busy) {
      body = '<p class="hint-text is-loading">Asking the board…</p>';
    }
    const err = S.hintError && S.hintError.id === c.id && S.hintError.tier === tier
      ? `<p class="result bad" role="alert">${esc(S.hintError.text)}</p>` : '';
    const btn = showBtn
      ? `<button type="button" class="hint-btn${busy ? ' is-busy' : ''}" data-hint="${tier}" data-key="hint-${tier}" aria-disabled="${!enabled}" aria-describedby="hint-title-${tier}">${label}</button>`
      : '';
    return `<div class="hint${shown ? ' is-open' : ''}"><div class="hint-head"><span class="hint-meta"><span class="hint-title" id="hint-title-${tier}">${HINT_META[tier - 1][0]}</span><span class="hint-desc">${desc}</span></span>${btn}</div>${body}${err}</div>`;
  }).join('');
}

function renderAnswer(c) {
  const form = $('answer-form');
  form.hidden = c.answer !== true;
  if (form.hidden) return;
  $('answer-btn').setAttribute('aria-disabled', String(S.answering));
  const a = S.answer && S.answer.id === c.id ? S.answer : null;
  const box = $('answer-result');
  if (!a) { box.innerHTML = ''; return; }
  if (!a.ok) { box.innerHTML = `<p class="result bad">${esc(a.text)}</p>`; return; }
  box.innerHTML = '<div class="result ok answer-ok"><p>Correct. Here is the flag for this challenge:</p>' +
    `<span class="answer-flag">${esc(a.flag)}</span>` +
    '<div class="answer-actions">' +
    `<button type="button" class="btn-quiet" data-answer-act="copy" data-key="answer-copy">${S.copied ? 'Copied' : 'Copy'}</button>` +
    '<button type="button" class="hint-btn" data-answer-act="submit" data-key="answer-submit">Submit this flag</button>' +
    '</div></div>';
}

/* ---------- Actions ---------- */

function pickChallenge(id) {
  if (id === S.selId) return;
  S.selId = id;
  S.result = null;
  S.answer = null;
  S.copied = false;
  $('answer').value = '';
  S.hintError = null;
  S.hintTried.clear();
  closePrimer(false);
  renderPlay();
  if (matchMedia('(max-width: 980px)').matches) {
    $('panel').scrollIntoView({ block: 'start', behavior: reducedMotion() ? 'auto' : 'smooth' });
  }
}

function pickTab(k, focus) {
  S.tab = k;
  renderPlay();
  if (focus) $(`tab-${k}`).focus();
}

async function fetchHint(id, tier, { background = false } = {}) {
  const key = `${id}:${tier}`;
  if (S.hintBusy.has(key) || !S.link) return;
  S.hintBusy.add(key);
  S.hintError = null;
  renderPlay();
  try {
    const r = await S.link.request(`api hint ${id} ${tier}`, { background });
    if (r.ok) {
      S.hintText.set(key, String(r.text || ''));
      if (typeof r.points === 'number' && S.info) S.info = { ...S.info, points: r.points };
      if (tier === 1) S.shownFree.add(id);
      if (tier > 1) { try { await sync(); } catch { /* the next poll catches up */ } }
    } else if (r.error === 'points') {
      const have = typeof r.points === 'number' ? r.points : S.info.points;
      const c = S.list.find((x) => x.id === id);
      const cost = c && Array.isArray(c.prices) ? c.prices[tier - 1] : r.need;
      S.hintError = { id, tier, text: `This hint costs ${cost} points and you have ${have}. Solve a challenge to earn more.` };
    } else if (r.error === 'locked') {
      S.hintError = { id, tier, text: 'Unlock the earlier hint first.' };
    } else {
      S.hintError = { id, tier, text: `The board refused: ${r.error || 'unknown error'}. Try again.` };
    }
  } catch (e) {
    if (!background) S.hintError = { id, tier, text: 'The board did not answer. Check the USB cable, then try again.' };
  } finally {
    S.hintBusy.delete(key);
    renderPlay();
  }
}

function onHintClick(tier) {
  const c = selected();
  const owned = Math.max(1, Number(c.tier) || 1);
  if (tier === 1) {
    if (S.hintText.has(`${c.id}:1`)) { S.shownFree.add(c.id); renderPlay(); return; }
    fetchHint(c.id, 1);
    return;
  }
  const price = (c.prices || [])[tier - 1] ?? 0;
  if (tier !== owned + 1 || S.info.points < price) return; // aria-disabled
  fetchHint(c.id, tier);
}

function normaliseFlag(raw) {
  return raw.replace(/\s+/g, '').replace(/^esp\{/i, '').replace(/\}$/, '').toUpperCase();
}

async function submitFlag(e) {
  e.preventDefault();
  if (S.submitting || !S.link) return;
  const input = $('flag');
  const body = normaliseFlag(input.value);
  input.value = body;
  const c = selected();
  if (!/^[0-9A-F]{12}$/.test(body) && !(DEMO && body === DEMO_BODY)) {
    S.result = { ok: false, text: 'A flag has 12 characters, using only 0 to 9 and A to F.' };
    renderPlay();
    return;
  }
  S.submitting = true;
  renderPlay();
  try {
    if (S.transport.select) S.transport.select(c.id);
    const r = await S.link.request(`api submit ESP{${body}}`);
    const hit = S.list.find((x) => x.id === r.id);
    const name = hit ? hit.name : r.id;
    if (!r.ok) S.result = { ok: false, text: `The board could not check that flag (${r.error || 'unknown error'}). Try again.` };
    else if (r.result === 'new') { S.result = { ok: true, text: `Correct. ${name} solved, +${r.pts} points.` }; input.value = ''; }
    else if (r.result === 'already') S.result = { ok: true, text: `That flag is right, but ${name} was already solved. No points added.` };
    else S.result = { ok: false, text: 'Wrong flag. Nothing was deducted; try again.' };
    if (r.ok && typeof r.points === 'number') S.info = { ...S.info, points: r.points };
    if (r.ok && r.result !== 'wrong') { try { await sync(); } catch { /* next poll */ } }
  } catch {
    S.result = { ok: false, text: 'The board did not answer. Check the USB cable, then submit again.' };
  } finally {
    S.submitting = false;
    renderPlay();
  }
}

async function submitAnswer(e) {
  e.preventDefault();
  if (S.answering || !S.link) return;
  const c = selected();
  const value = $('answer').value.trim();
  S.copied = false;
  if (!value) {
    S.answer = { id: c.id, ok: false, text: 'Type your answer first.' };
    renderPlay();
    return;
  }
  S.answering = true;
  renderPlay();
  try {
    const r = await S.link.request(`api answer ${c.id} ${value}`);
    if (!r.ok) S.answer = { id: c.id, ok: false, text: `The board could not check that answer (${r.error || 'unknown error'}). Try again.` };
    else if (r.correct && r.flag) S.answer = { id: c.id, ok: true, flag: String(r.flag) };
    else S.answer = { id: c.id, ok: false, text: "That's not it. Nothing was deducted." };
  } catch {
    S.answer = { id: c.id, ok: false, text: 'The board did not answer. Check the USB cable, then try again.' };
  } finally {
    S.answering = false;
    renderPlay();
  }
}

async function onAnswerAction(act) {
  const a = S.answer;
  if (!a || !a.ok) return;
  if (act === 'copy') {
    try {
      await navigator.clipboard.writeText(a.flag);
      S.copied = true;
    } catch {
      // Clipboard blocked: put the flag in the flag box so it can be copied by hand.
      $('flag').value = normaliseFlag(a.flag);
      $('flag').select();
    }
    renderPlay();
  } else if (act === 'submit') {
    $('flag').value = normaliseFlag(a.flag);
    $('flag-form').requestSubmit();
  }
}

async function switchMode(mode) {
  if (!S.link || S.restarting || !S.info || S.info.mode === mode) return;
  S.restarting = true;
  stopPolling();
  showOverlay('Restarting the board…', `Switching to ${mode} mode. This takes a few seconds; your points stay.`, false);
  const banner = S.link.waitForText(BANNER, RESTART_WAIT_MS);
  try { await S.link.request(`api mode ${mode}`); } catch { /* the reply can be lost in the reset */ }
  await banner;
  await sleep(400); // let the prompt finish printing
  try {
    await sync({ retries: 2 });
    S.restarting = false;
    hideOverlay();
    renderPlay();
    startPolling();
  } catch {
    showOverlay('The board did not come back', 'Check the USB cable and press the board\'s EN button. If that does not help, disconnect and connect again.', true);
  }
}

function showOverlay(title, sub, actions) {
  $('overlay-title').textContent = title;
  $('overlay-sub').textContent = sub;
  $('overlay-actions').hidden = !actions;
  $('overlay').hidden = false;
  $('play-screen').inert = true;
  (actions ? $('overlay-disconnect') : $('overlay-card')).focus();
}

function hideOverlay() {
  $('overlay').hidden = true;
  $('play-screen').inert = false;
}

/* ---------- Primer ---------- */

const primerCache = new Map();

async function openPrimer(track, focus = true) {
  S.primer = track;
  $('challenge-view').hidden = true;
  $('primer-view').hidden = false;
  const body = $('primer-body');
  body.innerHTML = '<p>Loading the primer…</p>';
  $('panel').setAttribute('aria-label', `${TRACKS[track]} primer`);
  $('panel').removeAttribute('aria-labelledby');
  $('panel').scrollTop = 0;
  if (focus) $('primer-back').focus();
  try {
    let md = primerCache.get(track);
    if (md === undefined) {
      const r = await fetch(`content/primers/${PRIMER_FILE[track]}.md`);
      if (!r.ok) throw new Error(String(r.status));
      md = await r.text();
      primerCache.set(track, md);
    }
    if (S.primer === track) body.innerHTML = renderMarkdown(md, { headingOffset: 1 });
  } catch {
    if (S.primer === track) body.innerHTML = '<p>The primer could not be loaded. Check your connection and try again.</p>';
  }
}

function closePrimer(focus = true) {
  if (!S.primer) return;
  S.primer = null;
  $('primer-view').hidden = true;
  $('challenge-view').hidden = false;
  $('panel').removeAttribute('aria-label');
  $('panel').setAttribute('aria-labelledby', 'ch-name');
  if (focus) $('primer-link').focus();
}

/* ---------- Console drawer ---------- */

function setConsole(open, focus) {
  S.consoleOpen = open;
  $('drawer').hidden = !open;
  $('console-btn').setAttribute('aria-expanded', String(open));
  $('console-btn').textContent = open ? 'Hide console' : 'Console';
  if (open && consolePane) {
    consolePane.show({ focus }).then(updateDrawerHeight);
  }
  updateDrawerHeight();
}

function updateDrawerHeight() {
  const h = S.consoleOpen ? $('drawer').offsetHeight : 0;
  document.documentElement.style.setProperty('--drawer-h', `${h}px`);
}

/* ---------- Wiring ---------- */

function wire() {
  $('tabs').addEventListener('click', (e) => {
    const b = e.target.closest('[data-tab]');
    if (b) pickTab(b.dataset.tab, false);
  });
  $('tabs').addEventListener('keydown', (e) => {
    const tabs = [...$('tabs').querySelectorAll('[role="tab"]')];
    const i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    let j = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = (i + 1) % tabs.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') j = 0;
    else if (e.key === 'End') j = tabs.length - 1;
    if (j === null) return;
    e.preventDefault();
    pickTab(tabs[j].dataset.tab, true);
  });
  $('list').addEventListener('click', (e) => {
    const b = e.target.closest('[data-id]');
    if (b) pickChallenge(b.dataset.id);
  });
  $('hints').addEventListener('click', (e) => {
    const b = e.target.closest('[data-hint]');
    if (b && b.getAttribute('aria-disabled') !== 'true') onHintClick(Number(b.dataset.hint));
  });
  for (const b of document.querySelectorAll('.seg')) b.addEventListener('click', () => switchMode(b.dataset.mode));
  $('ch-mode-btn').addEventListener('click', (e) => switchMode(e.currentTarget.dataset.mode));
  $('primer-link').addEventListener('click', (e) => { e.preventDefault(); openPrimer(e.currentTarget.dataset.track); });
  $('primer-back').addEventListener('click', () => closePrimer(true));
  $('flag-form').addEventListener('submit', submitFlag);
  $('answer-form').addEventListener('submit', submitAnswer);
  $('answer-result').addEventListener('click', (e) => {
    const b = e.target.closest('[data-answer-act]');
    if (b) onAnswerAction(b.dataset.answerAct);
  });
  $('flag').addEventListener('input', (e) => {
    const v = e.target.value;
    const n = normaliseFlag(v);
    if (/^esp\{|\}$|\s/i.test(v)) e.target.value = n;
  });
  $('console-btn').addEventListener('click', () => setConsole(!S.consoleOpen, true));
  $('disconnect-btn').addEventListener('click', disconnect);
  $('overlay-disconnect').addEventListener('click', disconnect);
  $('ch-port-btn').addEventListener('click', disconnect);
  window.addEventListener('pagehide', releaseOnLeave);
  window.addEventListener('beforeunload', releaseOnLeave);
  window.addEventListener('pageshow', (e) => {
    // Back from the bfcache: the port was released on the way out.
    if (e.persisted && !S.link && S.info) {
      teardown();
      showScreen('connect');
      setConnectState('idle', MSG_FREE);
    }
    if (e.persisted) tabs.probe();
  });
  $('overlay-close').addEventListener('click', () => {
    S.restarting = false;
    hideOverlay();
    startPolling();
  });
  window.addEventListener('resize', updateDrawerHeight);
  if (window.ResizeObserver) new ResizeObserver(updateDrawerHeight).observe($('drawer'));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && S.primer && !$('play-screen').hidden) closePrimer(true);
  });
}

wire();
initConnect();
if (debug) console.debug('[ctf] debug logging on');
// Look for a tab that already holds the board before connecting on our own.
tabs.probe().then((peer) => {
  if (peer) { S.peer = peer; showScreen('connect'); renderTabNotice(); return; }
  if (DEMO && params.get('screen') !== 'connect') connect();
  else showScreen('connect');
});
