// One connected tab at a time. Only one program can own the board's serial
// port, so tabs of this app coordinate over a BroadcastChannel:
//   {type:'connected', board, tabId}   a tab holds the board (also the answer to 'who')
//   {type:'disconnected', tabId}       it let go
//   {type:'who', from}                 any connected tab, please announce yourself
//   {type:'release', tabId, from}      the tab `tabId` should disconnect itself
//   {type:'released', tabId, to}       it did
// Without BroadcastChannel every method is a harmless no-op.

const newId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

export class TabCoordinator {
  // channel: a BroadcastChannel-like object ({postMessage, onmessage, close}) or null.
  // onRelease(): async, called when another tab takes the board; resolves once
  // the port is closed. onPeer(peer|null): the connected peer changed.
  constructor({ channel, tabId = newId(), onRelease = async () => {}, onPeer = () => {} } = {}) {
    this.ch = channel || null;
    this.tabId = tabId;
    this.onRelease = onRelease;
    this.onPeer = onPeer;
    this.board = null;        // set while this tab is connected
    this.peer = null;         // { tabId, board } of another connected tab
    this.waiters = new Set(); // pending probe/release promises
    if (this.ch) this.ch.onmessage = (e) => this.handle(e && e.data);
  }

  static create(name, opts) {
    let channel = null;
    try { if (typeof BroadcastChannel === 'function') channel = new BroadcastChannel(name); } catch { /* unsupported */ }
    return new TabCoordinator({ ...opts, channel });
  }

  post(msg) { if (this.ch) { try { this.ch.postMessage(msg); } catch { /* channel closed */ } } }

  setPeer(peer) {
    const same = (this.peer && this.peer.tabId) === (peer && peer.tabId);
    this.peer = peer;
    if (!same) this.onPeer(peer);
  }

  announceConnected(board) {
    this.board = String(board || '');
    this.setPeer(null); // we hold the board now; any old record is stale
    this.post({ type: 'connected', board: this.board, tabId: this.tabId });
  }

  announceDisconnected() {
    if (this.board === null) return;
    this.board = null;
    this.post({ type: 'disconnected', tabId: this.tabId });
  }

  wait(match, ms) {
    return new Promise((resolve) => {
      const w = { match, resolve: (v) => { clearTimeout(w.timer); this.waiters.delete(w); resolve(v); } };
      w.timer = setTimeout(() => w.resolve(null), ms);
      this.waiters.add(w);
    });
  }

  // Ask whether another tab is connected. Resolves with the peer or null.
  async probe(ms = 250) {
    if (!this.ch) return null;
    const got = this.wait((m) => m.type === 'connected', ms);
    this.post({ type: 'who', from: this.tabId });
    const m = await got;
    return m ? { tabId: m.tabId, board: m.board } : this.peer;
  }

  // Ask the connected peer to let go. Resolves true when it confirmed, false
  // on timeout (a frozen or crashed tab); the peer record is cleared either way.
  async requestRelease(ms = 3000) {
    const peer = this.peer;
    if (!this.ch || !peer) return true;
    const got = this.wait((m) => m.type === 'released' && m.tabId === peer.tabId, ms);
    this.post({ type: 'release', tabId: peer.tabId, from: this.tabId });
    const m = await got;
    if (this.peer && this.peer.tabId === peer.tabId) this.setPeer(null);
    return !!m;
  }

  async handle(m) {
    if (!m || typeof m !== 'object' || m.tabId === undefined && m.type !== 'who') return;
    for (const w of [...this.waiters]) if (w.match(m)) w.resolve(m);
    switch (m.type) {
      case 'connected':
        if (m.tabId !== this.tabId) this.setPeer({ tabId: m.tabId, board: m.board });
        break;
      case 'disconnected':
        if (this.peer && this.peer.tabId === m.tabId) this.setPeer(null);
        break;
      case 'who':
        if (this.board !== null && m.from !== this.tabId) this.post({ type: 'connected', board: this.board, tabId: this.tabId });
        break;
      case 'release':
        if (m.tabId !== this.tabId || this.board === null) break;
        try { await this.onRelease(); } catch { /* best effort: the port is closed or gone */ }
        this.board = null;
        this.post({ type: 'released', tabId: this.tabId, to: m.from });
        break;
      default:
    }
  }

  close() { if (this.ch) { try { this.ch.close(); } catch { /* ignore */ } } }
}
