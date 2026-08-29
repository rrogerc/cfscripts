import { useState, useEffect, useRef, memo } from 'react';
import { ClipboardCopy, Check, GraduationCap, Terminal } from 'lucide-react';
import TurndownService from 'turndown';
import { API_BASE_URL, fetchJson } from './api';
import { ratingColorClass } from './colors';

declare global {
  interface Window {
    MathJax?: {
      typesetClear?: (elements: Element[]) => void;
      typesetPromise?: (elements: Element[]) => Promise<void>;
    };
  }
}

export type Problem = {
  contestId: number;
  index: string;
  rating?: number;
  name?: string;
};

// Sample-input line map. Per line: which Input-spec paragraph and clause
// explain it, and the variable behind each individual token. Positions are
// 1-based against the same statement HTML, and clause_text lets the client
// confirm its own clause split matched the server's before highlighting.
type LinemapVar = { tex: string; text: string };
type LinemapLine = {
  line: number;
  para: number;
  clause: number;
  clause_text: string;
  kind: 'scalars' | 'array' | 'line';
  vars: LinemapVar[];
  text: string;
};
type Linemap = { v: number; lines: LinemapLine[]; para_count: number };

// textContent collapses block boundaries — walk the tree and emit \n
// for each <div>/<p>/<li>/<br> so CF's per-line sample I/O divs and
// property-title labels survive markdown extraction.
function blockTextContent(node: Node): string {
  const BLOCK = new Set(['DIV', 'P', 'LI', 'TR']);
  const out: string[] = [];
  const endsWithNL = () => out.length > 0 && out[out.length - 1].endsWith('\n');
  const walk = (n: Node) => {
    if (n.nodeType === Node.TEXT_NODE) {
      out.push(n.textContent || '');
      return;
    }
    if (n.nodeType !== Node.ELEMENT_NODE) return;
    const el = n as Element;
    if (el.tagName === 'BR') { out.push('\n'); return; }
    const isBlock = BLOCK.has(el.tagName);
    if (isBlock && out.length && !endsWithNL()) out.push('\n');
    el.childNodes.forEach(walk);
    if (isBlock && !endsWithNL()) out.push('\n');
  };
  walk(node);
  return out.join('');
}

function htmlToMarkdown(html: string, problem: Problem): string {
  const td = new TurndownService({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced',
  });

  // Codeforces .section-title → markdown heading
  td.addRule('sectionTitle', {
    filter: (node) => node.classList?.contains('section-title') ?? false,
    replacement: (_content, node) => `\n## ${(node as HTMLElement).textContent?.trim()}\n\n`,
  });

  // Problem title
  td.addRule('title', {
    filter: (node) =>
      node.classList?.contains('title') === true &&
      (node.parentElement?.classList?.contains('header') ?? false),
    replacement: (_content, node) => `# ${(node as HTMLElement).textContent?.trim()}\n\n`,
  });

  // Property rows (time limit, memory limit) → "label: value"
  td.addRule('property', {
    filter: (node) => {
      const cl = node.classList;
      return (cl?.contains('time-limit') || cl?.contains('memory-limit') ||
              cl?.contains('input-file') || cl?.contains('output-file')) ?? false;
    },
    replacement: (_content, node) => {
      const parts = blockTextContent(node).split('\n').map(s => s.trim()).filter(Boolean);
      return `${parts.join(': ')}\n`;
    },
  });

  // Sample test wrapper — skip the container div, children are handled individually
  td.addRule('sampleTest', {
    filter: (node) => node.classList?.contains('sample-test') ?? false,
    replacement: (content) => content,
  });

  // Pre blocks inside sample I/O → fenced code blocks
  td.addRule('samplePre', {
    filter: (node) => node.nodeName === 'PRE',
    replacement: (_content, node) => {
      const text = blockTextContent(node).split('\n').map(s => s.trimEnd()).join('\n').trim();
      return `\n\`\`\`\n${text}\n\`\`\`\n\n`;
    },
  });

  let md = td.turndown(html);

  // Convert Codeforces $$$ delimiters to standard $ for markdown math
  md = md.replace(/\$\$\$/g, '$');

  // Prepend problem metadata; rating is absent for ranked matches (hidden
  // until the match resolves), so only include it when known.
  const rating = problem.rating != null ? ` | Rating: ${problem.rating}` : '';
  const header = `**${problem.contestId}${problem.index}**${rating}\n\n`;
  return header + md;
}

