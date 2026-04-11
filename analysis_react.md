# React Kanban App — Component Analysis

## File Tree Covered

```
src/
├── App.tsx
├── index.css
├── hooks/use-mobile.tsx
├── pages/Board.tsx
└── components/
    ├── layout/Navbar.tsx
    └── kanban/
        ├── KanbanBoard.tsx
        ├── KanbanCard.tsx
        ├── KanbanCardPreview.tsx
        ├── KanbanColumn.tsx
        ├── KanbanColumnPreview.tsx
        ├── CreateCardDialog.tsx
        ├── CreateColumnDialog.tsx
        ├── EditCardSheet.tsx
        └── EditColumnDialog.tsx
```

---

## 1. App Shell (`App.tsx`)

### Providers
- `QueryClientProvider` (TanStack React Query) — `staleTime: 5min`, `refetchOnWindowFocus: false`
- `TooltipProvider` (shadcn/ui)
- `WouterRouter` with `BASE_URL` prefix support
- `Toaster` (toast notifications)

### Routing
- Single route: `"/" → BoardPage`
- Catch-all renders `NotFound`

---

## 2. Page Layout (`Board.tsx`)

### Overall Structure
```
div.min-h-screen.flex.flex-col.bg-gradient-to-br(from-background via-background to-secondary/30)
├── div.absolute.inset-0.z-0  ← decorative background hero image (pointer-events-none, opacity-30)
│   └── img (hero-abstract.png, w-full h-[60vh] object-cover mix-blend-multiply)
│   └── div.absolute.inset-0.bg-gradient-to-b(transparent → background)  ← fade overlay
├── Navbar (sticky top-0 z-50)
└── main.flex-1.relative.z-10.overflow-hidden.flex.flex-col
    ├── div.px-6.pt-8.pb-4.shrink-0  ← board title block
    │   ├── h2.text-3xl.font-display.font-bold.tracking-tight  "Project Alpha"
    │   └── p.text-muted-foreground.mt-1
    └── KanbanBoard
```

### Key layout traits
- **Full-height page**: `min-h-screen flex flex-col`
- **Background decor**: absolutely positioned, `z-0`, `overflow-hidden`, `pointer-events-none`; hero image covers top 60vh with `mix-blend-multiply` blending
- **Main content area**: `flex-1 relative z-10 overflow-hidden flex flex-col` — grows to fill remaining height, clips overflow at this boundary
- Title block has `shrink-0` so it never compresses when the board grows tall

---

## 3. Navbar (`Navbar.tsx`)

### Layout
```
header.sticky.top-0.z-50.w-full.border-b.bg-white/80.backdrop-blur-md.shadow-sm
└── div.container.mx-auto.px-4.h-14.flex.items-center.gap-6
    ├── Link (logo + "MyDay" wordmark)  ← shrink-0, hover:scale-[1.02]
    ├── nav.flex.items-center.gap-1  ← nav links
    └── div.ml-auto.hidden.md:flex  ← "Connected" status pill (hidden on mobile)
```

### Active state
- Active link: `bg-primary/10 text-primary`; inactive: `text-muted-foreground hover:text-foreground hover:bg-accent`
- Active detection via `window.location.pathname` comparison (not a React router hook)

### Nav links
- "Kanban" — internal `<Link>` via wouter
- "My Day", "Tasks", "CoP Admin" — external `<a>` tags pointing to `/task-manager/*`

### Status indicator
- Animated green dot (`animate-pulse`) + "Connected" text — hidden below `md` breakpoint

---

## 4. KanbanBoard (`KanbanBoard.tsx`)

### State
| State | Type | Purpose |
|---|---|---|
| `columns` | `Column[]` | Locally sorted column list (optimistic) |
| `cards` | `Card[]` | All cards globally (filtered per-column when rendering) |
| `activeColumn` | `Column \| null` | Column being dragged (drives DragOverlay) |
| `activeCard` | `Card \| null` | Card being dragged (drives DragOverlay) |
| `editingCard` | `Card \| null` | Card open in EditCardSheet |

`columnsRef` and `cardsRef` store current values for use inside `useCallback` closures without stale closure issues.

