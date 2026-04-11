# MyDay Template & Style Analysis

## Files Analyzed

**Templates (19 files):**
- `index.html` — Landing/dashboard page
- `my_day.html` — Primary daily view (largest: 54KB)
- `kanban.html` — Kanban board
- `focus.html` — Pomodoro-style focus timer
- `tasks.html` — All-tasks list with sortable table
- `task_edit.html` — Full task edit form
- `morning_checkin.html` — Morning ritual / setup flow
- `morning_checkin_pick.html` — Must-do selection step
- `close_day.html` — Evening wrap-up / day review
- `inbox.html` — Meeting inbox list
- `inbox_detail.html` — Individual inbox item triage
- `meetings.html` — Meetings timeline view
- `notes.html` — Reference notes list
- `note_detail.html` — Individual note with Notion export
- `projects_list.html` — Projects overview
- `project_detail.html` — Individual project with Notion export
- `cop_initiatives.html` — CoP admin (wide table)
- `cop_import.html` — CSV bulk import
- `integrations_notion.html` — Notion integration config

**Static files:**
- `style.css` — Global design system (631 lines)
- `app.js` — Shared JS: theme, noise, kanban behaviors (367 lines)

---

## 1. style.css Analysis

### Color Palette / CSS Variables

The app uses a dual-theme system declared in `:root` (light) and `html.dark` (dark).

**Light theme (default — Stone/Light):**
| Token | Value | Role |
|---|---|---|
| `--bg` | `#F5F5F4` | Page background |
| `--surface` | `#FFFFFF` | Card/nav background |
| `--border` | `#E5E7EB` | Default border |
| `--border-focus` | `#4F46E5` | Focus ring border |
| `--text` | `#1C1917` | Primary text |
| `--text-muted` | `#6B7280` | Secondary text |
| `--text-faint` | `#9CA3AF` | Tertiary/placeholder |
| `--accent` | `#4F46E5` | Indigo — primary action |
| `--accent-hover` | `#4338CA` | Darker indigo |
| `--accent-soft` | `#E0E7FF` | Accent background tint |
| `--accent-text` | `#3730A3` | Text on accent-soft |
| `--success` | `#22C55E` | Green |
| `--success-soft` | `#DCFCE7` | Green tint |
| `--warning` | `#F97316` | Orange |
| `--warning-soft` | `#FFEDD5` | Orange tint |
| `--danger` | `#DC2626` | Red |
| `--focus-bg` | `#EEF2FF` | Focus mode background |
| `--focus-ring` | `#A5B4FC` | Focus ring color |
| `--ctrl-bg` | `#F3F4F6` | Control button background |

**Dark theme ("ADHD High-Signal Dark"):**
The dark theme is explicitly named for ADHD. Key changes:
| Token | Value | Role |
|---|---|---|
| `--bg` | `#1A1A1A` | Very dark background |
| `--surface` | `#242424` | Slightly lighter surface |
| `--accent` | `#FFCC00` | **Bright yellow** — replaces indigo |
| `--accent-hover` | `#F0BB00` | Slightly darker yellow |
| `--success` | `#2DD4BF` | Teal (instead of green) |
| `--warning` | `#F97316` | Same orange |
| `--danger` | `#EF4444` | Slightly brighter red |
| `--focus-ring` | `#FFCC00` | Yellow ring |

The dark mode accent shift from indigo (`#4F46E5`) to yellow (`#FFCC00`) is deliberate: yellow provides maximum luminance contrast on dark backgrounds, which is an ADHD-friendly design choice.

### Border Radius System

```
--radius-sm:  .35rem
--radius:     .55rem
--radius-lg:  .85rem
--radius-xl:  1.1rem
```

Rounded but not pill-shaped — consistent softness hierarchy.

### Typography

- **Font**: `Lexend` (Google Fonts, weights 300–800) — loaded globally. Lexend is specifically designed to improve reading fluency and is used in ADHD accessibility contexts.
- **Body**: `line-height: 1.75`, `letter-spacing: 0.025em`, `-webkit-font-smoothing: antialiased` — all optimized for readability
- **Base font size**: Browser default (16px); most UI text scaled via rem
- **Font scale pattern**: `0.68rem` (tiny labels) → `0.72rem` (badges) → `0.78–0.82rem` (meta) → `0.88rem` (body-small) → `0.92–1rem` (standard) → `1.05–1.15rem` (section heads) → `1.45–1.8rem` (page titles) → `2.5–4rem` (timer)

### Layout Constraints

All content pages share a `main` max-width pattern:

