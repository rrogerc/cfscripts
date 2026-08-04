// Codeforces rating tier colors (mirrors lib/colors.py)
export function ratingColorClass(v: number | string): string {
  if (typeof v !== 'number') return 'text-slate-500 dark:text-slate-400';
  if (v < 1200) return 'text-slate-500 dark:text-slate-400';
  if (v < 1400) return 'text-green-600 dark:text-green-400';
  if (v < 1600) return 'text-cyan-600 dark:text-cyan-400';
  if (v < 1900) return 'text-blue-600 dark:text-blue-400';
  if (v < 2100) return 'text-fuchsia-600 dark:text-fuchsia-400';
  if (v < 2400) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

export function deltaColorClass(d: number | string): string {
  if (typeof d !== 'number') return 'text-slate-500 dark:text-slate-400';
  if (d > 0) return 'text-green-600 dark:text-green-400';
  if (d < 0) return 'text-red-600 dark:text-red-400';
  return 'text-slate-500 dark:text-slate-400';
}
