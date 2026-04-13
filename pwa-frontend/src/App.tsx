import { useState, useEffect, useRef } from 'react';
import { RefreshCw, AlertCircle, BookOpen, Sun, Moon } from 'lucide-react';

declare global {
  interface Window {
    MathJax: any;
  }
}

const API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';

function App() {
  const [level, setLevel] = useState<number>(15);
  const handle = 'tourist'; // Default handle for now
  const [problem, setProblem] = useState<any>(null);
  const [html, setHtml] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');

  const contentRef = useRef<HTMLDivElement>(null);

  // Initialize theme from localStorage or default to dark
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light' || savedTheme === 'dark') {
      setTheme(savedTheme);
    }
  }, []);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#0f172a');
    } else {
      document.documentElement.classList.remove('dark');
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '#ffffff');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
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

  // Re-render MathJax when HTML content changes
  useEffect(() => {
    if (html && contentRef.current && window.MathJax) {
      const renderMath = async () => {
        try {
          // Clear previous MathJax typesetting state just in case
          if (window.MathJax.typesetClear) {
            window.MathJax.typesetClear([contentRef.current]);
          }
          // Typeset the new injected HTML
          if (window.MathJax.typesetPromise) {
            await window.MathJax.typesetPromise([contentRef.current]);
          }
        } catch (err) {
          console.error('MathJax error', err);
        }
      };

      // Slight delay to guarantee React has flushed the innerHTML to the DOM
      const timeoutId = setTimeout(renderMath, 50);
      return () => clearTimeout(timeoutId);
    }
  }, [html]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-50 font-sans selection:bg-blue-500/30 transition-colors duration-200">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 p-4 shadow-sm transition-colors duration-200">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400">
            <BookOpen className="w-6 h-6" />
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">CF Picker</h1>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg px-2 py-1 border border-slate-200 dark:border-slate-700 focus-within:border-blue-500 transition-colors">
              <span className="text-slate-500 dark:text-slate-400 text-sm font-medium mr-2">Lvl</span>
              <select 
                value={level} 
                onChange={(e) => setLevel(Number(e.target.value))}
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
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-2xl mx-auto p-4 md:p-6 lg:py-8 flex flex-col">
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
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            {/* Problem Header Details */}
            <div className="mb-6 pb-6 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2 mb-2 text-sm font-medium text-slate-500 dark:text-slate-400">
                <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                  {problem.contestId}{problem.index}
                </span>
                <span className="px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded border border-blue-200 dark:border-blue-800/50">
                  Rating: {problem.rating}
                </span>
              </div>
            </div>

            {/* Injected Codeforces HTML */}
            <div 
              ref={contentRef}
              className="problem-statement text-slate-800 dark:text-slate-200 transition-colors duration-200" 
              dangerouslySetInnerHTML={{ __html: html }} 
            />
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-4">
            <BookOpen className="w-16 h-16 opacity-20" />
            <p className="text-lg font-medium text-center text-slate-600 dark:text-slate-400">Tap Pick to find a problem.</p>
            <p className="text-sm text-center max-w-sm opacity-60">Level {level} corresponds to rating {level * 100}. Adjust the level in the top right.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;