import { NavLink } from "react-router-dom";
import LiveBadge from "./LiveBadge";
import { useWebSocket } from "../../hooks/useWebSocket";

const NAV_LINKS = [
  { to: "/", label: "Arena" },
  { to: "/bots", label: "Bots" },
  { to: "/book", label: "Book" },
  { to: "/behavior", label: "Behavior" },
  { to: "/eval", label: "Eval" },
  { to: "/retrieval", label: "Retrieval" },
  { to: "/config", label: "Setup" },
];

export default function Navbar() {
  const { connected } = useWebSocket();

  return (
    <header className="fixed left-0 right-0 top-0 z-50 min-h-16 border-b border-border/80 bg-white/90 px-3 shadow-sm shadow-slate-200/70 backdrop-blur md:px-6">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-2 py-2 md:h-16 md:flex-nowrap md:gap-0 md:py-0">
        <div className="flex shrink-0 items-center gap-2 md:w-52">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-sm font-black text-claude">
            AI
          </span>
          <span className="hidden text-sm font-bold tracking-tight text-ink sm:inline">Market Arena</span>
        </div>

        <nav className="order-3 -mx-1 flex w-[calc(100%+0.5rem)] flex-1 items-center justify-start gap-1 overflow-x-auto px-1 pb-1 md:order-none md:mx-0 md:w-auto md:justify-center md:px-0 md:pb-0">
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm md:px-3.5 md:py-2",
                  isActive ? "bg-soft-blue text-claude" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
                ].join(" ")
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex justify-end sm:w-52">
          <LiveBadge connected={connected} />
        </div>
      </div>
    </header>
  );
}
