import { Router, type IRouter } from "express";
import { db, columnsTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import {
  CreateColumnBody,
  UpdateColumnParams,
  UpdateColumnBody,
  DeleteColumnParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

router.get("/columns", async (_req, res) => {
  const columns = await db.select().from(columnsTable).orderBy(columnsTable.position);
  res.json(columns);
});

router.post("/columns", async (req, res) => {
  const body = CreateColumnBody.parse(req.body);
  const [column] = await db.insert(columnsTable).values(body).returning();
  res.status(201).json(column);
});

router.patch("/columns/:id", async (req, res) => {
  const { id } = UpdateColumnParams.parse(req.params);
  const body = UpdateColumnBody.parse(req.body);
  const [column] = await db
    .update(columnsTable)
    .set(body)
    .where(eq(columnsTable.id, id))
    .returning();
  if (!column) {
    res.status(404).json({ error: "Column not found" });
    return;
  }
  res.json(column);
});

router.delete("/columns/:id", async (req, res) => {
  const { id } = DeleteColumnParams.parse(req.params);
  const [column] = await db
    .delete(columnsTable)
    .where(eq(columnsTable.id, id))
    .returning();
  if (!column) {
    res.status(404).json({ error: "Column not found" });
    return;
  }
  res.json({ success: true });
});

export default router;
