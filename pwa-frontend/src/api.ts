export const API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';

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
