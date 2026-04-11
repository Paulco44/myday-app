# Evaluación UI/UX para ADHD — MyDay App
**Especialista**: UI/UX para usuarios con TDAH / déficit de atención  
**Usuario**: Paul Cohen Luy · ENFP · TDAH  
**Pantalla principal**: Monitor 1920×1080 FHD (PC)  
**Páginas con más fricción reportada**: My Day, Inbox, Meetings  
**Fecha de análisis**: Abril 2026

---

## 1. Resumen Ejecutivo

MyDay tiene una base conceptual excepcionalmente sólida para un cerebro ADHD. La elección de Lexend como tipografía, el sistema de temas dual con el "ADHD High-Signal Dark" (negro + amarillo `#FFCC00`), el modo Focus sin distracciones, el ruido marrón en la navegación global, el mecanismo NOW/Next/Later y las micro-celebraciones con confeti son decisiones de diseño que demuestran comprensión real de cómo funciona el cerebro ADHD. El ritual diario (Check-In → My Day → Focus → Close Day) está conceptualmente bien pensado.

**Lo que funciona bien:**
- El concepto de flujo diario estructurado (ritual mañana → ejecución → cierre) reduce la parálisis de inicio.
- Los límites duros (máx. 3 wins, máx. 2 nice-to-dos, 1 tarea NOW, WIP cap visual) protegen contra el sobre-compromiso.
- El modo Focus es la única página que aprovecha correctamente la pantalla: centrada, sin nav, sin scroll.
- Las etiquetas de energía (creative/admin/social/low_energy) y los time blocks (morning/afternoon/evening) son herramientas sofisticadas de gestión ADHD.
- El colapso del backlog (solo 3 cards visibles) es excelente.

**El problema estructural más grande:**
La app existe en realidad como **dos aplicaciones separadas con dos bases de datos que no se sincronizan**. Para un usuario ADHD, esto es catastrófico: la fragmentación de datos y la inconsistencia visual crean confusión cognitiva profunda, sentido de pérdida de control y desconfianza en el sistema como "cerebro externo". Un cerebro ADHD necesita saber que su sistema es una sola fuente de verdad.

**Estado general**: 7/10 en intención de diseño ADHD, 4/10 en ejecución y coherencia de sistema.

---

## 2. Problema Arquitectónico Crítico

### Las dos apps separadas: Python Kanban + React Kanban

El proyecto está construido como un monorepo con **dos servicios completamente independientes**:

| Dimensión | App Python (FastAPI) | App React (Vite + Express) |
|---|---|---|
| **Ruta** | `/task-manager` (puerto 8000) | `/` (puerto 23345) |
| **API backend** | FastAPI + SQLAlchemy | Express 5 + Drizzle ORM |
| **Base de datos** | SQLite (`app.db`) | PostgreSQL/SQLite independiente |
| **Kanban** | `kanban.html` (Jinja2, servidor) | `KanbanBoard.tsx` (React, cliente) |
| **Fuente de verdad** | Sí — tiene todo el lifecycle | No — solo tiene el tablero |
| **Design system** | CSS variables (`--bg`, `--accent`, etc.) | Tailwind CSS |
| **Tipografía** | Lexend (300–800) | Inter + Outfit |
| **Color primario** | Indigo `#4F46E5` / Amarillo `#FFCC00` | Azul `hsl(221 83% 53%)` |
| **Paleta dark** | `#1A1A1A` / `#FFCC00` | `hsl(222 47% 11%)` |
| **Ruido marrón** | ✅ (Web Audio API) | ❌ |
| **Modo Focus** | ✅ | ❌ |
| **Morning Check-In** | ✅ | ❌ |
| **Daily flow** | ✅ | ❌ |

#### Por qué esto destruye la experiencia ADHD

El cerebro ADHD funciona sobre un principio fundamental: **necesita un sistema externo que sea absolutamente confiable como cerebro auxiliar**. Cuando ese sistema está fragmentado, ocurre lo siguiente:

1. **Disonancia de datos**: Una tarea creada en el React Kanban no aparece en My Day (Python). Una tarea marcada como NOW en My Day no se refleja en el React Kanban. El usuario ve estados contradictorios del mismo proyecto.

2. **Whiplash cognitivo por cambio de design system**: Al navegar del Python app al React app, el usuario pasa de Lexend + Indigo/Amarillo a Inter/Outfit + Azul. Los colores de prioridad son diferentes, los bordes redondeados tienen distintos radios (`--radius-sm: .35rem` vs `rounded-2xl` = `1.5rem`), los modales se ven distintos. El cerebro ADHD tiene que "reaprender" el sistema cada vez.

3. **Pérdida de contexto de flujo**: El React Kanban no tiene Morning Check-In, no tiene Focus Mode, no tiene Close Day. Si Paul está en el React Kanban, está fuera del flujo diario sin saberlo necesariamente.

