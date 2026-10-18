// Demo board (?demo): an in-memory fake ESP32 that speaks the same byte
// protocol as the firmware (SOH machine commands, STX/ETX JSON replies, a
// tiny echoing console). It holds no real hint texts and no real flags: the
// only accepted flag body is DEMO00000000, which solves the selected
// challenge.

const CATALOG = [
  ['BLE-01', 'Read the flag', 100, ''], ['BLE-02', 'Hex and friends', 100, ''],
  ['BLE-03', 'Notify me', 100, ''], ['BLE-04', 'Indicate and ack', 200, ''],
  ['BLE-05', 'Write to unlock', 100, ''], ['BLE-06', 'Descriptor hunt', 200, ''],
  ['BLE-07', 'Advertising payload', 200, ''], ['BLE-08', 'Big MTU', 200, ''],
  ['BLE-09', 'Passkey pairing', 200, ''], ['BLE-10', 'Rate-limited PIN', 300, ''],
  ['BLE-11', 'Write-without-response sequence', 300, ''],
  ['BTC-01', 'SPP console', 100, ''], ['BTC-02', 'Hidden menu', 200, ''],
  ['BTC-03', 'Device class clue', 200, ''],
  ['WEB-01', 'Hidden SSID', 100, ''], ['WEB-02', 'View source', 100, ''],
  ['WEB-03', 'Cookie admin', 100, ''], ['WEB-04', 'Header check', 100, ''],
  ['WEB-05', 'Weak JWT', 200, ''], ['WEB-06', 'Ping tool', 200, ''],
  ['WEB-07', 'WebSocket chatter', 200, ''], ['WEB-08', 'mDNS discovery', 200, ''],
  ['WEB-09', 'UDP knock', 300, ''],
  ['SER-01', 'Boot log', 100, ''], ['SER-02', 'Wrong baud', 200, 'USB-UART adapter'],
  ['SER-03', 'Debug login', 300, ''], ['SER-04', 'Escape sequence', 200, ''],
  ['HW-01', 'Jumper it', 100, 'jumper wire'], ['HW-02', 'Blinky Morse', 100, ''],
  ['HW-03', 'PWM frequency', 200, 'logic analyzer'], ['HW-04', 'I2C chatter', 200, 'logic analyzer'],
  ['HW-05', 'SPI dump', 200, 'logic analyzer'], ['HW-06', 'Touch pad code', 200, ''],
  ['RE-01', 'Strings in flash', 100, ''], ['RE-02', 'NVS secrets', 200, ''],
  ['RE-03', 'Crackme', 300, ''], ['RE-04', "XOR'd asset", 300, ''],
  ['CRY-01', 'Classic cipher', 100, ''], ['CRY-02', 'ECB penguin', 300, ''],
  ['CRY-03', 'Reused nonce', 200, ''],
];
const MODE_OF = { BLE: 'radio', BTC: 'radio', WEB: 'net' };
const TIER_NAME = ['nudge', 'hint', 'walkthrough'];
const DEMO_BODY = 'DEMO00000000';
const BOARD = 'ESP32-CTF-DEMO';
const PROMPT = '\x1b[38;2;180;240;74mctf>\x1b[0m ';

const price = (pts, tier) => (tier === 1 ? 0 : Math.round(pts * (tier === 2 ? 0.2 : 0.5)));

export class DemoTransport {
  constructor() {
    this.mode = 'radio';
    this.solved = new Set(['BLE-01', 'BLE-02', 'SER-01']);
    this.tier = {};        // id -> highest owned tier (2 or 3)
    this.line = '';
    this.machine = false;  // inside a SOH line
    this.booting = false;
    this.selected = '';    // set by the app so DEMO00000000 knows what to solve
    this.enc = new TextEncoder();
  }

  attach(link) {
    this.link = link;
    setTimeout(() => this.out('\r\nDemo board: a pretend ESP32 that lives in this page. Its hints and flags are placeholders.\r\n' + PROMPT), 50);
  }

  out(text) {
    if (this.link && !this.closed) this.link.receive(this.enc.encode(text));
  }

  reply(obj) { this.out('\x02' + JSON.stringify(obj) + '\x03\r\n'); }

  select(id) { this.selected = id; }

  points() {
    let earned = 0, spent = 0;
    for (const [id, , pts] of CATALOG) {
      if (this.solved.has(id)) earned += pts;
      const t = this.tier[id] || 1;
      if (t >= 2) spent += price(pts, 2);
      if (t >= 3) spent += price(pts, 3);
    }
    return { points: 100 + earned - spent, earned, spent };
  }

  async write(bytes) {
    if (this.booting) return; // the chip is resetting; bytes are lost
    for (const b of bytes) {
      if (b === 0x01) { this.machine = true; this.line = ''; continue; }
      if (b === 0x0d || b === 0x0a) {
        const line = this.line.trim();
        this.line = '';
        if (this.machine) { this.machine = false; setTimeout(() => this.api(line), 30); continue; }
        this.out('\r\n');
        this.human(line);
        continue;
      }
      if (this.machine) { this.line += String.fromCharCode(b); continue; }
      if (b === 0x03) { this.line = ''; this.out('^C\r\n' + PROMPT); continue; }
      if (b === 0x7f || b === 0x08) {
        if (this.line) { this.line = this.line.slice(0, -1); this.out('\b \b'); }
        continue;
      }
      if (b >= 0x20 && b < 0x7f) { this.line += String.fromCharCode(b); this.out(String.fromCharCode(b)); }
    }
  }

