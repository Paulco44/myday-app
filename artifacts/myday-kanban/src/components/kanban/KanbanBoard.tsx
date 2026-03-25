import { useState, useEffect, useMemo } from "react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragOverEvent,
  DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { createPortal } from "react-dom";

import { useGetColumns, useGetCards, useUpdateCard, useUpdateColumn, getGetCardsQueryKey, getGetColumnsQueryKey } from "@workspace/api-client-react";
import type { Column, Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { KanbanColumn } from "./KanbanColumn";
import { KanbanCard } from "./KanbanCard";
import { CreateColumnDialog } from "./CreateColumnDialog";
import { EditCardSheet } from "./EditCardSheet";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

export function KanbanBoard() {
  const queryClient = useQueryClient();
  const { data: serverColumns, isLoading: isLoadingColumns } = useGetColumns();
  const { data: serverCards, isLoading: isLoadingCards } = useGetCards();
  
  const { mutate: updateCard } = useUpdateCard({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() })
    }
  });

  const { mutate: updateColumn } = useUpdateColumn({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() })
    }
  });

  const [columns, setColumns] = useState<Column[]>([]);
  const [cards, setCards] = useState<Card[]>([]);

  // Local state for dragging overlays
  const [activeColumn, setActiveColumn] = useState<Column | null>(null);
  const [activeCard, setActiveCard] = useState<Card | null>(null);

  // For the edit card sheet
  const [editingCard, setEditingCard] = useState<Card | null>(null);

  useEffect(() => {
    if (serverColumns) {
      setColumns([...serverColumns].sort((a, b) => a.position - b.position));
    }
  }, [serverColumns]);

  useEffect(() => {
    if (serverCards) {
      setCards([...serverCards].sort((a, b) => a.position - b.position));
    }
  }, [serverCards]);

  const columnsId = useMemo(() => columns.map((col) => col.id), [columns]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 3,
      },
    }),
    useSensor(KeyboardSensor)
  );

  if (isLoadingColumns || isLoadingCards) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const highestColPos = columns.length > 0 ? Math.max(...columns.map(c => c.position)) : 0;

  function onDragStart(event: DragStartEvent) {
    if (event.active.data.current?.type === "Column") {
      setActiveColumn(event.active.data.current.column);
      return;
    }
    if (event.active.data.current?.type === "Card") {
      setActiveCard(event.active.data.current.card);
      return;
    }
  }

  function onDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;

    if (activeId === overId) return;

    const isActiveACard = active.data.current?.type === "Card";
    const isOverACard = over.data.current?.type === "Card";
    const isOverAColumn = over.data.current?.type === "Column";

    if (!isActiveACard) return;

    // Moving card over another card
    if (isActiveACard && isOverACard) {
      setCards((cards) => {
        const activeIndex = cards.findIndex((t) => t.id === activeId);
        const overIndex = cards.findIndex((t) => t.id === overId);
        
        if (cards[activeIndex].columnId !== cards[overIndex].columnId) {
          const newCards = [...cards];
          newCards[activeIndex].columnId = cards[overIndex].columnId;
          return arrayMove(newCards, activeIndex, overIndex);
        }
        return arrayMove(cards, activeIndex, overIndex);
      });
    }

    // Moving card over an empty column
    if (isActiveACard && isOverAColumn) {
      setCards((cards) => {
        const activeIndex = cards.findIndex((t) => t.id === activeId);
        const newCards = [...cards];
        newCards[activeIndex].columnId = overId as number;
        return arrayMove(newCards, activeIndex, activeIndex);
      });
    }
  }

  function onDragEnd(event: DragEndEvent) {
    setActiveColumn(null);
    setActiveCard(null);

    const { active, over } = event;
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;

    if (activeId === overId) return;

    const isActiveColumn = active.data.current?.type === "Column";
    if (isActiveColumn) {
      setColumns((columns) => {
        const activeColumnIndex = columns.findIndex((col) => col.id === activeId);
        const overColumnIndex = columns.findIndex((col) => col.id === overId);
        const newColumns = arrayMove(columns, activeColumnIndex, overColumnIndex);
        
        // Optimistic update locally
        newColumns.forEach((col, index) => { col.position = index; });
        
        // Fire API request for the moved column
        updateColumn({
          id: activeId as number,
          data: { position: overColumnIndex }
        });
        
        return newColumns;
      });
      return;
    }

    const isActiveCard = active.data.current?.type === "Card";
    if (isActiveCard) {
      // Find the card in our local state (which was updated in onDragOver)
      const activeIndex = cards.findIndex((t) => t.id === activeId);
      const card = cards[activeIndex];
      
      if (card) {
        updateCard({
          id: card.id,
          data: {
            columnId: card.columnId,
            position: activeIndex, // using index as new position approximation
          }
        });
      }
    }
  }

  return (
    <>
      <div className="flex-1 flex overflow-x-auto overflow-y-hidden p-6 gap-6 items-start h-[calc(100vh-4rem)]">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={onDragStart}
          onDragOver={onDragOver}
          onDragEnd={onDragEnd}
        >
          <SortableContext items={columnsId} strategy={horizontalListSortingStrategy}>
            {columns.map((col) => (
              <KanbanColumn
                key={col.id}
                column={col}
                cards={cards.filter((c) => c.columnId === col.id)}
                onCardClick={(card) => setEditingCard(card)}
              />
            ))}
          </SortableContext>

          <CreateColumnDialog highestPosition={highestColPos} />

          {typeof document !== "undefined" && createPortal(
            <DragOverlay>
              {activeColumn && (
                <KanbanColumn
                  column={activeColumn}
                  cards={cards.filter((c) => c.columnId === activeColumn.id)}
                  onCardClick={() => {}}
                />
              )}
              {activeCard && <KanbanCard card={activeCard} onClick={() => {}} />}
            </DragOverlay>,
            document.body
          )}
        </DndContext>
      </div>

      <EditCardSheet 
        card={editingCard} 
        open={!!editingCard} 
        onOpenChange={(open) => !open && setEditingCard(null)} 
      />
    </>
  );
}