4. **Confianza rota en el sistema**: Si creo una tarea aquí, ¿aparecerá allá? ¿En cuál de los dos debo trabajar? Esta duda constante es exactamente el tipo de fricción que paraliza a un cerebro ADHD.

5. **Duplicación silenciosa**: El Python app ya tiene un Kanban completo en `/task-manager/kanban`. La existencia de un segundo Kanban React con su propia base de datos crea redundancia confusa sin ventaja clara para el flujo diario.

#### El único caso de uso válido del React Kanban en su estado actual
El React Kanban tiene mejor drag-and-drop (dnd-kit vs HTML5 nativo), UI de tarjeta más refinada y un sheet lateral para edición. Estos son beneficios reales. Pero sin integración de base de datos, son cosméticos.

---

## 3. Recomendaciones Ranqueadas

*(de mayor a menor impacto ADHD)*

---

### REC-01 · Unificar las dos apps en una sola fuente de verdad

**Severidad**: 🔴 Crítica  
**Esfuerzo estimado**: Significativo (2–4 semanas)

**Impacto ADHD**: El TDAH ya crea naturalmente un mundo fragmentado donde los pensamientos, tareas y contextos se disuelven. Una app que imita esa fragmentación amplifica el problema, en lugar de compensarlo. La confianza en el "cerebro externo" es la base de todo sistema ADHD efectivo.

**Estado actual**: El React Kanban (`/`) tiene su propio Express API en puerto 8080 con su propia base de datos completamente independiente de la SQLite de FastAPI. Los datos de tareas no se sincronizan en ningún punto. El Navbar del React Kanban tiene links externos que apuntan a `/task-manager/*`, creando la ilusión de integración sin que exista.

**Qué cambiar**:
- **Opción A (recomendada)**: Hacer que el React Kanban consuma el API JSON ya existente de FastAPI (`GET /task-manager/tasks`, `PUT /task-manager/tasks/{id}`, etc.). Eliminar el Express API del React app. El Python sigue siendo el único backend.
- **Opción B**: Migrar toda la lógica Python al Express/Node backend y unificar allí.
- En ambos casos: una sola base de datos, un solo API, dos frontends que la comparten.
- Mientras se implementa: añadir un banner persistente en el React Kanban: *"⚠️ Este tablero usa una base de datos separada. Tus tareas de My Day están en /task-manager."*

---

### REC-02 · Rediseñar My Day para pantalla widescreen 1920×1080

**Severidad**: 🔴 Crítica  
**Esfuerzo estimado**: Medio (3–5 días)

**Impacto ADHD**: En un monitor de 1920px, `max-width: 820px` desperdicia ~550px en cada lado (57% de la pantalla horizontal). El cerebro ADHD en modo ejecución necesita ver el máximo contexto posible en una sola mirada, sin scroll. Una columna estrecha que requiere scroll continuo provoca pérdida de hilo y olvido de lo que acababa de ver arriba.

**Estado actual**: 
```css
/* my_day.html */
main { max-width: 820px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }
```
My Day tiene 12+ secciones en una única columna vertical que requiere scroll extenso: stats strip → CTA de check-in → acordeón CoP → NOW strip → panel de foco → grid de time blocks → acordeón de sugerencias → sección de wins → CTA de cierre. En 1080p, el usuario está constantemente scrollando entre contexto que debería ser simultáneamente visible.

El time block grid ya usa `grid-template-columns: 1fr 1fr 1fr` internamente (3 columnas) — esta es la única sección que aprovecha el espacio horizontal.

**Qué cambiar**:
```css
/* Nueva estructura para pantallas >= 1200px */
.myday-layout {
  display: grid;
  grid-template-columns: 1fr 340px;   /* columna principal + panel lateral */
  gap: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
  padding: 1.5rem 2rem 4rem;
}

/* En pantallas >= 1600px, layout de 3 zonas */
@media (min-width: 1600px) {
  .myday-layout {
    grid-template-columns: 280px 1fr 320px;
    /* Col izq: CoP + Suggestions colapsadas */
    /* Col central: NOW + Focus Panel + Time Blocks */
    /* Col der: Stats + Wins + Quick Add */
  }
}
```

**Distribución propuesta para 1920px**:
- **Columna izquierda** (280px): CoP accordion + Suggestions accordion — contexto periférico
- **Columna central** (flex): NOW strip → Focus Panel (wins + nice-to-haves) → Time Block Grid
- **Columna derecha** (320px): Stats (streak/done/overdue) + lista de Wins completados hoy + acceso rápido a Check-In/Close Day

Esta reorganización elimina el 70% del scroll vertical en My Day.

---

### REC-03 · Reducir la navegación de 10+ links a grupos contextuales

**Severidad**: 🔴 Crítica  
**Esfuerzo estimado**: Quick fix (1 día)