| Template | Max-width | Padding |
|---|---|---|
| `my_day.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `inbox.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `inbox_detail.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `meetings.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `notes.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `projects_list.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `project_detail.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `close_day.html` | `720px` | `1.75rem 1.25rem 6rem` |
| `note_detail.html` | `820px` | `1.75rem 1.25rem 6rem` |
| `focus.html` | `520px` (focus-wrap) | `2rem 1.25rem 4rem` |
| `task_edit.html` | `580px` | `2rem 1.25rem 4rem` |
| `tasks.html` | `1000px` | `2rem 1.5rem` |
| `cop_initiatives.html` | `1200px` | `2rem 1.5rem` |
| `cop_import.html` | `640px` | `2.5rem 1.25rem 4rem` |
| `morning_checkin.html` | `640px` | `3rem 1.5rem 5rem` |
| `morning_checkin_pick.html` | `620px` | `2.5rem 1.25rem 4rem` |

**Pattern**: Narrow pages (focus, edit, checkin) are 520–640px. Standard detail/list pages are 820px. Wide admin/table pages are 1000–1200px. Bottom padding is consistently `6rem` on main views to ensure content clears the FAB button.

### Spacing Patterns

- Gap between task rows: `.35rem–.5rem` (tight)
- Gap between sections: `1.25rem–1.75rem`
- Card internal padding: `.65rem .9rem` (task rows) to `1.5rem 1.75rem` (focus card)
- Section margins: `margin-bottom: 1.75rem` (standard), `2rem` (close day)

### ADHD-Specific Design Patterns in CSS

1. **Progressive disclosure on task rows**: `.task-row-meta` has `max-height: 0; opacity: 0` by default, transitioning to visible on `:hover` or `.expanded` — reduces visual clutter while preserving access
2. **Celebratory animations**: `bloom-out` (confetti ring), `card-burst` (card completing animation), `count-bump` (wins counter bounce)
3. **NOW strip**: Prominent left-bordered highlight strip with `box-shadow` draws eye to single current task
4. **Brown noise toggle**: Built into nav — audio cue for focus states
5. **Dual theme explicitly labeled "ADHD High-Signal Dark"**: High-contrast yellow on black
6. **Backlog collapse**: Shows only 3 cards by default, preventing overwhelm
7. **WIP limit visual**: `column.wip-exceeded` gets red background warning
8. **Energy type filters**: Match task energy to user's current state

---

## 2. app.js Analysis

### Theme System

- On load, reads `localStorage.getItem('myday-theme')` and calls `applyTheme(isDark)`
- `applyTheme()` toggles `html.dark` class AND inlines all CSS variable values directly on `<html>` element — this guarantees override of any inline `<style>` blocks in individual templates
- An anti-flicker script runs in `<head>` of each template: `(function(){try{if(localStorage.getItem('myday-theme')==='dark')document.documentElement.classList.add('dark');}catch(e){}})()` — ensures no flash before CSS loads
- Theme toggle button text updates between `☀️ Light` and `🌙 Dark`

### Brown Noise (Focus Audio)

- Generates procedural brown noise using the Web Audio API (`createBuffer`, `createBufferSource`)
- Gain set to `0.22` — ambient/background level
- Loops a 2-second buffer
- State persisted in `localStorage('myday-noise')`
- Auto-resumes on first page click if previously active (handles autoplay restrictions)

### Kanban Behaviors (IIFE)

#### Project Tag Colorization
- `PROJECT_COLORS` map: 7 hardcoded project names → `{bg, color, dbg, dc}` (light/dark variants)
- Runs on init and after theme toggle with 60ms debounce
- Applied as inline `style.cssText` on `.card-project` elements

#### Move Button Collapse
- `STATUS_ORDER = ['backlog','todo','doing','waiting','done']`
- For each card, identifies the "next" status and promotes that button to `.move-btn-primary`
- All other status buttons are collapsed into a `···` dropdown (`.move-dropdown`)
- Dropdown opens on click, closes on any document click

#### Quick-Add Buttons
- Adds a `+ Add task` button at the bottom of each column
- Clicking shows an inline form (`.col-quick-form`) with title input, hidden status/priority inputs
- Only one form open at a time — clicking another column closes previous
- Form submits via POST to `/tasks-page` with `redirect_to` back to kanban

#### Celebratory Card Completion
- Listens for form `submit` on `#board` where `status === 'done'`
- Prevents default, adds `.card-completing` class (burst animation)
- Increments `#kanban-wins-num` counter with bounce animation (`count-bump`)
- Shows `.kanban-wins-bar` if hidden
- Submits form after 450ms delay

#### Energy Filter Bar
- `.energy-filter-btn` buttons toggle `.active` state
- Filters `#board .card` elements by checking for `etag-{energy}` class
- `data-energy="all"` shows all cards

#### Backlog Collapse
- Shows only first 3 cards in `[data-status="backlog"] .column-body`
- Hides others with `.backlog-hidden` class
- Appends a toggle button showing count
- Toggle expands/collapses with text update

#### NOW Task Management
- Listens for clicks on `.btn-set-now` and `.btn-clear-now`
- POSTs to `/tasks/{id}/set-now` or `/tasks/{id}/clear-now`
- On success: clears all `data-now="true"` cards, sets new one
- Inserts `▶ NOW` badge above card title
- Adds a `✕ Clear` button