// Sections that belong beside the statement rather than after it. The note
// explains the samples, so it travels with them.
const SIDE_SECTIONS = ['sample-tests', 'sample-test', 'note'];

/** Split an injected statement into a reading column (legend + input/output
 * spec) and a companion column (sample tests + note), returning the column
 * elements.
 *
 * The wrappers are created unconditionally and CSS decides whether they sit
 * side by side or stack — so switching layouts at the breakpoint never
 * mutates the DOM, and the stacked order matches the original statement.
 * Returns [] for statements with no sample section to pair against.
 */
function splitIntoColumns(host: HTMLElement): HTMLElement[] {
  // The injected CF markup has its own .problem-statement root nested
  // inside the host div, which carries the same class.
  const root = host.querySelector(':scope > .problem-statement') ?? host;
  const kids = Array.from(root.children).filter(
    (c): c is HTMLElement => c instanceof HTMLElement,
  );
  const isSide = (c: HTMLElement) => SIDE_SECTIONS.some((s) => c.classList.contains(s));
  if (!kids.some(isSide)) return [];

  const cols = document.createElement('div');
  cols.className = 'cf-cols';
  const main = document.createElement('div');
  main.className = 'cf-col-main';
  const side = document.createElement('div');
  side.className = 'cf-col-side';
  cols.append(main, side);

  // The header (title, limits) spans both columns, so it stays put.
  const header = kids.find((c) => c.classList.contains('header')) ?? null;
  for (const child of kids) {
    if (child === header) continue;
    (isSide(child) ? side : main).appendChild(child);
  }
  root.insertBefore(cols, header ? header.nextSibling : null);
  return [main, side];
}

/** The variable a TeX span refers to, or '' if it isn't a bare variable.
 * Subscripts collapse to the base name so $$$a_1$$$, $$$a_i$$$ and $$$a$$$
 * all highlight together. Anything more complex — a whole constraint like
 * 1 \le n \le 10^5, or display math — is deliberately not an anchor. */
function texBase(tex: string): string {
  const m = /^\\?([A-Za-z]+)(?:_\{?[A-Za-z0-9]+\}?)?$/.exec(tex.trim());
  return m ? m[1] : '';
}

/** Wrap each bare-variable $$$...$$$ occurrence in a tagged span, before
 * MathJax turns it into SVG. This is what makes "every mention of n" —
 * anywhere in the statement, legend included — addressable later. Complex
 * expressions are left completely untouched. */
function wrapMathVariables(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts: Text[] = [];
  while (walker.nextNode()) texts.push(walker.currentNode as Text);

  for (const node of texts) {
    if (!node.data.includes('$$$')) continue;
    const matches = [...node.data.matchAll(/\$\$\$(.+?)\$\$\$/g)]
      .filter((m) => texBase(m[1]));
    if (!matches.length) continue;

    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of matches) {
      const at = m.index!;
      if (at > last) frag.append(node.data.slice(last, at));
      const span = document.createElement('span');
      span.className = 'cf-tex';
      span.dataset.texBase = texBase(m[1]);
      span.textContent = m[0]; // delimiters intact so MathJax still typesets
      frag.append(span);
      last = at + m[0].length;
    }
    if (last < node.data.length) frag.append(node.data.slice(last));
    node.replaceWith(frag);
  }
}

// Mirrors split_clauses() in scraper.py. A boundary inside math would break
// typesetting, but wrapMathVariables has already made those spans atomic.
const CLAUSE_BOUNDARY = /(?<=[.;:])\s+|\s+[—–-]\s+/g;

type Unit =
  | { kind: 'text'; node: Text; start: number; map: number[] }
  | { kind: 'atom'; el: HTMLElement; start: number; end: number };

/** Flatten a paragraph into units while building the same whitespace-collapsed
 * string the backend built, remembering where every character came from. */
