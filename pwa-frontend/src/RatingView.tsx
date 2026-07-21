import { useEffect, useRef, useState } from 'react';
import { RefreshCw, AlertCircle, TrendingUp } from 'lucide-react';
import { API_BASE_URL } from './api';

type Participation = {
  contest_id: number;
  contest_name: string;
  participation_type: string;
  start_time: number;
};

type Perf = {
  contest_id: number;
  contest_name: string;
  points: number;
  penalty: number;
  rating: number;
  rank: number;
  delta: number | string;
  performance: number | string;
  participation_type: string;
  result_status: string;
  user_was_rated: boolean;
};

type SimPoint = {
  contest_id: number;
  contest_name: string;
  start_time: number;
  oldRating: number;
  newRating: number;
  delta: number;
};

type SimState =
  | { status: 'idle' }
  | { status: 'running'; done: number; total: number; points: SimPoint[] }
  | { status: 'done'; points: SimPoint[]; stale?: boolean }
  | { status: 'error'; message: string; points: SimPoint[] };

type RowState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; perf: Perf };

const PAGE_SIZE = 20;
const CONCURRENCY = 3;

// Codeforces rating tier colors (mirrors lib/colors.py)
function ratingColorClass(v: number | string): string {
  if (typeof v !== 'number') return 'text-slate-500 dark:text-slate-400';
  if (v < 1200) return 'text-slate-500 dark:text-slate-400';
  if (v < 1400) return 'text-green-600 dark:text-green-400';
  if (v < 1600) return 'text-cyan-600 dark:text-cyan-400';
  if (v < 1900) return 'text-blue-600 dark:text-blue-400';
  if (v < 2100) return 'text-fuchsia-600 dark:text-fuchsia-400';
  if (v < 2400) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

function deltaColorClass(d: number | string): string {
  if (typeof d !== 'number') return 'text-slate-500 dark:text-slate-400';
  if (d > 0) return 'text-green-600 dark:text-green-400';
  if (d < 0) return 'text-red-600 dark:text-red-400';
  return 'text-slate-500 dark:text-slate-400';
}

const TYPE_BADGE: Record<string, { label: string; cls: string }> = {
  contestant: {
    label: 'official',
    cls: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800/50',
  },
  virtual: {
    label: 'virtual',
    cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800/50',
  },
  out_of_competition: {
    label: 'unofficial',
    cls: 'bg-cyan-50 text-cyan-700 border-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-400 dark:border-cyan-800/50',
  },
};

// Finished-contest results are immutable — cache them client-side forever.
const CACHEABLE_STATUSES = new Set(['normal', 'unrated/old/unusual']);
const cacheKey = (handle: string, p: Participation) =>
  `perf:v1:${handle}:${p.contest_id}:${p.start_time}`;

// Codeforces "fake rating" adjustment for new accounts (mirrors scripts/whatif.py):
// displayed rating = real rating - ADJUSTMENT[min(ratedContests, 6)],
// with an internal starting rating of 1400.
const RATING_ADJUSTMENT = [1400, 900, 550, 300, 150, 50, 0];
const INITIAL_RATING = 1400;
const displayedRating = (real: number, nRated: number) =>
  real - RATING_ADJUSTMENT[Math.min(nRated, RATING_ADJUSTMENT.length - 1)];

const simSignature = (parts: Participation[]) =>
  parts.map(p => `${p.contest_id}:${p.start_time}`).join(',');
const simResultKey = (handle: string) => `whatifResult:v1:${handle}`;
// The step cache is keyed by the incoming simulated rating too: the delta for
// contest N depends on the rating carried out of contest N-1.
const simStepKey = (handle: string, p: Participation, ratingIn: number) =>
  `whatifStep:v1:${handle}:${p.contest_id}:${p.start_time}:${ratingIn}`;

function Sparkline({ points }: { points: SimPoint[] }) {
  if (points.length < 2) return null;
  const values = points.map(p => p.newRating);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 300;
  const H = 60;
  const PAD = 4;
  const coords = values.map((v, i) => {
    const x = PAD + (i * (W - 2 * PAD)) / (values.length - 1);
    const y = H - PAD - ((v - min) * (H - 2 * PAD)) / range;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-16" preserveAspectRatio="none">
        <polyline
          points={coords.join(' ')}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-blue-500"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="flex justify-between text-[10px] text-slate-400 dark:text-slate-500">
        <span>{new Date(points[0].start_time * 1000).toLocaleDateString()}</span>
        <span>
          {min} – {max}
        </span>
        <span>{new Date(points[points.length - 1].start_time * 1000).toLocaleDateString()}</span>
      </div>
    </div>
  );
}

export function RatingView({ handle, active }: { handle: string; active: boolean }) {
  const [parts, setParts] = useState<Participation[] | null>(null);
  const [officialRating, setOfficialRating] = useState<number | null>(null);
  const [rows, setRows] = useState<Record<number, RowState>>({});
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState('');
  const [sim, setSim] = useState<SimState>({ status: 'idle' });
  const startedRef = useRef(false);
  const queuedRef = useRef<Set<number>>(new Set());
  const simRunningRef = useRef(false);

  const fetchPerf = async (p: Participation) => {
    const key = cacheKey(handle, p);
    const cached = localStorage.getItem(key);
    if (cached) {
      try {
        const perf: Perf = JSON.parse(cached);
        setRows(prev => ({ ...prev, [p.contest_id]: { status: 'done', perf } }));
        return;
      } catch {
        localStorage.removeItem(key);
      }
    }
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/perf?handle=${handle}&contest_id=${p.contest_id}&start_time=${p.start_time}`
      );
      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || `Error: ${res.statusText}`);
      }
      const perf: Perf = await res.json();
      if (CACHEABLE_STATUSES.has(perf.result_status)) {
        try {
          localStorage.setItem(key, JSON.stringify(perf));
        } catch {
          // storage full — results just won't persist
        }
      }
      setRows(prev => ({ ...prev, [p.contest_id]: { status: 'done', perf } }));
    } catch (err) {
      setRows(prev => ({
        ...prev,
        [p.contest_id]: {
          status: 'error',
          message: err instanceof Error ? err.message : 'Failed',
        },
      }));
    }
  };

  const loadList = async () => {
    setListLoading(true);
    setListError('');
    setParts(null);
    setRows({});
    setVisible(PAGE_SIZE);
    queuedRef.current = new Set();
    try {
      const res = await fetch(`${API_BASE_URL}/api/participations?handle=${handle}`);
      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || `Error: ${res.statusText}`);
      }
      const data = await res.json();
      setParts(data.participations);
      setOfficialRating(data.official_rating ?? null);
      // Restore a previously computed simulation; flag it stale when the
      // participation list has changed since it ran.
      const stored = localStorage.getItem(simResultKey(handle));
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setSim({
            status: 'done',
            points: parsed.points,
            stale: parsed.signature !== simSignature(data.participations),
          });
        } catch {
          localStorage.removeItem(simResultKey(handle));
        }
      }
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Failed to load participations.');
    } finally {
      setListLoading(false);
    }
  };

  // Whatif chain (mirrors scripts/whatif.py): walk participations oldest to
  // newest, feeding each contest the simulated rating carried out of the
  // previous one. Sequential by necessity — each delta depends on the last.
  const runSimulation = async () => {
    if (!parts || parts.length === 0 || simRunningRef.current) return;
    simRunningRef.current = true;
    const ordered = [...parts].sort((a, b) => a.start_time - b.start_time);
    const points: SimPoint[] = [];
    let real = INITIAL_RATING;
    let nRated = 0;
    setSim({ status: 'running', done: 0, total: ordered.length, points: [] });
    try {
      for (let i = 0; i < ordered.length; i++) {
        const p = ordered[i];
        const stepKey = simStepKey(handle, p, real);
        let perf: Perf | null = null;
        const cached = localStorage.getItem(stepKey);
        if (cached) {
          try {
            perf = JSON.parse(cached);
          } catch {
            localStorage.removeItem(stepKey);
          }
        }
        if (!perf) {
          const res = await fetch(
            `${API_BASE_URL}/api/perf?handle=${handle}&contest_id=${p.contest_id}&start_time=${p.start_time}&rating=${real}`
          );
          if (!res.ok) {
            const errorData = await res.json().catch(() => null);
            throw new Error(errorData?.detail || `Error: ${res.statusText}`);
          }
          perf = (await res.json()) as Perf;
          if (CACHEABLE_STATUSES.has(perf.result_status)) {
            try {
              localStorage.setItem(stepKey, JSON.stringify(perf));
            } catch {
              // storage full — step just won't be cached
            }
          }
        }
        // Skip rules from scripts/whatif.py: zero-point runs, unknown deltas,
        // and official participations that weren't rated for the user.
        const applicable =
          typeof perf.delta === 'number' &&
          perf.points > 0 &&
          !(p.participation_type === 'contestant' && !perf.user_was_rated);
        if (applicable) {
          const dispOld = displayedRating(real, nRated);
          real += perf.delta as number;
          nRated += 1;
          const dispNew = displayedRating(real, nRated);
          points.push({
            contest_id: p.contest_id,
            contest_name: p.contest_name,
            start_time: p.start_time,
            oldRating: dispOld,
            newRating: dispNew,
            delta: dispNew - dispOld,
          });
        }
        setSim({ status: 'running', done: i + 1, total: ordered.length, points: [...points] });
      }
      setSim({ status: 'done', points });
      try {
        localStorage.setItem(
          simResultKey(handle),
          JSON.stringify({ signature: simSignature(parts), points })
        );
      } catch {
        // storage full
      }
    } catch (err) {
      setSim({
        status: 'error',
        message: err instanceof Error ? err.message : 'Simulation failed',
        points,
      });
    } finally {
      simRunningRef.current = false;
    }
  };

  // Load the list the first time the tab is opened.
  useEffect(() => {
    if (active && !startedRef.current) {
      startedRef.current = true;
      loadList();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  // Fetch perf for visible rows that haven't been queued yet.
  useEffect(() => {
    if (!parts) return;
    const targets = parts
      .slice(0, visible)
      .filter(p => !queuedRef.current.has(p.contest_id));
    if (targets.length === 0) return;
    targets.forEach(p => queuedRef.current.add(p.contest_id));
    setRows(prev => {
      const next = { ...prev };
      targets.forEach(p => {
        next[p.contest_id] = { status: 'loading' };
      });
      return next;
    });
    const queue = [...targets];
    const worker = async () => {
      for (;;) {
        const p = queue.shift();
        if (!p) return;
        await fetchPerf(p);
      }
    };
    for (let i = 0; i < CONCURRENCY; i++) worker();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parts, visible]);

  if (listLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-500 dark:text-slate-400 space-y-4 animate-pulse">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600 dark:text-blue-500" />
        <p className="text-lg">Loading participations...</p>
      </div>
    );
  }

  if (listError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-red-600 dark:text-red-400 space-y-3 bg-red-50 dark:bg-red-950/20 p-6 rounded-2xl border border-red-200 dark:border-red-900/50">
        <AlertCircle className="w-10 h-10" />
        <p className="text-center font-medium">{listError}</p>
        <button
          onClick={loadList}
          className="mt-4 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-900 dark:text-white rounded-lg transition-colors border border-slate-200 dark:border-slate-700"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (!parts) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-4">
        <TrendingUp className="w-16 h-16 opacity-20" />
        <p className="text-lg font-medium text-center text-slate-600 dark:text-slate-400">
          Contest performance
        </p>
      </div>
    );
  }

  const simPoints = sim.status === 'idle' ? [] : sim.points;
  const simFinal = simPoints.length > 0 ? simPoints[simPoints.length - 1].newRating : null;

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-24 space-y-3">
      <div className="flex items-center justify-between pb-1">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
          {parts.length} participations
        </p>
        <button
          onClick={loadList}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Rating summary */}
      <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs text-slate-400 dark:text-slate-500">official rating</p>
            <p className={`text-2xl font-bold ${ratingColorClass(officialRating ?? '—')}`}>
              {officialRating ?? '—'}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-400 dark:text-slate-500">
              if virtuals counted
              {sim.status === 'done' && sim.stale ? ' (outdated)' : ''}
            </p>
            <p
              className={`text-2xl font-bold ${
                simFinal !== null
                  ? ratingColorClass(simFinal)
                  : 'text-slate-300 dark:text-slate-600'
              }`}
            >
              {simFinal !== null ? simFinal : '?'}
            </p>
          </div>
        </div>

        {sim.status === 'running' ? (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
              <span className="flex items-center gap-1.5">
                <RefreshCw className="w-3 h-3 animate-spin" />
                simulating...
              </span>
              <span>
                {sim.done}/{sim.total}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${(sim.done / sim.total) * 100}%` }}
              />
            </div>
          </div>
        ) : (
          <button
            onClick={runSimulation}
            className="w-full py-2 text-sm font-medium rounded-lg border transition-colors bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800/50 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50"
          >
            {sim.status === 'done'
              ? sim.stale
                ? 'Re-simulate (new contests since last run)'
                : 'Re-simulate'
              : 'Simulate rating as if virtuals were rated'}
          </button>
        )}
        {sim.status === 'error' && (
          <p className="text-xs text-red-500 dark:text-red-400">{sim.message}</p>
        )}
        {simPoints.length > 1 && <Sparkline points={simPoints} />}
      </div>

      {parts.slice(0, visible).map(p => {
        const row = rows[p.contest_id];
        const badge = TYPE_BADGE[p.participation_type] ?? {
          label: p.participation_type,
          cls: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
        };
        return (
          <div
            key={`${p.contest_id}-${p.start_time}`}
            className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <a
                href={`https://codeforces.com/contest/${p.contest_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-slate-800 dark:text-slate-200 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
              >
                {p.contest_name}
              </a>
              <span className="text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap pt-0.5">
                {new Date(p.start_time * 1000).toLocaleDateString()}
              </span>
            </div>

            <div className="mt-3 flex items-center gap-2 flex-wrap text-sm">
              <span className={`px-2 py-0.5 text-xs rounded border ${badge.cls}`}>
                {badge.label}
              </span>

              {!row || row.status === 'loading' ? (
                <span className="flex items-center gap-1.5 text-slate-400 dark:text-slate-500 text-xs">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  calculating...
                </span>
              ) : row.status === 'error' ? (
                <span className="text-xs text-red-500 dark:text-red-400">{row.message}</span>
              ) : (
                <>
                  <span className="text-slate-500 dark:text-slate-400">
                    #{row.perf.rank}
                  </span>
                  <span className={`font-semibold ${deltaColorClass(row.perf.delta)}`}>
                    {typeof row.perf.delta === 'number'
                      ? (row.perf.delta > 0 ? `+${row.perf.delta}` : `${row.perf.delta}`)
                      : '—'}
                  </span>
                  <span className={`font-semibold ${ratingColorClass(row.perf.performance)}`}>
                    {typeof row.perf.performance === 'number'
                      ? `perf ${row.perf.performance}`
                      : 'perf —'}
                  </span>
                  {row.perf.result_status === 'unrated/old/unusual' && (
                    <span className="text-xs text-slate-400 dark:text-slate-500">unrated</span>
                  )}
                  {row.perf.result_status === 'just_ended' && (
                    <span className="text-xs text-slate-400 dark:text-slate-500">pending</span>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}

      {visible < parts.length && (
        <button
          onClick={() => setVisible(v => v + PAGE_SIZE)}
          className="w-full py-2.5 text-sm font-medium rounded-xl border transition-colors bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
        >
          Show {Math.min(PAGE_SIZE, parts.length - visible)} more ({parts.length - visible} remaining)
        </button>
      )}
    </div>
  );
}
