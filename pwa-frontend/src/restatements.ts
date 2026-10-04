import { API_BASE_URL, fetchJson } from './api';

type ProblemId = { contestId: number; index: string };
type Entry = { source: string; promise: Promise<string>; html?: string };

const cache = new Map<string, Entry>();
const MAX_ENTRIES = 8;
const POLL_MS = 2000;
const MAX_POLLS = 150;
const keyFor = (problem: ProblemId) => `${problem.contestId}/${problem.index}`;

async function requestRestatement(problem: ProblemId, source: string): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source));
  const digest = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
  for (let polls = 0; ; polls++) {
    const data = await fetchJson(
      `${API_BASE_URL}/api/restate?contest_id=${problem.contestId}&index=${encodeURIComponent(problem.index)}`,
      { method: 'POST' },
    );
    const restatement = data.restatement;
    if (restatement?.status === 'done' && typeof restatement.html === 'string' && restatement.html) {
      if (restatement.statement_hash !== digest) {
        throw new Error('The original statement has changed. Reload the problem to simplify it.');
      }
      return restatement.html;
    }
    if (restatement?.status !== 'pending' || polls >= MAX_POLLS) {
      throw new Error('Simplification is taking longer than expected. Please try again.');
    }
    await new Promise(resolve => setTimeout(resolve, POLL_MS));
  }
}

/** Preloading and statement views share the same request, including polling. */
export function loadRestatement(problem: ProblemId, source: string): Promise<string> {
  const key = keyFor(problem);
  const cached = cache.get(key);
  if (cached?.source === source) return cached.promise;

  const entry: Entry = { source, promise: requestRestatement(problem, source) };
  cache.delete(key);
  cache.set(key, entry);
  if (cache.size > MAX_ENTRIES) {
    const oldest = cache.keys().next().value;
    if (oldest != null) cache.delete(oldest);
  }
  entry.promise.then(html => {
    entry.html = html;
  }, () => {
    // Failed preloads can retry, without deleting a newer source's request.
    if (cache.get(key) === entry) cache.delete(key);
  });
  return entry.promise;
}

/** A warmed result can be rendered on the first paint, without another fetch. */
export function cachedRestatement(problem: ProblemId, source: string): string | undefined {
  const entry = cache.get(keyFor(problem));
  return entry?.source === source ? entry.html : undefined;
}

export function preloadRestatement(problem: ProblemId, source: string): void {
  // Preloading is optional; errors belong to the view if the user opens it.
  void loadRestatement(problem, source).catch(() => {});
}
