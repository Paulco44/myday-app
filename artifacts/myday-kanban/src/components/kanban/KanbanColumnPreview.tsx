import type { Column, Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { KanbanCardPreview } from "./KanbanCardPreview";

interface KanbanColumnPreviewProps {
  column: Column;
  cards: Card[];
}

export function KanbanColumnPreview({ column, cards }: KanbanColumnPreviewProps) {
  return (
    <div className="shrink-0 w-[300px] flex flex-col bg-secondary/30 rounded-2xl border border-border/50 shadow-2xl opacity-95 rotate-1 max-h-[600px] overflow-hidden">
      <div className="p-4 flex items-center justify-between border-b border-border/40">
        <div className="flex items-center gap-2">
          <h3 className="font-display font-semibold text-foreground">{column.title}</h3>
          <span className="flex items-center justify-center bg-background border border-border/50 text-muted-foreground text-xs font-bold rounded-full w-5 h-5">
            {cards.length}
          </span>
        </div>
      </div>
      <div className="flex-1 overflow-hidden p-3">
        {cards.slice(0, 3).map((card) => (
          <KanbanCardPreview key={card.id} card={card} />
        ))}
        {cards.length > 3 && (
          <p className="text-xs text-muted-foreground text-center pt-1">
            +{cards.length - 3} more
          </p>
        )}
      </div>
    </div>
  );
}
