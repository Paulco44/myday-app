# MyDay — Roadmap V2: Plan Estratégico Comprehensivo

*Actualizado: 13 abril 2026*

---

## Dónde estamos

### Lo que está hecho ✅

| Track | Qué se hizo | Quién |
|-------|------------|-------|
| Fase 1 Quick Wins | 9/9 items (fonts, nav, click zones, atajos, CoP) | Nosotros + Replit |
| Fase 2 Restructuración | 7/7 items (3-col layout, master-detail, flow bar, wizard, quick-add) | Nosotros + Replit |
| Track A — Bridge | Migrations, graceful fallback, idempotency, badge honesto | Replit (prompt nuestro) |
| Track B — Design System | Shared tokens, paleta indigo+green, WCAG fixes, Lexend unificado | Nosotros |
| Track C — ADHD Features | Evening Reset, Focus Timer SVG + brown noise, keyboard shortcuts J/K/1/2/3, Weekly Review dashboard | Replit (prompt nuestro) |
| Integraciones | Whisper → Inbox, Notion import/export, Meeting views, 3 promotion paths | Replit |

### Lo que queda pendiente 🟡

| Item | Origen | Esfuerzo |
|------|--------|----------|
| Smart suggestions scoring | Plan original Track C P3 | Medio |
| Recurring tasks | Diseño original, modelo existe pero sin UI | Medio |
| `window.confirm()` → modal en Kanban | Plan original 3.7 | Bajo |
| Brown noise compartido (React + Python) | Plan original Track B P2 | Bajo |
| Decisión: ¿1 DB o 2? Migración Kanban | Decisión arquitectónica abierta | Alto |
| `task_edit.html` usa colores hardcoded, no tokens | Deuda técnica post-Track B | Bajo |

### Lo nuevo: Adopciones de Asana

10 patterns identificados del análisis de Asana, priorizados por impacto para ADHD.

---

## Principio estratégico

> **Hacer que lo existente se sienta profesional → Agregar valor ADHD → Resolver deuda técnica.**
> La decisión de 1 vs. 2 DBs se posterga deliberadamente hasta que el producto esté estable y usable.

---

## El plan: 5 Sprints

### Sprint D — "Slick" Visual Polish (nosotros, 1-2 días)
*Transformar la sensación de la app sin tocar backend. Puro CSS + SVG + JS.*

| # | Acción | Detalle | Asana ref |
|---|--------|---------|-----------|
| D1 | **Completion circles** | Reemplazar botones "✓ Done" con SVG circular: hueco → ghost check en hover → fill+pulse al completar. En My Day (NOW strip, suggestions) y Tasks page. | #2 |
| D2 | **Row hover highlight** | `background: var(--md-surface-alt)` en hover sobre task rows. Transición 80ms. | #7 |
| D3 | **Ghost affordances** | Ocultar botones secundarios (→ NOW, → NEXT, ✕) y mostrar solo en hover. Default: solo título + metadata + circle. | #5 |
| D4 | **Micro-celebración en done** | Al completar NOW task: circle pulsa, streak counter incrementa con animación (number count-up CSS). | #8 |
| D5 | **Fix `task_edit.html` tokens** | Reemplazar colores hardcoded (`#e2e8f0`, `#64748b`, `#4f46e5`) con variables `--md-*`. | Deuda |

**Quién lo hace:** Nosotros directamente en el repo.
**Impacto:** La app pasa de "funcional" a "pulida". Cada interacción con un task tiene feedback visual.

---

### Sprint E — Flujo de captura y organización (Replit, 2-3 días)
*Mejorar cómo entran y se organizan los tasks. Reduce fricción cognitiva.*

| # | Acción | Detalle | Asana ref |
|---|--------|---------|-----------|
| E1 | **Inline task creation** | Input persistente al final de cada sección en My Day ("Add a task..."). Enter crea con defaults. Cursor queda para encadenar. Mantener modal `N` para metadata completa. | #3 |
| E2 | **Secciones colapsables** | Headers de NOW/NEXT/LATER clickables con chevron + conteo ("LATER · 3"). Estado en localStorage. Default: NOW siempre abierto, LATER cerrado si 4+ items. | #4 |
| E3 | **Smart suggestions scoring** | Ponderar sugerencias: `score = (energy_match * 3) + (overdue_days * 2) + (due_today * 5) + (time_block_match * 2) + (priority_weight)`. Los datos ya existen. | Track C pendiente |
| E4 | **Sort/filter indicators** | En Tasks page: header de columna activa en `var(--md-primary)` con flecha. Chip "Sorted by: X" removible encima de tabla. | #6 |

**Quién lo hace:** Replit Agent (prompt nuestro).
**Impacto:** Captura instantánea de ideas, vista enfocada, sugerencias más inteligentes.

---

### Sprint F — Task Detail Pane (Replit, 3-4 días)
*El cambio arquitectónico más grande. Transforma la experiencia core.*