#### Kanban Inline Editing
- Click on card (not on action buttons) triggers `openInlineEdit()`
- Hides `.card-preview`, injects `.inline-form` div
- Form has: title input, textarea (description), priority select, date input
- `Escape` cancels, `Cmd/Ctrl+Enter` saves
- Save POSTs to `/tasks/{id}/quick-edit` as `application/x-www-form-urlencoded`
- Returns JSON; updates card `data-*` attributes and preview HTML
- "More options" button navigates to full edit page

#### Quick-Add Energy Toggle (Global Function)
- `setQuickEnergy(btn)` — toggles active state on energy buttons in the quick-add modal
- Updates hidden `#quick-energy-val` input
- Clicking active button again deactivates (toggle behavior)

---

## 3. Template-by-Template Analysis

---

### index.html — Landing Page

**Layout structure:**
- `body { display: flex; flex-direction: column; min-height: 100vh }`
- Nav bar (fixed height 3.25rem) + `.hero` (flex: 1, centered content)
- Hero inner: `max-width: 600px; text-align: center`

**Navigation:**
- Logo + links: My Day, Check In, Kanban, Tasks, Projects, CoP Admin
- Right side: Noise + Theme ctrl-btn controls
- No active state marking (landing page)

**Content sections:**
1. Logo + tagline ("Simple, focused task management")
2. Stats grid: 4 stat numbers (total tasks, today, doing, projects)
3. Action buttons: My Day (primary), Kanban (outline), All Tasks (ghost), API Docs (ghost)

**Interactive elements:**
- 4 navigation anchor buttons
- Theme/noise toggle buttons (shared across all pages)

**Visual density:** Very low — generous white space, centered minimal layout

**Scroll behavior:** No scroll needed on most screen sizes; hero fills viewport

---

### my_day.html — Primary Daily View

**Layout structure:**
- `main { max-width: 820px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }`
- Single-column vertical stack
- Time grid section uses `grid-template-columns: 1fr 1fr 1fr` (collapses to 1fr at ≤600px)
- FAB button (fixed, bottom-right, z-index 200) + quick-add modal overlay

**Navigation:**
- Full nav with all links: My Day (active), Check In, Kanban, Tasks, Projects, Inbox, Meetings, Notes, CoP Admin, Focus
- Conditional "Close Day" link shown in nav at evening (JS-controlled, `display:none` by default)
- Right: Noise + Theme buttons

**Content sections (in order):**
1. **Dump banner** (conditional): Brain dump success notice — success-soft background with green border
2. **Page header**: `h1` "☀️ My Day" + date + "Begin Today's Plan" button (or "Today Started" badge)
3. **Stats strip**: Streak badge (accent color), Done today (success), Overdue count (warning/success)
4. **Check-in CTA** (conditional, pre-start): Orange gradient card urging brain dump
5. **CoP accordion**: `<details>` element — collapsible CoP initiatives list with topic/type/market tags
6. **NOW focus strip** (conditional): Prominent accent-bordered strip with current task title, meta badges, action buttons (Focus 20 min, Done, Later)
7. **NOW empty state** (conditional): Dashed-border card with prompt
8. **Overflow warning** (conditional): Orange banner if too many tasks scheduled
9. **Focus panel**: Main list of today's tasks (wins + nice-to-haves) — `.focus-panel { flex-direction: column; gap: .45rem }`
10. **Time block grid**: 3-column grid (Morning/Afternoon/Evening), each column is a header + body
11. **Suggestions accordion**: Collapsible section for "not-today" task suggestions
12. **Wins section**: Done-today tasks with strikethrough
13. **Close-day CTA** (conditional, evening): Purple/indigo gradient card

**Task/card item display (.task-row):**
- `background: var(--surface); border: 1px solid var(--border); border-radius: .6rem; padding: .65rem .9rem`
- Flex row: `[checkbox/icon] [body: title + meta] [actions: state buttons]`
- `.is-next`: amber left border (`3px solid #f59e0b`)
- `.is-later`: `opacity: .85`
- **Progressive disclosure**: `.task-row-meta` hidden by default (`max-height: 0; opacity: 0`), revealed on hover with CSS transition — shows energy tag, time block, priority
- Action buttons: state-change (primary accent), done (success), park (ghost), edit (faint link)
- `btn-state.primary` = accent fill; `btn-state.warn` = orange tint; `btn-check` = green tint

**Color classes:**
- `.pri-high`: `#dc2626` (red)
- `.pri-medium`: `#d97706` (amber)
- `.pri-low`: `var(--text-faint)` (gray)
- `.etag-creative`: violet tint
- `.etag-admin`: blue tint
- `.etag-social`: green tint
- `.etag-low_energy`: yellow tint
- `.tblock-morning`: amber/warm
- `.tblock-afternoon`: blue
- `.tblock-evening`: purple
- `.stat.streak`: accent fill (indigo/yellow)
- `.stat.done`: success-soft
- `.stat.overdue`: warning-soft

