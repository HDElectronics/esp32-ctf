// Board link: splits the byte stream into console text and STX/ETX-framed
// JSON replies, and runs machine requests (SOH + command + CR) one at a time.
// Works over any transport with { write(Uint8Array), close() } that calls
// link.receive(bytes) for incoming data (Web Serial or the demo board).

const SOH = 0x01, STX = 0x02, ETX = 0x03;
const FRAME_MAX = 64 * 1024;
const DEFAULT_TIMEOUT = 3000;

export const debug = typeof location !== 'undefined' && new URLSearchParams(location.search).has('debug');
const log = (...a) => { if (debug) console.debug('[ctf]', ...a.map((x) => (typeof x === 'object' ? JSON.stringify(x) : x))); };

// Byte stream -> console text + frames. Text outside STX..ETX goes to onText;
// each complete frame goes to onFrame as a string. The "\r\n" that ends a
// frame line is swallowed so it does not show up as a blank console line.
export class FrameParser {
  constructor(onText, onFrame) {
    this.onText = onText;
    this.onFrame = onFrame;
    this.inFrame = false;
    this.afterFrame = false;
    this.frame = [];
    this.textDec = new TextDecoder();
  }

  push(bytes) {
    let start = 0;
    const flushText = (end) => {
      if (end > start) this.onText(this.textDec.decode(bytes.subarray(start, end), { stream: true }));
    };
    for (let i = 0; i < bytes.length; i++) {
      const b = bytes[i];
      if (this.inFrame) {
        if (b === ETX) {
          this.inFrame = false;
          this.afterFrame = true;
          const text = new TextDecoder().decode(new Uint8Array(this.frame));
          this.frame = [];
          start = i + 1;
          this.onFrame(text);
        } else if (b === STX) {
          this.frame = []; // a new frame started; drop the broken one
        } else if (b === 0x0d || b === 0x0a) {
          // Real frames are one line, so a line break means the STX was a
          // stray byte (boot noise after a reset). Give the bytes back to
          // the console instead of swallowing the boot log.
          this.inFrame = false;
          if (this.frame.length) this.onText(new TextDecoder().decode(new Uint8Array(this.frame)));
          this.frame = [];
          start = i;
        } else if (this.frame.length < FRAME_MAX) {
          this.frame.push(b);
        } else {
          this.inFrame = false; // runaway frame: give up on it
          this.frame = [];
          start = i + 1;
        }
        continue;
      }
      if (this.afterFrame) {
        if (b === 0x0d || b === 0x0a) { start = i + 1; continue; }
        this.afterFrame = false;
      }
      if (b === STX) {
        flushText(i);
        this.inFrame = true;
        this.frame = [];
        start = i + 1;
      }
    }
    if (!this.inFrame) flushText(bytes.length);
  }
}

// What a reply to each command must look like. A reply that does not match
// the request in flight (for example a late answer to a request that already
// timed out) is dropped instead of being handed to the wrong caller.
function matcher(cmd) {
  const verb = cmd.split(' ')[1];
  const isErr = (j) => j.ok === false && typeof j.error === 'string' && !('need' in j);
  switch (verb) {
    case 'info': return (j) => 'board' in j || isErr(j);
    case 'list': return (j) => Array.isArray(j.challenges) || isErr(j);
    case 'submit': return (j) => 'result' in j || isErr(j);
    case 'hint': return (j) => 'tier' in j || 'error' in j;
    case 'answer': return (j) => 'correct' in j || isErr(j);
    default: return () => true;
  }
}

export class BoardLink {
  constructor(transport) {
    this.transport = transport;
    this.queue = [];      // pending requests, FIFO
    this.current = null;  // request in flight
    this.textListeners = new Set();
    this.typed = 0;       // printable bytes the player typed since the last line end
    this.closed = false;
    this.writeChain = Promise.resolve();
    this.parser = new FrameParser((t) => this.emitText(t), (f) => this.onFrame(f));
    transport.attach(this);
  }

