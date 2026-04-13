import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Column, Card } from "@workspace/api-client-react/src/generated/api.schemas";
import type { Project } from "@/lib/projects";
import { KanbanCard, toCardDndId } from "./KanbanCard";
import { CreateCardDialog } from "./CreateCardDialog";
import { EditColumnDialog } from "./EditColumnDialog";

export const toColDndId = (id: number) => `col-${id}`;
export const fromColDndId = (dndId: string | number) =>
  Number(String(dndId).replace("col-", ""));

interface KanbanColumnProps {
  column: Column;
  cards: Card[];
  projects?: Project[];
  onCardClick: (card: Card) => void;
}

export function KanbanColumn({ column, cards, projects, onCardClick }: KanbanColumnProps) {
  const {
    setNodeRef,
    attributes,
    listeners,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: toColDndId(column.id),
    data: {
      type: "Column",
      column,
    },
  });

  const style = {
    transition,
    transform: CSS.Transform.toString(transform),
  };

  const highestCardPos = cards.length > 0 ? Math.max(...cards.map(c => c.position)) : 0;
  const cardDndIds = cards.map(c => toCardDndId(c.id));

  if (isDragging) {
    return (
      <div
        ref={setNodeRef}
        style={style}
        className="shrink-0 w-[300px] rounded-2xl bg-secondary/50 border-2 border-dashed border-primary/50 opacity-40 flex flex-col h-[500px]"
      />
    );
  }

  return (
    // setNodeRef AND listeners on the SAME outer element — no coordinate split.
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      tabIndex={-1}
      {...listeners}
      className="shrink-0 w-[300px] flex flex-col bg-secondary/30 rounded-2xl border border-border/50 shadow-sm max-h-full overflow-hidden touch-none select-none"
    >
      {/* Column header — visual grab area */}
      <div className="p-4 flex items-center justify-between cursor-grab active:cursor-grabbing hover:bg-secondary/50 transition-colors rounded-t-2xl border-b border-border/40">
        <div className="flex items-center gap-2 pointer-events-none">
          <h3 className="font-display font-semibold text-foreground">{column.title}</h3>
          <span className="flex items-center justify-center bg-background border border-border/50 text-muted-foreground text-xs font-bold rounded-full w-5 h-5">
            {cards.length}
          </span>
        </div>
        {/* Stop pointer events so the menu button doesn't start a column drag */}
        <div
          onPointerDown={(e) => e.stopPropagation()}
          className="cursor-default"
        >
          <EditColumnDialog column={column} />
        </div>
      </div>

      {/* Card list — stop propagation so cards don't trigger column drag */}
      <div
        onPointerDown={(e) => e.stopPropagation()}
        className="flex-1 overflow-y-auto overflow-x-hidden p-3 custom-scrollbar touch-auto select-auto"
      >
        <SortableContext items={cardDndIds} strategy={verticalListSortingStrategy}>
          <div className="flex flex-col min-h-[50px]">
            {cards.map((card) => (
              <KanbanCard key={card.id} card={card} projects={projects} onClick={onCardClick} />
            ))}
          </div>
        </SortableContext>
        <CreateCardDialog columnId={column.id} highestPosition={highestCardPos} />
      </div>
    </div>
  );
}