| # | Acción | Detalle |
|---|--------|---------|
| F1 | **Panel lateral de task detail** | Click en task → `<aside>` deslizable a la derecha (~380px). Campos editables inline: título, descripción, subtasks, priority, energy, time_block, due_date, project. `Esc` cierra. Fetch via API JSON. |
| F2 | **Subtasks en el panel** | Lista de subtasks con add/check/delete inline. Progress bar. Misma UX que el NOW strip pero dentro del panel. |
| F3 | **`X` full-screen mode** | Desde el panel, shortcut `X` expande a vista completa (como `task_edit.html` actual pero sin navegación). `Esc` vuelve al panel. |
| F4 | **Deprecar `task_edit.html` como vista principal** | El panel reemplaza la navegación a `/tasks/{id}/edit`. Mantener la ruta como fallback/bookmark pero redirigir al panel si se accede desde la app. |

**Quién lo hace:** Replit Agent (prompt nuestro detallado).
**Impacto:** Elimina el "perderse" al editar un task. Contexto siempre visible.

---

### Sprint G — Hábitos y automatización (Replit, 2-3 días)
*Features que hacen la app más útil con el uso diario.*

| # | Acción | Detalle |
|---|--------|---------|
| G1 | **Recurring tasks UI** | El modelo `RecurringTask` ya existe. Agregar: UI para crear recurrencias (diaria, semanal, custom), auto-generación al hacer Morning Check-In, badge "recurring" en My Day. |
| G2 | **Auto-promoción suave** | Tasks con due_date = hoy suben automáticamente a sugerencias con badge "due today". Due_date = mañana: badge "due tomorrow". NO auto-mover a NOW (control del usuario). |
| G3 | **Multi-select + bulk actions** | Shift+Click selecciona rango en Tasks page. Toolbar flotante: "3 selected: [✓ Done] [→ NOW] [→ NEXT] [✕ Delete]". |
| G4 | **Confirmaciones in-context** | Reemplazar `window.confirm()` en Kanban React con componente `<ConfirmDialog>`. |

**Quién lo hace:** Replit Agent.
**Impacto:** La app trabaja para ti en vez de requerir mantenimiento manual constante.

---

### Sprint H — Decisión arquitectónica: Una sola DB (Replit, 1-2 semanas)
*Eliminar la deuda técnica más grande. Solo si el producto ya se siente estable.*

| # | Opción recomendada | Detalle |
|---|--------|---------|
| H1 | **Migrar React Kanban a FastAPI backend** | React frontend llama a `/task-manager/api/cards`, `/api/columns` etc. Eliminar Express + Drizzle + Postgres separado. SQLAlchemy es la única fuente de verdad. |
| H2 | **Eliminar bridge** | Una vez migrado, el bridge es innecesario. Eliminar `push_to_kanban`, `sync_bridge`, raw SQL cross-DB. |
| H3 | **Simplificar deploy** | De 3 procesos (FastAPI + Express + Vite) a 2 (FastAPI + Vite). Una sola DB. |

**Quién lo hace:** Replit Agent (prompt muy detallado con mapping de endpoints).
**Timing:** Después de Sprints D-G. No antes, porque cada sprint previo agrega valor inmediato y usable.
**Impacto:** Elimina toda la deuda del bridge. Simplifica todo el desarrollo futuro.

---

## Timeline visual

```
Semana 1:   Sprint D (nosotros, visual polish)
            Sprint E (Replit, en paralelo — captura + organización)

Semana 2:   Sprint F (Replit, task detail pane)

Semana 3:   Sprint G (Replit, hábitos + automation)

Semana 4-5: Sprint H (Replit, migración DB — solo si D-G están estables)
```

D y E pueden correr en paralelo porque D es puro CSS/SVG (nosotros) y E es backend+templates (Replit).

---

## División de trabajo

| Nosotros (CSS/HTML/tokens/design) | Replit Agent (backend/JS/React) |
|---|---|
| Sprint D completo | Sprint E completo |
| Prompts detallados para F, G, H | Sprint F, G, H |
| Revisión de cada push | Implementación |
| WCAG audit de cada sprint | Testing funcional |

---

## Métricas de éxito (dogfooding)

Después de cada sprint, evaluar:

1. **¿Cuántos clicks para completar tu loop diario?** (Morning → Focus → Evening)
   - Meta: reducir de ~25 clicks a ~12
2. **¿Cuántas veces pierdes contexto?** (navegaciones a página nueva)
   - Meta: 0 después de Sprint F
3. **¿La app se siente "slick"?** (subjetivo pero real)
   - Sprint D debería mover esto significativamente
4. **¿Usas la app todos los días laborales?**
   - El verdadero KPI. Si no, algo falta o algo estorba.

---

## Lo que NO está en este plan (y por qué)

| Feature | Razón de exclusión |
|---|---|
| Calendar integration (Google Cal) | Útil pero no bloquea el loop diario. Agregar después de Sprint G. |
| Email daily summary export | Nice-to-have. No afecta el uso diario. |
| Whisper auto-POST | Ya diseñado, pendiente de implementar en la Whisper app separada. No depende de MyDay. |
| Mobile native app | Overkill. El responsive actual es suficiente por ahora. |
| AI-powered task suggestions | Interesante pero prematuro. Primero el scoring manual (E3) tiene que funcionar bien. |