  // Called by the transport with incoming bytes.
  receive(bytes) { this.parser.push(bytes); }

  onText(fn) { this.textListeners.add(fn); return () => this.textListeners.delete(fn); }

  emitText(t) { for (const fn of this.textListeners) fn(t); }

  // Raw keystrokes from the console pane, passed through untouched (Ctrl-]
  // included). Tracks whether the player has a half-typed line on the board,
  // so a machine command is never glued onto it.
  sendUser(data) {
    if (data.startsWith('\x1b')) { /* arrow keys etc.: the editor swallows them */ }
    else {
      for (const ch of data) {
        if (ch === '\r' || ch === '\n' || ch === '\x03') this.typed = 0;
        else if (ch === '\x7f' || ch === '\b') this.typed = Math.max(0, this.typed - 1);
        else if (ch >= ' ') this.typed++;
      }
    }
    this.write(new TextEncoder().encode(data));
  }

  get lineDirty() { return this.typed > 0; }

  write(bytes) {
    this.writeChain = this.writeChain
      .then(() => (this.closed ? undefined : this.transport.write(bytes)))
      .catch((e) => log('write failed', e));
    return this.writeChain;
  }

  // Send `cmd` (e.g. "api info") as a machine command; resolves with the
  // parsed JSON reply or rejects with Error('timeout' | 'closed' | 'busy').
  request(cmd, { timeout = DEFAULT_TIMEOUT, background = false } = {}) {
    return new Promise((resolve, reject) => {
      this.queue.push({ cmd, timeout, background, resolve, reject, match: matcher(cmd) });
      this.pump();
    });
  }

  pump() {
    if (this.current || this.closed) return;
    const req = this.queue.shift();
    if (!req) return;
    if (this.lineDirty) {
      // A background poll waits for a later round rather than touching the
      // player's half-typed line. An action the player asked for drops that
      // line with Ctrl-C first (the board prints ^C and a fresh prompt).
      if (req.background) { req.reject(new Error('busy')); this.pump(); return; }
      this.write(new Uint8Array([0x03]));
      this.typed = 0;
    }
    this.current = req;
    req.timer = setTimeout(() => {
      if (this.current !== req) return;
      log('timeout', req.cmd);
      this.current = null;
      req.reject(new Error('timeout'));
      this.pump();
    }, req.timeout);
    log('tx', req.cmd);
    const enc = new TextEncoder().encode(req.cmd);
    const bytes = new Uint8Array(enc.length + 2);
    bytes[0] = SOH;
    bytes.set(enc, 1);
    bytes[bytes.length - 1] = 0x0d;
    this.write(bytes);
  }

  onFrame(text) {
    let json;
    try { json = JSON.parse(text); } catch {
      log('bad frame', text);
      return;
    }
    log('rx', json);
    const req = this.current;
    if (!req || !req.match(json)) { log('unexpected frame dropped'); return; }
    clearTimeout(req.timer);
    this.current = null;
    req.resolve(json);
    this.pump();
  }

  // Resolves when the console text contains `needle` or after `ms`
  // (true if seen). Used to wait for the boot banner after a mode switch.
  waitForText(needle, ms) {
    return new Promise((resolve) => {
      let seen = '';
      const off = this.onText((t) => {
        seen = (seen + t).slice(-512);
        if (seen.includes(needle)) { done(true); }
      });
      const timer = setTimeout(() => done(false), ms);
      function done(v) { off(); clearTimeout(timer); resolve(v); }
    });
  }

  async close() {
    if (this.closed) return;
    this.closed = true;
    if (this.current) { clearTimeout(this.current.timer); this.current.reject(new Error('closed')); this.current = null; }
    for (const r of this.queue.splice(0)) r.reject(new Error('closed'));
    try { await this.writeChain; } catch { /* already logged */ }
    await this.transport.close();
  }
}
