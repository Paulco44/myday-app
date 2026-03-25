import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { CalendarIcon, AlignLeft, Flag } from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import type { Card } from "@workspace/api-client-react/src/generated/api.schemas";

interface KanbanCardProps {
  card: Card;
  onClick: (card: Card) => void;
}

export function KanbanCard({ card, onClick }: KanbanCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: card.id,
    data: {
      type: "Card",
      card,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const priorityColors = {
    high: "bg-red-50 text-red-700 border-red-200",
    medium: "bg-amber-50 text-amber-700 border-amber-200",
    low: "bg-blue-50 text-blue-700 border-blue-200",
  };

  if (isDragging) {
    return (
      <div
        ref={setNodeRef}
        style={style}
        className="h-[120px] rounded-xl border-2 border-primary/50 border-dashed bg-primary/5 opacity-50 mb-3"
      />
    );
  }

  const isOverdue = card.dueDate && new Date(card.dueDate) < new Date();

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={() => onClick(card)}
      className="group cursor-grab active:cursor-grabbing mb-3 bg-card border border-border/60 rounded-xl p-4 shadow-sm hover:shadow-md transition-all hover:border-primary/20 hover:-translate-y-[1px]"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="font-medium text-sm text-foreground leading-tight line-clamp-2">
          {card.title}
        </h4>
      </div>

      {(card.description || card.priority || card.dueDate) && (
        <div className="flex items-center flex-wrap gap-2 mt-3 pt-3 border-t border-border/40">
          {card.priority && (
            <div className={clsx(
              "flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md border uppercase tracking-wider",
              priorityColors[card.priority as keyof typeof priorityColors]
            )}>
              <Flag className="w-3 h-3" />
              {card.priority}
            </div>
          )}

          {card.dueDate && (
            <div className={clsx(
              "flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground",
              isOverdue && "bg-destructive/10 text-destructive border border-destructive/20"
            )}>
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
