// Flag and answer checks in the page, the same derivation as ctf_core
// (SPEC "Flags"): body = upper hex of the first 6 bytes of
// HMAC-SHA256(K, mac6 || id); derived values use HMAC-SHA256(K, mac6 || label).
// K and the catalogue come from content/board-data.json, generated from the
// firmware sources by scripts/build-app-content.py. HMAC runs on WebCrypto.

const HEX = '0123456789ABCDEF';
const enc = new TextEncoder();

export const toHex = (bytes) => Array.from(bytes, (b) => HEX[b >> 4] + HEX[b & 15]).join('');

/** "24:0A:C4:12:34:56", dashes, spaces, dots or nothing between bytes, any
 *  case, optionally after a pasted "board MAC:" -> Uint8Array(6), or null. */
export function parseMac(text) {
  if (typeof text !== 'string') return null;
  const s = text.trim().replace(/^.*\bmac\s*:?\s*/i, '');
  let hex;
  if (/^[0-9a-f]{12}$/i.test(s)) hex = s;
  else if (/^[0-9a-f]{1,2}([:\-. ][0-9a-f]{1,2}){5}$/i.test(s)) hex = s.split(/[:\-. ]/).map((p) => p.padStart(2, '0')).join('');
  else if (/^[0-9a-f]{4}([.\- ][0-9a-f]{4}){2}$/i.test(s)) hex = s.replace(/[.\- ]/g, '');
  else return null;
  const out = new Uint8Array(6);
  for (let i = 0; i < 6; i++) out[i] = parseInt(hex.slice(2 * i, 2 * i + 2), 16);
  return out;
}

export const macHex = (mac) => toHex(mac);                                  // "240AC4123456"
export const macPretty = (mac) => toHex(mac).match(/../g).join(':');        // "24:0A:C4:12:34:56"
export const boardName = (mac) => `ESP32-CTF-${toHex(mac.subarray(4, 6))}`; // same as ctf_platform_board_name

/** Same rules as parse_submission() in ctf_core.c: ASCII whitespace around
 *  the input is ignored; "ESP{body}" (prefix any case) or the bare body;
 *  body = exactly 12 hex characters, any case. Returns the upper-case body or null. */
export function normaliseFlag(input) {
  if (typeof input !== 'string') return null;
  let s = input.replace(/^[ \t\n\r\v\f]+|[ \t\n\r\v\f]+$/g, '');
  if (s.length === 17 && /^esp\{/i.test(s) && s[16] === '}') s = s.slice(4, 16);
  return /^[0-9A-Fa-f]{12}$/.test(s) ? s.toUpperCase() : null;
}

function concat(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

/** HW-03 style answer: a number, optionally followed by spaces and "Hz"
 *  (as hw03_answer() in track_hw.c, which reads it with strtod). */
function parseNumber(value) {
  const m = /^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?) *(?:hz)?\s*$/i.exec(String(value));
  return m ? Number(m[1]) : NaN;
}

/**
 * createEngine(boardData, subtle?) -> engine bound to the firmware key.
 * All methods take the board MAC as a Uint8Array(6).
 */
export async function createEngine(data, subtle = globalThis.crypto && globalThis.crypto.subtle) {
  if (!subtle) throw new Error('no-webcrypto');
  if (!data || !/^[0-9a-f]{64}$/i.test(data.key || '')) throw new Error('bad-board-data');
  const raw = new Uint8Array(32);
  for (let i = 0; i < 32; i++) raw[i] = parseInt(data.key.slice(2 * i, 2 * i + 2), 16);
  const key = await subtle.importKey('raw', raw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const ids = data.challenges.map((c) => c.id);
  const bodyCache = new Map(); // "MACHEX:ID" -> body

  async function block(mac6, label) {
    const msg = concat(mac6, enc.encode(label));
    return new Uint8Array(await subtle.sign('HMAC', key, msg));
  }

  async function flagBody(mac6, id) {
    const k = `${macHex(mac6)}:${id}`;
    let b = bodyCache.get(k);
    if (b === undefined) {
      b = toHex((await block(mac6, id)).subarray(0, 6));
      bodyCache.set(k, b);
    }
    return b;
  }

  // First 4 derived bytes, big-endian (ctf_derive_u32). Only block 0 is needed:
  // the counter-mode blocks of ctf_derive start after 32 bytes.
  async function deriveU32(mac6, label) {
    const d = await block(mac6, label);
    return ((d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]) >>> 0;
  }

  async function flag(mac6, id) {
    return `ESP{${await flagBody(mac6, id)}}`;
  }

  /** Matched challenge id, or null. Compares against every challenge, like ctf_submit. */
  async function checkFlag(mac6, input) {
    const body = normaliseFlag(input);
    if (!body) return null;
    for (const id of ids) {
      if ((await flagBody(mac6, id)) === body) return id;
    }
    return null;
  }

  const hasAnswer = (id) => !!(data.answers && data.answers[id]);

  /** { correct: boolean, flag?: "ESP{…}" } for a challenge with an answer gate. */
  async function checkAnswer(mac6, id, value) {
    const gate = data.answers && data.answers[id];
    if (!gate) return { correct: false };
    if (gate.kind !== 'u32-range') throw new Error(`unknown answer gate ${gate.kind}`);
    const v = parseNumber(value);
    if (!Number.isFinite(v)) return { correct: false };
    const want = gate.base + ((await deriveU32(mac6, gate.label)) % gate.mod);
    if (Math.abs(v - want) > want * gate.tolerance) return { correct: false };
    return { correct: true, flag: await flag(mac6, id) };
  }

  return { flagBody, flag, deriveU32, checkFlag, checkAnswer, hasAnswer };
}
