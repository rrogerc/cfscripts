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

// Sample-input line map: which Input-spec paragraph describes each line of
// the first sample, plus a concrete value gloss ("n = 5 (array length)").
// Positions are 1-based and were computed against the same statement HTML,
// so they resolve directly against the rendered DOM.
type LinemapLine = { line: number; para: number; text: string };
type Linemap = { lines: LinemapLine[]; para_count: number };

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

    // Formulas wider than the statement column get .mjx-scroll so they
    // scroll in place instead of stretching the page (see index.css).
    // Re-checked on resize / text-width setting changes via ResizeObserver.
    const markOverflowingMath = () => {
      el.querySelectorAll('mjx-container').forEach((c) => {
        c.classList.remove('mjx-scroll');
        if (c.getBoundingClientRect().width > el.clientWidth) {
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
            observer.observe(el);
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
        } else if (lm?.status === 'pending' && polls++ < 8) {
          // Another client holds the generation lock — poll until it lands.
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

  // Decorate the DOM once both the statement and the map are in: hovering a
  // sample-input line highlights the Input-spec paragraph that defines it
  // (and vice versa) and reveals the line's value gloss.
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

    const byPara = new Map<number, HTMLElement[]>();
    const cleanups: (() => void)[] = [];
    const link = (hovered: HTMLElement, lines: HTMLElement[], para: HTMLElement) => {
      const on = () => {
        lines.forEach((l) => l.classList.add('cf-line-active'));
        para.classList.add('cf-spec-active');
      };
      const off = () => {
        lines.forEach((l) => l.classList.remove('cf-line-active'));
        para.classList.remove('cf-spec-active');
      };
      hovered.addEventListener('mouseenter', on);
      hovered.addEventListener('mouseleave', off);
      cleanups.push(() => {
        off();
        hovered.removeEventListener('mouseenter', on);
        hovered.removeEventListener('mouseleave', off);
      });
    };

    for (const m of linemap.lines) {
      const lineEl = lineEls[m.line - 1];
      const para = paras[m.para - 1];
      if (!lineEl || !para) continue;
      lineEl.classList.add('cf-line-mapped');
      const gloss = document.createElement('span');
      gloss.className = 'cf-line-gloss';
      gloss.textContent = m.text;
      lineEl.appendChild(gloss);
      cleanups.push(() => {
        lineEl.classList.remove('cf-line-mapped');
        gloss.remove();
      });
      link(lineEl, [lineEl], para);
      byPara.set(m.para, [...(byPara.get(m.para) ?? []), lineEl]);
    }
    byPara.forEach((lines, p) => link(paras[p - 1], lines, paras[p - 1]));

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
