const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const RETRYABLE_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504]);
const GET_RETRY_DELAYS_MS = [0, 1000, 3000, 7000, 15000];

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function apiFetch(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const maxAttempts = method === "GET" ? GET_RETRY_DELAYS_MS.length : 1;
  let lastError = null;

  try {
    const { headers = {}, ...requestOptions } = options;
    const requestHeaders = requestOptions.body == null
      ? headers
      : { "Content-Type": "application/json", ...headers };

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      if (attempt > 0) await wait(GET_RETRY_DELAYS_MS[attempt]);

      try {
        const res = await fetch(`${BASE}${path}`, {
          cache: "no-store",
          ...requestOptions,
          headers: requestHeaders,
        });
        if (res.ok) return await res.json();

        const error = new Error(`API ${res.status}: ${path}`);
        error.status = res.status;
        if (!RETRYABLE_STATUSES.has(res.status)) throw error;
        lastError = error;
      } catch (err) {
        lastError = err;
        if (attempt === maxAttempts - 1 || (err.status && !RETRYABLE_STATUSES.has(err.status))) break;
      }
    }
  } catch (err) {
    lastError = err;
  }

  if (lastError) console.error(lastError);
  return null;
}

export { BASE };
