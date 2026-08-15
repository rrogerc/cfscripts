import { useEffect, useRef, useState, memo } from 'react';
import { ArrowLeft, BookOpen, RefreshCw, AlertCircle } from 'lucide-react';
import { marked } from 'marked';
import { API_BASE_URL, fetchJson } from './api';
import { ProblemContent } from './ProblemContent';
import { ratingColorClass, deltaColorClass } from './colors';
import type { MatchRow } from './RankedView';

type Solution = {
  status: 'pending' | 'done';
  content_md: string | null;
  model: string | null;
};

const POLL_MS = 5_000;

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// The editorial is markdown with CF-style $$$...$$$ math. marked would mangle
// TeX (underscores → <em>, backslashes eaten), so math spans are swapped for
// placeholders before parsing and restored (HTML-escaped) after — MathJax then
// typesets them exactly like the statement's math.
function solutionHtml(md: string): string {
  // Models occasionally emit $$ where $$$ was meant; one mismatched delimiter
  // makes MathJax swallow paragraphs of prose as "math". Any run of 2+ dollars
  // can only be an intended delimiter, so snap them all to exactly three.
  const repaired = md.replace(/\${2,}/g, () => '$$$');
  const math: string[] = [];
  const shielded = repaired.replace(/\$\$\$[\s\S]*?\$\$\$/g, m => `@@MATH${math.push(m) - 1}@@`);
  const html = marked.parse(shielded, { async: false });
  return html.replace(/@@MATH(\d+)@@/g, (_, i) => escapeHtml(math[Number(i)]));
}

/** Isolated like ProblemContent so MathJax's DOM edits survive re-renders. */
const SolutionContent = memo(function SolutionContent({ md }: { md: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !md) return;
    el.innerHTML = solutionHtml(md);
    if (window.MathJax) {
      window.MathJax.typesetClear?.([el]);
      window.MathJax.typesetPromise?.([el]).catch((err: unknown) =>
        console.error('MathJax error', err)
      );
    }
  }, [md]);

  return (
    <div
      ref={ref}
      className="problem-statement solution-content text-slate-800 dark:text-slate-200"
    />
  );
});

export function MatchReview({
  handle,
  row,
  onBack,
}: {
  handle: string;
  row: MatchRow;
  onBack: () => void;
}) {
  const [html, setHtml] = useState('');
  const [error, setError] = useState('');
  const [solution, setSolution] = useState<Solution | null>(null);
  const [generating, setGenerating] = useState(false);
  const [solError, setSolError] = useState('');
  const pollRef = useRef<number | null>(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      if (pollRef.current != null) clearTimeout(pollRef.current);
    };
  }, []);

  const requestSolution = async () => {
    setGenerating(true);
    setSolError('');
    try {
      const data = await fetchJson(
        `${API_BASE_URL}/api/ranked/solution?handle=${handle}&match_id=${row.id}`,
        { method: 'POST' }
      );
      if (!aliveRef.current) return;
      setSolution(data.solution);
      if (data.solution?.status === 'done') {
        setGenerating(false);
      } else {
        // Another request holds the generation lock — keep asking. The POST
        // also adopts the lock if that generator died, so polling self-heals.
        pollRef.current = window.setTimeout(requestSolution, POLL_MS);
      }
    } catch (err) {
      if (!aliveRef.current) return;
      setSolError(err instanceof Error ? err.message : 'Failed to get the solution');
      setGenerating(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchJson(
          `${API_BASE_URL}/api/ranked/review?handle=${handle}&match_id=${row.id}`
        );
        if (cancelled) return;
        setHtml(data.html);
        setSolution(data.solution);
        // Someone is already generating (e.g. a previous visit here) — resume waiting.
        if (data.solution?.status === 'pending') requestSolution();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load the problem');
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handle, row.id]);

  const delta = Math.round(row.elo_after) - Math.round(row.elo_before);
  const resultLabel =
    row.result === 'win' ? 'Victory' : row.result === 'surrender' ? 'Surrendered' : 'Defeat';
  const resultCls =
    row.result === 'win'
      ? 'text-green-600 dark:text-green-400'
      : 'text-red-600 dark:text-red-400';

  return (
    <div className="pb-16">
      {/* Review header — mirrors the live match's sticky bar */}
      <div className="sticky top-[calc(env(safe-area-inset-top)+4.75rem)] z-[5] -mx-(--content-pad) px-(--content-pad) sm:-mx-4 sm:px-4 py-2 bg-slate-50/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 mb-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
          <div className="min-w-0 flex-1 text-center">
            <span className={`text-sm font-bold uppercase tracking-wide ${resultCls}`}>
              {resultLabel}
            </span>
            <span className="mx-2 text-slate-300 dark:text-slate-600">·</span>
            <span className={`text-sm font-bold ${deltaColorClass(delta)}`}>
              {delta >= 0 ? '+' : ''}{delta}
            </span>
          </div>
          <span className={`text-sm font-bold ${ratingColorClass(row.problem_rating)}`}>
            {row.problem_rating}
          </span>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400 mb-3">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {html ? (
        <ProblemContent
          html={html}
          problem={{
            contestId: row.contest_id,
            index: row.problem_index,
            name: row.problem_name,
            rating: row.problem_rating,
          }}
        />
      ) : !error ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500 dark:text-slate-400 space-y-3 animate-pulse">
          <RefreshCw className="w-6 h-6 animate-spin" />
          <p>Loading problem...</p>
        </div>
      ) : null}

      {/* Solution — behind a click so the statement alone never spoils it */}
      {html && (
        <div className="-mt-12 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 p-5">
          <div className="flex items-center gap-2 mb-1">
            <BookOpen className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Solution
            </h2>
          </div>

          {solution?.status === 'done' && solution.content_md ? (
            <SolutionContent md={solution.content_md} />
          ) : generating ? (
            <div className="flex flex-col items-center py-8 text-slate-500 dark:text-slate-400 space-y-3">
              <RefreshCw className="w-5 h-5 animate-spin" />
              <p className="text-sm">Writing the editorial… takes about a minute, first time only.</p>
            </div>
          ) : (
            <div className="flex flex-col items-center py-6 space-y-3">
              <button
                onClick={requestSolution}
                className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold rounded-xl transition-all"
              >
                <BookOpen className="w-4 h-4" />
                Reveal solution
              </button>
              {solError && (
                <p className="text-sm text-red-600 dark:text-red-400 text-center">{solError}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