function collectUnits(para: HTMLElement): { units: Unit[]; text: string } {
  const units: Unit[] = [];
  let text = '';
  let lastSpace = true; // leading whitespace collapses away, as on the server

  const visit = (n: Node) => {
    if (n.nodeType === Node.TEXT_NODE) {
      const node = n as Text;
      const start = text.length;
      const map: number[] = [];
      for (let i = 0; i < node.data.length; i++) {
        const ch = node.data[i];
        if (/\s/.test(ch)) {
          if (lastSpace) continue;
          text += ' ';
          lastSpace = true;
        } else {
          text += ch;
          lastSpace = false;
        }
        map.push(i);
      }
      units.push({ kind: 'text', node, start, map });
      return;
    }
    if (n.nodeType !== Node.ELEMENT_NODE) return;
    const el = n as HTMLElement;
    // A wrapped variable is one indivisible character run.
    if (el.classList.contains('cf-tex')) {
      const start = text.length;
      text += (el.textContent ?? '').replace(/\s+/g, ' ');
      lastSpace = text.endsWith(' ');
      units.push({ kind: 'atom', el, start, end: text.length });
      return;
    }
    Array.from(el.childNodes).forEach(visit);
  };
  Array.from(para.childNodes).forEach(visit);
  return { units, text };
}

/** Tag every clause of a spec paragraph with data-clause, splitting text
 * nodes at the boundaries. A clause can end up as several spans (it may run
 * across inline markup), so they share one index rather than nesting. */
function wrapClauses(para: HTMLElement) {
  const { units, text } = collectUnits(para);
  if (!text) return;

  const ranges: Array<[number, number]> = [];
  let from = 0;
  const re = new RegExp(CLAUSE_BOUNDARY.source, 'g');
  for (let m = re.exec(text); m; m = re.exec(text)) {
    ranges.push([from, m.index]);
    from = m.index + m[0].length;
  }
  ranges.push([from, text.length]);
  const clauses = ranges.filter(([a, b]) => text.slice(a, b).trim());
  if (clauses.length < 2) return; // nothing gained over the paragraph itself

  // Record the clause texts now, while the math is still literal $$$...$$$.
  // After MathJax runs, textContent no longer resembles what the server
  // split, so this is the only moment the two can be compared.
  para.dataset.clauses = JSON.stringify(
    clauses.map(([a, b]) => text.slice(a, b).trim()),
  );

  const clauseAt = (pos: number) =>
    clauses.findIndex(([a, b]) => pos >= a && pos < b);

  for (const unit of units) {
    if (unit.kind === 'atom') {
      const i = clauseAt(unit.start);
      if (i >= 0) unit.el.dataset.clause = String(i + 1);
      continue;
    }
    const { node, start, map } = unit;
    if (!map.length) continue;

    // Group the node's characters by clause, keeping full coverage so no
    // text is lost — separators between clauses stay unwrapped.
    const pieces: Array<{ a: number; b: number; clause: number }> = [];
    for (let k = 0; k < map.length; k++) {
      const clause = clauseAt(start + k);
      const at = map[k];
      const prev = pieces[pieces.length - 1];
      if (prev && prev.clause === clause && prev.b === at) prev.b = at + 1;
      else pieces.push({ a: at, b: at + 1, clause });
    }
    if (pieces.length === 1 && pieces[0].clause < 0) continue;

    const frag = document.createDocumentFragment();
    let cursor = 0;
    for (const piece of pieces) {
      if (piece.a > cursor) frag.append(node.data.slice(cursor, piece.a));
      const slice = node.data.slice(piece.a, piece.b);
      if (piece.clause < 0) {
        frag.append(slice);
      } else {
        const span = document.createElement('span');
        span.className = 'cf-clause';
        span.dataset.clause = String(piece.clause + 1);
        span.textContent = slice;
        frag.append(span);
      }
      cursor = piece.b;
    }
    if (cursor < node.data.length) frag.append(node.data.slice(cursor));
    node.replaceWith(frag);
  }
}

const COACH_PROMPT_INSTRUCTIONS = `I'm working on this competitive programming problem and want to think it
through with you. Coach me — don't just hand over the solution:

- Meet me where I am. If I share code, read it carefully first (even when it
  already works) and treat it as what I already understand — build from there
  instead of re-teaching it.
- Let me drive the reasoning. When something's off, nudge me with a question
  or counterexample rather than correcting me outright.
- Only walk through the full solution if I ask.`;

const CPP_TEMPLATE = `#include <bits/stdc++.h>

using namespace std;

void solve() {


}

int main() {
    int tc;

    cin >> tc;

    while (tc--) {
        solve();
    }
}
`;

