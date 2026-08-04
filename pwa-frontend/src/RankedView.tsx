import { useEffect, useRef, useState } from 'react';
import { Swords, Flag, RefreshCw, AlertCircle, Trophy, Skull } from 'lucide-react';
import { API_BASE_URL } from './api';
import { ProblemContent } from './ProblemContent';
import { Sparkline } from './RatingView';
import { ratingColorClass, deltaColorClass } from './colors';

type ActiveMatch = {
  id: number;
  contest_id: number;
  problem_index: string;
  problem_name: string;
  start_ts: number;
  deadline_ts: number;
};

type MatchRow = {
  id: number;
  contest_id: number;
  problem_index: string;
  problem_name: string;
  problem_rating: number;
  result: 'win' | 'loss' | 'surrender';
  elo_before: number;
  elo_after: number;
  start_ts: number;
  solved_ts: number | null;
};

type RankedStateData = {
  elo: number;
  seeded: boolean;
  wins: number;
  losses: number;
  server_now: number;
  active: ActiveMatch | null;
  history: MatchRow[];
};

const POLL_MS = 60_000;
const htmlKey = (handle: string, matchId: number) => `rankedHtml:v1:${handle}:${matchId}`;

const nowSec = () => Math.floor(Date.now() / 1000);

function fmtClock(sec: number): string {
  const s = Math.max(0, sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

async function fetchJson(url: string, init?: RequestInit) {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error: ${res.statusText}`);
  }
  return res.json();
}

const RESULT_STYLE: Record<MatchRow['result'], { label: string; banner: string; cls: string }> = {
  win: { label: 'W', banner: 'VICTORY', cls: 'text-green-600 dark:text-green-400' },
  loss: { label: 'L', banner: 'DEFEAT', cls: 'text-red-600 dark:text-red-400' },
  surrender: { label: 'L', banner: 'SURRENDERED', cls: 'text-slate-500 dark:text-slate-400' },
};

export function RankedView({ handle, active }: { handle: string; active: boolean }) {
  const [data, setData] = useState<RankedStateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [html, setHtml] = useState('');
  const [postMatch, setPostMatch] = useState<MatchRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmSurrender, setConfirmSurrender] = useState(false);
  const [now, setNow] = useState(nowSec());

  const loadedRef = useRef(false);
  const activeIdRef = useRef<number | null>(null);
  const skewRef = useRef(0);
  const fetchingRef = useRef(false);

  // Detect a match that resolved server-side: the id we were tracking is no
  // longer active, so its finalized row (rating now revealed) is in history.
  const applyState = (next: RankedStateData) => {
    skewRef.current = next.server_now - nowSec();
    const prevId = activeIdRef.current;
    if (prevId != null && next.active?.id !== prevId) {
      const row = next.history.find(r => r.id === prevId);
      if (row) setPostMatch(row);
      localStorage.removeItem(htmlKey(handle, prevId));
      setHtml('');
    }
    activeIdRef.current = next.active?.id ?? null;
    setData(next);
  };

  const loadState = async (initial = false) => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    if (initial) setLoading(true);
    try {
      const state: RankedStateData = await fetchJson(
        `${API_BASE_URL}/api/ranked/state?handle=${handle}`
      );
      applyState(state);
      setError('');
      if (state.active) {
        const cached = localStorage.getItem(htmlKey(handle, state.active.id));
        if (cached) {
          setHtml(cached);
        } else {
          const prob = await fetchJson(`${API_BASE_URL}/api/ranked/problem?handle=${handle}`);
          try {
            localStorage.setItem(htmlKey(handle, prob.match_id), prob.html);
          } catch { /* statement too big for the quota — refetch next time */ }
          setHtml(prob.html);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load ranked state');
    } finally {
      fetchingRef.current = false;
      setLoading(false);
    }
  };

  // Lazy-load on first tab activation; refresh on later activations.
  useEffect(() => {
    if (!active) return;
    if (!loadedRef.current) {
      loadedRef.current = true;
      loadState(true);
    } else {
      loadState();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  // 1s clock while a match is live.
  const activeMatch = data?.active ?? null;
  useEffect(() => {
    if (!activeMatch) return;
    const t = setInterval(() => setNow(nowSec()), 1000);
    return () => clearInterval(t);
  }, [activeMatch]);

  // Poll for the AC while live and visible; also on tab refocus.
  useEffect(() => {
    if (!activeMatch || !active) return;
    const poll = () => { if (!document.hidden) loadState(); };
    const t = setInterval(poll, POLL_MS);
    const onVisible = () => { if (!document.hidden) loadState(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMatch?.id, active]);

  const remaining = activeMatch ? activeMatch.deadline_ts - (now + skewRef.current) : 0;

  // The moment the clock crosses zero, ask the server for the verdict
  // (grace period so a last-second AC has landed in the submissions API).
  useEffect(() => {
    if (!activeMatch || remaining > 0) return;
    const t = setTimeout(() => loadState(), 1500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMatch?.id, remaining <= 0]);

  const queueUp = async () => {
    setBusy(true);
    setError('');
    setPostMatch(null);
    try {
      const state = await fetchJson(
        `${API_BASE_URL}/api/ranked/queue?handle=${handle}`,
        { method: 'POST' }
      );
      const { html: statementHtml, ...rest } = state;
      applyState(rest);
      if (rest.active && statementHtml) {
        try {
          localStorage.setItem(htmlKey(handle, rest.active.id), statementHtml);
        } catch { /* quota */ }
        setHtml(statementHtml);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start match');
      loadState();
    } finally {
      setBusy(false);
    }
  };

  const surrender = async () => {
    if (!confirmSurrender) {
      setConfirmSurrender(true);
      setTimeout(() => setConfirmSurrender(false), 3000);
      return;
    }
    setConfirmSurrender(false);
    setBusy(true);
    try {
      const state = await fetchJson(
        `${API_BASE_URL}/api/ranked/surrender?handle=${handle}`,
        { method: 'POST' }
      );
      applyState(state);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to surrender');
    } finally {
      setBusy(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-500 dark:text-slate-400 space-y-4 animate-pulse">
        <Swords className="w-8 h-8 text-blue-600 dark:text-blue-500" />
        <p className="text-lg">Loading ranked...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-red-600 dark:text-red-400 space-y-3 bg-red-50 dark:bg-red-950/20 p-6 rounded-2xl border border-red-200 dark:border-red-900/50">
        <AlertCircle className="w-10 h-10" />
        <p className="text-center font-medium">{error || 'Failed to load ranked state'}</p>
        <button
          onClick={() => loadState(true)}
          className="mt-4 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-900 dark:text-white rounded-lg transition-colors border border-slate-200 dark:border-slate-700"
        >
          Try Again
        </button>
      </div>
    );
  }

  // ---- Live match ----
  if (activeMatch) {
    const urgent = remaining <= 180;
    const warning = remaining <= 600;
    return (
      <div className="pb-16">
        {/* Timer bar — sticks below the app header */}
        <div className="sticky top-[calc(env(safe-area-inset-top)+4.75rem)] z-[5] -mx-4 px-4 py-2 bg-slate-50/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 mb-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Swords className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                Ranked match
              </span>
            </div>
            <span
              className={`font-mono text-2xl font-bold tabular-nums ${
                remaining <= 0
                  ? 'text-slate-400 dark:text-slate-500'
                  : urgent
                  ? 'text-red-600 dark:text-red-400 animate-pulse'
                  : warning
                  ? 'text-amber-600 dark:text-amber-400'
                  : 'text-slate-900 dark:text-white'
              }`}
            >
              {remaining <= 0 ? 'checking…' : fmtClock(remaining)}
            </span>
            <button
              onClick={surrender}
              disabled={busy}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors disabled:opacity-50 ${
                confirmSurrender
                  ? 'bg-red-600 border-red-600 text-white'
                  : 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900/50 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40'
              }`}
            >
              <Flag className="w-4 h-4" />
              {confirmSurrender ? 'Sure?' : 'FF'}
            </button>
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>
        )}

        {html ? (
          <ProblemContent
            html={html}
            problem={{ contestId: activeMatch.contest_id, index: activeMatch.problem_index }}
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-slate-500 dark:text-slate-400 space-y-3 animate-pulse">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <p>Loading problem...</p>
          </div>
        )}

        <p className="text-xs text-slate-400 dark:text-slate-500 text-center -mt-12">
          Submit on Codeforces as usual — your AC is detected automatically.
        </p>
      </div>
    );
  }

  // ---- Idle / post-match ----
  const history = data.history;
  const sparkPoints = [...history]
    .reverse()
    .map(r => ({ newRating: Math.round(r.elo_after), start_time: r.start_ts }));
  const total = data.wins + data.losses;

  return (
    <div className="pb-16 space-y-4">
      {postMatch && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 p-6 text-center space-y-3 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {postMatch.result === 'win' ? (
            <Trophy className="w-10 h-10 mx-auto text-amber-500" />
          ) : (
            <Skull className="w-10 h-10 mx-auto text-slate-400 dark:text-slate-500" />
          )}
          <p className={`text-3xl font-extrabold tracking-wide ${RESULT_STYLE[postMatch.result].cls}`}>
            {RESULT_STYLE[postMatch.result].banner}
          </p>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            <a
              href={`https://codeforces.com/problemset/problem/${postMatch.contest_id}/${postMatch.problem_index}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium hover:underline"
            >
              {postMatch.contest_id}{postMatch.problem_index} · {postMatch.problem_name}
            </a>{' '}
            was rated{' '}
            <span className={`font-bold ${ratingColorClass(postMatch.problem_rating)}`}>
              {postMatch.problem_rating}
            </span>
            {postMatch.result === 'win' && postMatch.solved_ts != null && (
              <> — solved in {fmtClock(postMatch.solved_ts - postMatch.start_ts)}</>
            )}
          </p>
          <p className="text-lg">
            <span className="text-slate-500 dark:text-slate-400">{Math.round(postMatch.elo_before)}</span>
            <span className="mx-2 text-slate-400">→</span>
            <span className={`font-bold ${ratingColorClass(Math.round(postMatch.elo_after))}`}>
              {Math.round(postMatch.elo_after)}
            </span>
            <span
              className={`ml-3 font-bold ${deltaColorClass(
                Math.round(postMatch.elo_after) - Math.round(postMatch.elo_before)
              )}`}
            >
              {Math.round(postMatch.elo_after) - Math.round(postMatch.elo_before) >= 0 ? '+' : ''}
              {Math.round(postMatch.elo_after) - Math.round(postMatch.elo_before)}
            </span>
          </p>
          <button
            onClick={() => setPostMatch(null)}
            className="px-4 py-2 text-sm font-medium bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg border border-slate-200 dark:border-slate-700 transition-colors"
          >
            Continue
          </button>
        </div>
      )}

      {/* Elo card */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 p-6 text-center space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
            Problem Elo
          </p>
          <p className={`text-5xl font-extrabold ${ratingColorClass(Math.round(data.elo))}`}>
            {Math.round(data.elo)}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
            {data.seeded
              ? 'Seeded from your CF rating — play a match to make it yours'
              : `${data.wins}W · ${data.losses}L${total > 0 ? ` · ${Math.round((100 * data.wins) / total)}%` : ''}`}
          </p>
        </div>

        {sparkPoints.length > 1 && <Sparkline points={sparkPoints} />}

        <button
          onClick={queueUp}
          disabled={busy}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold rounded-xl transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {busy ? (
            <>
              <RefreshCw className="w-5 h-5 animate-spin" />
              Finding your opponent...
            </>
          ) : (
            <>
              <Swords className="w-5 h-5" />
              Queue Up · 40:00
            </>
          )}
        </button>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          A hidden-rating problem near your elo. The clock starts the moment you see it —
          surrendering counts as a loss.
        </p>
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </div>

      {/* Match history */}
      {history.length > 0 && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 divide-y divide-slate-100 dark:divide-slate-800">
          {history.map(r => {
            const delta = Math.round(r.elo_after) - Math.round(r.elo_before);
            return (
              <div key={r.id} className="flex items-center gap-3 px-4 py-3">
                <span
                  className={`w-7 h-7 shrink-0 rounded-lg flex items-center justify-center text-sm font-bold ${
                    r.result === 'win'
                      ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400'
                      : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400'
                  }`}
                >
                  {RESULT_STYLE[r.result].label}
                </span>
                <div className="min-w-0 flex-1">
                  <a
                    href={`https://codeforces.com/problemset/problem/${r.contest_id}/${r.problem_index}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sm font-medium text-slate-800 dark:text-slate-200 truncate hover:underline"
                  >
                    {r.contest_id}{r.problem_index} · {r.problem_name}
                  </a>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    {new Date(r.start_ts * 1000).toLocaleDateString()}
                    {r.result === 'surrender' && ' · surrendered'}
                    {r.result === 'win' && r.solved_ts != null && ` · ${fmtClock(r.solved_ts - r.start_ts)}`}
                  </p>
                </div>
                <span className={`text-sm font-semibold ${ratingColorClass(r.problem_rating)}`}>
                  {r.problem_rating}
                </span>
                <span className={`text-sm font-bold w-10 text-right ${deltaColorClass(delta)}`}>
                  {delta >= 0 ? '+' : ''}{delta}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