**Interactive elements:**
- Brain-dump brain dump CTA link
- CoP `<details>` accordion
- "Begin Today's Plan" form submit
- NOW strip: "Focus 20 min" link, "Done" form submit, "Later" form submit
- Task row hover reveals meta + action buttons
- `.btn-state` forms: inline status change POSTs
- Suggestions accordion toggle (JS: `suggest-toggle`)
- FAB (`+` button, fixed): opens `.quick-modal` dialog
- Quick-add modal: title input, priority buttons, energy buttons, time block buttons, submit
- Toast notification (`.add-toast`): briefly appears after task add
- Confetti (`canvas-confetti` CDN) triggered on task done

**Scroll behavior:** Single long column; FAB floats over content with 6rem bottom padding to prevent content clipping

**Visual density:** Medium — 8-12 sections in sequence with clear visual hierarchy, progressive disclosure reduces apparent density

---

### kanban.html — Kanban Board

**Layout structure:**
- `body { display: flex; flex-direction: column }` — nav + wins bar + filter bar + board
- `#board { flex: 1; display: flex; gap: 1rem; padding: 1.25rem 1.5rem; overflow-x: auto; align-items: flex-start }`
- Columns: `width: 260px; min-width: 260px` — fixed width, horizontal scroll
- Each column: `max-height: calc(100vh - 7rem)` — vertical scroll within column
- Column body: `overflow-y: auto; display: flex; flex-direction: column; gap: .5rem`

**Navigation:**
- Full nav links
- Right side: WIP info + Noise/Theme controls

**Content sections:**
1. `.kanban-wins-bar` — top strip (hidden by default, shown if `done_today_count > 0`)
2. `.energy-filter-bar` — right-aligned filter pills: All, Creative, Admin, Social, Low energy
3. `#board` — 5 columns: Backlog, Todo, Doing, Waiting, Done
4. Each column has: header (title + count), body (cards), JS-injected quick-add button

**Card item display (.card):**
- `background: var(--bg); border: 1px solid var(--border); border-left-width: 4px; border-radius: .55rem; padding: .7rem .8rem`
- Left border color driven by priority: high=red, medium=amber, low=slate
- `draggable="true"` — HTML5 drag and drop
- `.card-title`: `-webkit-line-clamp: 2` — 2-line truncation
- `.card-meta`: priority label, due date (overdue=red background), project tag, today badge, energy tag, time estimate pill
- `card-now-badge`: `▶ NOW` label (accent color, small)
- `card-expand-btn`: `⤢` icon, top-right, `opacity: 0` until card hover
- `.card-actions`: Move-to buttons (JS collapses to primary + `···` dropdown)
- `.card[data-now="true"]`: accent left border + focus-bg background tint
- `.column[data-status="doing"] .card:hover .btn-set-now`: Set NOW button revealed on hover in Doing column

**Column header tinting:**
- Backlog: slate/gray `#F8FAFC`
- Todo: blue `#EFF6FF`
- Doing: amber `#FFFBEB` (title colored `#D97706`)
- Waiting: purple `#F5F3FF`
- Done: green `#F0FDF4`

**WIP exceeded state:**
- Column gets `wip-exceeded` class: `background: #fee2e2`
- Warning text shows `⚠ WIP limit exceeded (N/limit)`

**Interactive elements:**
- Drag-and-drop (HTML5 `draggable`, `ondragstart`, `ondragover`, `ondrop`)
- Click-to-inline-edit (JS: `handleCardClick`)
- Inline edit form: title, description textarea, priority select, date picker
- `Escape` to cancel, `Cmd/Ctrl+Enter` to save (async fetch)
- "More options" → full edit page
- Close-on-outside-click for inline editor
- Move buttons (form POST)
- `···` more-actions dropdown
- `+ Add task` quick-add per column (JS injected)
- Energy filter buttons (client-side show/hide)
- `▶ Set NOW` / `✕ Clear` buttons (fetch API)
- Celebration burst when moving card to Done

**Scroll behavior:** Horizontal scroll on board container; vertical scroll within each column; sticky column headers via `position: sticky; top: 0` in `.column-head`

**Visual density:** Medium-high; compact cards with progressive disclosure; board scrolls both axes

---

### focus.html — Focus Timer

**Layout structure:**
- Minimal nav (`.focus-nav`): logo left, noise/theme/exit-link right
- `main { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center }` — vertically centered
- `.focus-wrap { width: 100%; max-width: 520px }` — narrow constrained column

**Navigation:**
- Minimal: logo + noise/theme buttons + "← Exit Focus" link
- No full nav links — deliberate distraction reduction