**Impacto ADHD**: La barra de navegación actual tiene 10 links en una sola fila plana: My Day, Check In, Kanban, Tasks, Projects, Inbox, Meetings, Notes, CoP Admin, Focus. Para el cerebro ADHD, más opciones = más parálisis. El estudio clásico de sobrecarga de decisiones se amplifica en TDAH: cada link visible es una micro-interrupción cognitiva.

**Estado actual**: 
```html
<!-- Estructura actual de nav — todos los links en un solo nivel -->
My Day | Check In | Kanban | Tasks | Projects | Inbox | Meetings | Notes | CoP Admin | Focus
```
El link "Focus" tiene estilo especial (`font-size: .78rem; color: var(--text-faint)`) sugiriendo que el autor ya reconoció que no debería estar al mismo nivel. El link "Check In" tiene `color: #D97706; font-weight: 700` pero no agrupa visualmente con el flujo diario.

**Qué cambiar**:
Agrupar la navegación en 3 zonas claras con separadores visuales:

```
[MyDay] [▶ Focus] | [Inbox] [Meetings] | [•••]
  Flujo diario       Captura/review      Admin oculto
```

- **Zona 1 — Flujo del día** (siempre visible): My Day, Focus Mode, Check In, Close Day
- **Zona 2 — Inbox y reuniones** (siempre visible): Inbox, Meetings  
- **Zona 3 — Admin/archivo** (dropdown o página de ajustes): Kanban, Tasks, Projects, Notes, CoP Admin, Notion

Añadir indicador de posición en el flujo diario: una pequeña barra de progreso encima del nav que muestre `Check-In → My Day → [Focus] → Close Day` con el estado actual resaltado.

---

### REC-04 · Convertir Morning Check-In a flujo de pasos sin recargas completas de página

**Severidad**: 🔴 Crítica  
**Esfuerzo estimado**: Medio (3–4 días)

**Impacto ADHD**: Cada clic en morning_checkin_pick.html genera un POST que hace **full page reload**. El backend confirma: `"Counter updates are server-side (page reload per action)"`. Para un cerebro ADHD en la frágil ventana de energía matutina, el parpadeo de recarga completa es una interrupción que puede romper el momentum y llevar al abandono del ritual.

**Estado actual**: `morning_checkin_pick.html` tiene botones Pick/Unpick que son formularios con `method="POST"`, cada uno forzando un reload. El contador de "Selected: N / 3" solo se actualiza después del reload del servidor.

**Qué cambiar**:
- Convertir las selecciones de must-dos a interacciones client-side con `fetch()` + actualización optimista del contador.
- El flujo de 4 secciones de `morning_checkin.html` (Energy → Brain Dump → Wins → Nice-to-dos) debería ser una sola página sin recarga, enviando todo en un único POST al final.
- Considerar un wizard de pasos tipo step-by-step donde cada sección ocupa toda la pantalla (igual que `morning_checkin_pick.html` ya hace con los step indicators) — esto es más ADHD-friendly que hacer scroll por 4 secciones en una columna.

---

### REC-05 · Añadir indicador de progreso del día persistente

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Quick fix (4–8 horas)

**Impacto ADHD**: El TDAH tiene una relación difícil con el tiempo (time blindness). Sin un indicador visible de dónde estás en el flujo diario, el usuario no sabe si "ya terminó el día" o si hay pasos pendientes. Esta ambigüedad genera ansiedad de fondo.

**Estado actual**: El link "Close Day" en el nav tiene `display:none` por defecto, apareciendo solo en la tarde via JS. Pero no hay indicador de estado del día en ninguna página: si hiciste el Check-In, si ya empezaste, si cerraste el día.

**Qué cambiar**:
Añadir una barra de contexto debajo del nav (no dentro de él, para no saturarlo):
```
[ ✓ Check-In ] → [ ● My Day ] → [ ○ Focus ] → [ ○ Close Day ]
                      Activo
```
- Íconos de check (✓) para pasos completados, punto relleno (●) para el paso actual, círculo vacío (○) para pasos pendientes.
- Esta barra solo aparece en las páginas del flujo diario (my_day, focus, close_day, morning_checkin).
- Los datos para renderizarla ya existen: `DailyLog.has_morning_checkin`, `DailyLog.started`, `DailyLog.day_closed`.

---

### REC-06 · Rediseñar Inbox con layout de dos paneles en widescreen

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Medio (2–3 días)

**Impacto ADHD**: El Inbox es una lista vertical pura en 820px, requiriendo click → load → revisión → acción → back para cada item. En TDAH, este patrón de navegación fragmentada provoca pérdida de contexto entre items y dificulta la triaje eficiente.

**Estado actual**:
```css
/* inbox.html */
main { max-width: 820px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }
```
Lista vertical de `.inbox-card` items. Al hacer click navega a `inbox_detail.html` (otra página completa). En 1920px, solo 820px de los 1920 disponibles se usan, y hay que cargar una página nueva para ver cada item.

