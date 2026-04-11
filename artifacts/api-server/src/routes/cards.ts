import { Router, type IRouter } from "express";
import { db, cardsTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { sql } from "drizzle-orm";
import {
  CreateCardBody,
  UpdateCardParams,
  UpdateCardBody,
  DeleteCardParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

router.get("/cards", async (_req, res) => {
  const cards = await db.select().from(cardsTable).orderBy(cardsTable.position);
  res.json(cards);
});

router.post("/cards", async (req, res) => {
  const body = CreateCardBody.parse(req.body);
  const [card] = await db.insert(cardsTable).values(body).returning();
  res.status(201).json(card);
});

router.patch("/cards/:id", async (req, res) => {
  const { id } = UpdateCardParams.parse(req.params);
  const body = UpdateCardBody.parse(req.body);
  const [card] = await db
    .update(cardsTable)
    .set(body)
    .where(eq(cardsTable.id, id))
    .returning();
  if (!card) {
    res.status(404).json({ error: "Card not found" });
    return;
  }

  // Bridge sync: if card moved to a "Done" column and has a linked task, mark it done
  if (body.columnId && card.taskId) {
    try {
      const colRows = await db.execute(
        sql`SELECT title FROM columns WHERE id = ${body.columnId} LIMIT 1`
      );
      const colTitle: string = (colRows.rows[0] as { title: string })?.title ?? "";
      const isDoneCol = /done/i.test(colTitle);
      if (isDoneCol) {
        await db.execute(
          sql`UPDATE tasks SET status = 'done', updated_at = now(), completed_at = COALESCE(completed_at, now()) WHERE id = ${card.taskId}`
        );
      }
    } catch {
      // Non-fatal: bridge sync is best-effort
    }
  }

  res.json(card);
});

router.delete("/cards/:id", async (req, res) => {
  const { id } = DeleteCardParams.parse(req.params);
  const [card] = await db
    .delete(cardsTable)
    .where(eq(cardsTable.id, id))
    .returning();
  if (!card) {
    res.status(404).json({ error: "Card not found" });
    return;
  }

  // Bridge cleanup: if card had a linked task, clear its card_id
  if (card.taskId) {
    try {
      await db.execute(
        sql`UPDATE tasks SET card_id = NULL WHERE id = ${card.taskId}`
      );
    } catch {
      // Non-fatal
    }
  }

  res.json({ success: true });
});

export default router;
