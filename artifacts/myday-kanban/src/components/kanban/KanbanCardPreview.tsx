import { CalendarIcon, AlignLeft, Flag, Maximize2, Link2 } from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import type { Card } from "@workspace/api-client-react/src/generated/api.schemas";

interface KanbanCardPreviewProps {
  card: Card;
  onFullEdit?: (e: React.MouseEvent) => void;
}

const priorityColors = {
  high: "bg-red-50 text-red-700 border-red-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-blue-50 text-blue-700 border-blue-200",
};

export function KanbanCardPreview({ card, onFullEdit }: KanbanCardPreviewProps) {
  const isOverdue = card.dueDate && new Date(card.dueDate) < new Date();

  return (
    <div className="mb-3 bg-card border border-border/60 rounded-xl p-4 shadow-sm hover:border-primary/40 hover:shadow-md transition-all duration-150 relative">

      {/* Expand to full-edit button — visible only on hover */}
      {onFullEdit && (
        <button
          type="button"
          onClick={onFullEdit}
          title="Open full edit"
          className="absolute top-2.5 right-2.5 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary focus:opacity-100 focus:outline-none"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
      )}

      <div className="flex items-start gap-2 mb-2 pr-6">
        <h4 className="font-medium text-sm text-foreground leading-tight line-clamp-2 flex-1">
          {card.title}
        </h4>
      </div>

      {(card.description || card.priority || card.dueDate || card.taskId) && (
        <div className="flex items-center flex-wrap gap-2 mt-3 pt-3 border-t border-border/40">
          {card.taskId && (
            <div className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md border bg-primary/10 text-primary border-primary/25">
              <Link2 className="w-3 h-3" />
              Task #{card.taskId}
            </div>
          )}
          {card.priority && (
            <div
              className={clsx(
                "flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md border uppercase tracking-wider",
                priorityColors[card.priority as keyof typeof priorityColors]
              )}
            >
              <Flag className="w-3 h-3" />
              {card.priority}
            </div>
          )}
          {card.dueDate && (
            <div
              className={clsx(
                "flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground",
                isOverdue &&
                  "bg-destructive/10 text-destructive border border-destructive/20"
              )}
            >
              <CalendarIcon className="w-3 h-3" />
              {format(new Date(card.dueDate), "MMM d")}
            </div>
          )}
          {card.description && (
            <div className="flex items-center text-muted-foreground ml-auto">
              <AlignLeft className="w-4 h-4" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
