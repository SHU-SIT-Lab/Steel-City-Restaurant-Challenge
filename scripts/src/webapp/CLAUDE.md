# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`steel-city-ops-webapp` ("Steel City Ops") is a real-time restaurant **operations dashboard** for the
[Steel City Restaurant Challenge](https://sitlabresearch.uk/research/robotics-challenge/) — an internal
staff control surface for supervising customers, tables, orders, robots, and high-level robot behaviors.
It is **not** a customer-facing ordering site.

This app lives at `scripts/src/webapp` inside the larger `Steel-City-Restaurant-Challenge` repo (one git
repo, rooted three levels up), alongside the Python robot modules in `scripts/` and the ROS workspaces.
Firestore is the **shared-state layer** between this web app and the robot/ROS side; ROS remains the
execution layer. The design doc at
`<repo-root>/docs/webapp/plan.md` is the authoritative spec for the data model, RBAC matrix, command
catalogue, and state machines — read it before changing Firestore document shapes or command semantics.

## Commands

Run all of these from this directory (`scripts/src/webapp`):

- `npm run dev` — Vite dev server. This **also serves the backend API** (see Architecture); it is the only
  command you need to exercise the full app locally.
- `npm run build` — `tsc -b` (type-check via project references) then `vite build`. Type errors fail the build.
- `npm run lint` — ESLint (flat config in `eslint.config.mjs`). Ignores `dist`, `export.js`, `server/**/*.cjs`.
- `npm run preview` — serve the production `dist/` build.
- `node export.js` — dump every Firestore collection/document to stdout (debugging / regenerating seed data).

There is **no test runner** configured (no `test` script, no test files). Don't invent one or claim tests pass.

## Architecture

**Single Vite process, not a separate backend.** There is no Express/Next server. `vite.config.ts` mounts a
middleware plugin that routes every `/api/*` request to `server/api.cjs`. That file is plain **CommonJS**
(hence `.cjs`, and why ESLint ignores it) and is the entire backend — Firestore reads/writes via the
`firebase-admin` SDK live only here and in `export.js`. The React client never imports `firebase-admin` or a
Firebase client SDK; it reaches Firestore exclusively through these `/api` routes.

**Data flow (polling, not realtime).** `src/hooks/useOpsData.ts` is the single source of app state:
- On mount and **every 3 seconds** it `GET`s `/api/snapshot`, which returns the entire `OpsSnapshot`
  (all collections in one payload). Despite the plan mentioning Firestore realtime listeners, the
  implementation polls.
- Every mutation goes through `mutate()`: call the write endpoint, then immediately `refresh()`. The UI has
  `loading`/`saving`/`error` flags but no optimistic local updates.
- **`mock` vs `live` mode:** the app boots in `mock` mode rendering `src/data/mockFirestore.ts`. A successful
  snapshot flips it to `live`; **any fetch error falls back to `mock`**. So if you see static demo data, the
  API/Firestore call is failing — check credentials, not the components.

**Layering:** `src/lib/api/client.ts` (typed `fetch` wrappers, one per endpoint) → `useOpsData` (state +
actions) → `src/App.tsx` (composes the `components/ops/*` panels). Shared document/command types live in
`src/types/firestore.ts` and `src/types/commands.ts` and are imported by both client and `api.cjs`'s mental model.

**Commands & tasks are written but ROS is not yet wired.** `POST /api/commands` validates the request, then in
one Firestore batch creates a `commands` doc **and** a linked `tasks` doc with
`current_step: "Queued by web app; waiting for ROS bridge integration"`. The ROS bridge adapter (plan Phase 4)
does not exist yet — nothing consumes these documents on the robot side here. `ros_request_id` stays `null`.

**RBAC is UI-only — the server does not enforce it.** Roles rank `viewer < kitchen < operator < manager <
admin` (`src/lib/rbac.ts`). Components gate buttons via `hasRole`/`hasMinimumRole`/`canUpdateOrders`, but
`server/api.cjs` performs **payload validation only and no role checks** — it just echoes the role from
`WEBAPP_DEFAULT_ROLE`. Treat any "only admins can X" guarantee as cosmetic until server-side enforcement and
Firestore security rules are added. The UI `commandCatalogue` (in `mockFirestore.ts`) exposes all 11
`CommandType`s; `CommandDeck` renders a param form per command (robot/table/order/party pickers, a count
stepper, a waypoint field, an emergency-stop reason), and `server/api.cjs` validates each and applies
Firestore side effects (e.g. `COLLECT_ORDER`/`DELIVER_ORDER` advance the order; `UPDATE_CUSTOMER_COUNT`
patches `entrance.party_size`).

**Business rules live in `server/api.cjs`**, not the client — e.g. the `nextOrderStatus` order state machine,
table-assignability checks (can't assign `occupied`/`needs_cleaning`/`unavailable`), and side effects like
clearing `current_order`/`current_party`/`occupied_since` when a table goes `empty` or an order reaches a
terminal state. Every privileged write also appends an `events` doc (`writeEvent`) for the activity log.

## Firestore & conventions

- **Project:** `restaurant-robocup-2026`. Collections: `entrance`, `menu`, `orders`, `robots`, `tables`,
  `commands`, `tasks`, `events` (`users` is planned, not implemented). Doc IDs follow patterns like `t_01`
  for tables and `ninja` for the robot.
- **Timestamps** are the admin-SDK serialized form `{ _seconds, _nanoseconds }` (`FirestoreTimestamp`), not
  JS `Date`. Use `formatFirestoreTime` in `src/lib/firestore/converters.ts` to render them.
- **Order `items` have a legacy dual format:** either `string[]` (item ids) or `NormalizedOrderItem[]`.
  Reads must tolerate both — use `normalizeOrderItems`; all new writes should use the object form.
- **Credentials (env vars only):** `server/api.cjs` and `export.js` read Firestore credentials from the
  environment — `FIREBASE_SERVICE_ACCOUNT` (inline JSON, takes precedence; for deploys/CI) or
  `GOOGLE_APPLICATION_CREDENTIALS` (path to a local service-account JSON, standard ADC). There is **no
  committed-key fallback**. For dev, put the value in a local `.env` (gitignored; copy `.env.example`):
  `server/api.cjs` parses `.env` itself on load (overriding a stale `GOOGLE_APPLICATION_CREDENTIALS` whose
  file is missing), and `export.js` does the same. Service-account keys (`*firebase-adminsdk*.json`) are
  gitignored — never commit or print one.
- **Env vars:** `GOOGLE_APPLICATION_CREDENTIALS` or `FIREBASE_SERVICE_ACCOUNT` (Firestore auth, required),
  `FIREBASE_PROJECT_ID` (optional, defaults to `restaurant-robocup-2026`),
  `WEBAPP_DEFAULT_ROLE` (server snapshot role, default `manager`), `VITE_DEFAULT_ROLE` (client fallback role).

## Stack

React 19 + TypeScript (strict, `noUnusedLocals`/`noUnusedParameters`) + Vite 7. No CSS framework — a single
hand-written `src/styles.css` styles the dark "mission-control" dashboard. No router (single page).
