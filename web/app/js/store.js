// Points wallet and progress per board, kept in this browser (SPEC "Points
// wallet" and "Player app — offline guide and scoreboard"). Same rules as
// ctf_core: points = start + earned − spent; hint tier 1 is free, tiers 2 and 3
// are bought in order and need enough points; buying after solving is allowed.
// This score is separate from the board's own console score.

const PREFIX = 'esp32ctf:v1:';
const LAST_KEY = `${PREFIX}last`;
export const EXPORT_APP = 'esp32-ctf';
export const EXPORT_VERSION = 1;

/** localStorage wrapped in try/catch. When storage is missing or refuses a
 *  write, everything works in memory and `persistent` is false. */
export function openStorage(ls) {
  const mem = new Map();
  let backend = null;
  try {
    const s = ls === undefined ? globalThis.localStorage : ls;
    if (s) {
      const probe = `${PREFIX}probe`;
      s.setItem(probe, '1');
      s.removeItem(probe);
      backend = s;
    }
  } catch { backend = null; }
  const st = {
    get persistent() { return backend !== null; },
    get(key) {
      if (backend) {
        try { return backend.getItem(key); } catch { /* fall through to memory */ }
      }
      return mem.has(key) ? mem.get(key) : null;
    },
    set(key, value) {
      mem.set(key, value);
      if (!backend) return;
      try { backend.setItem(key, value); } catch { backend = null; } // full or blocked: memory from now on
    },
    remove(key) {
      mem.delete(key);
      if (backend) { try { backend.removeItem(key); } catch { /* ignore */ } }
    },
  };
  return st;
}

export const lastMac = (st) => st.get(LAST_KEY);
export const setLastMac = (st, hex) => st.set(LAST_KEY, hex);

/** Tiers are { id: 2|3 } (tier 1 is free and not recorded). */
function sanitize(data, solvedIn, tiersIn) {
  const known = new Map(data.challenges.map((c) => [c.id, c]));
  const solved = new Set();
  const tiers = new Map();
  if (Array.isArray(solvedIn)) for (const id of solvedIn) if (known.has(id)) solved.add(id);
  if (tiersIn && typeof tiersIn === 'object') {
    for (const [id, t] of Object.entries(tiersIn)) if (known.has(id) && (t === 2 || t === 3)) tiers.set(id, t);
  }
  return { solved, tiers };
}

export class Progress {
  /** data = board-data.json, mac = "240AC4123456", st = openStorage(). */
  constructor(data, mac, st) {
    this.data = data;
    this.mac = mac;
    this.st = st;
    this.byId = new Map(data.challenges.map((c) => [c.id, c]));
    this.solved = new Set();
    this.tiers = new Map();
    this.load();
  }

  get key() { return PREFIX + this.mac; }

  load() {
    let rec = null;
    try { rec = JSON.parse(this.st.get(this.key) || 'null'); } catch { rec = null; }
    const ok = rec && rec.v === EXPORT_VERSION && rec.mac === this.mac;
    const { solved, tiers } = sanitize(this.data, ok ? rec.solved : [], ok ? rec.tiers : {});
    this.solved = solved;
    this.tiers = tiers;
  }

  save() {
    this.st.set(this.key, JSON.stringify({
      v: EXPORT_VERSION, mac: this.mac, solved: [...this.solved], tiers: Object.fromEntries(this.tiers),
    }));
  }

  value(id) { const c = this.byId.get(id); return c ? c.value : 0; }
  get start() { return this.data.start; }
  earned() { let n = 0; for (const id of this.solved) n += this.value(id); return n; }
  spent() {
    let n = 0;
    for (const [id, t] of this.tiers) for (let k = 2; k <= t; k++) n += this.price(id, k);
    return n;
  }
  points() { return this.start + this.earned() - this.spent(); }
  isSolved(id) { return this.solved.has(id); }
  /** Highest owned tier: 1 if none bought; 0 for an unknown id. */
  tier(id) { return this.byId.has(id) ? (this.tiers.get(id) || 1) : 0; }
  /** Price of a tier; -1 for an unknown id or a tier outside 1..3. */
  price(id, tier) {
    const c = this.byId.get(id);
    if (!c || !(tier >= 1 && tier <= 3)) return -1;
    return c.prices[tier - 1];
  }

