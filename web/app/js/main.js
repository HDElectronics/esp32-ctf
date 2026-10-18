// ESP32 CTF player app: an offline guide and scoreboard (SPEC "Player app —
// offline guide and scoreboard"). The page never opens the board's port.
// Catalogue, hints and the flag key come from content/board-data.json
// (generated from the firmware sources); briefs and tools from
// content/challenges.json. Progress lives in localStorage per board MAC.

import { renderMarkdown, escapeHtml as esc } from './markdown.js';
import { createEngine, parseMac, macHex, macPretty, boardName, normaliseFlag } from './engine.js';
import { openStorage, Progress, parseImport, lastMac, setLastMac } from './store.js';

const params = new URLSearchParams(location.search);

const TRACKS = { BLE: 'Bluetooth LE', BTC: 'Bluetooth Classic', WEB: 'Wi-Fi and web', SER: 'Serial', HW: 'Hardware pins', RE: 'Firmware', CRY: 'Crypto' };
const TRACK_ORDER = ['BLE', 'BTC', 'WEB', 'SER', 'HW', 'RE', 'CRY'];
const PRIMER_FILE = { BLE: 'ble', BTC: 'btc', WEB: 'web', SER: 'serial', HW: 'hw', RE: 're', CRY: 'crypto' };
const LEVELS = { 100: ['Easy', 1, 'lv-easy'], 200: ['Medium', 2, 'lv-medium'], 300: ['Hard', 3, 'lv-hard'] };
const HINT_META = [['Nudge', 'A push in the right direction'], ['Hint', 'Names the technique you need'], ['Walkthrough', 'Step by step, without the flag']];
const MODE_NOTE = {
  radio: { cls: 'notice-info', html: 'Runs in radio mode, the board\'s default. If you switched to net mode, type <span class="mono">mode radio</span> in your serial terminal.' },
  net: { cls: 'notice-warn', html: 'Needs the board in net mode: type <span class="mono">mode net</span> in your serial terminal. Switching restarts the board; its own console progress stays.' },
};
const PORT_NOTE = {
  'SER-02': 'This one uses the board\'s second serial port (pins 17/16) with a USB-UART adapter or a logic analyzer, not its USB port.',
};

const $ = (id) => document.getElementById(id);
const levelOf = (pts) => LEVELS[pts] || (pts >= 300 ? LEVELS[300] : pts >= 200 ? LEVELS[200] : LEVELS[100]);
const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

const st = openStorage();

const S = {
  data: null,            // board-data.json
  content: {},           // challenges.json
  engine: null,
  mac: null,             // Uint8Array(6) of the current board
  prog: null,            // Progress of the current board
  tab: params.get('tab') ? params.get('tab').toUpperCase() : null,
  selId: params.get('sel') ? params.get('sel').toUpperCase() : null,
  shownFree: new Set(),  // ids whose free tier-1 text is shown
  hintError: null,       // { id, tier, text }
  result: null,          // { text, ok }
  checking: false,
  answer: null,          // { id, ok, flag?, text? }
  copied: false,
  primer: null,          // track key while the primer view is open
  menuOpen: false,
  confirm: null,         // 'reset' | 'import'
  pendingImport: null,   // validated import for another board
  menuResult: null,      // { text, ok }
};

/* ---------- Content ---------- */

async function loadJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function loadContent() {
  const [data, content] = await Promise.all([
    loadJson('content/board-data.json'),
    loadJson('content/challenges.json').catch(() => ({})),
  ]);
  S.data = data;
  S.content = content;
  S.engine = await createEngine(data);
}

const challenges = () => S.data.challenges;
const byId = (id) => challenges().find((c) => c.id === id);

/* ---------- Screens ---------- */

function showScreen(which) {
  $('setup-screen').hidden = which !== 'setup';
  $('play-screen').hidden = which !== 'play';
  document.title = which === 'play' ? 'ESP32 CTF: challenges' : 'ESP32 CTF: set up your board';
}

/* ---------- Setup screen ---------- */

function renderMacStatus({ submitted = false } = {}) {
  const raw = $('mac').value;
  const mac = parseMac(raw);
  const status = $('mac-status');
  $('start-btn').hidden = !mac;
  if (mac) {
    status.hidden = false;
    status.className = 'status-line';
    status.innerHTML = `This is board <span class="mono">${esc(boardName(mac))}</span>.`;
  } else if (raw.trim() && (submitted || raw.replace(/[^0-9a-f]/gi, '').length >= 12)) {
    status.hidden = false;
    status.className = 'status-line bad';
    status.textContent = 'A MAC is 6 bytes in hex, like 24:0A:C4:12:34:56.';
  } else {
    status.hidden = true;
  }
  return mac;
}