  human(line) {
    const [cmd, arg] = line.split(/\s+/);
    let text = '';
    if (!cmd) text = '';
    else if (cmd === 'help') {
      text = 'Demo board commands: help, status, list [track], mode.\r\nThe real board has many more.\r\n';
    } else if (cmd === 'status') {
      const p = this.points();
      text = `Points: ${p.points} (started with 100, +${p.earned} solved, -${p.spent} hints)\r\n` +
        `Solved: ${this.solved.size} of ${CATALOG.length}\r\n`;
    } else if (cmd === 'list') {
      const want = (arg || '').toUpperCase();
      for (const [id, name, pts, kit] of CATALOG) {
        if (want && !id.startsWith(want + '-')) continue;
        text += `${id.padEnd(7)} ${name.padEnd(32)} ${String(pts).padStart(3)}  ${this.solved.has(id) ? 'solved' : '-'}` +
          (kit ? `   [needs ${kit}]` : '') + '\r\n';
      }
    } else if (cmd === 'mode') {
      text = `mode: ${this.mode}\r\n`;
    } else {
      text = 'Unknown command. Type `help`.\r\n';
    }
    this.out(text + PROMPT);
  }

  api(line) {
    const [, verb, a, b] = line.split(/\s+/);
    const find = (id) => CATALOG.find((c) => c[0] === (id || '').toUpperCase());
    if (verb === 'info') {
      const p = this.points();
      return this.reply({ ok: true, fw: '0.2.0-demo', board: BOARD, mode: this.mode, points: p.points, start: 100,
        earned: p.earned, spent: p.spent, solved: this.solved.size, total: CATALOG.length });
    }
    if (verb === 'list') {
      return this.reply({ ok: true, challenges: CATALOG.map(([id, name, pts, kit]) => {
        const track = id.split('-')[0];
        return { id, track, name, pts, kit, mode: MODE_OF[track] || 'any', solved: this.solved.has(id),
          tier: this.tier[id] || 1, prices: [0, price(pts, 2), price(pts, 3)] };
      }) });
    }
    if (verb === 'submit') {
      const v = (a || '').trim().toUpperCase().replace(/^ESP\{/, '').replace(/\}$/, '');
      const c = v === DEMO_BODY ? find(this.selected) : null;
      if (!c) return this.reply({ ok: true, result: 'wrong', points: this.points().points });
      const already = this.solved.has(c[0]);
      this.solved.add(c[0]);
      return this.reply({ ok: true, result: already ? 'already' : 'new', id: c[0], pts: c[2], points: this.points().points });
    }
    if (verb === 'hint') {
      const c = find(a), tier = Number(b);
      if (!c || ![1, 2, 3].includes(tier)) return this.reply({ ok: false, error: 'unknown challenge or tier' });
      const owned = this.tier[c[0]] || 1;
      const p = price(c[2], tier), pts = this.points().points;
      if (tier > owned) {
        if (tier > owned + 1) return this.reply({ ok: false, error: 'locked', need: 0, points: pts });
        if (pts < p) return this.reply({ ok: false, error: 'points', need: p, points: pts });
        this.tier[c[0]] = tier;
      }
      return this.reply({ ok: true, id: c[0], tier,
        text: `Demo ${TIER_NAME[tier - 1]} for ${c[0]}. On a real board, this is where the ${TIER_NAME[tier - 1]} text appears.`,
        points: this.points().points });
    }
    if (verb === 'answer') return this.reply({ ok: true, correct: false });
    if (verb === 'mode') {
      if (a !== 'radio' && a !== 'net') return this.reply({ ok: false, error: 'mode must be radio or net' });
      this.reply({ ok: true, mode: a });
      this.reboot(a);
      return undefined;
    }
    return this.reply({ ok: false, error: 'unknown command' });
  }

  reboot(mode) {
    this.booting = true;
    setTimeout(() => {
      this.mode = mode;
      this.out('\r\nets Jun  8 2016 00:22:57\r\n\r\nrst:0xc (SW_CPU_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)\r\n');
      this.out('I (31) boot: ESP-IDF v6.1 2nd stage bootloader\r\nI (412) main_task: Calling app_main()\r\n');
    }, 400);
    setTimeout(() => {
      this.booting = false;
      this.out('\r\n==========================================\r\n  ESP32 CTF (demo board)\r\n' +
        `  mode: ${mode}\r\n  board MAC: 02:00:00:00:DE:30\r\n  type \`help\` to get started\r\n` +
        '==========================================\r\n\r\n' + PROMPT);
    }, 1800);
  }

  async close() { this.closed = true; }
}