### Data fetching
- `useGetColumns()` + `useGetCards()` from `@workspace/api-client-react`
- Both sorted by `position` on arrival, stored in state
- Loading state: centred `Loader2` spinner (`w-8 h-8 animate-spin text-primary`)

### Board container
```
div.flex-1.flex.overflow-x-auto.overflow-y-hidden.p-6.gap-6.items-start.h-[calc(100vh-4rem)]
```
- **Horizontal scroll**: `overflow-x-auto overflow-y-hidden` — board scrolls left/right, never vertically
- **Fixed height**: `h-[calc(100vh-4rem)]` — fills remaining viewport height
- **Column spacing**: `gap-6` (24px)
- **Alignment**: `items-start` — columns align to top, allowing variable-height columns

### DnD Context
- Library: `@dnd-kit/core` + `@dnd-kit/sortable`
- Sensor: `PointerSensor` with `activationConstraint: { distance: 10 }` (prevents accidental drags on click)
- Collision detection: custom strategy —
  - Columns use `closestCenter` scoped to column droppables only
  - Cards use `pointerWithin` first (catches empty columns), falls back to `rectIntersection`

### Drag logic

**onDragStart**: Sets `activeColumn` or `activeCard` based on `data.current.type`

**onDragOver** (card movement only):
- Card → Card: cross-column boundary only — updates `columnId` and reorders via `arrayMove`; same-column reordering is deferred to `onDragEnd` (handled visually by CSS transforms from `verticalListSortingStrategy`)
- Card → Column: moves card into empty column (updates `columnId`)

**onDragEnd**:
- Column: recalculates positions (`arrayMove` → assign index as `position`), fires `updateColumn` for all changed columns in parallel; invalidates column query on last completion
- Card: commits same-column reorder if needed, then calls `updateCard({ columnId, position: ai })`; invalidates cards query on success

### DragOverlay
```jsx
<DragOverlay>
  {activeColumn && <KanbanColumnPreview ... />}
  {activeCard && (
    <div className="rotate-2 scale-105 opacity-95 rounded-xl">
      <KanbanCardPreview card={activeCard} />
    </div>
  )}
</DragOverlay>
```
- Column preview: `rotate-1` on the preview component itself
- Card preview: `rotate-2 scale-105 opacity-95` — lifted, slightly rotated drag ghost

### Column rendering
```jsx
<SortableContext items={columnsId} strategy={horizontalListSortingStrategy}>
  {columns.map(col => <KanbanColumn ... cards={cards.filter(c => c.columnId === col.id)} />)}
</SortableContext>
<CreateColumnDialog highestPosition={highestColPos} />
```

### EditCardSheet
- Mounted outside DndContext, at fragment root
- Controlled by `editingCard` state; `key={editingCard?.id ?? "none"}` resets form on card change

---

## 5. KanbanColumn (`KanbanColumn.tsx`)

### DnD
- `useSortable({ id: toColDndId(col.id), data: { type: "Column", column } })`
- CSS transform applied via `CSS.Transform.toString(transform)`

### Drag placeholder state (`isDragging`)
```
div.shrink-0.w-[300px].rounded-2xl.bg-secondary/50.border-2.border-dashed.border-primary/50.opacity-40.flex.flex-col.h-[500px]
```
- Fixed 500px height placeholder with dashed primary border, 40% opacity

### Normal state
```
div.shrink-0.w-[300px].flex.flex-col.bg-secondary/30.rounded-2xl.border.border-border/50.shadow-sm
  .max-h-full.overflow-hidden.touch-none.select-none
```
- **Fixed width**: `w-[300px] shrink-0` — always 300px, never compresses
- **Height**: `max-h-full` + `overflow-hidden` — constrained by parent
- `touch-none select-none` on the column element enables pointer drag without text selection

### Column header
```
div.p-4.flex.items-center.justify-between.cursor-grab.active:cursor-grabbing
  .hover:bg-secondary/50.transition-colors.rounded-t-2xl.border-b.border-border/40
```
- Entire header is the grab handle (pointer events propagate to dnd listeners)
- Title + card count badge: `pointer-events-none` to avoid interfering with drag
- `EditColumnDialog` wrapped in `onPointerDown: e.stopPropagation()` to prevent column drag when clicking the menu button

