export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg:          "#F8FAFC",
        panel:       "#FFFFFF",
        border:      "#E2E8F0",
        claude:      "#2563EB",
        gpt:         "#F97316",
        ink:         "#0F172A",
        muted:       "#64748B",
        "soft-blue": "#EFF6FF",
        "soft-orange": "#FFF7ED",
        "pnl-green": "#16A34A",
        "pnl-red":   "#DC2626",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
