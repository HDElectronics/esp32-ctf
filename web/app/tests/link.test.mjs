// Run: node web/app/tests/link.test.mjs  (stray STX in reset noise must not swallow the boot log)
import { FrameParser } from '../js/link.js';
let text = '', frames = [];
const p = new FrameParser((t) => { text += t; }, (f) => frames.push(f));
const enc = (s) => new TextEncoder().encode(s);
p.push(new Uint8Array([0xff, 0x02, 0x41, 0x00]));            // reset noise with a stray STX
p.push(enc('ets Jul 29 2019\r\nrst:0x1 (POWERON_RESET)\r\n'));
p.push(enc('I (982) locale: cipher shard 1/4: NB\r\n  ESP32 CTF\r\nctf> '));
p.push(enc('\x02{"ok":true,"board":"X"}\x03\r\n'));              // a real frame still works
p.push(enc('ctf> '));
const ok = text.includes('POWERON_RESET') && text.includes('ESP32 CTF') && frames.length === 1 && frames[0].includes('"board"');
if (!ok) process.exitCode = 1;
console.log(ok ? 'PASS' : 'FAIL', JSON.stringify({ frames, tail: text.slice(-60) }));