### Card list area
```
div.flex-1.overflow-y-auto.overflow-x-hidden.p-3.custom-scrollbar.touch-auto.select-auto
  [onPointerDown: e.stopPropagation()]
```
- `flex-1` — grows to fill column height
- **Vertical scroll**: `overflow-y-auto` — cards scroll within column
- `touch-auto select-auto` restores normal touch/text behaviour inside card area (overriding parent `touch-none`)
- `custom-scrollbar` class (utility from index.css — not defined there, likely from a shadcn or global style)
- `onPointerDown: e.stopPropagation()` prevents card interactions from triggering column drag

### Card list inner container
```
div.flex.flex-col.min-h-[50px]
```
- `min-h-[50px]` ensures empty columns have a drop target area

### DnD ID helpers
```ts
toColDndId = (id: number) => `col-${id}`
fromColDndId = (dndId) => Number(String(dndId).replace("col-", ""))
```

---

## 6. KanbanCard (`KanbanCard.tsx`)

### Modes
The card has three render modes:

| Mode | Trigger | Appearance |
|---|---|---|
| **Drag placeholder** | `isDragging === true` | Dashed `border-primary/50`, `bg-primary/5`, `opacity-50`, fixed `h-[80px]` |
| **Inline edit form** | `isEditing === true` | Bordered form card with fields |
| **View (default)** | — | `KanbanCardPreview` wrapped in drag container |

### DnD integration
- `useSortable({ id: toCardDndId(card.id), data: { type: "Card", card }, disabled: isEditing })`
- Drag disabled while editing to prevent accidental moves
- Outer container: `cursor-grab active:cursor-grabbing touch-none group`

### Inline edit form (isEditing)
```
form.bg-card.border-2.border-primary/50.rounded-xl.p-3.shadow-lg.space-y-2.5
├── input (title) — transparent, no border, autoFocus
├── textarea (description) — bg-secondary/50, 2 rows, resize-none
├── div.flex.gap-2
│   ├── select (priority) — flex-1, bg-secondary/50
│   └── input[type=date] (dueDate) — flex-1, bg-secondary/50
└── div.flex.items-center.justify-between
    ├── "More options" → triggers EditCardSheet (handleOpenFull)
    └── div [Cancel button | Save button]
```

Keyboard shortcuts:
- `Escape` → cancel
- `Cmd/Ctrl + Enter` → submit

### View mode
- Clicking anywhere on the card sets `isEditing = true`
- `handleOpenFull` (via Maximize2 button in preview) opens the full EditCardSheet instead

### Form schema (Zod)
```ts
{ title: string (min 1), description?: string, priority?: "low"|"medium"|"high"|"none", dueDate?: string }
```

### DnD ID helpers
```ts
toCardDndId = (id: number) => `card-${id}`
fromCardDndId = (dndId) => Number(String(dndId).replace("card-", ""))
```

---

## 7. KanbanCardPreview (`KanbanCardPreview.tsx`)

Used in both the interactive card view and the DragOverlay.

### Structure
```
div.mb-3.bg-card.border.border-border/60.rounded-xl.p-4.shadow-sm
  .hover:border-primary/40.hover:shadow-md.transition-all.duration-150.relative
├── button (Maximize2 icon) — absolute top-2.5 right-2.5, opacity-0 group-hover:opacity-100
├── div.flex.items-start.gap-2.mb-2.pr-6
│   └── h4.font-medium.text-sm.text-foreground.leading-tight.line-clamp-2.flex-1
└── (conditional metadata row, when priority/dueDate/description exist)
    div.flex.items-center.flex-wrap.gap-2.mt-3.pt-3.border-t.border-border/40
    ├── priority badge (conditional)
    ├── dueDate badge (conditional)
    └── AlignLeft icon (conditional, ml-auto)
```

### Priority badge colors
| Priority | Classes |
|---|---|
| `high` | `bg-red-50 text-red-700 border-red-200` |
| `medium` | `bg-amber-50 text-amber-700 border-amber-200` |
| `low` | `bg-blue-50 text-blue-700 border-blue-200` |

