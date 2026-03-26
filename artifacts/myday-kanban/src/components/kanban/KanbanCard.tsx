import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { KanbanCardPreview } from "./KanbanCardPreview";

export const toCardDndId = (id: number) => `card-${id}`;
export const fromCardDndId = (dndId: string | number) =>
  Number(String(dndId).replace("card-", ""));

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
    id: toCardDndId(card.id),
    data: {
      type: "Card",
      card,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  if (isDragging) {
    return (
      <div
        ref={setNodeRef}
        style={style}
        className="h-[80px] rounded-xl border-2 border-primary/50 border-dashed bg-primary/5 opacity-50 mb-3"
      />
    );
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={() => onClick(card)}
      className="cursor-grab active:cursor-grabbing touch-none"
    >
      <KanbanCardPreview card={card} />
    </div>
  );
}
