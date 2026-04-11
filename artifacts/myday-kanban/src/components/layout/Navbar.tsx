import { Headphones, KanbanSquare } from "lucide-react";
import { Link } from "wouter";
import { useBrownNoise } from "@/hooks/useBrownNoise";
import { Button } from "@/components/ui/button";

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
  const { active: noiseActive, toggle: toggleNoise } = useBrownNoise();

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

        <div className="ml-auto flex items-center gap-2">
          {/* Brown noise toggle */}
          <Button
            variant={noiseActive ? "default" : "outline"}
            size="sm"
            onClick={toggleNoise}
            className={`h-8 gap-1.5 text-xs font-semibold transition-all ${
              noiseActive
                ? "bg-primary text-primary-foreground shadow-md shadow-primary/25"
                : "text-muted-foreground"
            }`}
            title="Toggle brown noise (focus sound)"
          >
            <Headphones className="w-3.5 h-3.5" />
            {noiseActive ? "Noise On" : "Noise"}
          </Button>

          {/* Bridge badge — honest about the link type */}
          <div className="hidden md:flex items-center gap-1.5 text-xs font-semibold text-primary bg-primary/10 px-2.5 py-1 rounded-lg border border-primary/25" title="Kanban cards can be linked to Task Manager tasks via the bridge">
            <span>↔</span>
            <span>Linked via Bridge</span>
          </div>
        </div>
      </div>
    </header>
  );
}