All badges: `text-[10px] font-semibold px-2 py-0.5 rounded-md border uppercase tracking-wider` with a `Flag` icon

### Due date badge
- Normal: `bg-secondary text-secondary-foreground text-[11px]`
- Overdue: `bg-destructive/10 text-destructive border border-destructive/20`
- Date formatted as `"MMM d"` via `date-fns/format`

### Description indicator
- Just an `AlignLeft` icon (`w-4 h-4`) positioned `ml-auto` — indicates description exists without showing text

### Expand button (onFullEdit)
- Absolutely positioned `Maximize2` icon (`w-3.5 h-3.5`)
- `opacity-0 group-hover:opacity-100` — only visible on hover of parent (group class on KanbanCard outer div)
- `focus:opacity-100` for keyboard accessibility

---

## 8. KanbanColumnPreview (`KanbanColumnPreview.tsx`)

Used exclusively in the `DragOverlay` when dragging a column.

```
div.shrink-0.w-[300px].flex.flex-col.bg-secondary/30.rounded-2xl.border.border-border/50
  .shadow-2xl.opacity-95.rotate-1.max-h-[600px].overflow-hidden
├── header — same structure as KanbanColumn header (no drag listeners, no EditColumnDialog)
└── div.flex-1.overflow-hidden.p-3
    ├── cards.slice(0, 3).map(card => <KanbanCardPreview />)  ← max 3 cards shown
    └── (if cards.length > 3) p.text-xs.text-muted-foreground.text-center  "+N more"
```

Key differences from KanbanColumn:
- `shadow-2xl` (elevated drag ghost)
- `rotate-1` (subtle tilt for "picked up" feel)
- `opacity-95` (slightly translucent)
- No `useSortable` (prevents duplicate droppable registration)
- Cards capped at 3 with overflow count label
- No `overflow-y-auto` — cards are not scrollable in preview

---

## 9. CreateCardDialog (`CreateCardDialog.tsx`)

### Trigger
```
Button variant="ghost" className="w-full mt-2 h-10 text-muted-foreground
  hover:text-foreground justify-start px-3 hover:bg-secondary/80 rounded-xl"
```
Full-width ghost button at bottom of card list, left-aligned "+ Add Card"

### Dialog
```
DialogContent className="sm:max-w-[500px] rounded-2xl"
├── DialogHeader (title: "New Task", description)
└── Form (space-y-4 mt-4)
    ├── title: Input h-12 px-4 rounded-xl bg-secondary/30
    ├── description: Textarea min-h-[100px] rounded-xl bg-secondary/30 resize-none p-4
    ├── div.grid.grid-cols-2.gap-4
    │   ├── priority: Select h-12 rounded-xl bg-secondary/30
    │   └── dueDate: Input[type=date] h-12 px-4 rounded-xl bg-secondary/30
    └── div.flex.justify-end.pt-4
        └── Button (submit) h-12 px-8 rounded-xl gradient + shadow
```

### Submit button style
`bg-gradient-to-r from-primary to-primary/80 shadow-lg shadow-primary/25 hover:shadow-xl hover:shadow-primary/30 transition-all hover:-translate-y-0.5 active:translate-y-0 active:shadow-md`
— Gradient fill, primary-tinted drop shadow, lift on hover, returns on active

### On success: invalidates cards query, shows toast "Task added", closes dialog, resets form
### On error: destructive toast with error message

---

## 10. CreateColumnDialog (`CreateColumnDialog.tsx`)

### Trigger
```
Button variant="outline" className="h-12 border-dashed border-2 bg-transparent
  hover:bg-secondary/50 shrink-0 w-[300px] flex items-center justify-center gap-2
  text-muted-foreground hover:text-foreground"
```
Dashed outline button, 300px wide (matches column width), positioned after all columns in board flex row

### Dialog
```
DialogContent className="sm:max-w-[425px] rounded-2xl"
├── DialogHeader (title: "New Column")
└── Form (space-y-6 mt-4)
    ├── title: Input h-12 px-4 rounded-xl bg-secondary/30, max 50 chars
    └── div.flex.justify-end.pt-2
        └── Button (submit) — same gradient style as CreateCardDialog
```

### On success: invalidates columns query, shows toast, closes dialog, resets form

