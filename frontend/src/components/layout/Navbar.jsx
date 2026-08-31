import { NavLink } from "react-router-dom";
import LiveBadge from "./LiveBadge";
import { useWebSocket } from "../../hooks/useWebSocket";

const NAV_LINKS = [
  { to: "/", label: "Arena" },
  { to: "/brief", label: "Recap" },
  { to: "/research", label: "Research" },
];

export default function Navbar() {
  const { connected } = useWebSocket();

  return (
    <header className="fixed left-0 right-0 top-0 z-50 min-h-16 border-b border-border bg-white px-4 md:px-8">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-2 py-2 md:h-16 md:flex-nowrap md:gap-5 md:py-0">
        <div className="flex shrink-0 items-center gap-3 md:w-48">
          <span className="grid h-8 w-8 place-items-center rounded-md bg-ink text-[11px] font-bold tracking-tight text-white">
            MS
          </span>
          <div className="hidden leading-tight sm:block">
            <div className="text-sm font-semibold tracking-tight text-ink">MarketSim</div>
            <div className="text-[10px] text-slate-500">Focused trading arena</div>
          </div>
        </div>

        <nav aria-label="Primary" className="order-3 -mx-1 flex w-[calc(100%+0.5rem)] flex-1 items-center justify-start gap-1 overflow-x-auto px-1 pb-1 md:order-none md:mx-0 md:w-auto md:justify-center md:px-0 md:pb-0">
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "whitespace-nowrap border-b-2 px-2.5 py-2 text-xs font-medium transition-colors sm:text-sm",
                  isActive ? "border-ink text-ink" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-900",
                ].join(" ")
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex justify-end md:w-48">
          <LiveBadge connected={connected} />
        </div>
      </div>
    </header>
  );
}
