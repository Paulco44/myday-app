import { useState, useEffect } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Check, X } from "lucide-react";
import { useUpdateCard, getGetCardsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import type { Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { KanbanCardPreview } from "./KanbanCardPreview";

export const toCardDndId = (id: number) => `card-${id}`;
export const fromCardDndId = (dndId: string | number) =>
  Number(String(dndId).replace("card-", ""));

const formSchema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  priority: z.enum(["low", "medium", "high", "none"]).optional(),
  dueDate: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

interface KanbanCardProps {
  card: Card;
  onClick: (card: Card) => void;
}

export function KanbanCard({ card, onClick }: KanbanCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: card.title,
      description: card.description || "",
      priority: (card.priority as FormValues["priority"]) || "none",
      dueDate: card.dueDate
        ? new Date(card.dueDate).toISOString().split("T")[0]
        : "",
    },
  });

  useEffect(() => {
    if (!isEditing) {
      form.reset({
        title: card.title,
        description: card.description || "",
        priority: (card.priority as FormValues["priority"]) || "none",
        dueDate: card.dueDate
          ? new Date(card.dueDate).toISOString().split("T")[0]
          : "",
      });
    }
  }, [card.id, card.title, card.description, card.priority, card.dueDate, isEditing]);

  const { mutate: updateCard, isPending } = useUpdateCard({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() });
        setIsEditing(false);
      },
    },
  });

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: toCardDndId(card.id),
      data: { type: "Card", card },
      disabled: isEditing,
    });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  function onSubmit(values: FormValues) {
    updateCard({
      id: card.id,
      data: {
        title: values.title,
        description: values.description || null,
        priority:
          !values.priority || values.priority === "none"
            ? null
            : values.priority,
        dueDate: values.dueDate
          ? new Date(values.dueDate).toISOString()
          : null,
      },
    });
  }

  function handleCancel() {
    form.reset();
    setIsEditing(false);
  }

  function handleOpenFull(e: React.MouseEvent) {
    e.stopPropagation();
    setIsEditing(false);
    onClick(card);
  }

  if (isDragging) {
    return (
      <div
        ref={setNodeRef}
        style={style}
        className="h-[80px] rounded-xl border-2 border-primary/50 border-dashed bg-primary/5 opacity-50 mb-3"
      />
    );
  }

  if (isEditing) {
    return (
      <div ref={setNodeRef} style={style} className="mb-3">
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              handleCancel();
            }
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              form.handleSubmit(onSubmit)();
            }
          }}
          className="bg-card border-2 border-primary/50 rounded-xl p-3 shadow-lg space-y-2.5"
        >
          <input
            {...form.register("title")}
            autoFocus
            placeholder="Task title"
            className="w-full text-sm font-semibold bg-transparent border-0 outline-none placeholder:text-muted-foreground text-foreground leading-snug"
          />

          {form.formState.errors.title && (
            <p className="text-[10px] text-destructive -mt-1">
              {form.formState.errors.title.message}
            </p>
          )}

          <textarea
            {...form.register("description")}
            placeholder="Add a note..."
            rows={2}
            className="w-full text-xs bg-secondary/50 rounded-lg border border-border/50 p-2 outline-none focus:border-primary/50 text-foreground placeholder:text-muted-foreground resize-none leading-relaxed"
          />

          <div className="flex gap-2">
            <select
              {...form.register("priority")}
              className="flex-1 text-xs bg-secondary/50 border border-border/50 rounded-lg px-2 py-1.5 text-foreground outline-none focus:border-primary/50 cursor-pointer"
            >
              <option value="none">No priority</option>
              <option value="low">🔵 Low</option>
              <option value="medium">🟡 Medium</option>
              <option value="high">🔴 High</option>
            </select>
            <input
              type="date"
              {...form.register("dueDate")}
              className="flex-1 text-xs bg-secondary/50 border border-border/50 rounded-lg px-2 py-1.5 text-foreground outline-none focus:border-primary/50"
            />
          </div>

          <div className="flex items-center justify-between pt-0.5">
            <button
              type="button"
              onClick={handleOpenFull}
              className="text-[11px] text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
            >
              More options
            </button>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleCancel}
                className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg text-muted-foreground hover:bg-secondary transition-colors"
              >
                <X className="w-3 h-3" />
                Cancel
              </button>
              <button
                type="submit"
                disabled={isPending}
                className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
              >
                <Check className="w-3 h-3" />
                {isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      tabIndex={-1}
      onClick={() => setIsEditing(true)}
      className="cursor-grab active:cursor-grabbing touch-none group"
    >
      <KanbanCardPreview card={card} onFullEdit={handleOpenFull} />
    </div>
  );
}
