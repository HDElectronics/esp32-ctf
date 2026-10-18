// Web Serial transport: 115200 8N1, DTR and RTS both asserted right after
// open (the DevKit's auto-reset circuit resets the chip when RTS is asserted
// without DTR), one read loop feeding the BoardLink.

export const serialSupported = () => 'serial' in navigator;

export class SerialTransport {
  constructor(port) {
    this.port = port;
    this.reader = null;
    this.reading = false;
    this.onLost = null; // called once if the port goes away (unplugged)
    this.loop = null;
  }

  // Ask the player to pick a port. Rejects with NotFoundError on cancel.
  static async pick() {
    const port = await navigator.serial.requestPort();
    return new SerialTransport(port);
  }

  async open() {
    await this.port.open({ baudRate: 115200, dataBits: 8, stopBits: 1, parity: 'none', flowControl: 'none' });
    try {
      await this.port.setSignals({ dataTerminalReady: true, requestToSend: true });
    } catch { /* some bridges have no control lines; nothing to protect then */ }
  }

  attach(link) {
    this.link = link;
    this.reading = true;
    this.loop = this.readLoop();
  }

  async readLoop() {
    while (this.reading && this.port.readable) {
      this.reader = this.port.readable.getReader();
      try {
        for (;;) {
          const { value, done } = await this.reader.read();
          if (done) break;
          if (value && value.length) this.link.receive(value);
        }
      } catch (e) {
        // Framing, parity, break and overrun errors are not fatal: the
        // stream is reopened by the loop. A lost device ends the loop
        // because port.readable becomes null.
        console.warn('[ctf] serial read error:', e && e.name, e && e.message);
        if (this.reading && e && e.name === 'NetworkError') break;
      } finally {
        try { this.reader.releaseLock(); } catch { /* already released */ }
        this.reader = null;
      }
    }
    if (this.reading) {
      console.warn('[ctf] serial read loop ended; readable =', this.port.readable);
      this.reading = false;
      if (this.onLost) this.onLost();
    }
  }

  async write(bytes) {
    if (!this.port.writable) throw new Error('port not writable');
    const writer = this.port.writable.getWriter();
    try { await writer.write(bytes); } finally { writer.releaseLock(); }
  }

  async close() {
    this.reading = false;
    if (this.reader) {
      try { await this.reader.cancel(); } catch { /* port already gone */ }
    }
    if (this.loop) { try { await this.loop; } catch { /* ignore */ } }
    try { await this.port.close(); } catch { /* already closed or unplugged */ }
  }
}
