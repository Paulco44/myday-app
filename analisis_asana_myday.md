# Lo que MyDay puede aprender de Asana

## Filosofía clave de Asana

Asana vive por un principio: **"clarity punctuated by energy"** — el canvas es limpio y neutral; el color solo aparece en momentos de acción (completar, celebrar, alertar). Esto entrena al cerebro a asociar color con significado, no con decoración.

Para un usuario con ADHD esto es doblemente importante: menos ruido visual = menos distracción, y las señales de color son más salientes cuando son escasas.

**Fuentes:** [Inside Asana — Teamwork is Beautiful](https://asana.com/inside-asana/teamwork-is-beautiful-introducing-asanas-new-look), [Asana Design Tokens Talk (Schema 2021)](https://www.youtube.com/watch?v=ylDed18OVdY)

---

## Recomendaciones priorizadas

### Tier 1 — Alto impacto, esfuerzo medio (lo que más "slick" hace a Asana)

#### 1. Task detail como panel lateral, no página separada

**Asana:** Click en un task → se abre un panel derecho (~35% del ancho) que se desliza. La lista sigue visible a la izquierda. `Esc` cierra. `Tab+X` va a full-screen.

**MyDay hoy:** Click en un task → navega a `/task-manager/tasks/{id}/edit` — una página completamente nueva. Pierdes contexto de la lista.

**Propuesta:** En la página de Tasks (y en My Day), click en un task abre un `<aside>` deslizable a la derecha con todos los campos del task (título, descripción, subtasks, prioridad, energy tag, time block, due date, project). Editar inline sin salir. `Esc` cierra y vuelve a la lista.

**Por qué importa para ADHD:** Cambiar de página rompe el flujo. El panel lateral mantiene el contexto visual de "dónde estaba" mientras trabajas en el detalle. Es la diferencia entre "perderse" y "profundizar".

**Implementación:** Nuevo `<aside id="task-detail-pane">` con CSS `position: fixed; right: 0; transform: translateX(100%)` que anima a `translateX(0)`. Fetch del task data via API y render con JavaScript. No requiere React.

---

#### 2. Completion circle en vez de checkbox cuadrado

**Asana:** El checkbox de "done" es un **círculo hueco**. Al hacer hover, aparece un checkmark fantasma (preview del resultado). Al completar, el círculo se llena con un pulso de color.

**MyDay hoy:** Usa botones de texto ("✓ Done") o checkboxes cuadrados estándar.

**Propuesta:** Reemplazar los botones/checkboxes de completar con un SVG circular:
- Estado normal: círculo hueco, borde `var(--md-border)`
- Hover: checkmark fantasma aparece (opacity 0.3, color `var(--md-success)`)
- Done: llena con `var(--md-success)`, breve pulso de escala (1 → 1.15 → 1, 200ms)
- El task title se atenúa con `text-decoration: line-through; opacity: 0.5` brevemente antes de desaparecer

**Por qué importa para ADHD:** La micro-recompensa visual del círculo llenándose es un dopamine hit pequeño pero consistente. Asana reporta que este detalle es de los más elogiados por usuarios.

---

#### 3. Inline task creation con Enter

**Asana:** Estás en la lista, presionas Enter → aparece un input inline justo debajo del task actual. Escribes el nombre, Enter de nuevo → se crea y aparece otro input. Flujo continuo sin modal.

**MyDay hoy:** Quick Add es un `<dialog>` modal con varios campos. Funcional pero rompe el flujo.

**Propuesta:** En My Day y Tasks page, agregar un input inline persistente al final de cada sección (NOW, NEXT, LATER, sugerencias):
- Input con placeholder "Add a task..." (estilo Asana: borde solo en focus, no en reposo)
- Enter crea el task en esa sección con defaults (prioridad medium, sin fecha)
- Después de crear, el cursor queda en un nuevo input para encadenar
- Mantener el Quick Add modal (`N`) para cuando quieres agregar metadata completa

**Por qué importa para ADHD:** Captura rápida = menor fricción = más probabilidad de externalizar pensamientos antes de olvidarlos. El modal obliga a un "cambio de modo" cognitivo.

---

#### 4. Secciones colapsables con contadores

**Asana:** Cada sección (Today, Upcoming, Later) tiene un header clickable con chevron que colapsa/expande. El header muestra el conteo de tasks.

**MyDay hoy:** Las secciones en My Day (NOW, NEXT, LATER, Suggestions) están siempre visibles. No se colapsan.

**Propuesta:** Hacer cada sección colapsable:
- Click en el header → toggle animado (chevron rota, contenido slide up/down)
- Header muestra: nombre + conteo (ej: "LATER TODAY · 3 tasks")
- Guardar estado en localStorage
- Default: NOW siempre expandido, LATER colapsado si tiene 4+ items

**Por qué importa para ADHD:** Reduce la carga visual inmediata. Ver 15 tasks de golpe causa parálisis. Ver "NOW: 1 task" + secciones cerradas da foco.

---

### Tier 2 — Impacto medio, esfuerzo bajo-medio

#### 5. Ghost affordances en hover

**Asana:** Al hacer hover sobre una fila de task, aparecen acciones contextuales que no existían visualmente: drag handle, botones de acción rápida, el checkmark fantasma.

**MyDay hoy:** Los botones siempre están visibles (Done, Remove, etc.), creando ruido visual constante.

**Propuesta:** Ocultar acciones secundarias y mostrarlas solo en hover:
- Default visible: solo el título, tags de metadata, y el completion circle
- Hover: aparecen "→ NOW", "→ NEXT", "→ LATER", "✕", drag handle
- Fade in rápido (opacity 0 → 1, 100ms)
- En mobile: las acciones aparecen con swipe o long-press

**Por qué importa para ADHD:** Menos botones visibles = interfaz más limpia = el ojo va al contenido (el task) en vez de a los controles. Cuando necesitas actuar, un hover revela todo.

---

#### 6. Sort/filter con indicador visual activo

**Asana:** Cuando un sort o filtro está activo, el botón cambia de color (se pone azul). Es un recordatorio persistente de "estás viendo un subset".

**MyDay hoy:** La tabla de Tasks tiene sorting por columnas pero sin indicador visual claro.

**Propuesta:** En Tasks page:
- Cuando sort está activo: el header de la columna se colorea con `var(--md-primary)` + flecha direccional
- Agregar un chip "Sorted by: Priority ↓" encima de la tabla que se puede clickar para remover
- Si hay filtros activos: chip similar "Filtered: status = doing" con "×" para limpiar

---

#### 7. Row hover highlight sutil

**Asana:** Hover sobre una fila → el background cambia sutilmente (de blanco a un gris muy tenue).

**MyDay hoy:** No hay feedback visual al hacer hover sobre tasks en la lista.

**Propuesta:** Agregar a `.task-card:hover` o equivalente:
```css
background: var(--md-surface-alt);
transition: background 80ms ease;
```
Pequeño pero hace la interfaz sentirse "viva" y responsive.

---

### Tier 3 — Nice-to-have, requiere más trabajo

#### 8. Celebraciones sutiles al completar

**Asana:** Completar varios tasks consecutivos trigger una criatura animada que vuela por la pantalla (unicornio, narwhal, etc.). Es opt-in y random.

**MyDay ya tiene:** Confetti en Evening Reset cuando completas todos los wins.

**Propuesta:** Extender a My Day: al marcar done el task NOW, mostrar una micro-celebración:
- No criaturas voladoras (demasiado estímulo para ADHD)
- Sí: un breve pulse de color en el streak counter + el número incrementa con animación
- Quizás: particle burst muy sutil (3-5 partículas, 400ms, solo la primera vez del día)

**Fuente:** [Asana Celebrations](https://asana.com/inside-asana/new-celebrations)

---

#### 9. Auto-promoción de tasks por fecha

**Asana:** Tasks en Later se mueven automáticamente a Upcoming 1 semana antes del due date, y a Today a medianoche del due date.

**MyDay hoy:** Las sugerencias se ordenan por urgencia pero no se mueven automáticamente entre secciones.

**Propuesta:** Implementar auto-promoción suave:
- Si un task en Later tiene due_date = hoy: aparece en las sugerencias de My Day con badge "due today" (ya existe parcialmente)
- Si un task en Later tiene due_date = mañana: aparece con badge "due tomorrow"
- NO mover automáticamente a NOW/NEXT (violaría el principio de control del usuario en ADHD). Solo hacer visible en sugerencias.

---

#### 10. Multi-select con Shift+Click

**Asana:** Shift+Click selecciona un rango de tasks para bulk actions (completar, mover, borrar).

**MyDay hoy:** No hay multi-select.

**Propuesta:** En Tasks page, permitir Shift+Click para seleccionar rango. Al tener múltiples seleccionados, mostrar toolbar flotante: "3 selected: [✓ Done] [→ NOW] [→ NEXT] [✕ Delete]"

---

## Lo que NO adoptar de Asana

| Pattern de Asana | Por qué no para MyDay |
|---|---|
| Multi-homing (task en múltiples proyectos) | Complejidad innecesaria para uso personal. MyDay tiene 1 user. |
| Assignee / Collaborators | Single-user app. No hay a quién asignar. |
| Comments / Activity feed | No hay equipo. Las notas del task son suficientes. |
| Sidebar con projects/teams | MyDay no tiene muchos proyectos. El nav horizontal es más simple. |
| Custom fields dinámicos | Los campos de MyDay (energy, time_block, priority) son suficientes y están adaptados a ADHD. |
| Mode-based navigation | Demasiado complejo para una app personal. |
| Tab como modifier key | MyDay ya tiene shortcuts con letras simples (F, D, N, J, K). Más intuitivo para un solo usuario. |

---

## Resumen visual: MyDay hoy vs. MyDay con adopciones

| Aspecto | MyDay actual | MyDay con adopciones |
|---|---|---|
| Ver detalle de un task | Navega a página nueva | Panel lateral deslizable |
| Completar un task | Botón "✓ Done" | Círculo con checkmark fantasma → pulso |
| Crear task rápido | Modal Quick Add | Input inline + modal para metadata |
| Densidad visual | Todos los botones siempre visibles | Botones aparecen en hover |
| Secciones de My Day | Siempre abiertas | Colapsables con conteo |
| Feedback en hover | Ninguno | Highlight sutil de fila |
| Sort/filter activo | Sin indicador | Chip coloreado visible |

---

## Orden de implementación sugerido

```
Sprint 1 (máximo impacto visual):
  - Completion circles (#2)
  - Row hover highlight (#7)
  - Ghost affordances en hover (#5)

Sprint 2 (flujo de trabajo):
  - Inline task creation (#3)
  - Secciones colapsables (#4)

Sprint 3 (arquitectura):
  - Task detail panel lateral (#1) — este es el más grande

Sprint 4 (polish):
  - Sort/filter indicators (#6)
  - Celebraciones sutiles (#8)
  - Auto-promoción (#9)
```

Sprint 1 es puro CSS + SVG — bajo riesgo, se puede hacer desde el design system sin tocar backend.
Sprint 3 es el más ambicioso pero el que más transformaría la experiencia.
