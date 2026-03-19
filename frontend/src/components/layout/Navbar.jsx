import { NavLink } from "react-router-dom";
import LiveBadge from "./LiveBadge";
import { useWebSocket } from "../../hooks/useWebSocket";

const NAV_LINKS = [
  { to: "/",        label: "Arena"   },
  { to: "/bots",    label: "Bots"    },
  { to: "/book",    label: "Book"    },
  { to: "/sandbox", label: "Sandbox" },
];

export default function Navbar() {
  const { connected } = useWebSocket();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-panel border-b border-border flex items-center px-6">
      {/* Logo */}
      <div className="flex items-center gap-2 w-56 shrink-0">
        <span className="text-lg">🤖</span>
        <span className="font-mono font-bold text-sm tracking-tight text-[#F1F5F9]">
          AI TRADING ARENA
        </span>
      </div>

      {/* Nav links — centered */}
      <nav className="flex-1 flex justify-center items-center gap-1">
        {NAV_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              [
                "px-4 py-1.5 text-sm font-medium transition-colors rounded-md",
                isActive
                  ? "text-claude border-b-2 border-claude"
                  : "text-[#64748B] hover:text-[#F1F5F9]",
              ].join(" ")
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Live badge — right */}
      <div className="w-56 flex justify-end">
        <LiveBadge connected={connected} />
      </div>
    </header>
  );
}
