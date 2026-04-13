import { useBrownNoise } from "@/hooks/useBrownNoise";

const TM_BASE = "/task-manager";

interface NavItem {
  label: string;
  href?: string;
  internal?: boolean;
  sep?: boolean;
}

const navItems: NavItem[] = [
  { label: "My Day",     href: `${TM_BASE}/my-day` },
  { label: "✦ Check In", href: `${TM_BASE}/morning-checkin` },
  { label: "Focus",      href: `${TM_BASE}/focus` },
  { sep: true, label: "" },
  { label: "Inbox",     href: `${TM_BASE}/inbox` },
  { label: "Meetings",  href: `${TM_BASE}/meetings` },
  { sep: true, label: "" },
  { label: "Kanban",    href: "/", internal: true },
  { label: "Tasks",     href: `${TM_BASE}/tasks-page` },
  { label: "Projects",  href: `${TM_BASE}/projects-list` },
  { label: "Notes",     href: `${TM_BASE}/notes` },
  { label: "Review",    href: `${TM_BASE}/weekly-review` },
  { label: "CoP Admin", href: `${TM_BASE}/cop-admin` },
];

export function Navbar() {
  const currentPath = typeof window !== "undefined" ? window.location.pathname : "/";
  const base = import.meta.env.BASE_URL?.replace(/\/$/, "") ?? "";
  const isKanban =
    currentPath === "/" ||
    currentPath === base ||
    currentPath === `${base}/`;

  const { active: noiseActive, toggle: toggleNoise } = useBrownNoise();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white">
      <div className="flex items-stretch h-[3.25rem] px-4 overflow-x-auto">
        <a
          href="/"
          className="flex items-center font-extrabold text-[1.1rem] tracking-tight text-indigo-600 shrink-0 mr-3 no-underline"
        >
          MyDay
        </a>

        <nav className="flex items-stretch flex-1 min-w-0">
          {navItems.map((item, i) => {
            if (item.sep) {
              return (
                <span
                  key={`sep-${i}`}
                  className="w-px bg-gray-200 mx-1 self-center h-4 shrink-0"
                />
              );
            }

            const isActive = item.internal
              ? isKanban
              : currentPath.startsWith(item.href ?? "__never__");

            if (item.internal) {
              return (
                <a
                  key={item.label}
                  href={item.href}
                  className={`h-full px-3 text-[.82rem] font-medium flex items-center border-b-2 whitespace-nowrap transition-colors shrink-0 ${
                    isActive
                      ? "text-indigo-600 border-indigo-600"
                      : "text-slate-500 border-transparent hover:text-slate-800"
                  }`}
                >
                  {item.label}
                </a>
              );
            }

            return (
              <a
                key={item.label}
                href={item.href}
                className={`h-full px-3 text-[.82rem] font-medium flex items-center border-b-2 whitespace-nowrap transition-colors shrink-0 ${
                  isActive
                    ? "text-indigo-600 border-indigo-600"
                    : "text-slate-500 border-transparent hover:text-slate-800"
                }`}
              >
                {item.label}
              </a>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2 shrink-0 pl-3">
          <button
            onClick={toggleNoise}
            className={`h-8 px-3 rounded text-xs font-semibold border transition-all ${
              noiseActive
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-slate-500 border-gray-300 hover:border-indigo-400 hover:text-indigo-600"
            }`}
            title="Toggle brown noise (focus sound)"
          >
            🎧 Noise
          </button>
        </div>
      </div>
    </header>
  );
}
