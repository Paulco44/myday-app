import { useState, useEffect, useMemo, useCallback } from "react";
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

const POINTER_SENSOR_OPTIONS = { activationConstraint: { distance: 3 } };

export function KanbanBoard() {
  const queryClient = useQueryClient();
  const { data: serverColumns, isLoading: isLoadingColumns } = useGetColumns();
  const { data: serverCards, isLoading: isLoadingCards } = useGetCards();

  const { mutate: updateCard } = useUpdateCard({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() }),
    },
  });

  const { mutate: updateColumn } = useUpdateColumn({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() }),
    },
  });

  const [columns, setColumns] = useState<Column[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [activeColumn, setActiveColumn] = useState<Column | null>(null);
  const [activeCard, setActiveCard] = useState<Card | null>(null);
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
    useSensor(PointerSensor, POINTER_SENSOR_OPTIONS),
    useSensor(KeyboardSensor)
  );

  // ── All useCallback hooks must be declared before any conditional return ──

  const onDragStart = useCallback((event: DragStartEvent) => {
    if (event.active.data.current?.type === "Column") {
      setActiveColumn(event.active.data.current.column);
    } else if (event.active.data.current?.type === "Card") {
      setActiveCard(event.active.data.current.card);
    }
  }, []);

  const onDragOver = useCallback((event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;
    if (activeId === overId) return;

    const isActiveACard = active.data.current?.type === "Card";
    const isOverACard = over.data.current?.type === "Card";
    const isOverAColumn = over.data.current?.type === "Column";

    if (!isActiveACard) return;

    if (isActiveACard && isOverACard) {
      setCards((prev) => {
        const activeIndex = prev.findIndex((t) => t.id === activeId);
        const overIndex = prev.findIndex((t) => t.id === overId);
        if (prev[activeIndex].columnId !== prev[overIndex].columnId) {
          const next = [...prev];
          next[activeIndex] = { ...next[activeIndex], columnId: prev[overIndex].columnId };
          return arrayMove(next, activeIndex, overIndex);
        }
        return arrayMove(prev, activeIndex, overIndex);
      });
    }

    if (isActiveACard && isOverAColumn) {
      setCards((prev) => {
        const activeIndex = prev.findIndex((t) => t.id === activeId);
        const next = [...prev];
        next[activeIndex] = { ...next[activeIndex], columnId: overId as number };
        return arrayMove(next, activeIndex, activeIndex);
      });
    }
  }, []);

  const onDragEnd = useCallback((event: DragEndEvent) => {
    setActiveColumn(null);
    setActiveCard(null);

    const { active, over } = event;
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;
    if (activeId === overId) return;

    if (active.data.current?.type === "Column") {
      setColumns((prev) => {
        const activeIndex = prev.findIndex((col) => col.id === activeId);
        const overIndex = prev.findIndex((col) => col.id === overId);
        const next = arrayMove(prev, activeIndex, overIndex);
        next.forEach((col, i) => { col.position = i; });
        updateColumn({ id: activeId as number, data: { position: overIndex } });
        return next;
      });
      return;
    }

    if (active.data.current?.type === "Card") {
      setCards((prev) => {
        const activeIndex = prev.findIndex((t) => t.id === activeId);
        const card = prev[activeIndex];
        if (card) {
          updateCard({ id: card.id, data: { columnId: card.columnId, position: activeIndex } });
        }
        return prev;
      });
    }
  }, [updateCard, updateColumn]);

  const handleCardClick = useCallback((card: Card) => setEditingCard(card), []);
  const handleEditClose = useCallback((open: boolean) => { if (!open) setEditingCard(null); }, []);

  // ── Conditional render after all hooks ──

  if (isLoadingColumns || isLoadingCards) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const highestColPos = columns.length > 0 ? Math.max(...columns.map(c => c.position)) : 0;

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
                onCardClick={handleCardClick}
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
                  onCardClick={handleCardClick}
                />
              )}
              {activeCard && <KanbanCard card={activeCard} onClick={handleCardClick} />}
            </DragOverlay>,
            document.body
          )}
        </DndContext>
      </div>

      <EditCardSheet
        card={editingCard}
        open={!!editingCard}
        onOpenChange={handleEditClose}
      />
    </>
  );
}
