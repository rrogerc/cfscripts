import { useState, useEffect } from 'react';
import { RefreshCw, AlertCircle, BookOpen, Sun, Moon, Monitor, TrendingUp, Swords, Settings, X } from 'lucide-react';
import { API_BASE_URL } from './api';
import { ProblemContent, type Problem } from './ProblemContent';
import { RatingView } from './RatingView';
import { RankedView } from './RankedView';

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
        <div className="max-w-2xl mx-auto flex items-center justify-between">
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

      {/* Main Content Area — all views stay mounted so MathJax DOM, fetched
          rating rows, and the live match timer survive tab switches */}
      <main className="flex-1 w-full max-w-2xl mx-auto px-(--content-pad) py-4 sm:px-4 md:p-6 lg:py-8 pb-16 flex flex-col">
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
              {textWidth === 'cozy' && 'Bigger text with roomier margins.'}
              {textWidth === 'wide' && 'Balanced — slightly smaller text, trimmed margins.'}
              {textWidth === 'max' && 'Edge-to-edge with the smallest text.'}
              {' '}Affects phone screens.
            </p>
          </div>
        </div>
      )}

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
