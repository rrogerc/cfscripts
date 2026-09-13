// Vite proxies /api locally; production serves it on the same origin too.
// This also works from iOS Simulator without cross-origin requests.
export const API_BASE_URL = '';

export async function fetchJson(url: string, init?: RequestInit) {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      (typeof body?.detail === 'string' && body.detail) ||
      `Request failed (HTTP ${res.status}). Please try again.`
    );
  }
  return res.json();
}
