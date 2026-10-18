// Tiny Markdown renderer for the primers: headings, paragraphs, bullet and
// numbered lists, fenced and inline code, bold, italic and links. All text is
// HTML-escaped first; only http(s), mailto, relative and #anchor links pass.

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function safeHref(url) {
  const u = url.trim();
  if (/^(https?:|mailto:)/i.test(u) || /^[#./]/.test(u) || !/^[a-z][a-z0-9+.-]*:/i.test(u)) return u;
  return null;
}

function inline(src) {
  // Pull code spans out first so nothing inside them is formatted.
  const codes = [];
  let s = src.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = escapeHtml(s);
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, url) => {
    const href = safeHref(url.replace(/&amp;/g, '&'));
    if (!href) return text;
    const ext = /^https?:/i.test(href) ? ' target="_blank" rel="noopener"' : '';
    return `<a href="${escapeHtml(href)}"${ext}>${text}</a>`;
  });
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*\w])\*([^*\s][^*]*)\*(?!\w)/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^_\w])_([^_\s][^_]*)_(?!\w)/g, '$1<em>$2</em>');
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${escapeHtml(codes[Number(i)])}</code>`);
}

// headingOffset shifts levels: with 1, "# Title" renders as <h2>.
export function renderMarkdown(md, { headingOffset = 1 } = {}) {
  const lines = md.replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let para = [];
  let list = null; // { tag, items: [string] }

  const flushPara = () => {
    if (para.length) out.push(`<p>${inline(para.join(' '))}</p>`);
    para = [];
  };
  const flushList = () => {
    if (list) out.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join('')}</${list.tag}>`);
    list = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const fence = line.match(/^\s*(```|~~~)\s*([\w-]*)\s*$/);
    if (fence) {
      flushPara(); flushList();
      const body = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith(fence[1]); i++) body.push(lines[i]);
      out.push(`<pre><code>${escapeHtml(body.join('\n'))}</code></pre>`);
      continue;
    }
    const h = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (h) {
      flushPara(); flushList();
      const level = Math.min(6, h[1].length + headingOffset);
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      continue;
    }
    const li = line.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
    if (li) {
      flushPara();
      const tag = /\d/.test(li[1]) ? 'ol' : 'ul';
      if (list && list.tag !== tag) flushList();
      if (!list) list = { tag, items: [] };
      list.items.push(li[2]);
      continue;
    }
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if (list && /^\s{2,}\S/.test(line)) { list.items[list.items.length - 1] += ' ' + line.trim(); continue; }
    flushList();
    para.push(line.trim());
  }
  flushPara(); flushList();
  return out.join('\n');
}