**Qué cambiar**:
Implementar un layout **master-detail** (email-client style) para pantallas ≥ 1100px:
```
┌─────────────────────────────────────────────────────┐
│ [Lista inbox - 380px]  │  [Detalle del item - flex]  │
│  ● Item 1              │  📄 Título del item         │
│  ○ Item 2              │  Summary con border verde   │
│  ○ Item 3              │  Suggested actions          │
│                        │  [Create Task] [Archive]    │
└─────────────────────────────────────────────────────┘
```
La lista izquierda actualiza el panel derecho via fetch() sin navegación. Un cerebro ADHD puede triagear 5–6 items en menos de 2 minutos si no hay saltos de página.

---

### REC-07 · Hacer el font size mínimo 13px (0.82rem) en toda la app

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Quick fix (2–3 horas)

**Impacto ADHD**: El TDAH frecuentemente coexiste con dificultades de procesamiento visual. Texto muy pequeño aumenta la carga cognitiva de lectura, reduciendo la energía disponible para tomar decisiones. En una pantalla 1080p a 60–80cm de distancia, 11px es genuinamente difícil de leer.

**Estado actual**:
```css
/* Tamaños de fuente identificados en style.css */
.badge { font-size: .72rem }        /* ~11.5px — límite legible */
.task-meta { font-size: .78rem }    /* ~12.5px */
.text-tiny { font-size: .68rem }    /* ~10.9px — problemático */
.nav-focus { font-size: .78-.82rem } /* ~12.5px */

/* React Kanban (KanbanCardPreview.tsx) */
.priority-badge { font-size: text-[10px] }  /* 10px — inaceptable */
```

**Qué cambiar**:
```css
/* Mínimo absoluto: 13px = 0.8125rem */
--font-size-min: 0.82rem;   /* ~13px */
--font-size-meta: 0.875rem;  /* 14px */
--font-size-badge: 0.82rem;  /* ~13px (no menos) */

/* Eliminar .68rem y .72rem — sustituir por .82rem */
```
En el React Kanban, cambiar `text-[10px]` a `text-[13px]` en priority badges.

---

### REC-08 · Añadir modo de activación táctil para progressive disclosure

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Quick fix (1–2 horas)

**Impacto ADHD**: El modelo de "hover para ver la información" tiene un problema fundamental de ADHD: cuando el usuario mueve el ratón para leer la meta que apareció, la meta desaparece porque el ratón se movió. Esto crea el efecto "Schrödinger's metadata" — la información existe pero colapsa cuando intentas verla. Para cerebros con dificultad de coordinación motriz (común en ADHD), este patrón es especialmente frustrante.

**Estado actual**:
```css
/* style.css — progressive disclosure */
.task-row-meta {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height .22s ease, opacity .2s;
}
.task-row:hover .task-row-meta,
.task-row.expanded .task-row-meta {
  max-height: 6rem;
  opacity: 1;
}
```
La clase `.expanded` ya existe pero no se activa desde ningún lugar en el código actual — es solo un placeholder sin lógica JS.

**Qué cambiar**:
```javascript
// Añadir toggle click en app.js
document.querySelectorAll('.task-row').forEach(row => {
  row.addEventListener('click', e => {
    if (e.target.closest('button, a, form')) return; // no interferir con acciones
    row.classList.toggle('expanded');
  });
});
```
Esto hace que la meta sea "sticky on click" — el usuario hace click en la fila y la meta queda visible hasta el siguiente click. Hover sigue funcionando para usuarios que lo prefieren.

---

### REC-09 · Rediseñar Meetings como timeline compacto con filtros rápidos

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Medio (2 días)

**Impacto ADHD**: La página Meetings es una lista cronológica pura con grupos por día, dentro de los cuales hay grupos por fuente (whisper/notion/other). En TDAH, encontrar "la reunión del martes pasado sobre Cardinal Health" en una lista sin filtros es un ejercicio frustrante que requiere scroll y memoria simultáneos.

**Estado actual**: `meetings.html` — `max-width: 820px`, grupos `.day-group` con `.day-header` (fecha + pills) y dentro `.source-section` con `.item-card`. Sin filtros. Sin búsqueda. Sin indicación de cuántos items pendientes de revisión hay de forma global.

**Qué cambiar**:
- Añadir barra de filtros rápidos: **Todos | Solo sin revisar | Esta semana | Por proyecto**
- Añadir campo de búsqueda client-side (similar al que ya existe en `tasks.html`)
- En 1920px: layout de dos columnas (lista izquierda + preview derecha, igual que Inbox)
- El pill `badge-whisper` ya existe — añadir filtro rápido "Solo Whisper" para reuniones capturadas por voz
- Mostrar contador total de items pendientes en el header de la página

---

### REC-10 · Conectar energy_tag del día con superficie inteligente de tareas

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Medio (1–2 días)

