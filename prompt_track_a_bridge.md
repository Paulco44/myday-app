# Track A — Estabilizar el Bridge Kanban ↔ Task Manager

## Contexto
El bridge bidireccional entre el Kanban (Express/Drizzle/Postgres) y el Task Manager (FastAPI/SQLAlchemy) funciona en producción con PostgreSQL compartido, pero tiene varios problemas de robustez que necesitan arreglarse antes de agregar más features.

## Tareas (en orden de prioridad)

### 1. Migration scripts para las columnas del bridge
**Problema:** `tasks.card_id` (SQLAlchemy) y `cards.task_id` (Drizzle) se agregaron al código pero no hay migrations. En un Postgres existente, las columnas no existen hasta que se ejecute ALTER TABLE.

**Solución:**
- Crear migration SQLAlchemy: `ALTER TABLE tasks ADD COLUMN IF NOT EXISTS card_id INTEGER;`
- Crear migration Drizzle: `ALTER TABLE cards ADD COLUMN IF NOT EXISTS task_id INTEGER;`
- Ejecutar ambas migrations al startup si las columnas no existen
- Para SQLAlchemy, puedes agregar la lógica en `database.py` después de `Base.metadata.create_all()`
- Para Drizzle, usa `drizzle-kit push` o un script SQL en el startup del Express server

### 2. Graceful fallback cuando no hay PostgreSQL compartido
**Problema:** `push_to_kanban` en `main.py` ejecuta `INSERT INTO cards` con raw SQL. Si la DB es SQLite (sin `DATABASE_URL`), la tabla `cards` no existe y falla silenciosamente.

**Solución:**
- En `push_to_kanban`, antes de ejecutar el raw SQL, verificar si la tabla `cards` existe:
  ```python
  try:
      db.execute(sa_text("SELECT 1 FROM cards LIMIT 0"))
  except:
      raise HTTPException(status_code=503, detail="Bridge requires shared PostgreSQL. Cards table not found.")
  ```
- En el frontend (tasks.html), el `pushToKanban()` JS debe manejar el error 503 y mostrar un mensaje amigable en vez de fallar silencioso
- Alternativamente, si `DATABASE_URL` no está configurado, ocultar el botón "📋 Board" completamente pasando un flag `bridge_available` al template context

### 3. Idempotency en el Done sync (Express side)
**Problema:** Cuando mueves un card a "Done" en Kanban, el Express PATCH handler actualiza el task linked. Si el task ya estaba done (ej: lo marcaste done en ambos lados), hay un doble-write en `completed_at`.

**Solución:**
En `artifacts/api-server/src/routes/cards.ts`, en el bridge sync block, agregar:
```sql
UPDATE tasks SET status = 'done', updated_at = now(), completed_at = COALESCE(completed_at, now()) 
WHERE id = ${card.taskId} AND status != 'done'
```
Esto ya usa COALESCE para `completed_at`, pero el `AND status != 'done'` evita el write innecesario completamente.

### 4. Cleanup bidireccional
**Problema:** Si borras un task en el Task Manager que tiene un card linked, el card queda huérfano con un `task_id` apuntando a un task que no existe.

**Solución:**
- En `main.py`, en la ruta de delete task, si el task tiene `card_id`, limpiar el `task_id` del card:
  ```python
  if task.card_id:
      try:
          db.execute(sa_text("UPDATE cards SET task_id = NULL WHERE id = :cid"), {"cid": task.card_id})
      except:
          pass  # Best-effort, non-fatal
  ```

## Principios
- Todos los cambios de bridge son **best-effort** — si falla el sync, la operación principal (mover card, borrar task) debe completarse igual
- No introducir nueva UI compleja — solo mensajes de error claros y fallbacks
- No cambiar la arquitectura de 2 DBs — eso es un proyecto separado más adelante
