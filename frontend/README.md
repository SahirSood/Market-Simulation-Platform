# Frontend Dashboard

The frontend is a React, Vite, and Tailwind dashboard for the public read-only
arena. It focuses on comparing Claude and OpenAI bots on identical inputs while
showing the market mechanics and evidence behind each decision.

## Routes

- `/`: arena overview, leaderboard, telemetry, and model comparison.
- `/bots`: bot roster and per-bot detail drawer.
- `/book`: order book, depth, midpoint, and spread.
- `/behavior`: action mix, confidence, citations, fills, and portfolio traces.
- `/eval`: replay and evaluation results with export tools.
- `/retrieval`: RAG retrieval quality, cases, runs, and evidence inspection.
- `/config`: public-safe arena configuration.

## Local Commands

```powershell
cd frontend
npm ci
npm run dev
npm run build
```

Set `VITE_API_URL` when the API is not running at the default local address.