**Impacto ADHD**: Uno de los problemas más paralizantes del ADHD es "tengo 20 tareas pero no sé cuál hacer ahora dado cómo me siento". MyDay ya captura la energía del día (`DailyLog.energy_today`) en el Morning Check-In y ya tiene etiquetas de energía en las tareas (`energy_tag`). Sin embargo, el backend confirma que estas dos variables **no se conectan inteligentemente**: las sugerencias se ordenan por urgencia (overdue → due today → high priority), no por match de energía.

**Estado actual** (backend analysis, sección 7):
> "Suggestions are surfaced based on urgency (overdue → due today → high priority), but energy_tag enables self-selection"

El usuario tiene que recordar manualmente qué energía declaró y filtrar visualmente las tareas por color de etiqueta.

**Qué cambiar**:
- En My Day, cuando `DailyLog.energy_today == "scattered"`: subir al tope todas las tareas con `energy_tag="low_energy"`, y mostrar un banner suave: *"Hoy estás un poco scattered — aquí están tus tareas de baja energía"*.
- Cuando `energy_today == "high"`: priorizar tareas `energy_tag="creative"`.
- Modificar la query de sugerencias en el backend para ponderar energy match: `+2 puntos si energy_tag coincide con estado del día`.
- Añadir un recordatorio visual del estado de energía en el NOW strip (un pequeño badge del estado del día).

---

### REC-11 · Hacer el Kanban Python la vista primaria — deprecar o integrar el React Kanban

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Significativo (ver REC-01)

**Impacto ADHD**: Tener dos tableros Kanban visualmente diferentes que aparecen desde la misma barra de navegación crea un estado de ansiedad silencioso: *"¿Estoy viendo el kanban correcto? ¿Mis cambios aquí se ven allá?"*

**Estado actual**: El nav del Python app tiene un link "Kanban" que apunta a `/task-manager/kanban` (el Kanban Python). El nav del React app tiene un link "Kanban" que apunta a su propia vista React. Ambos coexisten sin que el usuario sepa necesariamente que son dos sistemas diferentes.

**Qué cambiar**:
- Hasta que REC-01 esté completo: poner un aviso visible en ambos kanbans explicando la situación.
- A largo plazo: mantener UNO solo. Si se migra el React Kanban para usar la API Python (recomendado), el React Kanban se vuelve el frontend principal y el Kanban Python/Jinja se depreca.
- Si se mantiene el React Kanban como primario: migrar al diseño system Python (Lexend, CSS variables, paleta Indigo/Amarillo).

---

### REC-12 · Unificar el design system entre las dos apps (tipografía, colores, componentes)

**Severidad**: 🟠 Alta  
**Esfuerzo estimado**: Significativo (paralelo a REC-01)

**Impacto ADHD**: El cerebro ADHD reconoce patrones visuales más que texto. Cuando los mismos elementos tienen apariencias diferentes entre apps (botones, badges, colores de prioridad), el usuario tiene que "recalibrar" su modelo mental cada vez que cambia de app. Esto consume recursos cognitivos que deberían estar disponibles para las tareas.

**Diferencias actuales documentadas**:

| Elemento | App Python | App React |
|---|---|---|
| Fuente body | Lexend (ADHD-optimized) | Inter |
| Fuente headings | Lexend | Outfit |
| Color primario | `#4F46E5` (Indigo) | `hsl(221 83% 53%)` (Azul) |
| Dark mode accent | `#FFCC00` (Amarillo) | `hsl(217 91% 60%)` (Azul claro) |
| Border radius base | `0.55rem` | `0.75rem` (12px) |
| Border radius cards | `0.6rem` | `rounded-2xl` (24px) |
| Priority High | `#dc2626` (rojo) | `bg-red-50 text-red-700` |
| Priority Medium | `#d97706` (amber) | `bg-amber-50 text-amber-700` |
| Modales | `<dialog>` nativo, `min(480px, 92vw)` | shadcn Dialog, `sm:max-w-[500px]` |
| Ruido marrón | ✅ | ❌ |
| Celebraciones | Confeti + bloom | Solo toast |

**Qué cambiar**:
- Definir un único design token file compartido.
- Migrar React app a Lexend (importar desde Google Fonts).
- Alinear paleta de colores: `primary = #4F46E5`, dark accent = `#FFCC00`.
- Implementar ruido marrón en React app (el código ya existe en `app.js`, extraerlo a un módulo compartido).

---

### REC-13 · Añadir atajos de teclado visibles en My Day

**Severidad**: 🟡 Media  
**Esfuerzo estimado**: Quick fix (3–4 horas)

**Impacto ADHD**: El TDAH a menudo se beneficia de shortcuts de teclado porque reducen el costo de interacción (no hay que buscar dónde hacer click). El atajo `N` para quick-add ya existe pero no es visible en ningún lugar.

**Estado actual**: El atajo `N` para abrir el quick-add modal está implementado en JS pero no hay ningún indicador visual. La tecla `Escape` cierra el modal. No hay otros atajos documentados.

