const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function apiFetch(path, options = {}) {
  try {
    const { headers = {}, ...requestOptions } = options;
    const res = await fetch(`${BASE}${path}`, {
      cache: "no-store",
      ...requestOptions,
      headers: { "Content-Type": "application/json", ...headers },
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
    return await res.json();
  } catch (err) {
    console.error(err);
    return null;
  }
}

export { BASE };
