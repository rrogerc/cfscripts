import { useState, useEffect, useRef } from 'react';
import { RefreshCw, AlertCircle, BookOpen, Sun, Moon, Monitor, TrendingUp, Swords, Settings, X, Minus, Plus, Timer } from 'lucide-react';
import { API_BASE_URL } from './api';
import { ratingColorClass } from './colors';
import { ProblemContent, type Problem } from './ProblemContent';
import { RatingView } from './RatingView';
import { RankedView } from './RankedView';

type PickData = { problem: Problem; html: string };

// One in-flight or completed /api/pick response. data: undefined while the
// request is in flight, null if it failed, otherwise ready to show.
type PrefetchEntry = {
  level: number;
  promise: Promise<PickData | null>;
  data?: PickData | null;
  ts: number;
};

const PREFETCH_STALE_MS = 60_000;

const MIN_LEVEL = 8;
const MAX_LEVEL = 32;
const LEVELS = Array.from({ length: MAX_LEVEL - MIN_LEVEL + 1 }, (_, i) => i + MIN_LEVEL);

function fmtElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`;
}

// Count-up clock for the current pick. Owns its own tick so the rest of the
// app doesn't re-render every second, and derives from wall-clock time so it
// stays right after the tab is backgrounded (intervals get throttled there).
function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const t = setInterval(tick, 1000);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(t);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [since]);
  return (
    <span
      className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 rounded-full px-3 py-1.5 border border-slate-200 dark:border-slate-700 font-mono text-sm font-semibold tabular-nums text-slate-700 dark:text-slate-200"
      title="Time on this problem"
    >
      <Timer className="w-4 h-4 text-slate-400 dark:text-slate-500" />
      {fmtElapsed(now - since)}
    </span>
  );
}

function App() {
  const [level, setLevel] = useState<number>(() => {
    const saved = localStorage.getItem('level');
    return saved ? Number(saved) : 15;
  });
  const handle = 'Exonerate';
  const [tab, setTab] = useState<'pick' | 'rating' | 'ranked'>('pick');
  const [problem, setProblem] = useState<Problem | null>(null);
  const [html, setHtml] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [theme, setTheme] = useState<'light' | 'dark' | 'auto'>(() => {
    const saved = localStorage.getItem('theme');
    return saved === 'light' || saved === 'dark' || saved === 'auto' ? saved : 'dark';
  });
  const [textWidth, setTextWidth] = useState<'cozy' | 'wide' | 'max'>(() => {
    const saved = localStorage.getItem('textWidth');
    return saved === 'cozy' || saved === 'wide' || saved === 'max' ? saved : 'wide';
  });
  const [settingsOpen, setSettingsOpen] = useState(false);

  // When the current pick was first shown. Keyed on problem identity rather
  // than on each fetch: /api/pick is deterministic, so "Pick again" returns
  // the same problem until it's solved — the clock keeps running through
  // that, and restarts only when a different problem comes back.
  const [startedAt, setStartedAt] = useState(0);
  const problemKey = problem ? `${problem.contestId}${problem.index}` : '';
  const lastKeyRef = useRef('');
  useEffect(() => {
    if (!problemKey || problemKey === lastKeyRef.current) return;
    lastKeyRef.current = problemKey;
    setStartedAt(Date.now());
  }, [problemKey]);

  useEffect(() => {
    document.documentElement.dataset.width = textWidth;
    localStorage.setItem('textWidth', textWidth);
  }, [textWidth]);

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

  const changeLevel = (v: number) => {
    const clamped = Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, v));
    setLevel(clamped);
    localStorage.setItem('level', String(clamped));
  };

  const requestPick = async (lvl: number): Promise<PickData> => {
    const response = await fetch(`${API_BASE_URL}/api/pick?handle=${handle}&level=${lvl}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.detail || `Error: ${response.statusText}`);
    }
    return response.json();
  };

  // Prefetch the pick so tapping the button renders instantly. Safe because
  // /api/pick is deterministic (newest unsolved problem at the level), so the
  // prefetched answer is exactly what a live fetch would return.
  const prefetchRef = useRef<PrefetchEntry | null>(null);

  const startPrefetch = (lvl: number) => {
    const entry: PrefetchEntry = {
      level: lvl,
      promise: requestPick(lvl).catch(() => null),
      ts: Date.now(),
    };
    entry.promise.then(d => { entry.data = d; });
    prefetchRef.current = entry;
  };

  // Warm on launch; re-warm when the level changes (debounced in case of
  // rapid cycling through the selector).
  useEffect(() => {
    const t = setTimeout(() => startPrefetch(level), prefetchRef.current ? 300 : 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [level]);

  // Refresh a stale prefetch when the app regains visibility — a problem
  // solved on Codeforces while away must not be re-served from the cache.
  useEffect(() => {
    const onVisible = () => {
      if (document.hidden) return;
      const entry = prefetchRef.current;
      if (!entry || entry.level !== level || Date.now() - entry.ts > PREFETCH_STALE_MS) {
        startPrefetch(level);
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [level]);

  const fetchProblem = async () => {
    setError('');

    const entry = prefetchRef.current;
    if (entry && entry.level === level) {
      if (entry.data) {
        // Prefetch already resolved — show it without any loading flash.
        setProblem(entry.data.problem);
        setHtml(entry.data.html);
        setLoading(false);
        return;
      }
      if (entry.data === undefined) {
        // Still in flight — wait for it instead of firing a duplicate.
        setLoading(true);
        setProblem(null);
        setHtml('');
        const data = await entry.promise;
        if (data) {
          setProblem(data.problem);
          setHtml(data.html);
          setLoading(false);
          return;
        }
        // Prefetch failed — fall through and refetch so the real error surfaces.
      }
    }

    setLoading(true);
    setProblem(null);
    setHtml('');
    try {
      const data = await requestPick(level);
      setProblem(data.problem);
      setHtml(data.html);
      prefetchRef.current = { level, promise: Promise.resolve(data), data, ts: Date.now() };
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch problem. Make sure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-50 font-sans selection:bg-blue-500/30 transition-colors duration-200">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 pt-[calc(env(safe-area-inset-top)+1rem)] pb-4 px-4 shadow-sm transition-colors duration-200">
        <div className="max-w-(--content-max) mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
            <BookOpen className="w-6 h-6" />
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">CF Picker</h1>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
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

          </div>
        </div>
      </header>

      {/* Main Content Area — all views stay mounted so MathJax DOM, fetched
          rating rows, and the live match timer survive tab switches */}
      <main className="flex-1 w-full max-w-(--content-max) mx-auto px-(--content-pad) py-4 sm:px-4 md:p-6 lg:py-8 pb-16 flex flex-col">
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
          ) : html && problem ? (
            <div>
              {/* Compact re-pick strip — centered, above the statement */}
              <div className="flex flex-wrap items-center justify-center gap-3 mb-5">
                <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-full px-3 py-1.5 border border-slate-200 dark:border-slate-700 focus-within:border-blue-500 transition-colors">
                  <span className="text-slate-500 dark:text-slate-400 text-sm font-medium mr-2">Lvl</span>
                  <select
                    value={level}
                    onChange={(e) => changeLevel(Number(e.target.value))}
                    className="bg-transparent text-slate-900 dark:text-white font-semibold outline-none appearance-none cursor-pointer"
                  >
                    {LEVELS.map(l => (
                      <option key={l} value={l} className="bg-white dark:bg-slate-800 text-slate-900 dark:text-white">{l}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={fetchProblem}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white transition-all disabled:opacity-50"
                >
                  <RefreshCw className="w-4 h-4" />
                  Pick again
                </button>
                {startedAt > 0 && <Elapsed since={startedAt} />}
              </div>
              <ProblemContent html={html} problem={problem} />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center py-8">
              <div className="w-full max-w-sm rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/50 p-8 text-center space-y-7 shadow-sm">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-widest text-slate-400 dark:text-slate-500">
                    Difficulty
                  </p>
                  <div className="flex items-center justify-center gap-5">
                    <button
                      onClick={() => changeLevel(level - 1)}
                      disabled={level <= MIN_LEVEL}
                      className="w-11 h-11 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition-colors flex items-center justify-center"
                      aria-label="Decrease level"
                    >
                      <Minus className="w-5 h-5" />
                    </button>
                    {/* The big number is a native select — tap it to jump levels */}
                    <select
                      value={level}
                      onChange={(e) => changeLevel(Number(e.target.value))}
                      className="appearance-none bg-transparent text-center text-6xl font-extrabold tabular-nums text-slate-900 dark:text-white outline-none cursor-pointer w-24"
                      aria-label="Level"
                    >
                      {LEVELS.map(l => (
                        <option key={l} value={l} className="bg-white dark:bg-slate-800 text-base font-normal text-slate-900 dark:text-white">{l}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => changeLevel(level + 1)}
                      disabled={level >= MAX_LEVEL}
                      className="w-11 h-11 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-30 transition-colors flex items-center justify-center"
                      aria-label="Increase level"
                    >
                      <Plus className="w-5 h-5" />
                    </button>
                  </div>
                  <p className={`text-sm font-bold ${ratingColorClass(level * 100)}`}>
                    {level * 100} rated
                  </p>
                </div>
                <button
                  onClick={fetchProblem}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:from-blue-700 active:to-indigo-700 text-white font-semibold rounded-xl transition-all"
                >
                  <BookOpen className="w-5 h-5" />
                  Pick a problem
                </button>
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  The newest unsolved Div. 2 problem at this rating.
                </p>
              </div>
            </div>
          )}
        </div>
        <div className={tab === 'rating' ? 'flex-1 flex flex-col' : 'hidden'}>
          <RatingView handle={handle} active={tab === 'rating'} />
        </div>
        <div className={tab === 'ranked' ? 'flex-1 flex flex-col' : 'hidden'}>
          <RankedView handle={handle} active={tab === 'ranked'} />
        </div>
      </main>

      {/* Settings sheet */}
      {settingsOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/40 flex items-end sm:items-center justify-center"
          onClick={() => setSettingsOpen(false)}
        >
          <div
            className="w-full sm:max-w-sm bg-white dark:bg-slate-800 rounded-t-2xl sm:rounded-2xl p-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] shadow-xl animate-in slide-in-from-bottom-4 duration-300"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">Settings</h2>
              <button
                onClick={() => setSettingsOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                aria-label="Close settings"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm font-medium text-slate-600 dark:text-slate-300 mb-2">Text width</p>
            <div className="grid grid-cols-3 gap-2 mb-2">
              {([
                { key: 'cozy', label: 'Cozy' },
                { key: 'wide', label: 'Wide' },
                { key: 'max', label: 'Max' },
              ] as const).map(opt => (
                <button
                  key={opt.key}
                  onClick={() => setTextWidth(opt.key)}
                  className={`py-2 text-sm font-medium rounded-lg border transition-colors ${
                    textWidth === opt.key
                      ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-slate-100 dark:bg-slate-700/50 border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {textWidth === 'cozy' && 'Narrow column; bigger text on phones.'}
              {textWidth === 'wide' && 'Balanced column width (default).'}
              {textWidth === 'max' && 'Widest column; edge-to-edge on phones.'}
            </p>
          </div>
        </div>
      )}

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 inset-x-0 z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 pb-[env(safe-area-inset-bottom)] transition-colors duration-200">
        <div className="max-w-(--content-max) mx-auto flex">
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
            onClick={() => setTab('ranked')}
            className={`flex-1 py-2 flex flex-col items-center gap-0.5 transition-colors ${
              tab === 'ranked'
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'
            }`}
          >
            <Swords className="w-5 h-5" />
            <span className="text-xs font-medium">Ranked</span>
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