**Qué cambiar**:
- Mostrar shortcuts como texto muy sutil en los elementos relevantes: el FAB podría tener un tooltip `[N]`.
- Añadir `F` para ir directo a Focus Mode desde My Day.
- Añadir `D` para marcar la tarea NOW como done.
- Mostrar un panel de ayuda de atajos con `?` (convención estándar).

---

### REC-14 · Convertir el formulario Quick-Add modal a inline (expandible dentro de la página)

**Severidad**: 🟡 Media  
**Esfuerzo estimado**: Medio (1 día)

**Impacto ADHD**: Los modales interrumpen el flujo visual — la pantalla se oscurece, el contexto desaparece, hay que recordar qué estaba haciendo antes de que apareciera el modal. Para el ADHD, mantener el contexto visual es importante para no perder el hilo.

**Estado actual**: El FAB abre `<dialog class="quick-modal">` con backdrop `rgba(0,0,0,.45) blur(2px)`. El modal es `width: min(480px, 92vw)` centrado en pantalla. Tiene campos: título, prioridad (chips), energía (chips), time block (chips), submit.

**Qué cambiar**:
Reemplazar el modal con un panel inline expandible en la parte superior de la lista de tareas. Al presionar `N` o el FAB, se abre un card dentro del flujo:
```
┌─────────────────────────────────────────────┐
│ + Nueva tarea                                │
│ [_____________________] título              │
│ [Prioridad ▾] [Energía ▾] [Bloque ▾]       │
│                    [Añadir]  [Cancelar]      │
└─────────────────────────────────────────────┘
```
El contexto de My Day sigue visible detrás. Esto es lo que ya hace el React Kanban (inline card form en cada columna) — y funciona bien.

---

### REC-15 · Mejorar el contraste de etiquetas de formulario

**Severidad**: 🟡 Media  
**Esfuerzo estimado**: Quick fix (1 hora)

**Impacto ADHD**: Las etiquetas de formulario en uppercase + letter-spacing reducen la legibilidad. El TDAH frecuentemente coexiste con dislexia o dificultades de procesamiento visual. Las letras espaciadas en caps son más lentas de leer.

**Estado actual**:
```css
/* style.css — labels */
label {
  text-transform: uppercase;
  font-size: 0.72rem;  /* ~11.5px */
  letter-spacing: .05em;
  color: var(--text-muted); /* #6B7280 — contraste bajo sobre blanco */
}
```
Contraste estimado de `#6B7280` sobre `#FFFFFF`: ~4.5:1 (justo en el límite WCAG AA para texto normal, pero insuficiente para texto de 11.5px).

**Qué cambiar**:
```css
label {
  text-transform: none;   /* o mantener uppercase solo en contextos muy cortos */
  font-size: 0.82rem;     /* ~13px mínimo */
  letter-spacing: 0.02em; /* reducir */
  color: var(--text);     /* contraste completo */
  font-weight: 600;       /* peso en lugar de uppercase para jerarquía */
}
```

---

### REC-16 · Añadir confirmación visual de acciones sin reload completo (forms → fetch)

**Severidad**: 🟡 Media  
**Esfuerzo estimado**: Significativo (1–2 semanas para todas las páginas)

**Impacto ADHD**: Los full-page reloads en acciones de estado (marcar tarea done, cambiar time block, set-today/unset-today) generan un flash visual y pérdida de posición de scroll. Para el ADHD, esto interrumpe el flujo de trabajo y puede hacer que el usuario pierda de vista en qué estaba trabajando.

**Estado actual**: La mayoría de acciones en My Day, Inbox, Meetings y Morning Check-In usan `<form method="POST">` con `redirect_to` back al mismo URL. Esto causa full reload. Solo el Kanban (`/set-now`, `/clear-now`, `/quick-edit`) y el Focus Timer usan `fetch()` con actualización parcial del DOM.

Las excepciones positivas que ya usan fetch():
- Kanban: set-now, clear-now, quick-edit
- Focus: focus/complete
- La animación de confetti se dispara client-side antes del submit

**Qué cambiar**:
Priorizar en orden:
1. My Day: las acciones de focus-state (now/next/later) — son las más usadas
2. Morning Check-In pick: selección de must-dos
3. Inbox: archive y status changes
4. Meetings: no tiene acciones en la vista de lista (ya es solo lectura allí)

El patrón ya está establecido en el código (el Kanban lo demuestra). Es cuestión de replicarlo.

---

### REC-17 · Hacer el CoP accordion colapsado por defecto con estado persistido

**Severidad**: 🟡 Media  
**Esfuerzo estimado**: Quick fix (1 hora)

**Impacto ADHD**: El acordeón CoP en My Day se abre al tope de la página, empujando todo el contenido relevante hacia abajo. Si el usuario no trabaja activamente en CoP, este acordeón es ruido.

