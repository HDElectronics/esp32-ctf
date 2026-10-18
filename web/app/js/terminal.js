// Console drawer: xterm.js (pinned in index.html's import map) showing all
// board text outside machine frames; keystrokes go raw to the board. Falls
// back to a read-only text pane if xterm.js cannot be loaded (offline).

const KEEP = 256 * 1024; // console text kept while the drawer is closed

export class ConsolePane {
  constructor(host, onKey) {
    this.host = host;
    this.onKey = onKey;
    this.term = null;
    this.fit = null;
    this.pending = '';
    this.fallback = null;
    this.opening = null;
  }

  write(text) {
    if (this.term) this.term.write(text);
    else if (this.fallback) this.appendFallback(text);
    else this.pending = (this.pending + text).slice(-KEEP);
  }

  // Create the terminal the first time the drawer opens (xterm needs a
  // visible element to measure its cells).
  async show({ focus = false } = {}) {
    if (!this.term && !this.fallback) {
      if (!this.opening) this.opening = this.create();
      await this.opening;
    }
    this.resize();
    if (focus) this.focus();
  }

  async create() {
    try {
      const [{ Terminal }, { FitAddon }] = await Promise.all([import('@xterm/xterm'), import('@xterm/addon-fit')]);
      const term = new Terminal({
        convertEol: true,
        cursorBlink: true,
        fontFamily: "'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace",
        fontSize: 13,
        lineHeight: 1.35,
        scrollback: 5000,
        theme: {
          background: '#0e0c14', foreground: '#c3bdd3', cursor: '#b4f04a', cursorAccent: '#0e0c14',
          selectionBackground: '#3a3350', green: '#b4f04a', brightGreen: '#c9f57a',
        },
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      this.host.textContent = '';
      term.open(this.host);
      term.onData((d) => this.onKey(d));
      // The board's editor ignores Tab, so Tab and Shift+Tab keep moving
      // focus through the page instead of trapping keyboard users here.
      term.attachCustomKeyEventHandler((e) => e.key !== 'Tab');
      this.term = term;
      this.fit = fit;
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      this.resize();
      if (this.pending) { term.write(this.pending); this.pending = ''; }
      window.addEventListener('resize', () => this.resize());
    } catch (e) {
      console.warn('xterm.js did not load; using a plain console pane', e);
      this.host.textContent = '';
      this.fallback = document.createElement('pre');
      this.fallback.className = 'console-fallback';
      this.fallback.tabIndex = 0;
      this.fallback.setAttribute('aria-label', 'Console output (typing needs the terminal, which did not load)');
      this.host.append(this.fallback);
      this.appendFallback(this.pending);
      this.pending = '';
    }
  }

  appendFallback(text) {
    // eslint-disable-next-line no-control-regex
    const clean = text.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '').replace(/\r/g, '');
    this.fallback.textContent = (this.fallback.textContent + clean).slice(-KEEP);
    this.fallback.scrollTop = this.fallback.scrollHeight;
  }

  resize() {
    if (this.fit && this.host.offsetParent) {
      try { this.fit.fit(); } catch { /* not laid out yet */ }
    }
  }

  focus() { if (this.term) this.term.focus(); }

  clear() {
    this.pending = '';
    if (this.term) this.term.reset();
    if (this.fallback) this.fallback.textContent = '';
  }
}