**Content sections:**
1. **No-task state**: Centered box with icon, message, link back to My Day
2. **Task header card** (`.task-card`): accent-bordered card with task title, energy/time-block/due badges — always visible during timer
3. **Idle panel**: Duration presets (20/30/45 min) + Start button
4. **Timer panel**: SVG ring countdown + phase label + Done/Pause/Stop buttons
5. **Paused notice**: Orange warning bar
6. **Stopped panel**: Encouragement message + retry/back buttons
7. **Done panel**: Success state with message + navigation buttons
8. **Error notice**: Red border error display

**Preset buttons (.preset-btn):**
- `flex: 1; max-width: 120px; text-align: center`
- Large minute number + label text
- `border: 2px solid var(--border)` → accent color when selected
- 3 presets: 20 (Quick), 30 (Standard), 45 (Deep)

**SVG Ring Timer:**
- `viewBox="0 0 120 120"`, displayed at `210×210px`
- Background circle (border color) + foreground arc (accent color)
- Arc uses `stroke-dasharray: 314.16` (circumference of r=50) with `stroke-dashoffset` animated
- Center shows digital countdown text
- Rotated -90deg so arc starts at top
- `stroke-linecap: round` for smooth arc end

**Timer state machine:**
- States: idle → running → paused → stopped/done
- Tick interval: 500ms
- Wall-clock based: uses `Date.now()` and accumulated segments — accurate even in background tabs
- `visibilitychange` listener snaps display on tab refocus
- Browser notifications API on completion (requests permission silently)

**Interactive elements:**
- Preset buttons (onclick, JS state)
- Start Focus button
- Done / Pause / Stop buttons
- Resume button (replaces Pause when paused)
- Try Again (resets to idle)
- Back to My Day / Another focus block links
- Brown noise / theme controls

**Visual density:** Very low — single focused element in center of screen, sequential state machine

**ADHD relevance:** Entire page is a reduced-distraction single-task experience. No nav links. Large visual countdown. Encouraging language throughout ("Every bit of time you put in counts").

---

### tasks.html — All Tasks List

**Layout structure:**
- `main { max-width: 1000px; margin: 0 auto; padding: 2rem 1.5rem }`
- Full-width table within main column
- Form grid: `grid-template-columns: 2fr 1.5fr 1fr 1fr 1fr auto` (responsive: 2-col at 800px, 1-col at 480px)

**Content sections:**
1. **Add task form** (white card): title, project, priority, due date, status, energy type, time estimate, submit
2. **Filter pills**: Status tabs (All, Todo, Doing, Backlog, Waiting, Done) — pill-shaped links
3. **Table toolbar**: Search input with SVG icon, sort reset button, visible count
4. **Tasks table**: Sortable columns (title, status, priority, project, due, created), edit/delete actions

**Task display in table:**
- Row: Title (bold + description preview) | Status badge | Priority text | Project | Due date | Created | Edit/Delete
- Status badges: colored pill backgrounds (todo=blue, doing=amber, done=green, backlog=gray, waiting=pink)
- Hover: `tr:hover td { background: var(--bg) }` — subtle row highlight
- Hidden rows: `.hidden-row { display: none }` (for search filtering)

**Interactive elements:**
- New task form (POST)
- Filter links (GET with status param)
- Search input: JS `filterSearch()` — client-side row show/hide
- Sortable column headers: JS click sort with asc/desc toggle
- Reset sort button
- Edit link → `task_edit.html`
- Delete form (confirm dialog)

**Scroll behavior:** Page scrolls normally; table can be long for many tasks

---

### task_edit.html — Full Task Edit

**Layout structure:**
- `main { max-width: 580px; margin: 0 auto; padding: 2rem 1.25rem 4rem }`
- Single white form card (`.form-card`)
- Two-column grid for status/priority and due/project pairs: `grid-template-columns: 1fr 1fr` (collapses at 480px)

**Content sections:**
1. Back link + "Edit task" heading
2. Form card:
   - Title (text input, autofocus)
   - Notes (textarea)
   - Divider + "Status & priority" label
   - Status + Priority selects (grid)
   - Due date + Project selects (grid)
   - Divider + "Focus & scheduling" label
   - **Focus state**: chip group (None, ⚡ Now, → Next, Today, Parked)
   - **Time block**: chip group (Any time, Morning, Afternoon, Evening)
   - **Energy type** (radio chips): Not set, Creative, Admin, Social, Low energy
   - **Energy type** (select duplicate — appears to be redundant/legacy field)
   - Time estimate (number input)
   - Save / Cancel actions

**Chip selector pattern:**
- Hidden `<input type="radio">` + visible `<label class="chip-label">`
- Default: `border: 1.5px solid #e2e8f0; color: #64748b`
- Checked: `border-color: var(--accent); background: #4f46e5; color: #fff`
- Energy chips get colored backgrounds when selected (creative=violet, admin=blue, social=green, low=amber)
- Time block chips: morning=amber, afternoon=blue, evening=purple when selected

**Visual density:** Medium — well-structured form with clear sections separated by dividers

