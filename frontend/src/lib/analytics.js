const PLAUSIBLE_DOMAIN = import.meta.env.VITE_PLAUSIBLE_DOMAIN || "";
const PLAUSIBLE_SRC =
  import.meta.env.VITE_PLAUSIBLE_SRC ||
  "https://plausible.io/js/script.outbound-links.js";

let initialized = false;

export function initAnalytics() {
  if (!PLAUSIBLE_DOMAIN || typeof window === "undefined" || initialized) {
    return false;
  }

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
  initialized = true;
  return true;
}

export function trackEvent(name, options = {}) {
  if (!initialized || typeof window === "undefined" || !window.plausible) {
    return;
  }
  window.plausible(name, options);
}
