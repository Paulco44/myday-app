# Build & native binaries (portability notes)

## Native platform binaries (rollup / lightningcss / @tailwindcss/oxide / esbuild)

The Kanban frontend (`artifacts/myday-kanban`, React 19 + Vite 7 + Tailwind 4)
depends on tools that ship their compiled core as **per-platform native
binaries** published as `optionalDependencies` (e.g.
`@rollup/rollup-win32-x64-msvc`, `@tailwindcss/oxide-*`, `lightningcss-*`).
Node/pnpm pick the right one at install time from the host's `os`/`cpu`/`libc`.

### How we keep this reproducible *and* portable

We rely on pnpm's **`supportedArchitectures`** (see `pnpm-workspace.yaml`) to
declare the full matrix we want the lockfile to cover:

```yaml
supportedArchitectures:
  os:   [win32, darwin, linux]
  cpu:  [x64, arm64]
  libc: [glibc, musl]
```

With this set, `pnpm install` records the native binaries for **all** those
platforms in `pnpm-lock.yaml` (deterministic lockfile), while only linking the
binary matching the current host into `node_modules`. The result builds on a
Windows dev box, macOS, Linux, and CI from the same lockfile.

### What we deliberately do NOT do anymore

This repo was originally scaffolded on Replit (linux-x64-gnu). The old setup:

1. Used `overrides` in `pnpm-workspace.yaml` to **delete** (`"-"`) every
   platform variant of rollup/lightningcss/@tailwindcss/oxide *except*
   `linux-x64-gnu`, to keep the Replit lockfile lean — but this also deleted the
   `win32-x64-msvc` variants the Windows dev machine needs.
2. To compensate, it re-added those three `*-win32-x64-msvc` binaries as
   **direct `devDependencies`** in the root `package.json`.

That made the build reproducible on *exactly two* platforms (linux-x64-gnu and
win32-x64) and broken everywhere else (macOS / arm64 / npm on any non-win host,
which errors with `EBADPLATFORM` on the win-only direct deps).

Both workarounds were removed in favour of `supportedArchitectures`. The
`overrides` block still prunes **`esbuild`** and **`@expo/ngrok-bin`** platform
variants on purpose — those are unrelated to the Vite build (esbuild also has a
security-pinned version override) and are left as-is.

> If you ever need to support another platform/arch (e.g. linux-arm64 on a new
> CI runner), add it to `supportedArchitectures` and run `pnpm install` — do
> **not** re-introduce platform-specific direct dependencies.

## Building the Kanban frontend

`vite.config.ts` requires `PORT` and `BASE_PATH` env vars (normally provided by
the `START-MyDay` scripts):

```powershell
$env:PORT='5173'; $env:BASE_PATH='/'
pnpm --filter @workspace/myday-kanban run build
```