---

### morning_checkin.html — Morning Ritual

**Layout structure:**
- `main { position: relative; z-index: 1; max-width: 640px; margin: 0 auto; padding: 3rem 1.5rem 5rem }`
- Soft radial gradient overlay on `body::before` (warm yellow + indigo, z-index 0)
- Sections stacked vertically as cards

**Content sections:**
1. **Page header**: Eyebrow pill ("☀️ Morning Ritual"), large title "Set up your day", subtitle
2. **Section 1 — Energy check**: 2×2 grid of energy cards (High energy, In the flow, Low energy, Scattered)
3. **Section 2 — Brain dump**: Large textarea for free-form thoughts
4. **Section 3 — Pick up to 3 must-dos**: Selectable task cards with checkboxes + counter
5. **Section 4 — Nice-to-haves**: Selectable task cards, max 2
6. **Submit**: Full-width "Let's go ✦" button + "Skip for now" link

**Energy card design:**
- `border: 2px solid var(--border)` → accent border + accent-soft background when selected
- `box-shadow: 0 0 0 3px rgba(255,204,0,.18)` when selected in dark mode
- Hidden radio input, custom visual selection
- Large emoji + label text; 2×2 grid

**Task pick card design:**
- `.task-pick-label`: bordered flex row with custom checkbox visual
- `.task-pick-check`: `1.1rem × 1.1rem` square with rounded corners; transparent text → accent background + white checkmark when checked
- Counter: "Selected: N / 3" in accent color
- `win-selected` class on nice-list items that are already picked as wins: `opacity: .35; pointer-events: none`

**Interactive elements:**
- Energy card onclick → `pickEnergy()`: JS adds `.selected` class, sets radio
- Task checkboxes: `onWinChange()` enforces max 3, syncs nice list; `onNiceChange()` enforces max 2
- `syncNiceList()`: auto-disables tasks in section 4 that are already selected in section 3
- Full form POST on submit

**Visual density:** Low-medium — generous padding, sectioned cards, clear guidance text

---

### morning_checkin_pick.html — Must-Do Selection

**Layout structure:**
- `main { flex: 1; max-width: 620px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; width: 100% }`
- Step progress indicator at top

**Content sections:**
1. **Steps progress bar**: Step 1 (✓ Brain Dump), Step 2 (active: Pick Must-Dos), Step 3 (inactive: Focus)
2. **Page header**: Title + explanatory text
3. **Counter bar**: 3 circle dots + count label + hint
4. **Cap warning**: Warning banner if 3 already selected
5. **Encouragement**: Green success bar if 3 selected
6. **Task list**: `.pick-row` cards with check indicator, title, edit link, Pick/Unpick form button
7. **Bottom CTA**: "Head to My Day" + "Skip picking" link

**Step indicator design:**
- Circular number badges: done=accent fill, active=accent fill, inactive=gray
- Connector lines between steps: done=accent color, pending=gray
- Linear progress concept

**Pick row design:**
- `background: #fff; border: 1px solid #e2e8f0; border-radius: .6rem`
- Selected: accent border + `#f5f3ff` background + accent outline
- Custom circular check indicator (not square)
- Separate Pick/Unpick buttons (form POSTs for server-side state)
- Edit link (`.btn-edit-sm`)

**Interactive elements:**
- Each row has a form POST for set-today/unset-today
- Counter updates are server-side (page reload per action)
- No client-side selection toggle — deliberately server-driven

---

### close_day.html — Evening Wrap-Up

**Layout structure:**
- `main { max-width: 720px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }`
- Single column with centered hero section

**Content sections:**
1. **Hero**: "🌙 Evening Reset" eyebrow badge, "Close the Day" h1, sub
2. **Early warning** (conditional): Orange banner if before 4pm
3. **Already-closed banner** (conditional): Green success banner
4. **Score ring**: Centered circular badge showing `N%` wins done (accent/success border, dark background)
5. **Form:**
   - Section 1 — Shipped today: Win-done rows (strikethrough, green background)
   - Section 2 — What to do with incomplete tasks: Each has Roll Over / Backlog radio choice
   - Quick-select all: "Roll over all" / "Backlog all" buttons
   - CTA: "🌙 Close the Day" button + hint text
6. **Nothing today** empty state (conditional)

**Score ring design:**
- `border: 6px solid var(--accent/success/border)` circle
- `.full`: success border + trophy emoji instead of %
- `.empty`: border color only, `0%` text

**Incomplete task row design:**
- `.incomplete-row`: surface background, border, rounded
- `.is-win`: accent left border (3px)
- `.is-nice`: purple left border (3px `#a78bfa`)
- Radio choice labels styled as pill buttons with selected states:
  - `selected-rollover`: accent border + accent-soft bg
  - `selected-backlog`: danger border + danger-light bg

