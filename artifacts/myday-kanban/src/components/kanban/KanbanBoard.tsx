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
  UniqueIdentifier,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, horizontalListSortingStrategy } from "@dnd-kit/sortable";

import {
  useGetColumns,
  useGetCards,
  useUpdateCard,
  useUpdateColumn,
  getGetCardsQueryKey,
  getGetColumnsQueryKey,
} from "@workspace/api-client-react";
import type { Column, Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { KanbanColumn, toColDndId, fromColDndId } from "./KanbanColumn";
import { KanbanCard, toCardDndId, fromCardDndId } from "./KanbanCard";
import { KanbanColumnPreview } from "./KanbanColumnPreview";
import { KanbanCardPreview } from "./KanbanCardPreview";
import { CreateColumnDialog } from "./CreateColumnDialog";
import { EditCardSheet } from "./EditCardSheet";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

// Larger activation distance to distinguish intentional drags from clicks.
const POINTER_SENSOR_OPTIONS = { activationConstraint: { distance: 10 } };

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

  // Refs give callbacks stable access to the latest state (avoids stale closures).
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

  // columnsId uses NAMESPACED IDs matching what useSortable registers.
  const columnsId = useMemo(() => columns.map((col) => toColDndId(col.id)), [columns]);

  const sensors = useSensors(
    useSensor(PointerSensor, POINTER_SENSOR_OPTIONS),
    useSensor(KeyboardSensor)
  );

  // Custom collision detection:
  //   Columns → only consider other column droppables (cards are invisible to column drag).
  //   Cards   → pointer-within first (easy drop into empty columns), then rect-intersection.
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

    const pointerHits = pointerWithin(args);
    if (pointerHits.length > 0) return pointerHits;
    return rectIntersection(args);
  }, []);

  // ── All hooks before any conditional return ─────────────────────────────────

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
    if (active.id === over.id) return;

    // Only cards are rearranged during drag-over. Columns wait for drag-end.
    if (active.data.current?.type !== "Card") return;

    const activeNumId = fromCardDndId(active.id);
    const isOverACard = over.data.current?.type === "Card";
    const isOverAColumn = over.data.current?.type === "Column";

    if (isOverACard) {
      const overNumId = fromCardDndId(over.id);
      setCards((prev) => {
        const ai = prev.findIndex((t) => t.id === activeNumId);
        const oi = prev.findIndex((t) => t.id === overNumId);
        if (ai === -1 || oi === -1) return prev;

        let next = prev;
        if (prev[ai].columnId !== prev[oi].columnId) {
          next = prev.map((c, i) => (i === ai ? { ...c, columnId: prev[oi].columnId } : c));
        }
        const moved = arrayMove(next, ai, oi);
        cardsRef.current = moved;
        return moved;
      });
    }

    if (isOverAColumn) {
      const overColNumId = fromColDndId(over.id);
      setCards((prev) => {
        const ai = prev.findIndex((t) => t.id === activeNumId);
        if (ai === -1) return prev;
        if (prev[ai].columnId === overColNumId) return prev;
        const next = prev.map((c, i) => (i === ai ? { ...c, columnId: overColNumId } : c));
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
    if (active.id === over.id) return;

    // ── Column reorder ────────────────────────────────────────────────────────
    if (active.data.current?.type === "Column") {
      const prev = columnsRef.current;
      const activeNumId = fromColDndId(active.id);
      const overNumId = fromColDndId(over.id);
      const ai = prev.findIndex((c) => c.id === activeNumId);
      const oi = prev.findIndex((c) => c.id === overNumId);
      if (ai === -1 || oi === -1) return;

      const next: Column[] = arrayMove([...prev], ai, oi).map((col, i) => ({
        ...col,
        position: i,
      }));
      setColumns(next);
      columnsRef.current = next;

      // Only update columns whose position actually changed.
      const changed = next.filter((col, i) => prev[i]?.id !== col.id);
      if (changed.length === 0) return;

      let pending = changed.length;
      const onDone = () => {
        pending -= 1;
        if (pending === 0) queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() });
      };
      changed.forEach((col) =>
        updateColumn({ id: col.id, data: { position: col.position } }, { onSuccess: onDone, onError: onDone })
      );
      return;
    }

    // ── Card drop ─────────────────────────────────────────────────────────────
    if (active.data.current?.type === "Card") {
      const activeNumId = fromCardDndId(active.id);
      const current = cardsRef.current;
      const ai = current.findIndex((c) => c.id === activeNumId);
      if (ai === -1) return;
      const card = current[ai];
      updateCard(
        { id: card.id, data: { columnId: card.columnId, position: ai } },
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

          {/*
            DragOverlay uses PREVIEW components (no useSortable inside),
            eliminating duplicate draggable/droppable registrations that
            caused the wrong-object detection bug.
          */}
          <DragOverlay>
            {activeColumn && (
              <KanbanColumnPreview
                column={activeColumn}
                cards={cards.filter((c) => c.columnId === activeColumn.id)}
              />
            )}
            {activeCard && <KanbanCardPreview card={activeCard} />}
          </DragOverlay>
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
