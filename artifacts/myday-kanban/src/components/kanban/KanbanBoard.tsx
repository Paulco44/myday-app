import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  DndContext,
  DragOverlay,
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
import { KanbanColumnPreview } from "./KanbanColumnPreview";
import { KanbanCardPreview } from "./KanbanCardPreview";
import { fromCardDndId } from "./KanbanCard";
import { CreateColumnDialog } from "./CreateColumnDialog";
import { EditCardSheet } from "./EditCardSheet";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

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

  const columnsId = useMemo(() => columns.map((col) => toColDndId(col.id)), [columns]);

  const sensors = useSensors(
    useSensor(PointerSensor, POINTER_SENSOR_OPTIONS)
  );

  // Columns → only match other column droppables.
  // Cards   → pointer-within first (easy empty-column entry), then rect-intersection.
  const collisionDetection: CollisionDetection = useCallback((args) => {
    if (args.active.data.current?.type === "Column") {
      return closestCenter({
        ...args,
        droppableContainers: args.droppableContainers.filter(
          (c) => c.data.current?.type === "Column"
        ),
      });
    }
    const hits = pointerWithin(args);
    return hits.length > 0 ? hits : rectIntersection(args);
  }, []);

  // ── All hooks before conditional return ────────────────────────────────────

  const onDragStart = useCallback((event: DragStartEvent) => {
    if (event.active.data.current?.type === "Column") {
      setActiveColumn(event.active.data.current.column);
    } else if (event.active.data.current?.type === "Card") {
      setActiveCard(event.active.data.current.card);
    }
  }, []);

  const onDragOver = useCallback((event: DragOverEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    if (active.data.current?.type !== "Card") return;

    const activeNumId = fromCardDndId(active.id);

    // Card → Card: only act when crossing a column boundary.
    // Same-column reordering is handled visually by verticalListSortingStrategy
    // via CSS transforms — no state update needed, which means no re-renders.
    if (over.data.current?.type === "Card") {
      const overNumId = fromCardDndId(over.id);
      setCards((prev) => {
        const ai = prev.findIndex((t) => t.id === activeNumId);
        const oi = prev.findIndex((t) => t.id === overNumId);
        if (ai === -1 || oi === -1) return prev;
        if (prev[ai].columnId === prev[oi].columnId) return prev; // same column — skip

        // Cross-column: move the card to the target column and insert at target card's slot.
        const withNewCol = prev.map((c, i) =>
          i === ai ? { ...c, columnId: prev[oi].columnId } : c
        );
        const newAi = withNewCol.findIndex((c) => c.id === activeNumId);
        const newOi = withNewCol.findIndex((c) => c.id === overNumId);
        const moved = arrayMove(withNewCol, newAi, newOi);
        cardsRef.current = moved;
        return moved;
      });
    }

    // Card → empty Column: move card into the column.
    if (over.data.current?.type === "Column") {
      const overColNumId = fromColDndId(over.id);
      setCards((prev) => {
        const ai = prev.findIndex((t) => t.id === activeNumId);
        if (ai === -1 || prev[ai].columnId === overColNumId) return prev;
        const next = prev.map((c, i) =>
          i === ai ? { ...c, columnId: overColNumId } : c
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
    if (active.id === over.id) return;

    // ── Column reorder ──────────────────────────────────────────────────────
    if (active.data.current?.type === "Column") {
      const prev = columnsRef.current;
      const ai = prev.findIndex((c) => c.id === fromColDndId(active.id));
      const oi = prev.findIndex((c) => c.id === fromColDndId(over.id));
      if (ai === -1 || oi === -1) return;

      const next: Column[] = arrayMove([...prev], ai, oi).map((col, i) => ({
        ...col,
        position: i,
      }));
      setColumns(next);
      columnsRef.current = next;

      const changed = next.filter((col, i) => prev[i]?.id !== col.id);
      if (changed.length === 0) return;

      let pending = changed.length;
      const onDone = () => {
        if (--pending === 0) {
          queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() });
        }
      };
      changed.forEach((col) =>
        updateColumn(
          { id: col.id, data: { position: col.position } },
          { onSuccess: onDone, onError: onDone }
        )
      );
      return;
    }

    // ── Card drop ───────────────────────────────────────────────────────────
    if (active.data.current?.type === "Card") {
      const activeNumId = fromCardDndId(active.id);
      let current = cardsRef.current;
      let ai = current.findIndex((c) => c.id === activeNumId);
      if (ai === -1) return;

      // Within-column reorder: onDragOver skipped this, so commit here.
      if (over.data.current?.type === "Card") {
        const overNumId = fromCardDndId(over.id);
        const oi = current.findIndex((c) => c.id === overNumId);
        if (oi !== -1 && ai !== oi && current[ai].columnId === current[oi].columnId) {
          const reordered = arrayMove([...current], ai, oi);
          setCards(reordered);
          cardsRef.current = reordered;
          current = reordered;
          ai = oi;
        }
      }

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

          {/* Preview components have no useSortable — no duplicate registrations */}
          <DragOverlay>
            {activeColumn && (
              <KanbanColumnPreview
                column={activeColumn}
                cards={cards.filter((c) => c.columnId === activeColumn.id)}
              />
            )}
            {activeCard && (
              <div className="rotate-2 scale-105 opacity-95 rounded-xl">
                <KanbanCardPreview card={activeCard} />
              </div>
            )}
          </DragOverlay>
        </DndContext>
      </div>

      <EditCardSheet
        key={editingCard?.id ?? "none"}
        card={editingCard}
        open={!!editingCard}
        onOpenChange={handleEditClose}
      />
    </>
  );
}
