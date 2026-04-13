import app from "./app";
import { logger } from "./lib/logger";
import { db } from "@workspace/db";
import { sql } from "drizzle-orm";

// ── Startup migration: ensure bridge column exists ────────────────────────────
async function runStartupMigrations() {
  try {
    await db.execute(
      sql`ALTER TABLE cards ADD COLUMN IF NOT EXISTS task_id INTEGER`
    );
    await db.execute(
      sql`ALTER TABLE cards ADD COLUMN IF NOT EXISTS project_id INTEGER`
    );
    await db.execute(
      sql`UPDATE cards c SET project_id = t.project_id FROM tasks t WHERE c.task_id = t.id AND t.project_id IS NOT NULL AND c.project_id IS NULL`
    );
    logger.info("Bridge migration: cards.task_id and project_id ensured");
  } catch (err) {
    logger.warn({ err }, "Bridge migration skipped (non-fatal)");
  }
}

const rawPort = process.env["PORT"];

if (!rawPort) {
  throw new Error(
    "PORT environment variable is required but was not provided.",
  );
}

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

runStartupMigrations().then(() => {
  app.listen(port, (err) => {
    if (err) {
      logger.error({ err }, "Error listening on port");
      process.exit(1);
    }

    logger.info({ port }, "Server listening");
  });
});
