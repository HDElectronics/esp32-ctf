// Run: node --test web/app/tests/
// Points wallet and progress storage, over a fake localStorage.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { openStorage, Progress, parseImport, lastMac, setLastMac } from '../js/store.js';
import { parseMac, macHex } from '../js/engine.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(path.join(here, '../content/board-data.json'), 'utf8'));
const MAC = '240AC4123456';

class FakeStorage {
  constructor() { this.m = new Map(); this.fail = false; }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
  setItem(k, v) { if (this.fail) throw new Error('QuotaExceededError'); this.m.set(k, String(v)); }
  removeItem(k) { this.m.delete(k); }
}

const fresh = () => { const ls = new FakeStorage(); return { ls, st: openStorage(ls) }; };

test('starts with 100 points; solving adds the full value', () => {
  const { st } = fresh();
  const p = new Progress(data, MAC, st);
  assert.equal(p.points(), 100);
  assert.equal(p.solve('BLE-01'), 'new');   // 100
  assert.equal(p.solve('BLE-01'), 'already');
  assert.equal(p.solve('BLE-10'), 'new');   // 300
  assert.equal(p.solve('NOPE-01'), null);
  assert.equal(p.earned(), 400);
  assert.equal(p.points(), 500);
});

test('hint prices per level: 0/20/50, 0/40/100, 0/60/150', () => {
  const p = new Progress(data, MAC, fresh().st);
  assert.deepEqual([1, 2, 3].map((t) => p.price('BLE-01', t)), [0, 20, 50]);
  assert.deepEqual([1, 2, 3].map((t) => p.price('BLE-04', t)), [0, 40, 100]);
  assert.deepEqual([1, 2, 3].map((t) => p.price('BLE-10', t)), [0, 60, 150]);
  assert.equal(p.price('BLE-01', 0), -1);
  assert.equal(p.price('BLE-01', 4), -1);
  assert.equal(p.price('NOPE-01', 2), -1);
});

test('tiers unlock in order and need enough points', () => {
  const p = new Progress(data, MAC, fresh().st);
  assert.equal(p.tier('BLE-10'), 1);
  assert.equal(p.buy('BLE-10', 1), 'ok');           // free, records nothing
  assert.equal(p.spent(), 0);
  assert.equal(p.buy('BLE-10', 3), 'locked');       // tier 2 first
  assert.equal(p.buy('BLE-10', 2), 'ok');           // 60 -> 40 left
  assert.equal(p.points(), 40);
  assert.equal(p.buy('BLE-10', 2), 'ok');           // owned: no charge
  assert.equal(p.points(), 40);
  assert.equal(p.buy('BLE-10', 3), 'points');       // needs 150
  assert.equal(p.tier('BLE-10'), 2);
  assert.equal(p.hintText('BLE-10', 2), data.challenges.find((c) => c.id === 'BLE-10').hints[1]);
  assert.equal(p.hintText('BLE-10', 3), null);
  p.solve('BLE-10');                                // +300, buying after solving is allowed
  assert.equal(p.buy('BLE-10', 3), 'ok');
  assert.equal(p.points(), 100 + 300 - 60 - 150);
  assert.equal(p.buy('BLE-10', 'x'), 'bad');
  assert.equal(p.buy('NOPE-01', 2), 'bad');
  // Exactly enough is enough.
  const q = new Progress(data, '000000000001', fresh().st);
  assert.equal(q.buy('BLE-01', 2), 'ok');           // 100 - 20 = 80
  assert.equal(q.buy('BLE-01', 3), 'ok');           // 80 - 50 = 30
  assert.equal(q.buy('BLE-02', 2), 'ok');           // 30 - 20 = 10
  assert.equal(q.buy('BLE-03', 2), 'points');       // 10 < 20
  assert.equal(q.points(), 10);
});

