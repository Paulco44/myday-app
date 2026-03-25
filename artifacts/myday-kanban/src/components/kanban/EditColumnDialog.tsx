import { useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { MoreHorizontal, Trash2 } from "lucide-react";
import { useUpdateColumn, useDeleteColumn, getGetColumnsQueryKey, getGetCardsQueryKey } from "@workspace/api-client-react";
import type { Column } from "@workspace/api-client-react/src/generated/api.schemas";
import { useQueryClient } from "@tanstack/react-query";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

const formSchema = z.object({
  title: z.string().min(1, "Column title is required").max(50, "Title is too long"),
});

type FormValues = z.infer<typeof formSchema>;

export function EditColumnDialog({ column }: { column: Column }) {
  const [open, setOpen] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: column.title,
    },
  });

  const { mutate: updateColumn, isPending: isUpdating } = useUpdateColumn({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() });
        toast({ title: "Column updated" });
        setOpen(false);
      }
    }
  });

  const { mutate: deleteColumn, isPending: isDeleting } = useDeleteColumn({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetColumnsQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetCardsQueryKey() });
        toast({ title: "Column deleted" });
        setOpen(false);
      }
    }
  });

  function onSubmit(values: FormValues) {
    updateColumn({
      id: column.id,
      data: { title: values.title },
    });
  }

  function handleDelete() {
    if (confirm("Are you sure you want to delete this column and all its cards?")) {
      deleteColumn({ id: column.id });
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-foreground">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px] rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Edit Column</DialogTitle>
          <DialogDescription>
            Rename or delete this column.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6 mt-4">
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
            <div className="flex items-center justify-between pt-2">
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
                disabled={isUpdating || isDeleting}
                className="h-12 px-8 rounded-xl bg-gradient-to-r from-primary to-primary/80 shadow-lg shadow-primary/25 hover:shadow-xl hover:shadow-primary/30 transition-all hover:-translate-y-0.5 active:translate-y-0 active:shadow-md"
              >
                {isUpdating ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