function openSetup(prefill) {
  closeMenu(false);
  if (prefill) $('mac').value = macPretty(prefill);
  renderMacStatus();
  showScreen('setup');
}

function setupError(text) {
  $('setup-error').hidden = !text;
  $('setup-error').textContent = text || '';
}

/* ---------- Board / progress ---------- */

function useBoard(mac) {
  S.mac = mac;
  S.prog = new Progress(S.data, macHex(mac), st);
  setLastMac(st, macHex(mac));
  S.shownFree.clear();
  S.hintError = null;
  S.result = null;
  S.answer = null;
  S.copied = false;
  const ids = new Set(challenges().map((c) => c.id));
  if (!S.selId || !ids.has(S.selId)) {
    const first = challenges().find((c) => !S.prog.isSolved(c.id)) || challenges()[0];
    S.selId = first.id;
  }
  const tracks = new Set(challenges().map((c) => c.track));
  if (!S.tab || (S.tab !== 'ALL' && !tracks.has(S.tab))) S.tab = byId(S.selId).track;
}

function enterPlay(mac) {
  useBoard(mac);
  showScreen('play');
  renderPlay();
  if (params.get('primer')) {
    const key = Object.keys(PRIMER_FILE).find((k) => PRIMER_FILE[k] === params.get('primer')) || params.get('primer').toUpperCase();
    if (key in TRACKS) openPrimer(key, false);
  }
}

/* ---------- Play screen ---------- */

function selected() { return byId(S.selId) || challenges()[0]; }

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
  if (!S.prog) return;
  withFocus(() => {
    renderHeader();
    renderTabs();
    renderList();
    renderPanel();
  });
}

function renderHeader() {
  $('points').textContent = S.prog.points();
  $('board-name').textContent = boardName(S.mac);
  $('solved-total').textContent = `${S.prog.solved.size} of ${challenges().length} solved`;
  renderMenu();
}

function renderMenu() {
  $('progress-menu').hidden = !S.menuOpen;
  $('progress-btn').setAttribute('aria-expanded', String(S.menuOpen));
  $('storage-note').hidden = st.persistent;
  $('reset-confirm').hidden = S.confirm !== 'reset';
  $('import-confirm').hidden = S.confirm !== 'import';
  if (S.confirm === 'reset') {
    $('reset-confirm-text').innerHTML = `Reset progress for <span class="mono">${esc(boardName(S.mac))}</span>? This clears its solved challenges and bought hints on this page. The board's own score is not touched.`;
  }
  if (S.confirm === 'import' && S.pendingImport) {
    const name = boardName(parseMac(S.pendingImport.macHex));
    $('import-confirm-text').innerHTML = `This file is for board <span class="mono">${esc(name)}</span>, not <span class="mono">${esc(boardName(S.mac))}</span>. Switch to that board and load its progress?`;
    $('import-switch').textContent = `Switch to ${name}`;
  }
  const r = $('menu-result');
  r.hidden = !S.menuResult;
  if (S.menuResult) { r.textContent = S.menuResult.text; r.className = 'result ' + (S.menuResult.ok ? 'ok' : 'bad'); }
}

function renderTabs() {
  const list = challenges();
  const present = TRACK_ORDER.filter((k) => list.some((c) => c.track === k));
  const tabs = ['ALL', ...present];
  $('tabs').innerHTML = tabs.map((k) => {
    const items = k === 'ALL' ? list : list.filter((c) => c.track === k);
    const done = items.filter((c) => S.prog.isSolved(c.id)).length;
    const sel = S.tab === k;
    return `<button type="button" role="tab" class="tab" id="tab-${k}" data-tab="${k}" data-key="tab-${k}" aria-selected="${sel}" aria-controls="list" tabindex="${sel ? 0 : -1}">${k === 'ALL' ? 'All' : esc(TRACKS[k])} <span class="tab-count">${done}/${items.length}</span></button>`;
  }).join('');
  $('list').setAttribute('aria-labelledby', `tab-${S.tab}`);
}