---

## 11. EditCardSheet (`EditCardSheet.tsx`)

### Shell
```
Sheet (right-side panel)
└── SheetContent className="sm:max-w-[450px] sm:w-[450px] w-full p-0 flex flex-col border-l-0 shadow-2xl"
    ├── div.p-6.border-b.border-border/50.bg-secondary/20  ← header zone
    │   └── SheetHeader (title: "Edit Task")
    ├── div.flex-1.overflow-y-auto.p-6  ← scrollable form area
    │   └── Form (space-y-6)
    │       ├── title: Input h-12 rounded-xl bg-secondary/30
    │       ├── description: Textarea min-h-[160px] rounded-xl bg-secondary/30 resize-none p-4
    │       └── div.grid.grid-cols-2.gap-4
    │           ├── priority: Select h-12 rounded-xl bg-secondary/30
    │           └── dueDate: Input[type=date] h-12 rounded-xl bg-secondary/30
    └── div.p-6.border-t.border-border/50.bg-background.flex.items-center.justify-between  ← action bar
        ├── Button variant="destructive" size="icon" h-12 w-12 rounded-xl (Trash2)
        └── Button (submit) h-12 px-8 — same gradient style
```

### Layout pattern
- `p-0` on SheetContent — all padding managed internally
- Three vertical zones: sticky header, scrollable body (`flex-1 overflow-y-auto`), sticky action bar
- `border-l-0` removes default left border, `shadow-2xl` adds dramatic depth
- Full width on mobile (`w-full`), 450px on sm+

### Delete flow
- `window.confirm()` prompt before deletion (browser native)
- `useDeleteCard` mutation; on success invalidates cards, shows toast, closes sheet

### Form ID pattern
- Form has `id="edit-card-form"`, submit button uses `form="edit-card-form"` attribute — decoupled form from submit button for the sticky footer pattern

---

## 12. EditColumnDialog (`EditColumnDialog.tsx`)

### Trigger
```
Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-foreground"
  <MoreHorizontal className="h-4 w-4" />
```
Small icon button in column header

### Dialog
```
DialogContent className="sm:max-w-[425px] rounded-2xl"
├── DialogHeader (title: "Edit Column")
└── Form (space-y-6 mt-4)
    ├── title: Input h-12 px-4 rounded-xl bg-secondary/30
    └── div.flex.items-center.justify-between.pt-2
        ├── Button variant="destructive" size="icon" h-12 w-12 rounded-xl (Trash2)
        └── Button (submit) — same gradient style
```

### Delete flow
- `window.confirm()` prompt
- `useDeleteColumn` — on success invalidates both columns AND cards queries (cascade delete)

---

## 13. Design System (`index.css`)

### Typography
| Token | Font | Usage |
|---|---|---|
| `font-sans` / body | Inter (400, 500, 600, 700) | Body text, UI labels |
| `font-display` / headings | Outfit (500–800) | h1–h6, board title, dialog titles, logo |

Base: `antialiased`, selection highlight `bg-primary/20 text-primary`

### Color palette (light mode)
| Token | Value | Description |
|---|---|---|
| `background` | `hsl(210 33% 98%)` | Very light cool gray |
| `foreground` | `hsl(222 47% 11%)` | Deep slate |
| `card` | `hsl(0 0% 100%)` | Pure white |
| `primary` | `hsl(221 83% 53%)` | Vivid blue |
| `secondary` | `hsl(210 40% 96%)` | Light gray-blue |
| `muted-foreground` | `hsl(215 16% 47%)` | Medium slate |
| `destructive` | `hsl(0 84% 60%)` | Red |
| `border` | `hsl(214 32% 91%)` | Subtle gray |

### Color palette (dark mode)
| Token | Light → Dark |
|---|---|
| `background` | `98%` lightness → `11%` lightness |
| `primary` | `hsl(221 83% 53%)` → `hsl(217 91% 60%)` (slightly lighter) |
| `card`/`popover` | Match background (no card lift) |
| `border`/`input` | `hsl(217 33% 17%)` |

### Border radius
- `--radius: 0.75rem` (12px)
- Derived: `sm = 8px`, `md = 10px`, `lg = 12px`, `xl = 16px`
- Components use `rounded-xl` (16px) and `rounded-2xl` (24px) explicitly

