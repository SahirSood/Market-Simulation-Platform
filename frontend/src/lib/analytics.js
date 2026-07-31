const PLAUSIBLE_DOMAIN = import.meta.env.VITE_PLAUSIBLE_DOMAIN || "";
const PLAUSIBLE_SRC =
  import.meta.env.VITE_PLAUSIBLE_SRC ||
  "https://plausible.io/js/script.outbound-links.js";
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const FIRST_PARTY_ENABLED =
  (import.meta.env.VITE_SITE_ANALYTICS_ENABLED || "true").toLowerCase() !== "false";
const OWNER_OPT_OUT_KEY = "marketSimAnalyticsOwnerOptOut";

let initialized = false;
let outboundListenerAttached = false;
const VISIT_STARTED_KEY = "marketSimAnalyticsVisitStarted";
const LAST_PATH_KEY = "marketSimAnalyticsLastPath";

export function initAnalytics() {
  if (typeof window === "undefined" || initialized) {
    return false;
  }
  applyOwnerOptOutParam();
  if (isOwnerOptedOut()) {
    return false;
  }

  if (PLAUSIBLE_DOMAIN) {
    window.plausible =
      window.plausible ||
      function plausible() {
        window.plausible.q = window.plausible.q || [];
        window.plausible.q.push(arguments);
      };

    const script = document.createElement("script");
    script.defer = true;
    script.src = PLAUSIBLE_SRC;
    script.dataset.domain = PLAUSIBLE_DOMAIN;
    document.head.appendChild(script);
  }

  attachOutboundClickTracking();
  initialized = true;
  return true;
}

export function trackPageView(path) {
  if (isOwnerOptedOut()) {
    return;
  }
  const normalizedPath = path || window.location.pathname || "/";
  const visitStarted = getSessionFlag(VISIT_STARTED_KEY);
  const lastPath = getSessionValue(LAST_PATH_KEY);
  if (visitStarted && lastPath === normalizedPath) {
    return;
  }

  setSessionValue(LAST_PATH_KEY, normalizedPath);
  if (!visitStarted) {
    setSessionValue(VISIT_STARTED_KEY, "true");
    recordFirstPartyEvent("pageview", { path: normalizedPath, metadata: { action: "visit_start" } });
    return;
  }

  recordFirstPartyEvent("route_view", { path: normalizedPath, metadata: { action: "route_view" } });
}

export function trackEvent(name, options = {}) {
  if (typeof window === "undefined" || !window.plausible) {
    return;
  }
  window.plausible(name, options);
}

function attachOutboundClickTracking() {
  if (outboundListenerAttached || typeof document === "undefined") {
    return;
  }
  document.addEventListener(
    "click",
    (event) => {
      const anchor = event.target?.closest?.("a[href]");
      if (!anchor) return;
      const target = new URL(anchor.href, window.location.href);
      if (target.origin === window.location.origin) return;
      recordFirstPartyEvent("outbound_click", {
        path: window.location.pathname,
        target_url: target.href,
      });
    },
    { capture: true }
  );
  outboundListenerAttached = true;
}

function recordFirstPartyEvent(eventType, overrides = {}) {
  if (!FIRST_PARTY_ENABLED || typeof window === "undefined") {
    return;
  }
  if (isOwnerOptedOut()) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const payload = {
    event_type: eventType,
    path: overrides.path || window.location.pathname || "/",
    url: window.location.href,
    title: document.title,
    referrer: document.referrer || null,
    utm_source: params.get("utm_source"),
    utm_medium: params.get("utm_medium"),
    utm_campaign: params.get("utm_campaign"),
    target_url: overrides.target_url || null,
    session_id: getSessionId(),
    metadata: overrides.metadata || {},
  };
  const body = JSON.stringify(payload);
  const endpoint = `${API_BASE}/analytics/event`;
  if (navigator.sendBeacon) {
    navigator.sendBeacon(endpoint, new Blob([body], { type: "text/plain" }));
    return;
  }
  fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {});
}

function getSessionId() {
  const key = "marketSimAnalyticsSessionId";
  try {
    const existing = window.sessionStorage.getItem(key);
    if (existing) return existing;
    const next =
      window.crypto?.randomUUID?.() ||
      `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    window.sessionStorage.setItem(key, next);
    return next;
  } catch {
    return null;
  }
}

function getSessionFlag(key) {
  return getSessionValue(key) === "true";
}

function getSessionValue(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function setSessionValue(key, value) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    return false;
  }
  return true;
}

function applyOwnerOptOutParam() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("analytics") !== "off") {
    return;
  }
  try {
    window.localStorage.setItem(OWNER_OPT_OUT_KEY, "true");
  } catch {
    return false;
  }
  return true;
}

function isOwnerOptedOut() {
  try {
    return window.localStorage.getItem(OWNER_OPT_OUT_KEY) === "true";
  } catch {
    return false;
  }
}
