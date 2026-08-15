export const API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';

export async function fetchJson(url: string, init?: RequestInit) {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Error: ${res.statusText}`);
  }
  return res.json();
}