  /** Like ctf_hint_buy: 'ok' (free, owned or just bought), 'locked', 'points' or 'bad'. */
  buy(id, tier) {
    const c = this.byId.get(id);
    if (!c || !Number.isInteger(tier) || tier < 1 || tier > 3) return 'bad';
    const have = this.tier(id);
    if (tier <= have) return 'ok';
    if (tier > have + 1) return 'locked';
    if (this.points() < this.price(id, tier)) return 'points';
    this.tiers.set(id, tier);
    this.save();
    return 'ok';
  }

  hintText(id, tier) {
    const c = this.byId.get(id);
    return c && tier >= 1 && tier <= 3 && tier <= this.tier(id) ? c.hints[tier - 1] : null;
  }

  /** 'new' (marked solved, saved) or 'already'; null for an unknown id. */
  solve(id) {
    if (!this.byId.has(id)) return null;
    if (this.solved.has(id)) return 'already';
    this.solved.add(id);
    this.save();
    return 'new';
  }

  reset() {
    this.solved.clear();
    this.tiers.clear();
    this.save();
  }

  /** The export file's content (the board name goes into the file name too). */
  exportData(board, prettyMac, now = new Date()) {
    return {
      app: EXPORT_APP, v: EXPORT_VERSION, board, mac: prettyMac,
      solved: [...this.solved], tiers: Object.fromEntries(this.tiers),
      points: this.points(), exported: now.toISOString(),
    };
  }

  /** Replace this board's progress with a validated import (see parseImport). */
  replaceWith(imp) {
    this.solved = new Set(imp.solved);
    this.tiers = new Map(imp.tiers);
    this.save();
  }
}

/**
 * Validate an export file's text. Returns { macHex, solved: Set, tiers: Map }
 * or throws an Error whose message is shown to the player.
 * parseMacFn = engine.parseMac (kept as a parameter so this module stays crypto-free).
 */
export function parseImport(text, data, parseMacFn, toHexFn) {
  let obj;
  try { obj = JSON.parse(text); } catch { throw new Error('That file is not a progress file from this page.'); }
  if (!obj || obj.app !== EXPORT_APP || typeof obj.mac !== 'string') throw new Error('That file is not a progress file from this page.');
  if (obj.v !== EXPORT_VERSION) throw new Error('That progress file comes from a different version of this page.');
  const mac = parseMacFn(obj.mac);
  if (!mac) throw new Error('That progress file has no valid board MAC.');
  const known = new Set(data.challenges.map((c) => c.id));
  if (!Array.isArray(obj.solved) || obj.solved.some((id) => !known.has(id))) throw new Error('That progress file lists challenges this page does not know.');
  const tiers = obj.tiers && typeof obj.tiers === 'object' && !Array.isArray(obj.tiers) ? obj.tiers : null;
  if (!tiers || Object.entries(tiers).some(([id, t]) => !known.has(id) || (t !== 2 && t !== 3))) throw new Error('That progress file has hint records this page does not understand.');
  const clean = sanitize(data, obj.solved, tiers);
  // Spending more than was ever available means the file was edited by hand.
  const value = new Map(data.challenges.map((c) => [c.id, c]));
  let earned = 0;
  let spent = 0;
  for (const id of clean.solved) earned += value.get(id).value;
  for (const [id, t] of clean.tiers) for (let k = 2; k <= t; k++) spent += value.get(id).prices[k - 1];
  if (data.start + earned - spent < 0) throw new Error("That progress file doesn't add up: it spends more points than it earned.");
  return { macHex: toHexFn(mac), solved: clean.solved, tiers: clean.tiers };
}