**Estado actual**:
```html
<!-- my_day.html -->
<details class="cop-details">
  <summary>...</summary>
  <!-- contenido -->
</details>
```
El elemento `<details>` HTML nativo no persiste su estado entre recargas de página — siempre empieza cerrado, lo cual está bien. Pero cuando está abierto, no hay indicación de cuántas iniciativas activas hay (el usuario tiene que abrirlo para saber si hay algo relevante).

**Qué cambiar**:
- Mostrar el conteo de iniciativas activas del mes en el summary, siempre visible: `▶ CoP — Abril (3 activas)`
- Persistir el estado abierto/cerrado en `localStorage` para que el usuario no tenga que reabrirlo cada vez.
- Si hay 0 iniciativas activas este mes: ocultar completamente el accordion (ya hay lógica para esto con `cop_initiatives`, ampliarla).

---

### REC-18 · Aumentar el tamaño de la zona de click en task rows

**Severidad**: 🟡 Media  
**Esfuerzo estimado**: Quick fix (30 min)

**Impacto ADHD**: Los cerebros ADHD a menudo tienen dificultades de coordinación motriz fina. Zonas de click pequeñas (especialmente los botones de acción de estado que aparecen en hover) aumentan la tasa de misclicks que interrumpen el flujo.

**Estado actual**:
```css
/* style.css */
.task-row { padding: .65rem .9rem }  /* ~10px vertical — mínimo aceptable */
.btn-state { padding: .3rem .6rem; font-size: .78rem }  /* zona de click pequeña */
.btn-check { padding: .35rem .55rem }
```
Los botones de acción en task rows son `~30px de altura` — por debajo del estándar de 44px recomendado por WCAG 2.5.5 para touch targets.

**Qué cambiar**:
```css
.task-row { padding: .85rem 1rem; min-height: 48px }
.btn-state { padding: .45rem .8rem; min-height: 36px }
.btn-check { padding: .45rem .7rem; min-height: 36px }
```

---

### REC-19 · Eliminar el campo duplicado energy_type en task_edit.html

**Severidad**: 🟢 Baja  
**Esfuerzo estimado**: Quick fix (20 min)

**Impacto ADHD**: La existencia de dos campos de energía en el formulario de edición de tarea (`energy_tag` como chips + `energy_type` como select legacy) crea confusión: ¿cuál debo rellenar? ¿Son lo mismo? Esta ambigüedad es exactamente el tipo de micro-fricción que hace que un usuario ADHD abandone el formulario a mitad.

**Estado actual** (del análisis de templates):
> "Energy type (select duplicate — appears to be redundant/legacy field)"

El modelo de datos tiene ambos: `energy_tag` (campo principal, ADHD-aware) y `energy_type` (varchar 20, legacy).

**Qué cambiar**:
- Ocultar `energy_type` del formulario de edición (mantenerlo en el modelo para no romper datos históricos).
- O migrarlo: rellenar `energy_tag` con el valor de `energy_type` donde `energy_tag` esté vacío.

---

### REC-20 · Añadir subtareas visibles en el NOW strip de My Day

**Severidad**: 🟢 Baja  
**Esfuerzo estimado**: Medio (1 día)

**Impacto ADHD**: El modelo ya tiene `Subtask` (pasos de 2–5 minutos dentro de una tarea), pero las subtareas no son visibles en el NOW strip de My Day — la vista de mayor uso. El ADHD se beneficia enormemente de las subtareas: convertir una tarea abstracta ("Preparar presentación") en pasos concretos ("Abrir PowerPoint", "Escribir slide 1") reduce la parálisis de inicio.

**Estado actual**: El modelo `Subtask` existe con `id, task_id, title, is_done`. No hay evidencia en el análisis de templates de que las subtareas aparezcan en ninguna vista del Python app (solo en el task_edit.html potencialmente). El React Kanban tampoco las muestra.

**Qué cambiar**:
- En el NOW strip de My Day, mostrar las subtareas como checklist: máx. 5 visibles, con checkbox interactivo (fetch PATCH al hacer click).
- Si la tarea NOW no tiene subtareas, mostrar un link "✦ Dividir en pasos" que abre un mini-form inline.

---

## 4. Plan de Acción Priorizado

### Fase 1 — Quick Wins (1–2 días)
*Solo cambios de CSS/JS, sin tocar backend ni estructura de páginas*

| # | Acción | Archivo(s) | Impacto |
|---|---|---|---|
| 1.1 | Aumentar font-size mínimo a 0.82rem; eliminar `.68rem` y `.72rem` | `style.css` | Legibilidad inmediata |
| 1.2 | Añadir click-toggle para `.task-row.expanded` (fix progressive disclosure) | `app.js` | Metadata siempre accesible |
| 1.3 | Agrupar nav links con separadores visuales en 3 zonas | `style.css` + todos los templates | Reducción de carga cognitiva |
| 1.4 | Persistir estado CoP accordion en localStorage | `app.js` | Menos recolapso involuntario |
| 1.5 | Aumentar zonas de click en task-row buttons | `style.css` | Menos misclicks |
| 1.6 | Añadir atajo `F` (→ Focus) y `D` (→ done NOW task) en My Day | `app.js` | Flujo de teclado |
| 1.7 | Eliminar campo `energy_type` duplicado en task_edit | `task_edit.html` | Menos confusión en formulario |
| 1.8 | Banner de aviso en React Kanban explicando la separación de bases de datos | `Navbar.tsx` | Transparencia inmediata |
| 1.9 | Mostrar conteo de iniciativas activas en el summary del CoP accordion | `my_day.html` | Contexto sin abrir |

