import { useState, useEffect, useRef, memo } from 'react';
import { RefreshCw, AlertCircle, BookOpen, Sun, Moon, Monitor, ClipboardCopy, Check, GraduationCap, Code, TrendingUp } from 'lucide-react';
import TurndownService from 'turndown';
import { API_BASE_URL } from './api';
import { RatingView } from './RatingView';

declare global {
  interface Window {
    MathJax: any;
  }
}

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

function htmlToMarkdown(html: string, problem: any): string {
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

  // Prepend problem metadata
  const header = `**${problem.contestId}${problem.index}** | Rating: ${problem.rating}\n\n`;
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
const ProblemContent = memo(function ProblemContent({ html, problem }: { html: string; problem: any }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);
  const [coachCopied, setCoachCopied] = useState(false);
  const [templateCopied, setTemplateCopied] = useState(false);

  useEffect(() => {
    const el = contentRef.current;
    if (!el || !html) return;

    el.innerHTML = html;

    if (window.MathJax) {
      if (window.MathJax.typesetClear) {
        window.MathJax.typesetClear([el]);
      }
      if (window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([el]).catch((err: any) =>
          console.error('MathJax error', err)
        );
      }
    }
  }, [html]);

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

  const copyTemplate = async () => {
    await navigator.clipboard.writeText(CPP_TEMPLATE);
    setTemplateCopied(true);
    setTimeout(() => setTemplateCopied(false), 2000);
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
      {/* Problem Header Details */}
      <div className="mb-6 pb-6 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500 dark:text-slate-400">
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
            <span className="px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded border border-blue-200 dark:border-blue-800/50">
              Rating: {problem.rating}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={copyMarkdown}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
            >
              {copied ? <Check className="w-4 h-4 text-green-500" /> : <ClipboardCopy className="w-4 h-4" />}
              {copied ? 'Copied' : 'Problem'}
            </button>
            <button
              onClick={copyTemplate}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
            >
              {templateCopied ? <Check className="w-4 h-4 text-green-500" /> : <Code className="w-4 h-4" />}
              {templateCopied ? 'Copied' : 'Template'}
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
      </div>

      {/* Injected Codeforces HTML — managed via ref, not dangerouslySetInnerHTML */}
      <div
        ref={contentRef}
        className="problem-statement text-slate-800 dark:text-slate-200 transition-colors duration-200"
      />
    </div>
  );
});

function App() {
  const [level, setLevel] = useState<number>(() => {
    const saved = localStorage.getItem('level');
    return saved ? Number(saved) : 15;
  });
  const handle = 'Exonerate';
  const [tab, setTab] = useState<'pick' | 'rating'>('pick');
  const [problem, setProblem] = useState<any>(null);
  const [html, setHtml] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [theme, setTheme] = useState<'light' | 'dark' | 'auto'>(() => {
    const saved = localStorage.getItem('theme');
    return saved === 'light' || saved === 'dark' || saved === 'auto' ? saved : 'dark';
  });

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'auto' && media.matches);
      document.documentElement.classList.toggle('dark', dark);
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#0f172a' : '#ffffff');
    };
    apply();
    localStorage.setItem('theme', theme);
    if (theme === 'auto') {
      media.addEventListener('change', apply);
      return () => media.removeEventListener('change', apply);
    }
  }, [theme]);

  const cycleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : prev === 'dark' ? 'auto' : 'light');
  };

  const fetchProblem = async () => {
    setLoading(true);
    setError('');
    setProblem(null);
    setHtml('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/pick?handle=${handle}&level=${level}`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `Error: ${response.statusText}`);
      }
      const data = await response.json();
      setProblem(data.problem);
      setHtml(data.html);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch problem. Make sure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-50 font-sans selection:bg-blue-500/30 transition-colors duration-200">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 pt-[calc(env(safe-area-inset-top)+1rem)] pb-4 px-4 shadow-sm transition-colors duration-200">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
            <BookOpen className="w-6 h-6" />
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">CF Picker</h1>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={cycleTheme}
              className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label={`Theme: ${theme}`}
              title={`Theme: ${theme}`}
            >
              {theme === 'light' ? <Sun className="w-5 h-5" />
                : theme === 'dark' ? <Moon className="w-5 h-5" />
                : <Monitor className="w-5 h-5" />}
            </button>

            {tab === 'pick' && (
              <>
                <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg px-2 py-1 border border-slate-200 dark:border-slate-700 focus-within:border-blue-500 transition-colors">
                  <span className="text-slate-500 dark:text-slate-400 text-sm font-medium mr-2">Lvl</span>
                  <select
                    value={level}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setLevel(v);
                      localStorage.setItem('level', String(v));
                    }}
                    className="bg-transparent text-slate-900 dark:text-white font-semibold outline-none appearance-none cursor-pointer"
                  >
                    {Array.from({ length: 25 }, (_, i) => i + 8).map(l => (
                      <option key={l} value={l} className="bg-white dark:bg-slate-800 text-slate-900 dark:text-white">{l}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={fetchProblem}
                  disabled={loading}
                  className="bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white p-2 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium"
                >
                  <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                  <span className="hidden sm:inline">Pick</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area — both views stay mounted so MathJax DOM and
          fetched rating rows survive tab switches */}
      <main className="flex-1 w-full max-w-2xl mx-auto p-4 md:p-6 lg:py-8 pb-16 flex flex-col">
        <div className={tab === 'pick' ? 'flex-1 flex flex-col' : 'hidden'}>
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 dark:text-slate-400 space-y-4 animate-pulse">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-600 dark:text-blue-500" />
              <p className="text-lg">Finding a great problem...</p>
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center text-red-600 dark:text-red-400 space-y-3 bg-red-50 dark:bg-red-950/20 p-6 rounded-2xl border border-red-200 dark:border-red-900/50">
              <AlertCircle className="w-10 h-10" />
              <p className="text-center font-medium">{error}</p>
              <button onClick={fetchProblem} className="mt-4 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-900 dark:text-white rounded-lg transition-colors border border-slate-200 dark:border-slate-700">
                Try Again
              </button>
            </div>
          ) : html ? (
            <ProblemContent html={html} problem={problem} />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-4">
              <BookOpen className="w-16 h-16 opacity-20" />
              <p className="text-lg font-medium text-center text-slate-600 dark:text-slate-400">Tap Pick to find a problem.</p>
              <p className="text-sm text-center max-w-sm opacity-60">Level {level} corresponds to rating {level * 100}. Adjust the level in the top right.</p>
            </div>
          )}
        </div>
        <div className={tab === 'rating' ? 'flex-1 flex flex-col' : 'hidden'}>
          <RatingView handle={handle} active={tab === 'rating'} />
        </div>
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 inset-x-0 z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 pb-[env(safe-area-inset-bottom)] transition-colors duration-200">
        <div className="max-w-2xl mx-auto flex">
          <button
            onClick={() => setTab('pick')}
            className={`flex-1 py-2 flex flex-col items-center gap-0.5 transition-colors ${
              tab === 'pick'
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'
            }`}
          >
            <BookOpen className="w-5 h-5" />
            <span className="text-xs font-medium">Pick</span>
          </button>
          <button
            onClick={() => setTab('rating')}
            className={`flex-1 py-2 flex flex-col items-center gap-0.5 transition-colors ${
              tab === 'rating'
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'
            }`}
          >
            <TrendingUp className="w-5 h-5" />
            <span className="text-xs font-medium">Rating</span>
          </button>
        </div>
      </nav>
    </div>
  );
}

export default App;