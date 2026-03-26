import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragOverEvent,
  DragEndEvent,
  CollisionDetection,
  closestCenter,
  pointerWithin,
  rectIntersection,
  getFirstCollision,
  UniqueIdentifier,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { createPortal } from "react-dom";

import {
  useGetColumns,
  useGetCards,
  useUpdateCard,
  useUpdateColumn,
  getGetCardsQueryKey,
  getGetColumnsQueryKey,
} from "@workspace/api-client-react";
import type { Column, Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { KanbanColumn } from "./KanbanColumn";
import { KanbanCard } from "./KanbanCard";
import { CreateColumnDialog } from "./CreateColumnDialog";
import { EditCardSheet } from "./EditCardSheet";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

const POINTER_SENSOR_OPTIONS = { activationConstraint: { distance: 8 } };

export function KanbanBoard() {
  const queryClient = useQueryClient();
  const { data: serverColumns, isLoading: isLoadingColumns } = useGetColumns();
  const { data: serverCards, isLoading: isLoadingCards } = useGetCards();

  const { mutate: updateCard } = useUpdateCard();
  const { mutate: updateColumn } = useUpdateColumn();

  const [columns, setColumns] = useState<Column[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [activeColumn, setActiveColumn] = useState<Column | null>(null);
  const [activeCard, setActiveCard] = useState<Card | null>(null);
  const [editingCard, setEditingCard] = useState<Card | null>(null);

  // Refs give callbacks stable access to the latest state without stale closures.
  const columnsRef = useRef<Column[]>([]);
  const cardsRef = useRef<Card[]>([]);

  useEffect(() => {
    if (serverColumns) {
      const sorted = [...serverColumns].sort((a, b) => a.position - b.position);
      setColumns(sorted);
      columnsRef.current = sorted;
    }
  }, [serverColumns]);

  useEffect(() => {
    if (serverCards) {
      const sorted = [...serverCards].sort((a, b) => a.position - b.position);
      setCards(sorted);
      cardsRef.current = sorted;
    }
  }, [serverCards]);

  const columnsId = useMemo(() => columns.map((col) => col.id), [columns]);

  const sensors = useSensors(
    useSensor(PointerSensor, POINTER_SENSOR_OPTIONS),
    useSensor(KeyboardSensor)
  );

  // Custom collision detection:
  //  - When dragging a COLUMN → only match against other column droppables (ignore cards).
  //  - When dragging a CARD  → use pointer-within first (so empty columns are easy to drop into),
  //    then fall back to closest center.
  const collisionDetection: CollisionDetection = useCallback((args) => {
    const activeType = args.active.data.current?.type;

    if (activeType === "Column") {
      return closestCenter({
        ...args,
        droppableContainers: args.droppableContainers.filter(
          (c) => c.data.current?.type === "Column"
        ),
      });
    }

    // For cards: try pointer-within first so we can enter empty columns easily.
    const pointerCollisions = pointerWithin(args);
    if (pointerCollisions.length > 0) {
      return pointerCollisions;
    }
    return rectIntersection(args);
  }, []);

  // ── Drag handlers — all declared before any conditional return ──────────────

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

    // Only handle card movements during drag-over; column sorting is done in onDragEnd.
    if (active.data.current?.type !== "Card") return;

    const isOverACard = over.data.current?.type === "Card";
    const isOverAColumn = over.data.current?.type === "Column";

    if (isOverACard) {
      setCards((prev) => {
        const activeIndex = prev.findIndex((t) => t.id === activeId);
        const overIndex = prev.findIndex((t) => t.id === overId);
        if (activeIndex === -1 || overIndex === -1) return prev;

        let next = prev;
        if (prev[activeIndex].columnId !== prev[overIndex].columnId) {
          next = prev.map((c, i) =>
            i === activeIndex ? { ...c, columnId: prev[overIndex].columnId } : c
          );
        }
        const moved = arrayMove(next, activeIndex, overIndex);
        cardsRef.current = moved;
        return moved;
      });
    }

    if (isOverAColumn) {
      setCards((prev) => {
        const activeIndex = prev.findIndex((t) => t.id === activeId);
        if (activeIndex === -1) return prev;
        // Only move if the card isn't already in this column.
        if (prev[activeIndex].columnId === (overId as number)) return prev;
        const next = prev.map((c, i) =>
          i === activeIndex ? { ...c, columnId: overId as number } : c
        );
        cardsRef.current = next;
        return next;
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

    // ── Column reorder ──────────────────────────────────────────────────────
    if (active.data.current?.type === "Column") {
      const prev = columnsRef.current;
      const activeIndex = prev.findIndex((c) => c.id === activeId);
      // overId must also be a column (our collision detection ensures this).
      const overIndex = prev.findIndex((c) => c.id === overId);
      if (activeIndex === -1 || overIndex === -1) return;

      const next: Column[] = arrayMove([...prev], activeIndex, overIndex).map(
        (col, i) => ({ ...col, position: i })
      );
      setColumns(next);
      columnsRef.current = next;

      // Persist all columns whose index changed.
      const changed = next.filter((col, i) => prev[i]?.id !== col.id);
      if (changed.length === 0) return;

      let pending = changed.length;
      const onDone = () => {
        pending -= 1;
        if (pending === 0) {
          queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() });
        }
      };
      changed.forEach((col) => {
        updateColumn(
          { id: col.id, data: { position: col.position } },
          { onSuccess: onDone, onError: onDone }
        );
      });
      return;
    }

    // ── Card drop ───────────────────────────────────────────────────────────
    if (active.data.current?.type === "Card") {
      const current = cardsRef.current;
      const activeIndex = current.findIndex((c) => c.id === activeId);
      if (activeIndex === -1) return;
      const card = current[activeIndex];

      updateCard(
        { id: card.id, data: { columnId: card.columnId, position: activeIndex } },
        { onSuccess: () => queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() }) }
      );
    }
  }, [updateCard, updateColumn, queryClient]);

  const handleCardClick = useCallback((card: Card) => setEditingCard(card), []);
  const handleEditClose = useCallback((open: boolean) => { if (!open) setEditingCard(null); }, []);

  // ── Conditional render after all hooks ──────────────────────────────────────

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
          collisionDetection={collisionDetection}
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