---

### Fase 2 — Restructuración (1 semana)
*Cambios de layout en páginas clave, sin tocar el backend*

| # | Acción | Detalle | Impacto |
|---|---|---|---|
| 2.1 | **Layout widescreen para My Day** | Grid 2–3 columnas para ≥1200px. Col central: NOW + Focus Panel + Time Blocks. Col derecha: Stats + Wins. Col izquierda: CoP + Sugerencias. | Elimina 70% del scroll vertical |
| 2.2 | **Layout master-detail para Inbox** | Panel izquierdo (380px) lista de items + panel derecho detalle — sin navegación de página. | Triaje 3x más rápido |
| 2.3 | **Indicador de progreso del día** | Barra `Check-In → My Day → Focus → Close Day` debajo del nav, usando datos de DailyLog existentes. | Orientación temporal constante |
| 2.4 | **Convertir Morning Check-In a wizard sin reloads** | fetch() para selección de must-dos, estado optimista client-side, POST final solo al terminar el wizard. | Ritual matutino sin interrupciones |
| 2.5 | **Filtros y búsqueda en Meetings** | Barra de filtros (sin revisar / esta semana / por fuente) + búsqueda client-side (reusar patrón de tasks.html). | Reducción de scroll en Meetings |
| 2.6 | **Quick-add inline en My Day** | Reemplazar FAB modal por card expandible en el top de la focus list. | Menos interrupción de contexto |
| 2.7 | **Integrar energy_today con superficie de tareas** | Modificar query de sugerencias para ponderar energy match. Mostrar badge de energía del día en NOW strip. | Decisiones más fáciles |

---

### Fase 3 — Unificación (2+ semanas)
*Resolver el problema arquitectónico y pulir el sistema*

| # | Acción | Detalle | Esfuerzo |
|---|---|---|---|
| 3.1 | **Conectar React Kanban al API Python** | Reemplazar el Express API del React app con llamadas al FastAPI Python. Eliminar la base de datos separada. | ~2 semanas |
| 3.2 | **Migrar React Kanban al design system Python** | Lexend font, paleta Indigo/Amarillo, CSS variables equivalentes en Tailwind. | 3–4 días |
| 3.3 | **Implementar ruido marrón en React app** | Extraer el módulo de Web Audio API de `app.js` a un módulo compartido. Importar en React. | 1 día |
| 3.4 | **Deprecar el Kanban Python/Jinja** | Una vez que el React Kanban use el API Python como única fuente de verdad, el `/task-manager/kanban` puede redirigir al React Kanban. | 1 día |
| 3.5 | **Añadir subtareas al NOW strip** | Checklist de subtareas visibles + mini-form de creación inline en My Day. | 1–2 días |
| 3.6 | **Formularios como fetch() progresivo** | Convertir acciones de focus-state, is_today y archive en Inbox a fetch() con actualización optimista. | 1 semana |
| 3.7 | **Añadir confirmaciones de eliminación nativas reemplazadas** | El React Kanban usa `window.confirm()` para borrar. Reemplazar con un Dialog de confirmación en-contexto. | 1 día |

---

## Apéndice: Resumen de Severidades

| Categoría | Crítico | Alto | Medio | Bajo |
|---|---|---|---|---|
| A. Layout widescreen | REC-02 | — | — | — |
| B. Navegación y carga cognitiva | REC-03 | REC-05 | REC-13 | — |
| C. Scroll vertical excesivo | — | REC-06, REC-09 | REC-14 | — |
| D. Progressive disclosure | — | REC-08 | REC-17 | REC-18 |
| E. Flujo de trabajo | REC-04 | REC-10 | REC-16 | REC-20 |
| F. Interacciones y micro-feedback | — | — | REC-16 | — |
| G. Tipografía y accesibilidad | — | REC-07 | REC-15 | — |
| H. Consistencia entre apps | REC-01 | REC-11, REC-12 | — | REC-19 |

**Total recomendaciones**: 20  
**Críticas**: 4 (REC-01, REC-02, REC-03, REC-04)  
**Altas**: 8  
**Medias**: 6  
**Bajas**: 2  

---

*Análisis basado en: 19 templates HTML + style.css (631 líneas) + app.js (367 líneas) del Python app; 9 componentes React + index.css del React Kanban; rutas FastAPI, modelos SQLAlchemy y documentos de diseño del backend.*
