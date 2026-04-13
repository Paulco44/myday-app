import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { sql } from "drizzle-orm";

const router: IRouter = Router();

router.get("/projects", async (_req, res) => {
  const result = await db.execute(sql`SELECT id, name FROM projects ORDER BY id`);
  res.json(result.rows);
});

export default router;