**Interactive elements:**
- Radio buttons for each incomplete task (JS `updateChoice()` updates visual state)
- "Roll over all" / "Backlog all" JS quick-select
- Form POST on submit
- Confetti (`canvas-confetti`) fired:
  - Immediately if all wins done (page load, 400ms delay)
  - On click of close button

---

### inbox.html — Meeting Inbox

**Layout structure:**
- `main { max-width: 820px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }`
- Tab bar + list view

**Content sections:**
1. **Page header**: "📥 Meeting Inbox" + subtitle
2. **Tab bar**: Active / Archived tabs (bottom-border active indicator)
3. **Inbox list** or **Empty state**

**Inbox card design (.inbox-card):**
- Surface background, rounded, flex row
- Left status stripe (3px absolute positioned): yellow=new, blue=reviewing, green=promoted
- `.inbox-card-body`: title (truncated, bold), meta (badge + date), summary (2-line clamp)
- Right: "Review →" / "View →" button
- Hover: accent border + shadow

**Badge types:**
- `.badge-new`: amber tint
- `.badge-reviewing`: blue tint
- `.badge-promoted`: green tint
- `.badge-whisper`: violet (meeting source)

---

### inbox_detail.html — Inbox Item Triage

**Layout structure:**
- `main { max-width: 820px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }`
- Back link → header → sequential content blocks → action panel

**Content sections:**
1. Back link
2. **Header**: h1 title + meta badges (source, status, dates)
3. **Notion link** (conditional): provenance chip
4. **Promoted notices** (conditional): Success banner linking to created task/project/note
5. **Summary block**: Left green border, "✦ Summary" label, summary text
6. **Suggested actions**: List of action items with dot indicators + "Use →" buttons
7. **Raw transcript** (collapsible): Toggle button + hidden body
8. **Action panel**: Tab bar (Create task / Start project / Save as note) + corresponding form + Archive strip

**Action panel tab design:**
- `.action-tab` buttons: ghost by default → accent fill when `.active`
- Only one tab visible at a time (JS `switchTab()`)
- Each tab has its own form with relevant fields

**"Use →" button behavior:**
- Fills the currently-visible action panel's title/step input with the suggestion text
- Scrolls to the visible panel

---

### meetings.html — Meetings Timeline

**Layout structure:**
- `main { max-width: 820px; margin: 0 auto; padding: 1.75rem 1.25rem 6rem }`
- Day groups → source sections → item cards

**Content sections:**
1. Page header
2. Inbox review strip (if unreviewed items exist)
3. Day groups (`.day-group`): date header with pills + source sections
4. Source sections: label (whisper/notion/other) + item list

**Item card (.item-card):**
- Left stripe by source: `.stripe-whisper` (violet), `.stripe-notion` (blue), `.stripe-self` (gray)
- Title (truncated), summary (2-line), meta (status badge, timestamps)
- "→" arrow indicator on right
- Hover: accent border

**Day header:**
- Date + weekday + summary pills (total, promoted count, to-review count)
- `.pill-unreviewed`: amber tint — draws attention to pending items
- Day groups separated by `<hr class="day-divider">`

---

### notes.html / note_detail.html — Reference Notes

**List layout:** `max-width: 820px`, vertical card list (`.note-grid`)

**Note card:** Title (truncated), summary (2-line clamp), meta (source badge, Notion status dot, date)
- Notion icon link (↗) shown at right when `notion_url` exists

**Detail layout:** Back link → header → provenance links → summary block → collapsible full content → Notion export card

