export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg:          "#F4F5F7",
        panel:       "#FFFFFF",
        border:      "#D9DDE4",
        claude:      "#3157D5",
        gpt:         "#B95818",
        ink:         "#181C23",
        muted:       "#626A78",
        "soft-blue": "#F1F4FF",
        "soft-orange": "#FFF4EC",
        "pnl-green": "#087A55",
        "pnl-red":   "#BE3543",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
