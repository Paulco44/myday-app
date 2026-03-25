import { KanbanSquare } from "lucide-react";
import { Link } from "wouter";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-white/80 backdrop-blur-md shadow-sm shadow-black/5">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3 transition-transform hover:scale-[1.02] active:scale-95">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary/80 text-primary-foreground shadow-lg shadow-primary/20">
            <KanbanSquare className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold font-display leading-none text-foreground">MyDay</h1>
            <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">Kanban Flow</p>
          </div>
        </Link>
        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground bg-secondary/50 px-3 py-1.5 rounded-full border border-border/50">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            Workspace Connected
          </div>
        </div>
      </div>
    </header>
  );
}
