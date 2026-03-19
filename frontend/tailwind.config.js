export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg:          "#0A0A0F",
        panel:       "#111118",
        border:      "#1E1E2E",
        claude:      "#3B82F6",
        gpt:         "#F97316",
        "pnl-green": "#22C55E",
        "pnl-red":   "#EF4444",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
