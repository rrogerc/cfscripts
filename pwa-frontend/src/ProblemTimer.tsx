import { useEffect, useState } from 'react';
import { Pause, Play, RotateCcw, Timer } from 'lucide-react';

const DURATION_MS = 25 * 60 * 1000;

type Clock = { remainingMs: number; deadline: number | null };

export function ProblemTimer() {
  const [clock, setClock] = useState<Clock>(() => ({
    remainingMs: DURATION_MS,
    deadline: Date.now() + DURATION_MS,
  }));
  const { remainingMs, deadline } = clock;
  const expired = remainingMs === 0;
  const paused = deadline === null && !expired;
  const seconds = Math.ceil(remainingMs / 1000);
  const time = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

  // Use a deadline so background-tab throttling and device sleep don't lose
  // time. Only this component re-renders on each tick, not the statement.
  useEffect(() => {
    if (deadline === null) return;
    const tick = () => {
      const remaining = Math.max(0, deadline - Date.now());
      setClock(current => current.deadline !== deadline ? current : {
        remainingMs: remaining,
        deadline: remaining > 0 ? deadline : null,
      });
    };
    const interval = setInterval(tick, 250);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [deadline]);

  const togglePause = () => {
    const now = Date.now();
    setClock(current => {
      if (current.remainingMs === 0) return current;
      return current.deadline === null
        ? { ...current, deadline: now + current.remainingMs }
        : { remainingMs: Math.max(0, current.deadline - now), deadline: null };
    });
  };

  const reset = () => setClock({
    remainingMs: DURATION_MS,
    deadline: Date.now() + DURATION_MS,
  });

  return (
    <section
      aria-label="Problem timer"
      className={`mx-auto mb-6 max-w-xl rounded-2xl border p-3 sm:px-4 transition-colors duration-300 motion-reduce:transition-none ${
        expired
          ? 'border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-400/40 dark:bg-amber-400/10 dark:text-amber-100'
          : 'border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-100'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p
            role="status"
            className={`mb-1 flex items-center gap-1.5 text-xs font-medium ${expired ? 'text-amber-700 dark:text-amber-300' : 'text-slate-500 dark:text-slate-400'}`}
          >
            <Timer aria-hidden="true" className="h-3.5 w-3.5" />
            {expired ? 'Time’s up' : paused ? 'Paused' : 'Focus timer'}
          </p>
          <span role="timer" aria-label="Time remaining" aria-live="off" className="font-mono text-3xl font-semibold tabular-nums tracking-tight">
            {time}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={togglePause}
            disabled={expired}
            aria-label={paused ? 'Resume timer' : 'Pause timer'}
            className="flex min-h-11 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            {paused ? <Play aria-hidden="true" className="h-4 w-4" /> : <Pause aria-hidden="true" className="h-4 w-4" />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button
            type="button"
            onClick={reset}
            aria-label="Reset timer to 25 minutes"
            title="Reset timer to 25 minutes"
            className={`flex h-11 w-11 items-center justify-center rounded-xl border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 ${
              expired
                ? 'border-amber-300 bg-amber-100 text-amber-800 hover:bg-amber-200 dark:border-amber-400/40 dark:bg-amber-400/15 dark:text-amber-200 dark:hover:bg-amber-400/25'
                : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
          >
            <RotateCcw aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      </div>
      {expired && (
        <p className="mt-3 border-t border-amber-200 pt-3 text-sm text-amber-800 dark:border-amber-400/20 dark:text-amber-200">
          25 minutes complete. Reset when you’re ready for another session.
        </p>
      )}
    </section>
  );
}
