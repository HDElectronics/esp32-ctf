// Run: node --test web/app/tests/
// Flag and answer checks in the page vs an independent HMAC (node:crypto),
// plus real boards when their boot-banner values are available locally.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac, randomBytes } from 'node:crypto';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createEngine, parseMac, normaliseFlag, boardName, macHex, macPretty } from '../js/engine.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, '../../..');
const data = JSON.parse(readFileSync(path.join(here, '../content/board-data.json'), 'utf8'));
const K = Buffer.from(data.key, 'hex');
const ref = (mac, label) => createHmac('sha256', K).update(Buffer.concat([Buffer.from(mac), Buffer.from(label, 'ascii')])).digest();
const refBody = (mac, id) => ref(mac, id).subarray(0, 6).toString('hex').toUpperCase();
const refFreq = (mac) => 1000 + (ref(mac, 'HW-03:freq').readUInt32BE(0) % 9000);

const engine = await createEngine(data);

test('board data: 40 challenges, 3 hints each, prices follow the rule', () => {
  assert.equal(data.challenges.length, 40);
  assert.equal(data.start, 100);
  for (const c of data.challenges) {
    assert.equal(c.hints.length, 3);
    assert.deepEqual(c.prices, [0, Math.round(0.2 * c.value), Math.round(0.5 * c.value)]);
  }
  assert.deepEqual(data.answers['HW-03'], { kind: 'u32-range', label: 'HW-03:freq', base: 1000, mod: 9000, tolerance: 0.01, unit: 'Hz' });
});

test('parseMac accepts colons, dashes, spaces or none, any case', () => {
  const want = '240AC4123456';
  for (const s of ['24:0A:C4:12:34:56', '24:0a:c4:12:34:56', '24-0A-C4-12-34-56', '24 0A C4 12 34 56',
    '240ac4123456', '  240AC4123456 ', 'board MAC: 24:0A:C4:12:34:56', '240a.c412.3456']) {
    const m = parseMac(s);
    assert.ok(m, s);
    assert.equal(macHex(m), want, s);
  }
  for (const s of ['', '24:0A:C4:12:34', '240AC412345', '240AC41234567', 'G4:0A:C4:12:34:56', '24:0A:C4:12:34:56:00']) {
    assert.equal(parseMac(s), null, s);
  }
  const m = parseMac('24:0A:C4:12:34:56');
  assert.equal(boardName(m), 'ESP32-CTF-3456');
  assert.equal(macPretty(m), '24:0A:C4:12:34:56');
});

test('normaliseFlag matches ctf_submit parsing', () => {
  assert.equal(normaliseFlag('ESP{0123456789ab}'), '0123456789AB');
  assert.equal(normaliseFlag('esp{0123456789AB}'), '0123456789AB');
  assert.equal(normaliseFlag(' \t0123456789ab\r\n'), '0123456789AB');
  assert.equal(normaliseFlag('Esp{ABCDEFABCDEF}  '), 'ABCDEFABCDEF');
  for (const bad of ['', 'ESP{0123456789A}', '0123456789ABC', 'ESP{0123456789AG}', 'ESP{ 123456789AB}',
    'FLAG{0123456789AB}', 'ESP{0123456789AB', '0123 456789AB', 'ESP(0123456789AB)']) {
    assert.equal(normaliseFlag(bad), null, bad);
  }
});

test('flag bodies and derived values match an independent HMAC', async () => {
  for (let n = 0; n < 4; n++) {
    const mac = new Uint8Array(randomBytes(6));
    for (const c of data.challenges) assert.equal(await engine.flagBody(mac, c.id), refBody(mac, c.id), c.id);
    const u = ref(mac, 'HW-03:freq').readUInt32BE(0);
    assert.equal(await engine.deriveU32(mac, 'HW-03:freq'), u);
  }
});

test('checkFlag returns the matched challenge, for any challenge', async () => {
  const mac = parseMac('24:0A:C4:00:00:00');
  for (const c of data.challenges) {
    const b = refBody(mac, c.id);
    assert.equal(await engine.checkFlag(mac, `ESP{${b}}`), c.id);
    assert.equal(await engine.checkFlag(mac, b.toLowerCase()), c.id);
  }
  assert.equal(await engine.checkFlag(mac, 'ESP{000000000000}'), null);
  assert.equal(await engine.checkFlag(mac, 'nonsense'), null);
  // Another board's flag is wrong here.
  const other = parseMac('24:0A:C4:00:00:01');
  assert.equal(await engine.checkFlag(mac, refBody(other, 'BLE-01')), null);
});

test('checkAnswer: HW-03 frequency within 1 %, then the flag', async () => {
  const mac = parseMac('24:0A:C4:00:00:00');
  const f = refFreq(mac);
  const flag = `ESP{${refBody(mac, 'HW-03')}}`;
  for (const v of [String(f), `${f} Hz`, `${f}hz`, `${f}HZ`, String(f * 1.0099), String(f * 0.9901), ` ${f} `]) {
    assert.deepEqual(await engine.checkAnswer(mac, 'HW-03', v), { correct: true, flag }, v);
  }
  for (const v of [String(f * 1.02), String(f * 0.98), '', 'abc', `${f} kHz`, `${f}x`]) {
    assert.equal((await engine.checkAnswer(mac, 'HW-03', v)).correct, false, v);
  }
  assert.equal((await engine.checkAnswer(mac, 'BLE-01', String(f))).correct, false);
  assert.equal(engine.hasAnswer('HW-03'), true);
  assert.equal(engine.hasAnswer('HW-04'), false);
});

// Real boards: expected values read from their boot banners, kept out of git.
// File (or $CTF_REAL_BOARDS): {"boards":[{"mac":"24:0A:C4:…","flags":{"SER-01":"ESP{…}"},"hw03":1028}]}
const realFile = process.env.CTF_REAL_BOARDS || path.join(ROOT, '.cache', 'real-boards.local.json');
const real = existsSync(realFile) ? JSON.parse(readFileSync(realFile, 'utf8')).boards : null;

test('real boards: page-computed flags equal the boards\' own', { skip: real ? false : `no ${path.relative(ROOT, realFile)}` }, async () => {
  assert.ok(real.length > 0);
  for (const b of real) {
    const mac = parseMac(b.mac);
    assert.ok(mac, b.mac);
    for (const [id, want] of Object.entries(b.flags || {})) {
      assert.equal(await engine.flag(mac, id), want, `${b.mac} ${id}`);
      assert.equal(await engine.checkFlag(mac, want), id);
    }
    if (b.hw03 !== undefined) {
      const f = 1000 + ((await engine.deriveU32(mac, 'HW-03:freq')) % 9000);
      assert.equal(f, b.hw03, `${b.mac} HW-03 frequency`);
    }
  }
});