/** Isolated from parent re-renders so MathJax DOM mutations are never disturbed. */
export const ProblemContent = memo(function ProblemContent({ html, problem }: { html: string; problem: Problem }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [coachCopied, setCoachCopied] = useState(false);
  const [nvimCopied, setNvimCopied] = useState(false);

  useEffect(() => {
    const el = contentRef.current;
    if (!el || !html) return;

    el.innerHTML = html;
    const columns = splitIntoColumns(el);
    // Both run before MathJax: variable spans must exist while the TeX is
    // still text, and clause splitting must not cut through math.
    wrapMathVariables(el);
    el.querySelectorAll<HTMLElement>('.input-specification > p').forEach(wrapClauses);

    // Formulas wider than the column they sit in get .mjx-scroll so they
    // scroll in place instead of stretching the page (see index.css).
    // Measured against the containing column, not the full width, or the
    // two-column layout would under-detect overflow. Re-checked on resize /
    // text-width changes / the column breakpoint via ResizeObserver.
    const markOverflowingMath = () => {
      el.querySelectorAll('mjx-container').forEach((c) => {
        c.classList.remove('mjx-scroll');
        const box = c.closest('.cf-col-main, .cf-col-side') ?? el;
        if (c.getBoundingClientRect().width > box.clientWidth) {
          c.classList.add('mjx-scroll');
        }
      });
    };
    let observer: ResizeObserver | undefined;

    if (window.MathJax) {
      if (window.MathJax.typesetClear) {
        window.MathJax.typesetClear([el]);
      }
      if (window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([el])
          .then(() => {
            markOverflowingMath();
            observer = new ResizeObserver(markOverflowingMath);
            // The columns break out past el's width, so their size can
            // change while el's does not — observe both.
            [el, ...columns].forEach((n) => observer!.observe(n));
          })
          .catch((err: unknown) => console.error('MathJax error', err));
      }
    }
    return () => observer?.disconnect();
  }, [html]);

  // Kick off the line map as soon as the statement is shown (not on hover):
  // cached problems come back instantly, first-time problems finish while
  // the opening paragraphs are being read. Failures just mean no hover
  // annotations — the statement itself is untouched.
  const [linemap, setLinemap] = useState<Linemap | null>(null);
  useEffect(() => {
    setLinemap(null);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let polls = 0;
    const load = async () => {
      try {
        const res = await fetchJson(
          `${API_BASE_URL}/api/linemap?contest_id=${problem.contestId}&index=${problem.index}`,
          { method: 'POST' },
        );
        if (cancelled) return;
        const lm = res.linemap;
        if (lm?.status === 'done' && lm.data) {
          setLinemap(lm.data);
        } else if (lm?.status === 'pending' && polls++ < 30) {
          // Someone holds the generation lock — poll until it lands. The
          // budget covers a cold generation (the model gets the statement,
          // every spec clause and every sample line), not just a handoff.
          timer = setTimeout(load, 4000);
        }
      } catch {
        /* optional decoration; stay silent */
      }
    };
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [problem.contestId, problem.index]);

  // Decorate the DOM once both the statement and the map are in. Pointing at
  // a sample value highlights the clause that defines it, every mention of
  // that variable across the whole statement, and its sibling values — and
  // each of those is itself a target for the reverse direction.
  useEffect(() => {
    const el = contentRef.current;
    if (!el || !linemap?.lines?.length) return;
    const spec = el.querySelector('.input-specification');
    const pre = el.querySelector<HTMLElement>('.sample-test .input pre');
    if (!spec || !pre) return;

    const paras = Array.from(spec.children).filter(
      (c): c is HTMLElement => c.tagName === 'P',
    );
    // The map was built against this same HTML; a paragraph-count mismatch
    // means the assumption broke somewhere — bail rather than mislabel.
    if (paras.length !== linemap.para_count) return;

    // Line elements: modern statements already have one <div> per line;
    // older raw-text <pre>s get wrapped the same way the server counted
    // them (trailing blanks dropped, interior blanks kept).
    let lineEls = Array.from(pre.children).filter(
      (c): c is HTMLElement => c.tagName === 'DIV',
    );
    if (!lineEls.length) {
      // textContent drops <br>s (old statements delimit lines with them) —
      // turn them into newlines first, as the server did when counting.
      pre.querySelectorAll('br').forEach((br) => br.replaceWith('\n'));
      const lines = (pre.textContent ?? '').split('\n').map((l) => l.trimEnd());
      while (lines.length && !lines[lines.length - 1]) lines.pop();
      pre.textContent = '';
      lineEls = lines.map((l) => {
        const d = document.createElement('div');
        d.textContent = l || ' ';
        pre.appendChild(d);
        return d;
      });
    }

    const norm = (s: string) => s.replace(/\s+/g, ' ').trim();

    /** The clause that defines a line, verified by text so a disagreement
     * between the server's split and ours falls back to the whole paragraph
     * instead of pointing at the wrong phrase. */
    const clauseOf = (m: LinemapLine, para: HTMLElement): Element[] => {
      if (m.clause && m.clause_text && para.dataset.clauses) {
        let ours: string[] = [];
        try {
          ours = JSON.parse(para.dataset.clauses);
        } catch {
          ours = [];
        }
        if (norm(ours[m.clause - 1] ?? '') === norm(m.clause_text)) {
          const spans = Array.from(
            para.querySelectorAll(`[data-clause="${m.clause}"]`),
          );
          if (spans.length) return spans;
        }
      }
      return [para];
    };

    // Individual values are a pointer-device affordance; on touch the whole
    // line stays the tap target, which is the only thing sized for a finger.
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    const cleanups: (() => void)[] = [];
    const mentionsOf = (base: string) =>
      Array.from(el.querySelectorAll(`.cf-tex[data-tex-base="${base}"]`));
    const tokensOf = (base: string) =>
      Array.from(el.querySelectorAll(`.cf-tok[data-tex-base="${base}"]`));

    type Info = { m: LinemapLine; clause: Element[]; gloss: HTMLElement };
    const info = new Map<HTMLElement, Info>();
    const linesOfClause = new Map<Element, HTMLElement[]>();

    for (const m of linemap.lines) {
      const lineEl = lineEls[m.line - 1];
      const para = paras[m.para - 1];
      if (!lineEl || !para) continue;

      if (finePointer && m.kind !== 'line' && m.vars.length) {
        // Rebuild the line as one span per value so each is its own target.
        const parts = (lineEl.textContent ?? '').split(/(\s+)/);
        lineEl.textContent = '';
        let nth = 0;
        for (const part of parts) {
          if (!part) continue;
          if (/^\s+$/.test(part)) {
            lineEl.append(part);
            continue;
          }
          const v = m.kind === 'array' ? m.vars[0] : m.vars[nth];
          const span = document.createElement('span');
          span.className = 'cf-tok';
          const base = v?.tex ? texBase(v.tex) : '';
          if (base) span.dataset.texBase = base;
          if (v) span.dataset.gloss = `${v.tex} = ${part}${v.text ? ` — ${v.text}` : ''}`;
          span.textContent = part;
          lineEl.append(span);
          nth++;
        }
      }

      lineEl.classList.add('cf-line-mapped');
      const gloss = document.createElement('span');
      gloss.className = 'cf-line-gloss';
      gloss.textContent = m.text;
      lineEl.appendChild(gloss);

      const clause = clauseOf(m, para);
      info.set(lineEl, { m, clause, gloss });
      for (const c of clause) {
        linesOfClause.set(c, [...(linesOfClause.get(c) ?? []), lineEl]);
      }
      cleanups.push(() => {
        lineEl.classList.remove('cf-line-mapped');
        gloss.remove();
      });
    }

    const clear = () => {
      el.querySelectorAll('.cf-focus, .cf-hot, .cf-warm').forEach((n) =>
        n.classList.remove('cf-focus', 'cf-hot', 'cf-warm'),
      );
      info.forEach(({ m, gloss }) => { gloss.textContent = m.text; });
    };
    /** Three tiers, strongest last: `focus` is the one thing under the
     * cursor, `hot` is its counterpart (the defining clause, the matching
     * values), `warm` is where else that variable is mentioned. Variables
     * that merely sit inside a hot clause must not read as the focus. */
    const paint = (focus: Element[], hot: Element[], warm: Element[]) => {
      clear();
      warm.forEach((n) => n.classList.add('cf-warm'));
      hot.forEach((n) => {
        n.classList.remove('cf-warm');
        n.classList.add('cf-hot');
      });
      focus.forEach((n) => {
        n.classList.remove('cf-warm', 'cf-hot');
        n.classList.add('cf-focus');
      });
    };

    // One delegated listener rather than per-element pairs: moving between a
    // value and its line re-resolves the deepest target on every move, so
    // nested targets can't leave a stale highlight behind.
    const onOver = (ev: Event) => {
      const at = ev.target as Element | null;
      if (!at || !el.contains(at)) return clear();

      const lineEl = at.closest<HTMLElement>('.cf-line-mapped');
      const entry = lineEl ? info.get(lineEl) : undefined;
      const tok = at.closest<HTMLElement>('.cf-tok');

      if (tok && entry) {
        const base = tok.dataset.texBase ?? '';
        paint(
          [tok],
          // The line goes hot alongside the value: it carries the gloss
          // chip, which only shows on a hot line.
          [lineEl!, ...entry.clause],
          base ? [...mentionsOf(base), ...tokensOf(base)] : [],
        );
        if (tok.dataset.gloss) entry.gloss.textContent = tok.dataset.gloss;
        return;
      }
      if (entry) return paint([], [lineEl!, ...entry.clause], []);

      const tex = at.closest<HTMLElement>('.cf-tex');
      if (tex?.dataset.texBase) {
        const base = tex.dataset.texBase;
        return paint([tex], tokensOf(base), mentionsOf(base));
      }

      const clause = at.closest('[data-clause]');
      const para = at.closest<HTMLElement>('.input-specification > p');
      if (clause && para) {
        const key = clause.getAttribute('data-clause');
        const siblings = Array.from(
          para.querySelectorAll(`[data-clause="${key}"]`),
        );
        const lines = siblings.flatMap((s) => linesOfClause.get(s) ?? []);
        return paint([], [...siblings, ...new Set(lines)], []);
      }
      if (para) return paint([], [para, ...new Set(linesOfClause.get(para) ?? [])], []);
      clear();
    };

    el.addEventListener('mouseover', onOver);
    el.addEventListener('mouseleave', clear);
    cleanups.push(() => {
      el.removeEventListener('mouseover', onOver);
      el.removeEventListener('mouseleave', clear);
      clear();
    });

    return () => cleanups.forEach((fn) => fn());
  }, [html, linemap]);

  const copyMarkdown = async () => {
    const md = htmlToMarkdown(html, problem);
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyCoachPrompt = async () => {
    const md = htmlToMarkdown(html, problem);
    const prompt = `${COACH_PROMPT_INSTRUCTIONS}\n\n# Problem\n${md}\n\nLet's start: paste whatever code you've got and I'll work from it — otherwise, tell me how you're reading the problem.\n`;
    await navigator.clipboard.writeText(prompt);
    setCoachCopied(true);
    setTimeout(() => setCoachCopied(false), 2000);
  };

  // Seed the file with the template (only when it doesn't exist yet — never
  // clobber in-progress work), then open it. One paste starts the problem.
  const copyNvim = async () => {
    const file = `${problem.name}.cpp`;
    const cmd = `[ -s "${file}" ] || cat > "${file}" <<'CPP'\n${CPP_TEMPLATE}CPP\nnvim "${file}"`;
    await navigator.clipboard.writeText(cmd);
    setNvimCopied(true);
    setTimeout(() => setNvimCopied(false), 2000);
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
      {/* Problem Header Details — centered: badge row, then action row */}
      <div className="mb-6 pb-6 border-b border-slate-200 dark:border-slate-800 space-y-3">
        <div className="flex items-center justify-center gap-2 flex-wrap text-sm font-medium text-slate-500 dark:text-slate-400">
          <a
            href={`https://codeforces.com/problemset/problem/${problem.contestId}/${problem.index}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            {problem.contestId}{problem.index}
          </a>
          <a
            href={`https://codeforces.com/contest/${problem.contestId}/problem/${problem.index}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            contest
          </a>
          {problem.rating != null && (
            <span className={`px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 font-bold ${ratingColorClass(problem.rating)}`}>
              {problem.rating}
            </span>
          )}
        </div>
        <div className="flex items-center justify-center gap-2 flex-wrap">
            {problem.name && (
              <button
                onClick={copyNvim}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              >
                {nvimCopied ? <Check className="w-4 h-4 text-green-500" /> : <Terminal className="w-4 h-4" />}
                {nvimCopied ? 'Copied' : 'nvim'}
              </button>
            )}
            <button
              onClick={copyMarkdown}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
            >
              {copied ? <Check className="w-4 h-4 text-green-500" /> : <ClipboardCopy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Problem'}
            </button>
            <button
              onClick={copyCoachPrompt}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800/50 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50"
            >
              {coachCopied ? <Check className="w-4 h-4 text-green-500" /> : <GraduationCap className="w-4 h-4" />}
              {coachCopied ? 'Copied' : 'Coach'}
            </button>
        </div>
      </div>

      {/* Injected Codeforces HTML — managed via ref, not dangerouslySetInnerHTML */}
      <div
        ref={contentRef}
        className="problem-statement text-slate-800 dark:text-slate-200 transition-colors duration-200"
      />
    </div>
  );
});
