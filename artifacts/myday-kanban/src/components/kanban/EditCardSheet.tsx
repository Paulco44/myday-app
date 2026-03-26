import { useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Trash2 } from "lucide-react";
import { useUpdateCard, useDeleteCard, getGetCardsQueryKey } from "@workspace/api-client-react";
import type { Card } from "@workspace/api-client-react/src/generated/api.schemas";
import { useQueryClient } from "@tanstack/react-query";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

const formSchema = z.object({
  title: z.string().min(1, "Task title is required"),
  description: z.string().optional(),
  priority: z.enum(["low", "medium", "high", "none"]).optional().transform(val => val === "none" ? undefined : val),
  dueDate: z.string().optional().transform(val => val || undefined),
});

type FormValues = z.infer<typeof formSchema>;

export function EditCardSheet({ card, open, onOpenChange }: { card: Card | null, open: boolean, onOpenChange: (open: boolean) => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  // Format date for the input
  const defaultDate = card?.dueDate ? new Date(card.dueDate).toISOString().split('T')[0] : "";

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: card?.title || "",
      description: card?.description || "",
      priority: (card?.priority as any) || "none",
      dueDate: defaultDate,
    },
  });

  const { mutate: updateCard, isPending: isUpdating } = useUpdateCard({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() });
        toast({ title: "Task saved" });
        onOpenChange(false);
      }
    }
  });

  const { mutate: deleteCard, isPending: isDeleting } = useDeleteCard({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() });
        toast({ title: "Task deleted" });
        onOpenChange(false);
      }
    }
  });

  function onSubmit(values: FormValues) {
    if (!card) return;
    updateCard({
      id: card.id,
      data: {
        title: values.title,
        description: values.description || null,
        priority: values.priority || null,
        dueDate: values.dueDate ? new Date(values.dueDate).toISOString() : null,
      }
    });
  }

  function handleDelete() {
    if (!card) return;
    if (confirm("Are you sure you want to delete this task?")) {
      deleteCard({ id: card.id });
    }
  }

  if (!card) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[450px] sm:w-[450px] w-full p-0 flex flex-col border-l-0 shadow-2xl">
        <div className="p-6 border-b border-border/50 bg-secondary/20">
          <SheetHeader>
            <SheetTitle className="font-display text-2xl">Edit Task</SheetTitle>
            <SheetDescription>
              Update the details of your card.
            </SheetDescription>
          </SheetHeader>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6">
          <Form {...form}>
            <form id="edit-card-form" onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl>
                      <Input className="h-12 px-4 rounded-xl bg-secondary/30" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea 
                        className="min-h-[160px] rounded-xl bg-secondary/30 resize-none p-4" 
                        {...field} 
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="priority"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Priority</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="h-12 rounded-xl bg-secondary/30">
                            <SelectValue placeholder="Select priority" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
                          <SelectItem value="low">Low</SelectItem>
                          <SelectItem value="medium">Medium</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="dueDate"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Due Date</FormLabel>
                      <FormControl>
                        <Input type="date" className="h-12 px-4 rounded-xl bg-secondary/30" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </form>
          </Form>
        </div>

        <div className="p-6 border-t border-border/50 bg-background flex items-center justify-between">
          <Button
            type="button"
            variant="destructive"
            size="icon"
            className="h-12 w-12 rounded-xl"
            onClick={handleDelete}
            disabled={isDeleting || isUpdating}
          >
            <Trash2 className="h-5 w-5" />
          </Button>
          <Button 
            type="submit" 
            form="edit-card-form"
            disabled={isUpdating || isDeleting}
            className="h-12 px-8 rounded-xl bg-gradient-to-r from-primary to-primary/80 shadow-lg shadow-primary/25 hover:shadow-xl hover:shadow-primary/30 transition-all hover:-translate-y-0.5 active:translate-y-0 active:shadow-md"
          >
            {isUpdating ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
