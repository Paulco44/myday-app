import { Router, type IRouter } from "express";
import { db, cardsTable } from "@workspace/db";
import { eq } from "drizzle-orm";
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
  res.json({ success: true });
});

export default router;
