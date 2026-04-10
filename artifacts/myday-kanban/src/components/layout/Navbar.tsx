import { KanbanSquare } from "lucide-react";
import { Link } from "wouter";

const TM_BASE = "/task-manager";

const navLinks = [
  { label: "Kanban", href: "/", internal: true },
  { label: "My Day", href: `${TM_BASE}/my-day`, internal: false },
  { label: "Tasks", href: `${TM_BASE}/tasks-page`, internal: false },
  { label: "CoP Admin", href: `${TM_BASE}/cop-admin`, internal: false },
];

export function Navbar() {
  const currentPath = typeof window !== "undefined" ? window.location.pathname : "/";
  const isKanban = currentPath === "/" || currentPath === import.meta.env.BASE_URL?.replace(/\/$/, "");

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-white/80 backdrop-blur-md shadow-sm shadow-black/5">
      <div className="container mx-auto px-4 h-14 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2.5 shrink-0 transition-transform hover:scale-[1.02] active:scale-95">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary/80 text-primary-foreground shadow-md shadow-primary/20">
            <KanbanSquare className="w-4 h-4" />
          </div>
          <span className="text-lg font-bold font-display leading-none text-foreground">MyDay</span>
        </Link>

        <nav className="flex items-center gap-1">
          {navLinks.map(({ label, href, internal }) =>
            internal ? (
              <Link
                key={label}
                href={href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isKanban
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
              >
                {label}
              </Link>
            ) : (
              <a
                key={label}
                href={href}
                className="px-3 py-1.5 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              >
                {label}
              </a>
            )
          )}
        </nav>

        {/* ⚠ Separate-DB warning */}
        <div className="ml-auto hidden md:flex items-center gap-2 text-xs text-amber-700 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200">
          <span className="shrink-0">⚠️</span>
          <span>Este Kanban usa una BD separada — los cambios aquí <strong>no</strong> se reflejan en Task Manager.</span>
        </div>
      </div>
    </header>
  );
}