function renderList() {
  const items = S.tab === 'ALL' ? challenges() : challenges().filter((c) => c.track === S.tab);
  if (!items.length) { $('list').innerHTML = '<li class="list-empty">No challenges in this track.</li>'; return; }
  $('list').innerHTML = items.map((c) => {
    const [word, n, cls] = levelOf(c.value);
    const cur = c.id === S.selId;
    const sub = S.tab === 'ALL' ? TRACKS[c.track] || '' : (c.kit ? 'needs a ' + c.kit : '');
    const icon = S.prog.isSolved(c.id)
      ? '<svg width="18" height="18" viewBox="0 0 18 18" role="img" aria-label="Solved"><circle cx="9" cy="9" r="9" fill="#b4f04a"></circle><path d="M5 9.5l2.6 2.5L13 6.5" fill="none" stroke="#13111b" stroke-width="2"></path></svg>'
      : '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="8" fill="none" stroke="#4a4360" stroke-width="2"></circle></svg>';
    const pips = [1, 2, 3].map((p) => `<span class="pip${p <= n ? ' on' : ''}"></span>`).join('');
    return `<li><button type="button" class="row" data-id="${esc(c.id)}" data-key="row-${esc(c.id)}" aria-current="${cur}">` +
      `<span class="row-status">${icon}</span>` +
      `<span class="row-main"><span class="row-name">${esc(c.name)}</span>` +
      `<span class="row-sub"><span class="mono">${esc(c.id)}</span>${sub ? '&nbsp;&nbsp;' + esc(sub) : ''}</span></span>` +
      `<span class="row-level ${cls}"><span class="pips" aria-hidden="true">${pips}</span><span class="level-word">${word}</span></span>` +
      `<span class="row-pts">${c.value}<span class="sr-only"> points</span></span></button></li>`;
  }).join('');
}

function renderPanel() {
  const c = selected();
  if (!c) return;
  const tk = c.track;
  const [word, , cls] = levelOf(c.value);
  const info = S.content[c.id] || {};
  $('ch-id').textContent = c.id;
  $('ch-name').textContent = c.name;
  $('ch-chips').innerHTML =
    `<span class="chip">${esc(TRACKS[tk] || tk)}</span>` +
    `<span class="chip ${cls}">${word}</span>` +
    `<span class="chip chip-pts">${c.value} points</span>` +
    (c.kit ? `<span class="chip chip-kit">Needs a ${esc(c.kit)}</span>` : '') +
    (S.prog.isSolved(c.id) ? '<span class="chip chip-solved">Solved</span>' : '');
  $('ch-brief').textContent = info.brief || '';
  $('ch-brief').hidden = !info.brief;

  const modeNote = MODE_NOTE[c.mode];
  $('ch-mode').hidden = !modeNote;
  if (modeNote) {
    $('ch-mode').className = modeNote.cls;
    $('ch-mode-text').innerHTML = modeNote.html;
  }

  const port = PORT_NOTE[c.id];
  $('ch-port').hidden = !port;
  if (port) $('ch-port-text').textContent = port;

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
  $('submit-btn').setAttribute('aria-disabled', String(S.checking));
}

function renderHints(c) {
  const owned = S.prog.tier(c.id);
  const points = S.prog.points();
  $('hints').innerHTML = [1, 2, 3].map((tier) => {
    const p = S.prog.price(c.id, tier);
    const open = owned >= tier;
    const next = tier === owned + 1;
    const afford = points >= p;
    const shown = open && (tier > 1 || S.shownFree.has(c.id));
    const showBtn = !open || (tier === 1 && !S.shownFree.has(c.id));
    let label;
    if (tier === 1) label = 'Show';
    else if (!next) label = `Unlock hint ${tier - 1} first`;
    else if (!afford) label = `Need ${p} points`;
    else label = `Unlock for ${p}`;
    const enabled = tier === 1 || (next && afford);
    const desc = open ? (tier === 1 ? 'Free' : 'Unlocked') : `${HINT_META[tier - 1][1]}${tier === 1 ? ', free' : `, ${p} points`}`;
    const body = shown ? `<p class="hint-text">${esc(S.prog.hintText(c.id, tier) || '')}</p>` : '';
    const err = S.hintError && S.hintError.id === c.id && S.hintError.tier === tier
      ? `<p class="result bad" role="alert">${esc(S.hintError.text)}</p>` : '';
    const btn = showBtn
      ? `<button type="button" class="hint-btn" data-hint="${tier}" data-key="hint-${tier}" aria-disabled="${!enabled}" aria-describedby="hint-title-${tier}">${label}</button>`
      : '';
    return `<div class="hint${shown ? ' is-open' : ''}"><div class="hint-head"><span class="hint-meta"><span class="hint-title" id="hint-title-${tier}">${HINT_META[tier - 1][0]}</span><span class="hint-desc">${desc}</span></span>${btn}</div>${body}${err}</div>`;
  }).join('');
}