test('progress is saved per board MAC and reloaded', () => {
  const { st } = fresh();
  const a = new Progress(data, MAC, st);
  a.solve('SER-01');
  a.buy('SER-01', 2);
  const b = new Progress(data, '240AC4ABCDEF', st);
  assert.equal(b.points(), 100);
  const a2 = new Progress(data, MAC, st);
  assert.equal(a2.isSolved('SER-01'), true);
  assert.equal(a2.tier('SER-01'), 2);
  assert.equal(a2.points(), 100 + 100 - 20);
  setLastMac(st, MAC);
  assert.equal(lastMac(st), MAC);
  a2.reset();
  assert.equal(new Progress(data, MAC, st).points(), 100);
});

test('a corrupt or foreign record starts fresh', () => {
  const { ls, st } = fresh();
  ls.setItem(`esp32ctf:v1:${MAC}`, '{not json');
  assert.equal(new Progress(data, MAC, st).points(), 100);
  ls.setItem(`esp32ctf:v1:${MAC}`, JSON.stringify({ v: 1, mac: 'FFFFFFFFFFFF', solved: ['BLE-10'], tiers: {} }));
  assert.equal(new Progress(data, MAC, st).points(), 100);
  ls.setItem(`esp32ctf:v1:${MAC}`, JSON.stringify({ v: 1, mac: MAC, solved: ['BLE-10', 'NOPE-01'], tiers: { 'BLE-01': 7 } }));
  const p = new Progress(data, MAC, st);
  assert.equal(p.points(), 400);
  assert.equal(p.tier('BLE-01'), 1);
});

test('no storage, or storage that throws: works in memory', () => {
  const none = openStorage(null);
  assert.equal(none.persistent, false);
  const p = new Progress(data, MAC, none);
  p.solve('BLE-01');
  assert.equal(new Progress(data, MAC, none).points(), 200); // same session still sees it

  const ls = new FakeStorage();
  ls.fail = true;
  const st = openStorage(ls);
  assert.equal(st.persistent, false);

  const throwing = { getItem() { throw new Error('SecurityError'); }, setItem() { throw new Error('SecurityError'); }, removeItem() {} };
  assert.equal(openStorage(throwing).persistent, false);

  // Storage that fills up later falls back to memory without throwing.
  const later = new FakeStorage();
  const st2 = openStorage(later);
  assert.equal(st2.persistent, true);
  later.fail = true;
  const q = new Progress(data, MAC, st2);
  assert.doesNotThrow(() => q.solve('BLE-02'));
  assert.equal(st2.persistent, false);
});

test('export / import round trip', () => {
  const { st } = fresh();
  const p = new Progress(data, MAC, st);
  p.solve('BLE-01');
  p.solve('HW-03');
  p.buy('HW-03', 2);
  p.buy('HW-03', 3);
  const file = JSON.stringify(p.exportData('ESP32-CTF-3456', '24:0A:C4:12:34:56', new Date(0)));
  const imp = parseImport(file, data, parseMac, macHex);
  assert.equal(imp.macHex, MAC);

  const other = fresh().st;
  const q = new Progress(data, imp.macHex, other);
  q.replaceWith(imp);
  assert.deepEqual([...q.solved].sort(), ['BLE-01', 'HW-03']);
  assert.equal(q.tier('HW-03'), 3);
  assert.equal(q.points(), p.points());
  assert.equal(new Progress(data, MAC, other).points(), p.points()); // saved
});

test('import rejects files that are not ours or do not add up', () => {
  const base = { app: 'esp32-ctf', v: 1, board: 'ESP32-CTF-3456', mac: '24:0A:C4:12:34:56', solved: [], tiers: {} };
  const bad = (o) => assert.throws(() => parseImport(typeof o === 'string' ? o : JSON.stringify(o), data, parseMac, macHex));
  bad('not json');
  bad({ ...base, app: 'other' });
  bad({ ...base, v: 2 });
  bad({ ...base, mac: 'zz' });
  bad({ ...base, solved: ['NOPE-01'] });
  bad({ ...base, solved: 'BLE-01' });
  bad({ ...base, tiers: { 'BLE-01': 4 } });
  bad({ ...base, tiers: [] });
  bad({ ...base, tiers: { 'BLE-10': 3, 'BLE-11': 3 } }); // 420 spent from 100
  assert.ok(parseImport(JSON.stringify(base), data, parseMac, macHex));
});
