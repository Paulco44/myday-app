# MyDay — Plan de Siguiente Fase

## Estado actual: qué está hecho

### Evaluación original (20 recomendaciones)

#### Fase 1 — Quick Wins ✅ COMPLETA
| # | Item | Estado |
|---|------|--------|
| 1.1 | Font-size mínimo 0.82rem | ✅ Nosotros (commit `46f4d67`) |
| 1.2 | Click-toggle progressive disclosure | ✅ Replit |
| 1.3 | Nav links con separadores en 3 zonas | ✅ Nosotros (commit `46f4d67`) |
| 1.4 | Persistir estado CoP accordion en localStorage | ✅ Replit |
| 1.5 | Aumentar zonas de click en buttons | ✅ Nosotros (commit `46f4d67`) |
| 1.6 | Atajos de teclado F/D en My Day | ✅ Nosotros (commit `46f4d67`) |
| 1.7 | Eliminar campo energy_type duplicado | ✅ Nosotros (commit `46f4d67`) |
| 1.8 | Banner DB separada en React Kanban | ✅ Nosotros (commit `46f4d67`) |
| 1.9 | Conteo de iniciativas CoP en accordion summary | ✅ Nosotros (commit `46f4d67`) |

#### Fase 2 — Restructuración ✅ COMPLETA
| # | Item | Estado |
|---|------|--------|
| 2.1 | Layout widescreen 3-col para My Day | ✅ Nosotros (commits `cf4987f`, `549e7de`, `847bf65`, `40fa377`) |
| 2.2 | Layout master-detail para Inbox | ✅ Replit |
| 2.3 | Indicador de progreso del día (flow bar) | ✅ Replit |
| 2.4 | Morning Check-In wizard sin reloads | ✅ Replit (commit `2b7a5a4`) |
| 2.5 | Filtros y búsqueda en Meetings | ✅ Replit |
| 2.6 | Quick-add inline en My Day | ✅ Replit |
| 2.7 | Energy match en sugerencias | ✅ Replit |

#### Fase 3 — Unificación 🟡 EN PROGRESO
| # | Item | Estado |
|---|------|--------|
| 3.1 | Conectar React Kanban al API Python | 🟡 Parcial — bridge bidireccional existe (`f28e341`) pero son 2 DBs aún; raw SQL cross-DB |
| 3.2 | Migrar React Kanban al design system Python | 🟡 Parcial — Lexend agregado pero colores desalineados (amarillo vs. indigo) |
| 3.3 | Ruido marrón en React app | ✅ Replit (commit `25d1152`) — solo en Kanban, no compartido |
| 3.4 | Deprecar Kanban Python/Jinja | ✅ Replit (commit `608e024`) — redirect 301 a React |
| 3.5 | Subtareas en NOW strip | ✅ Replit (commit `25d1152`) |
| 3.6 | Formularios fetch() progresivo | ✅ Replit (commit `8e86a9a`) |
| 3.7 | Confirmaciones de eliminación nativas | ❌ Pendiente |

---

## Problemas detectados en las revisiones

### 🔴 Críticos
1. **"Shared DB" badge es falso** — Dice "Shared DB ✓" pero las DBs siguen separadas. El bridge solo funciona si ambas apps comparten el mismo PostgreSQL via `DATABASE_URL`. En dev local con SQLite, `push_to_kanban` falla silenciosamente.
2. **Cross-DB raw SQL frágil** — `push_to_kanban` ejecuta `INSERT INTO cards` con SQL directo al Postgres, sin ORM ni validación. No hay manejo del caso SQLite.
3. **Sin migration scripts** — `card_id` en SQLAlchemy y `taskId` en Drizzle se agregaron sin ALTER TABLE. Funciona en dev pero rompe en producción Postgres existente.

### 🟡 Medios
4. **Amarillo `#FFCC00` como primary del Kanban** — Ratio de contraste ~1.5:1 sobre blanco. Viola WCAG AA. Inconsistente con la paleta indigo+green del task manager.
5. **Inconsistencia tipográfica** — Kanban usa Lexend; Task Manager usa system fonts. No hay design tokens compartidos.
6. **Race condition en bridge Done** — Doble-write posible en `completed_at` si se marca done en ambos lados simultáneamente.
7. **Confirmaciones de eliminación** (3.7) — React Kanban sigue usando `window.confirm()`.

---

## Plan propuesto: 3 tracks paralelos

### Track A — Estabilidad del Bridge (1–2 días)
*Hacer que lo que existe funcione correctamente antes de agregar más.*