function renderAnswer(c) {
  const form = $('answer-form');
  form.hidden = !S.engine.hasAnswer(c.id);
  if (form.hidden) return;
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

function onHintClick(tier) {
  const c = selected();
  S.hintError = null;
  if (tier === 1) {
    S.shownFree.add(c.id);
    renderPlay();
    return;
  }
  const r = S.prog.buy(c.id, tier);
  if (r === 'points') {
    S.hintError = { id: c.id, tier, text: `This hint costs ${S.prog.price(c.id, tier)} points and you have ${S.prog.points()}. Solve a challenge to earn more.` };
  } else if (r === 'locked') {
    S.hintError = { id: c.id, tier, text: 'Unlock the earlier hint first.' };
  }
  renderPlay();
}

// The flag box shows the body only: strip the wrapper and spaces as you type.
const stripFlag = (raw) => raw.replace(/\s+/g, '').replace(/^esp\{/i, '').replace(/\}$/, '').toUpperCase();

async function submitFlag(e) {
  e.preventDefault();
  if (S.checking) return;
  const input = $('flag');
  const body = normaliseFlag(input.value) || stripFlag(input.value);
  input.value = body;
  const c = selected();
  if (!normaliseFlag(body)) {
    S.result = { ok: false, text: 'A flag has 12 characters, using only 0 to 9 and A to F.' };
    renderPlay();
    return;
  }
  S.checking = true;
  renderPlay();
  try {
    const id = await S.engine.checkFlag(S.mac, body);
    if (!id) {
      S.result = { ok: false, text: 'Wrong flag. Nothing was deducted.' };
    } else {
      const hit = byId(id);
      const res = S.prog.solve(id);
      if (id === c.id) {
        S.result = res === 'new'
          ? { ok: true, text: `Correct. ${hit.name} solved, +${hit.value} points.` }
          : { ok: true, text: 'Already solved.' };
      } else {
        S.result = res === 'new'
          ? { ok: true, text: `That's the flag for ${hit.id} ${hit.name}, not this one. ${hit.name} solved, +${hit.value} points.` }
          : { ok: true, text: `That's the flag for ${hit.id} ${hit.name}, which is already solved.` };
      }
      input.value = '';
    }
  } catch (err) {
    console.warn('[ctf] flag check failed:', err);
    S.result = { ok: false, text: 'This page could not check the flag. Reload it and try again.' };
  } finally {
    S.checking = false;
    renderPlay();
  }
}

async function submitAnswer(e) {
  e.preventDefault();
  const c = selected();
  const value = $('answer').value.trim();
  S.copied = false;
  if (!value) {
    S.answer = { id: c.id, ok: false, text: 'Type your answer first.' };
  } else {
    try {
      const r = await S.engine.checkAnswer(S.mac, c.id, value);
      S.answer = r.correct ? { id: c.id, ok: true, flag: r.flag } : { id: c.id, ok: false, text: "That's not it. Nothing was deducted." };
    } catch (err) {
      console.warn('[ctf] answer check failed:', err);
      S.answer = { id: c.id, ok: false, text: 'This page could not check the answer. Reload it and try again.' };
    }
  }
  renderPlay();
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
      $('flag').value = stripFlag(a.flag);
      $('flag').select();
    }
    renderPlay();
  } else if (act === 'submit') {
    $('flag').value = stripFlag(a.flag);
    $('flag-form').requestSubmit();
  }
}

/* ---------- Progress menu ---------- */

function openMenu() {
  S.menuOpen = true;
  S.confirm = null;
  S.menuResult = null;
  renderMenu();
  $('export-btn').focus();
}

function closeMenu(focus = true) {
  if (!S.menuOpen) return;
  S.menuOpen = false;
  S.confirm = null;
  S.pendingImport = null;
  renderMenu();
  if (focus) $('progress-btn').focus();
}

function exportProgress() {
  const name = boardName(S.mac);
  const json = JSON.stringify(S.prog.exportData(name, macPretty(S.mac)), null, 2) + '\n';
  const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `esp32-ctf-${name}.json`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  S.confirm = null;
  S.menuResult = { ok: true, text: `Saved ${a.download}.` };
  renderMenu();
}

