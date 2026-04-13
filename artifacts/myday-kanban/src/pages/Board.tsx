import { KanbanBoard } from "@/components/kanban/KanbanBoard";
import { Navbar } from "@/components/layout/Navbar";

export function BoardPage() {
  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-background via-background to-secondary/30">
      {/* Background Hero Abstract Decoration */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none opacity-30">
        <img 
          src={`${import.meta.env.BASE_URL}images/hero-abstract.png`} 
          alt="" 
          className="w-full h-[60vh] object-cover mix-blend-multiply"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-background"></div>
      </div>
      
      <Navbar />
      
      <main className="flex-1 relative z-10 overflow-hidden flex flex-col">
        <div className="px-6 pt-8 pb-4 shrink-0">
          <h2 className="text-3xl font-display font-bold tracking-tight text-foreground">Kanban Board</h2>
          <p className="text-muted-foreground mt-1">Drag cards between columns — your external brain at a glance.</p>
        </div>
        
        <KanbanBoard />
      </main>
    </div>
  );
}