| Prioridad | Acción | Detalle |
|-----------|--------|---------|
| P0 | **Fix badge "Shared DB"** | Cambiar a badge honesto: "Linked via Bridge" o detectar runtime si realmente comparten DB |
| P0 | **Migration scripts** | Crear `ALTER TABLE tasks ADD COLUMN card_id INTEGER` para Postgres + Drizzle migration para `task_id` en cards |
| P0 | **Graceful fallback para SQLite** | `push_to_kanban` debe detectar si la DB es SQLite y retornar error amigable ("Bridge requires PostgreSQL") en vez de fallar silencioso |
| P1 | **Idempotency en Done sync** | Agregar check `IF status != 'done'` antes de update en el Express handler para evitar race condition |

### Track B — Design System Unificado (3–4 días)
*Un solo lenguaje visual para ambas apps.*

| Prioridad | Acción | Detalle |
|-----------|--------|---------|
| P1 | **Definir design tokens compartidos** | Crear `shared-tokens.css` con variables CSS: `--primary` (indigo), `--success` (green), `--surface`, `--text`, `--border`. Ambas apps lo importan. |
| P1 | **Alinear Kanban a paleta indigo** | Reemplazar `#FFCC00` con `var(--primary)` / indigo. Mantener Lexend pero importarla también en el task manager para consistencia. |
| P1 | **Fix contraste WCAG** | Auditar todos los colores del Kanban contra AA (4.5:1 body, 3:1 large). Reemplazar amarillo sobre blanco. |
| P2 | **Ruido marrón compartido** | Extraer `useBrownNoise` a módulo vanilla JS que ambas apps importen. Agregar toggle en My Day (no solo Kanban). |
| P2 | **Confirmaciones in-context** (3.7) | Reemplazar `window.confirm()` en Kanban con dialog modal componente. |

### Track C — Mejoras ADHD de Alto Impacto (1–2 semanas)
*Features nuevos alineados con la investigación ADHD original.*

| Prioridad | Acción | Detalle |
|-----------|--------|---------|
| P1 | **Evening Reset page** | Planned vs. Done comparison, roll-to-tomorrow en 1 click, streak reinforcement, "inbox today" summary. Siempre fue parte del diseño original pero nunca se construyó. |
| P1 | **Focus Timer real en My Day** | El botón "Focus 20 min" lleva a `/focus` pero esa página necesita timer visual con ruido marrón, distraction-free mode, y auto-done al completar. |
| P2 | **Keyboard-first flow** | Expandir atajos: `N` = next, `L` = later, `Space` = toggle expand, `Enter` = focus on selected task. ADHD beneficia de flujo sin mouse. |
| P2 | **Weekly review dashboard** | Gráfico simple: completed vs planned por día (últimos 7 días). Refuerzo visual de "showed up" sin shame. |
| P3 | **Smart suggestions** | Ponderar sugerencias por: energy match del día + due date + overdue + time block match. Ya hay datos (`energy_today`, `time_block`), falta el scoring. |

---

## Orden de ejecución recomendado

```
Semana 1:  Track A completo + Track B (tokens + paleta)
Semana 2:  Track B (resto) + Track C (Evening Reset + Focus Timer)
Semana 3:  Track C (keyboard flow + weekly review)
Ongoing:   Smart suggestions, refinamiento basado en uso real
```

### Principio guía
> Estabilizar lo que existe → Unificar la experiencia visual → Agregar valor ADHD.
> No construir features nuevos sobre una base inestable.

---

## Decisión arquitectónica pendiente: ¿Una DB o dos?

El bridge es un parche. La solución real (3.1 de la evaluación original) es migrar el React Kanban para que use el FastAPI como único backend. Esto elimina:
- La necesidad del bridge
- El raw SQL cross-DB
- La duplicación de datos
- El riesgo de inconsistencia

**Opciones:**
1. **Mantener bridge** — Menos esfuerzo ahora, más deuda técnica. Requiere que ambas apps usen Postgres.
2. **Migrar Kanban a FastAPI** — ~2 semanas. El React frontend llama a endpoints `/task-manager/api/...` en vez del Express API. Elimina Express + Drizzle + Postgres separado.
3. **API gateway** — Un proxy que traduce llamadas del Kanban React a endpoints FastAPI. Complejidad media, mantiene el frontend intacto.

**Mi recomendación:** Opción 2, pero después de completar Tracks A y B. El bridge mantiene las cosas funcionando mientras se hace la migración real.