**Notion export card:**
- Shows export status or export form
- Re-export via `<details>` collapse
- Black button (`#1a1a1a`) for Notion export (matches Notion's own dark branding)

---

### projects_list.html / project_detail.html — Projects

**List layout:** `max-width: 820px`, create card + section labels + project card grid

**Project card (.proj-card):**
- Flex row: body (name + description + meta) + side (View button + Archive form)
- Progress bar: `90px wide, 5px tall, green fill`
- Archived projects shown at `opacity: .7`
- `badge-active` (green) / `badge-archived` (ghost)

**Detail layout:** Back link → header → description block → open tasks block → Notion export card

**Task rows in project detail:**
- Focus pip: accent=now, success=next, faint=later
- Focus label text + task title

---

### cop_initiatives.html — CoP Admin

**Layout structure:**
- `main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem }` — widest page
- Add form card (CSS grid with `repeat(auto-fill, minmax(200px, 1fr))`) + table

**Table design:**
- Full-width, rounded, `border-collapse: collapse`
- Sticky-ish header (background `#f8fafc`)
- Month status dots: 12 circle indicators, filled=active (accent), empty=gray
- `.table-wrap { overflow-x: auto }` — horizontal scroll on small screens

---

### cop_import.html — CSV Import

**Layout structure:** `max-width: 640px`, info cards + import button + result panel

**Result states:** `.result-box.success` (green), `.result-box.warning` (amber), `.result-box.error` (red)

---

## 4. Cross-Cutting Patterns

### Navigation Consistency

All pages share the same nav structure:
- Height: `3.25rem` (52px), sticky `top: 0`, `z-index: 100`
- Logo (accent color, 800 weight) + links (flex, border-bottom active indicator) + right controls
- Right controls always: Noise button + Theme button
- Some pages also show WIP info or nav-actions div
- "Focus" link styled dimmer: `.nav-focus { font-size: .78–.82rem; color: var(--text-faint) }`
- "Check In" link highlighted: `color: #D97706; font-weight: 700`

### Interactive Element Hierarchy

1. **Primary CTA**: `background: var(--accent); color: #fff` — highest visual weight
2. **Secondary/ghost**: `background: var(--surface); border: 1px solid var(--border)` — outlined
3. **State chips**: Pill buttons for enum selection
4. **Micro-actions**: Ghost/transparent buttons for park, edit, archive
5. **Destructive**: `danger` colors for delete

### Form Patterns

- All forms use `method="post"` (no AJAX except kanban quick-edit and NOW API calls)
- `redirect_to` hidden field pattern: server redirects back to originating page
- Focus-ring on inputs: `border-color: var(--accent)` + `box-shadow: 0 0 0 3px` glow
- Labels: uppercase, small, `letter-spacing: .05em` — reduced contrast vs content
- `autofocus` used on primary inputs in dedicated edit views

### Empty State Patterns

Three styles used:
- **Dashed border**: `border: 1px dashed var(--border)` — for list pages with no content
- **Centered box**: Icon + title + explanation + action link
- **Inline text**: Italic, faint color, padding

### Toast / Feedback Patterns

- `.add-toast`: Fixed bottom-right, slides up/fades in, success color — for task added
- `.add-toast.show` triggers visible state
- Notice blocks (`.notice-ok`, `.notice-archived`): Left-aligned inline confirmation
- `card-completing` burst animation: momentary success before DOM update
- Confetti (`canvas-confetti`): Major milestones (day close, all wins done)

### Scrolling Behavior Summary

| Page | Scroll type |
|---|---|
| index | None (hero fills viewport) |
| my_day | Single column vertical scroll |
| kanban | Board: horizontal; Columns: vertical (within fixed height) |
| focus | Centered, no scroll needed |
| tasks | Vertical page scroll |
| task_edit | Vertical page scroll |
| morning_checkin | Vertical page scroll |
| morning_checkin_pick | Vertical page scroll |
| close_day | Vertical page scroll |
| inbox | Vertical page scroll |
| inbox_detail | Vertical page scroll |
| meetings | Vertical page scroll |
| notes / note_detail | Vertical page scroll |
| projects | Vertical page scroll |
| cop_initiatives | Vertical + horizontal (table overflow) |

### Responsive Width Behavior

- All standard pages: `max-width: 820px` centered — at ≤820px, content fills full viewport with `1.25rem` side padding
- No explicit mobile breakpoints except:
  - `tasks.html` form grid: 2-col at 800px, 1-col at 480px
  - `my_day.html` time grid: 3-col → 1-col at 600px
  - `task_edit.html` field grid: collapses at 480px
  - Kanban board: no breakpoints — horizontal scroll on mobile
- No media queries for nav collapse/hamburger — nav may overflow on small screens

### FAB Pattern (my_day.html)

- Fixed `bottom: 1.75rem; right: 1.75rem; z-index: 200`
- 52px circle, accent color, `+` character
- Opens `<dialog>` `.quick-modal` (native HTML dialog element)
- Dialog: `width: min(480px, 92vw)` — responsive modal
- Backdrop: `rgba(0,0,0,.45)` with `backdrop-filter: blur(2px)`

### ADHD Design Philosophy Summary

The app makes several deliberate ADHD-friendly choices:

1. **Lexend font** — designed for reading accessibility
2. **Progressive disclosure** — task meta hidden until hover, reducing visual noise
3. **Single-focus NOW concept** — one task pinned as "Now" across views
4. **Focus mode** — stripped-down timer page with no distractions
5. **Brown noise** — always-available ambient focus audio
6. **Energy matching** — tasks tagged by energy type (creative/admin/social/low_energy) to match cognitive state
7. **Time blocks** — morning/afternoon/evening scheduling reduces decision fatigue
8. **Caps and structure** — max 3 wins, max 2 nice-to-haves
9. **Backlog collapse** — shows only 3 backlog items to prevent overwhelm
10. **High-signal dark mode** — yellow accent on black for maximum attention channeling
11. **Celebratory micro-interactions** — bloom animation, confetti, count bump for dopamine
12. **Encouragement language** — "no pressure," "every bit counts," "you showed up"
13. **WIP limit visual warning** — prevents overloading Doing column
14. **Progressive check-in flow** — step-by-step morning ritual prevents paralysis
15. **Close Day ceremony** — explicit ending ritual with choice framing (roll over vs backlog)
