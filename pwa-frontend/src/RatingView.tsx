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
};

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

export function RatingView({ handle, active }: { handle: string; active: boolean }) {
  const [parts, setParts] = useState<Participation[] | null>(null);
  const [rows, setRows] = useState<Record<number, RowState>>({});
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState('');
  const startedRef = useRef(false);
  const queuedRef = useRef<Set<number>>(new Set());

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
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Failed to load participations.');
    } finally {
      setListLoading(false);
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