### Elevation utilities
```css
.hover-elevate::after  { transition: background-color 0.2s; }
.hover-elevate:hover::after { background: var(--elevate-1); }  /* rgba(0,0,0,0.03) */
.active-elevate-2:active::after { background: var(--elevate-2); }  /* rgba(0,0,0,0.08) */
```
Pseudo-element overlay approach for elevation (used optionally, not seen in current components).

---

## 14. `use-mobile.tsx`

### Implementation
```ts
const MOBILE_BREAKPOINT = 768  // matches Tailwind's 'md'
useIsMobile() → boolean
```
- Uses `window.matchMedia` with a `change` listener for reactive updates
- Initializes synchronously with `window.innerWidth < 768`
- Returns `false` (not mobile) until effect runs

**Note**: `useIsMobile` is defined but not imported by any kanban component in this app — the Navbar uses a pure CSS `hidden md:flex` approach instead.

---

## 15. Cross-Cutting Patterns

### Layout architecture
```
min-h-screen flex flex-col            ← full-height page shell
  └── Navbar (sticky, z-50, h-14)
  └── main flex-1 overflow-hidden flex flex-col    ← clips board overflow
        └── Board title (shrink-0)
        └── KanbanBoard flex-1 overflow-x-auto overflow-y-hidden h-[calc(100vh-4rem)]
              └── columns (flex row, gap-6, items-start)
                    └── KanbanColumn (w-[300px] shrink-0, max-h-full, overflow-hidden)
                          └── card list (flex-1 overflow-y-auto)
```

### Scrolling strategy
- **Horizontal**: Board container — `overflow-x-auto overflow-y-hidden`
- **Vertical**: Per-column card lists — `overflow-y-auto` inside fixed-width columns
- **No vertical page scroll**: Outer `overflow-hidden` on `main` + fixed `h-[calc(100vh-4rem)]` on board

### Optimistic DnD state management
1. `onDragOver` immediately updates local `cards` state (via `setCards`) for visual feedback
2. `cardsRef.current` kept in sync for use in `onDragEnd` callback (avoids stale closure)
3. `onDragEnd` commits changes to API (`updateCard`/`updateColumn`)
4. On success, React Query cache invalidated to sync authoritative server state
5. No rollback on error — API failure leaves optimistic state in place (potential stale UI)

### Form patterns
- All forms: `react-hook-form` + `zodResolver`
- All inputs: `h-12 px-4 rounded-xl bg-secondary/30` (consistent styling)
- All submit buttons: gradient primary + shadow-primary/25 + lift-on-hover animation
- Priority field: always 4 options (none/low/medium/high); "none" transforms to `null`/`undefined` before API

### Modal/overlay types used
| Component | Overlay type | Position |
|---|---|---|
| CreateCardDialog | Dialog (centered modal) | Center of screen |
| CreateColumnDialog | Dialog (centered modal) | Center of screen |
| EditColumnDialog | Dialog (centered modal) | Center of screen |
| EditCardSheet | Sheet (side panel) | Right edge, 450px wide |
| DragOverlay | Portal overlay | Follows cursor |

### Interaction UX details
- Cards: single-click → inline edit; Maximize2 hover button → full Sheet
- Column drag handle: entire header area; ESC key propagation prevented from reaching parent
- `activationConstraint: { distance: 10 }` means you must drag 10px before DnD activates — prevents firing on regular clicks
- Drag ghosts: columns `rotate-1`, cards `rotate-2 scale-105 opacity-95`
- Inline card edit: `Escape` cancels, `Cmd/Ctrl+Enter` saves
- Delete confirmations: native `window.confirm()` (no custom confirmation dialog)

### Responsive behavior
- Navbar: status pill hidden below `md` (`hidden md:flex`)
- Board: no responsive breakpoints — always horizontal scroll layout; no column stacking on mobile
- Dialogs: `sm:max-w-[425px|500px]` — slightly narrower on very small screens
- EditCardSheet: `w-full` on mobile, `sm:w-[450px]` on sm+
- `useIsMobile` hook defined but unused in current kanban components