async function importFile(file) {
  S.confirm = null;
  S.pendingImport = null;
  let imp;
  try {
    imp = parseImport(await file.text(), S.data, parseMac, macHex);
  } catch (err) {
    S.menuResult = { ok: false, text: err.message };
    renderMenu();
    return;
  }
  if (imp.macHex === macHex(S.mac)) {
    applyImport(imp);
    return;
  }
  S.pendingImport = imp;
  S.confirm = 'import';
  S.menuResult = null;
  renderMenu();
  $('import-switch').focus();
}

function applyImport(imp) {
  const mac = parseMac(imp.macHex);
  if (imp.macHex !== macHex(S.mac)) useBoard(mac);
  S.prog.replaceWith(imp);
  S.confirm = null;
  S.pendingImport = null;
  S.menuResult = { ok: true, text: `Loaded the progress of ${boardName(mac)}: ${imp.solved.size} solved, ${S.prog.points()} points.` };
  renderPlay();
}

function resetProgress() {
  S.prog.reset();
  S.shownFree.clear();
  S.result = null;
  S.answer = null;
  S.hintError = null;
  S.confirm = null;
  S.menuResult = { ok: true, text: `Progress for ${boardName(S.mac)} is reset. You have ${S.prog.points()} points.` };
  renderPlay();
  $('reset-btn').focus();
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
    if (S.primer === track) body.innerHTML = '<p>The primer could not be loaded. Reload the page and try again.</p>';
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

/* ---------- Wiring ---------- */

function wire() {
  $('mac').addEventListener('input', () => renderMacStatus());
  $('mac-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const mac = renderMacStatus({ submitted: true });
    if (mac && S.data) enterPlay(mac);
  });
  $('change-board').addEventListener('click', () => { openSetup(S.mac); $('mac').focus(); $('mac').select(); });

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
    if (/^esp\{|\}$|\s/i.test(v)) e.target.value = stripFlag(v);
  });

  $('progress-btn').addEventListener('click', () => (S.menuOpen ? closeMenu() : openMenu()));
  $('export-btn').addEventListener('click', exportProgress);
  $('import-btn').addEventListener('click', () => { $('import-file').value = ''; $('import-file').click(); });
  $('import-file').addEventListener('change', (e) => { const f = e.target.files && e.target.files[0]; if (f) importFile(f); });
  $('reset-btn').addEventListener('click', () => { S.confirm = 'reset'; S.menuResult = null; renderMenu(); $('reset-no').focus(); });
  $('reset-yes').addEventListener('click', resetProgress);
  $('reset-no').addEventListener('click', () => { S.confirm = null; renderMenu(); $('reset-btn').focus(); });
  $('import-switch').addEventListener('click', () => { if (S.pendingImport) applyImport(S.pendingImport); $('import-btn').focus(); });
  $('import-no').addEventListener('click', () => { S.confirm = null; S.pendingImport = null; renderMenu(); $('import-btn').focus(); });
  document.addEventListener('click', (e) => {
    if (S.menuOpen && !e.target.closest('.menu-wrap')) closeMenu(false);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || $('play-screen').hidden) return;
    if (S.menuOpen) closeMenu(true);
    else if (S.primer) closePrimer(true);
  });
}

async function start() {
  wire();
  if (!st.persistent) {
    $('setup-note').textContent = 'This browser won\'t store data for this page, so your progress is lost when you close it. Use Progress, Export to keep it.';
  }
  try {
    await loadContent();
  } catch (err) {
    console.warn('[ctf] content failed to load:', err);
    setupError(err && err.message === 'no-webcrypto'
      ? 'This page checks flags with your browser\'s Web Crypto, which needs a secure page. Open it from localhost or over HTTPS.'
      : 'The challenge data could not be loaded. Serve the web folder (python3 -m http.server -d web) and reload.');
    showScreen('setup');
    return;
  }
  const fromUrl = params.get('mac') ? parseMac(params.get('mac')) : null;
  const remembered = lastMac(st) ? parseMac(lastMac(st)) : null;
  const mac = fromUrl || remembered;
  if (mac && params.get('screen') !== 'setup') {
    enterPlay(mac);
    if (params.get('menu') === 'progress') openMenu();
  } else {
    openSetup(mac);
  }
}

start();
