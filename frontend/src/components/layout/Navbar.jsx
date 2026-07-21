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
  { to: "/config", label: "Config" },
  { to: "/sandbox", label: "Sandbox" },
];

export default function Navbar() {
  const { connected } = useWebSocket();

  return (
    <header className="fixed left-0 right-0 top-0 z-50 h-16 border-b border-border/80 bg-white/90 px-4 shadow-sm shadow-slate-200/70 backdrop-blur md:px-6">
      <div className="mx-auto flex h-full max-w-[1440px] items-center">
        <div className="flex w-52 shrink-0 items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-sm font-black text-claude">
            AI
          </span>
          <span className="text-sm font-bold tracking-tight text-ink">Market Arena</span>
        </div>

        <nav className="flex flex-1 items-center justify-center gap-1 overflow-x-auto">
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                [
                  "whitespace-nowrap rounded-full px-3.5 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-soft-blue text-claude" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
                ].join(" ")
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex w-52 justify-end">
          <LiveBadge connected={connected} />
        </div>
      </div>
    </header>
  );
}
