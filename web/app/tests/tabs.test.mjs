// Run: node web/app/tests/tabs.test.mjs  (one connected tab at a time, over a fake BroadcastChannel)
import { TabCoordinator } from '../js/tabs.js';

// Fake bus: like BroadcastChannel, a message reaches every other channel, asynchronously.
const bus = new Set();
class FakeChannel {
  constructor() { this.onmessage = null; bus.add(this); }
  postMessage(data) {
    const copy = JSON.parse(JSON.stringify(data));
    for (const c of bus) if (c !== this) setTimeout(() => c.onmessage && c.onmessage({ data: copy }), 1);
  }
  close() { bus.delete(this); }
}

const fails = [];
const check = (name, cond) => { if (!cond) fails.push(name); console.log(cond ? 'ok  ' : 'FAIL', name); };
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

const log = [];
const a = new TabCoordinator({
  channel: new FakeChannel(), tabId: 'A',
  onRelease: async () => { log.push('A released'); await tick(5); a.announceDisconnected(); },
});
const peersB = [];
const b = new TabCoordinator({ channel: new FakeChannel(), tabId: 'B', onPeer: (p) => peersB.push(p) });

check('probe with nobody connected is null', (await b.probe(50)) === null);

a.announceConnected('ESP32-CTF-3014');
await tick();
check('live announce reaches the other tab', b.peer && b.peer.tabId === 'A' && b.peer.board === 'ESP32-CTF-3014');

// A tab that loads later finds the connected one by asking 'who'.
const c = new TabCoordinator({ channel: new FakeChannel(), tabId: 'C' });
const found = await c.probe(100);
check('late tab finds the connected tab with who', found && found.tabId === 'A');

const ok = await b.requestRelease(500);
check('release is confirmed', ok === true);
check('connected tab ran its release handler once', log.length === 1);
check('connected tab no longer holds the board', a.board === null);
check('releasing tab forgot the peer', b.peer === null);
await tick();
check('third tab saw the disconnect', c.peer === null);

b.announceConnected('ESP32-CTF-3014');
await tick();
check('new holder is seen by A and C', a.peer && a.peer.tabId === 'B' && c.peer && c.peer.tabId === 'B');

// A release aimed at another tab is ignored.
c.peer = { tabId: 'nobody' };
check('release to a missing tab times out', (await c.requestRelease(60)) === false);
check('B kept the board', b.board !== null);

// A frozen tab never answers: release times out and clears the record.
const frozen = new FakeChannel(); frozen.onmessage = null;
c.peer = null; c.setPeer({ tabId: 'F', board: 'x' });
check('frozen tab: release times out', (await c.requestRelease(60)) === false && c.peer === null);

b.announceDisconnected();
await tick();
check('disconnect clears the peer everywhere', a.peer === null && c.peer === null);

// No BroadcastChannel: everything is a no-op.
const n = new TabCoordinator({ channel: null });
n.announceConnected('x'); n.announceDisconnected();
check('no channel: probe null, release true', (await n.probe()) === null && (await n.requestRelease()) === true);

check('onPeer fired on changes only', peersB.length >= 2 && peersB[0].tabId === 'A');

for (const ch of [...bus]) ch.close();
if (fails.length) { process.exitCode = 1; console.log('FAIL', fails.join('; ')); } else console.log('PASS');
