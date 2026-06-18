# Web App Prototype Plan

## Product Goal

Build a real-time restaurant operations web app for the Steel City Restaurant Challenge. The app should let staff supervise customers, tables, orders, robots, and high-level ROS behaviors from one control surface.

The first prototype is an internal operations dashboard, not a customer-facing ordering site. It should be designed so Firestore remains the shared state layer and ROS remains the execution layer for robot behavior.

## Prototype Scope

### In Scope

- Live dashboard for restaurant state
- Table floor-plan view using Firestore table poses
- Customer arrival queue and seating workflow
- Order creation, confirmation, dispatch, and delivery tracking
- Robot status and task status display
- Management command console for ROS behaviors
- Role-based actions for admin, manager, operator, kitchen, and viewer users
- Backend API contract between web app, Firestore, and ROS bridge
- Firestore read/write mapping for each UI surface

### Out Of Scope For First Prototype

- Public customer accounts
- Payments
- Full menu inventory management
- Multi-restaurant tenancy
- Autonomous task planning inside the web app
- Replacing ROS task logic with web logic

## System Architecture

```text
Web Client
  React / Next.js prototype UI
  Firebase Auth session
  Firestore realtime listeners
  HTTPS calls for privileged actions

Backend API
  Validates role and request payload
  Writes command/task documents to Firestore
  Calls ROS bridge for immediate robot commands when required
  Normalizes Firestore writes
  Emits audit events

Firestore
  Source of truth for app-visible state
  Stores tables, entrance queue, menu, orders, robots, commands, tasks, events, users
  Streams realtime state into dashboard

ROS Bridge / Robot System
  Subscribes to command/task requests
  Executes robot behaviors
  Publishes robot/task status back to backend or Firestore
```

## Next-Level Design Direction

### Visual Style

The dashboard should feel like a restaurant mission-control surface rather than a generic admin panel.

- Use a dark charcoal operations canvas with warm steel, amber, and green status accents.
- Make the floor plan the visual anchor, not a small secondary widget.
- Use large status cards only for operationally important numbers.
- Keep commands close to the restaurant object they affect: table actions near tables, order actions near orders, robot actions near robots.
- Use strong contrast for critical states: blocked, error, waiting, cleaning, ready.

### Information Priority

1. Is the robot healthy and available?
2. Are customers waiting?
3. Which tables are free, occupied, assigned, or blocked?
4. Which orders need action?
5. Which ROS tasks are running, queued, or failed?
6. What changed recently?

## Page Layout / Wireframe

### Main Operations Page

```text
+------------------------------------------------------------------------------+
| Top Bar                                                                      |
| Steel City Ops | Live/Degraded/Offline | Robot: Ninja idle 95% | User role   |
+------------------------------------------------------------------------------+
| KPI Strip                                                                    |
| Waiting parties | Free tables | Active orders | Running tasks | Alerts       |
+-----------------------+--------------------------------------+---------------+
| Left Rail             | Center: Restaurant Floor Plan          | Right Rail    |
|                       |                                      |               |
| Customer Queue        |  Pose-based table map                 | Command Deck  |
| - party size          |  - table cards positioned by pose     | - command     |
| - wait duration       |  - table state rings                  | - params      |
| - assign action       |  - robot location marker              | - dry-run     |
|                       |  - selected table detail drawer       | - execute     |
| Robot Panel           |                                      |               |
| - battery             |                                      | Activity Log  |
| - current task        |                                      | - events      |
| - last seen           |                                      | - warnings    |
+-----------------------+--------------------------------------+---------------+
| Bottom Workspace                                                              |
| Orders board: New | Confirmed | Preparing | Ready | Delivering | Delivered   |
+------------------------------------------------------------------------------+
```

### Mobile / Tablet Layout

```text
+-----------------------------+
| Top Bar                     |
+-----------------------------+
| KPI Carousel                |
+-----------------------------+
| Tabs                        |
| Floor | Queue | Orders      |
| Robots | Commands | Log     |
+-----------------------------+
| Active tab content          |
+-----------------------------+
```

The mobile layout should prioritize monitoring and simple actions. Destructive actions and manual ROS commands should require a confirmation sheet.

## Key Screens

### 1. Operations Dashboard

Purpose: single-screen live state for competition operation.

Primary components:

- `ConnectionStatus`: Firestore listener state, backend health, ROS bridge health
- `KpiStrip`: waiting parties, occupied/free tables, active orders, alerts
- `FloorPlan`: pose-based table map and robot marker
- `CustomerQueue`: waiting/assigned/seated parties
- `RobotPanel`: robot state, battery, current task, last seen
- `CommandDeck`: role-gated ROS command executor
- `ActivityLog`: recent events and failures
- `OrdersBoard`: order lifecycle columns

### 2. Table Detail Drawer

Opened from the floor plan.

Shows:

- Table number and status
- Pose coordinates
- Current party or assigned entrance document
- Current order
- Recent table events
- Available actions for the user's role

Actions:

- Mark free
- Mark occupied
- Mark needs cleaning
- Assign waiting party
- Start `Introduce Table`
- Start `Take Order`
- Start `Collect Order`
- View current order

### 3. Customer Intake Page

Purpose: handle front-door arrivals.

Shows:

- Waiting parties
- Party size
- Detected by robot/manual
- Time waiting
- Suggested table
- Seating status

Actions:

- Add manual party
- Update party size
- Assign table
- Mark seated
- Cancel/no-show
- Trigger `Check Customer`
- Trigger `Update New Customer Number`

### 4. Orders Page

Purpose: manage order lifecycle.

Columns:

- `detected`
- `draft`
- `confirmed`
- `preparing`
- `ready`
- `collecting`
- `delivering`
- `delivered`
- `cancelled`
- `failed`

Actions:

- Create order for table
- Add menu items
- Confirm order
- Mark ready
- Request robot collection
- Mark delivered
- Cancel order

### 5. Command Console Page

Purpose: direct high-level behavior control.

Features:

- Command catalogue grouped by customer, table, order, robot, and recovery
- Dynamic parameter form
- Dry-run validation
- Confirmation for movement, override, or destructive commands
- Execution status timeline
- Link command to generated task and resulting events

## Backend API Design

The frontend should read public operational state from Firestore directly where security rules allow it. Privileged writes should go through the backend API so validation, RBAC, command mapping, and audit logs are consistent.

### API Principles

- Backend owns writes that trigger ROS behavior.
- Backend validates role permissions before every mutation.
- Backend writes normalized Firestore documents.
- Backend returns the Firestore document ID for created commands, tasks, orders, or events.
- Backend should be idempotent where possible using `idempotency_key`.

### Suggested API Routes

| Method | Route | Purpose | Roles |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Backend and ROS bridge health | all authenticated |
| `GET` | `/api/bootstrap` | Initial config, command catalogue, role permissions | all authenticated |
| `POST` | `/api/entrance` | Add manual customer party | operator, manager, admin |
| `PATCH` | `/api/entrance/:id` | Update party size/status/notes | operator, manager, admin |
| `POST` | `/api/entrance/:id/assign-table` | Assign party to table | operator, manager, admin |
| `PATCH` | `/api/tables/:id/status` | Update table state | operator, manager, admin |
| `POST` | `/api/orders` | Create order | operator, manager, admin |
| `PATCH` | `/api/orders/:id` | Update order fields | kitchen, operator, manager, admin |
| `POST` | `/api/orders/:id/confirm` | Confirm order | operator, manager, admin |
| `POST` | `/api/orders/:id/mark-ready` | Mark order ready | kitchen, manager, admin |
| `POST` | `/api/orders/:id/request-delivery` | Trigger collection/delivery task | operator, manager, admin |
| `POST` | `/api/commands` | Create and execute ROS command | manager, admin |
| `POST` | `/api/commands/:id/cancel` | Cancel queued command/task | manager, admin |
| `POST` | `/api/robots/:id/pause` | Pause robot task execution | manager, admin |
| `POST` | `/api/robots/:id/resume` | Resume robot task execution | manager, admin |
| `POST` | `/api/robots/:id/emergency-stop` | Emergency stop command | admin only for prototype |

### Example Command Request

```json
{
  "command_type": "TAKE_ORDER",
  "robot_id": "ninja",
  "target": {
    "table_id": "t_01"
  },
  "params": {
    "allow_skip_greeting": true
  },
  "idempotency_key": "take-order-t_01-1781098661"
}
```

### Example Command Response

```json
{
  "command_id": "cmd_20260611_001",
  "task_id": "task_20260611_001",
  "status": "queued"
}
```

## Firestore Read / Write Mapping

### Existing Collections

The current export shows these collections:

- `entrance`
- `menu`
- `orders`
- `robots`
- `tables`

The prototype should keep these collections and add explicit operational collections for commands, tasks, events, and users.

### Proposed Collections

```text
entrance/{partyId}
menu/{itemId}
orders/{orderId}
robots/{robotId}
tables/{tableId}
commands/{commandId}
tasks/{taskId}
events/{eventId}
users/{uid}
```

### `entrance/{partyId}`

Purpose: customer arrival queue and seating state.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `party_size` | number | Required |
| `status` | string | `waiting`, `assigned`, `seating`, `seated`, `cancelled`, `no_show` |
| `detected_by` | string | `robot`, `manual`, `sensor` |
| `assigned_table` | string/null | Table document ID such as `t_02` |
| `arrived_at` | timestamp | Set on create |
| `assigned_at` | timestamp/null | Set when table assigned |
| `seated_at` | timestamp/null | Set when seated |
| `notes` | string | Staff notes |
| `created_by` | string | User uid or `robot` |
| `updated_at` | timestamp | Backend managed |

Reads:

- Dashboard KPI waiting count
- Customer queue
- Table detail party context

Writes:

- Manual customer registration
- Robot customer detection
- Assign table
- Mark seated/no-show

### `tables/{tableId}`

Purpose: floor-plan state and table lifecycle.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `table_number` | number | Display label |
| `status` | string | `empty`, `reserved`, `assigned`, `occupied`, `needs_cleaning`, `unavailable` |
| `pose_x` | number | ROS/world x coordinate |
| `pose_y` | number | ROS/world y coordinate |
| `pose_theta` | number | ROS/world heading |
| `current_order` | string/null | Active order ID |
| `current_party` | string/null | Entrance party ID |
| `occupied_since` | timestamp/null | Set when occupied |
| `last_updated` | timestamp | Backend managed |

Reads:

- Floor plan
- Table KPI counts
- Command parameter dropdowns
- Order table selection

Writes:

- Assign party
- Mark occupied/free/cleaning/unavailable
- Link active order

### `menu/{itemId}`

Purpose: available order items and optional robot vision mapping.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Display label |
| `category` | string | `food`, `drink`, `meal`, etc. |
| `available` | boolean | Hide or disable if false |
| `display_order` | number | Sort order |
| `graspable` | boolean | Robot can collect/manipulate item |
| `yolo_class` | number/null | Vision class mapping |

Reads:

- Order builder
- Kitchen view
- ROS collect-order validation

Writes:

- Admin menu management, later phase

### `orders/{orderId}`

Purpose: order lifecycle.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `table_id` | string | Required table document ID |
| `status` | string | `draft`, `detected`, `confirmed`, `preparing`, `ready`, `collecting`, `delivering`, `delivered`, `cancelled`, `failed` |
| `items` | array | Normalize to objects: `{ item_id, name, quantity, notes, graspable }` |
| `assigned_robot` | string/null | Robot ID |
| `used_tray` | boolean/null | Delivery metadata |
| `customer_gesture` | string/null | Vision/speech context |
| `notes` | string | Staff notes |
| `created_at` | timestamp | Backend managed |
| `confirmed_at` | timestamp/null | Backend managed |
| `ready_at` | timestamp/null | Backend managed |
| `collected_at` | timestamp/null | Backend managed |
| `delivered_at` | timestamp/null | Backend managed |
| `created_by` | string | User uid or `robot` |
| `updated_at` | timestamp | Backend managed |

Compatibility note: the current export has `items` as both string arrays and object arrays. The frontend should read both formats, but all new writes should use object entries.

Reads:

- Orders board
- Table detail
- Robot task context
- Activity timeline

Writes:

- Create/edit order
- Confirm order
- Mark ready
- Mark collecting/delivering/delivered
- Cancel/fail order

### `robots/{robotId}`

Purpose: robot status visible to operators.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Display name |
| `model` | string | Example: `TurtleBot 4` |
| `status` | string | `idle`, `busy`, `paused`, `charging`, `error`, `offline` |
| `battery_pct` | number | 0-100 |
| `current_location` | string | Semantic location or waypoint |
| `current_task` | string/null | Active task ID |
| `last_seen` | timestamp | Updated by ROS/backend |
| `error_msg` | string | Empty when healthy |

Reads:

- Robot panel
- KPI strip
- Command validation
- Task assignment

Writes:

- ROS/backend robot heartbeat
- Backend pause/resume/emergency commands

### `commands/{commandId}`

Purpose: auditable high-level intent created by staff or automation.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `command_type` | string | See ROS command mapping |
| `status` | string | `draft`, `queued`, `sent`, `accepted`, `running`, `succeeded`, `failed`, `cancelled` |
| `robot_id` | string/null | Robot target |
| `target` | map | `{ table_id, order_id, party_id, waypoint }` |
| `params` | map | Command-specific parameters |
| `created_by` | string | User uid or service name |
| `created_at` | timestamp | Backend managed |
| `updated_at` | timestamp | Backend managed |
| `task_id` | string/null | Linked task |
| `ros_request_id` | string/null | ROS bridge correlation ID |
| `result` | map/null | Completion payload or failure reason |

Reads:

- Command console
- Activity log
- Task detail

Writes:

- Backend command creation
- ROS bridge status updates
- Backend cancellation

### `tasks/{taskId}`

Purpose: execution state for robot work produced from commands.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `command_id` | string | Parent command |
| `task_type` | string | `customer_check`, `seat_party`, `take_order`, `collect_order`, etc. |
| `status` | string | `queued`, `running`, `blocked`, `succeeded`, `failed`, `cancelled` |
| `robot_id` | string | Assigned robot |
| `current_step` | string/null | Human-readable progress |
| `progress_pct` | number/null | Optional |
| `started_at` | timestamp/null | Set by ROS/backend |
| `completed_at` | timestamp/null | Set by ROS/backend |
| `error_msg` | string | Empty when healthy |

Reads:

- Robot panel
- Activity log
- Command console result timeline

Writes:

- Backend task creation
- ROS bridge status updates

### `events/{eventId}`

Purpose: append-only audit and activity timeline.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `type` | string | `customer_detected`, `table_updated`, `order_ready`, `command_failed`, etc. |
| `severity` | string | `info`, `warning`, `error`, `critical` |
| `message` | string | Human-readable summary |
| `entity_type` | string | `table`, `order`, `robot`, `command`, `party` |
| `entity_id` | string/null | Related document ID |
| `created_at` | timestamp | Backend managed |
| `created_by` | string | User uid, `robot`, or service |
| `metadata` | map | Extra context |

Reads:

- Activity log
- Detail drawers
- Troubleshooting

Writes:

- Backend for all privileged actions
- ROS bridge for robot events

### `users/{uid}`

Purpose: role and profile metadata.

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `display_name` | string | Staff name |
| `email` | string | Firebase Auth email |
| `role` | string | `admin`, `manager`, `operator`, `kitchen`, `viewer` |
| `active` | boolean | Disable access if false |
| `created_at` | timestamp | Backend managed |
| `last_seen` | timestamp | Optional |

Reads:

- RBAC bootstrapping
- User menu

Writes:

- Admin only

## ROS Command Mapping

The web app should issue high-level commands. The backend or ROS bridge should translate them to the final ROS topic, service, or action names once the ROS nodes are implemented.

### Command Catalogue

| UI Command | Command Type | Required Params | Firestore Effects | ROS Intent |
| --- | --- | --- | --- | --- |
| Check Customer | `CHECK_CUSTOMER` | `robot_id` | Create `commands`, `tasks`; possible new `entrance` doc | Detect/confirm people at entrance |
| Update New Customer Number | `UPDATE_CUSTOMER_COUNT` | `party_id`, `party_size` | Patch `entrance.party_size`; event | Update perceived customer count |
| Introduce Table | `INTRODUCE_TABLE` | `robot_id`, `table_id`, `party_id` optional | Command/task; table may become `assigned` or `occupied` | Navigate to/announce table |
| Check Empty Table | `CHECK_EMPTY_TABLE` | `robot_id`, `table_id` optional | Command/task; may patch `tables.status` | Inspect table availability |
| Take Order | `TAKE_ORDER` | `robot_id`, `table_id` | Command/task; may create `orders` | Start order-taking behavior |
| Collect Order | `COLLECT_ORDER` | `robot_id`, `order_id` | Command/task; order becomes `collecting` | Navigate to collect prepared order |
| Deliver Order | `DELIVER_ORDER` | `robot_id`, `order_id`, `table_id` | Order becomes `delivering`, then `delivered` | Deliver order to table |
| Go To Location | `GO_TO_LOCATION` | `robot_id`, `waypoint` | Command/task only | Navigation to named waypoint |
| Pause Robot | `PAUSE_ROBOT` | `robot_id` | Robot status `paused`; event | Pause current robot task |
| Resume Robot | `RESUME_ROBOT` | `robot_id` | Robot status restore; event | Resume robot task processing |
| Emergency Stop | `EMERGENCY_STOP` | `robot_id`, `reason` | Robot status `error`; critical event | Immediate stop/safety command |

### Backend To ROS Bridge Payload

```json
{
  "request_id": "cmd_20260611_001",
  "command_type": "COLLECT_ORDER",
  "robot_id": "ninja",
  "target": {
    "order_id": "GxRqKftiKFh664ElhSdl",
    "table_id": "t_01"
  },
  "params": {
    "pickup_location": "kitchen_bar",
    "requires_tray": true
  }
}
```

### ROS Bridge To Backend Status Payload

```json
{
  "request_id": "cmd_20260611_001",
  "task_id": "task_20260611_001",
  "robot_id": "ninja",
  "status": "running",
  "current_step": "Navigating to kitchen_bar",
  "progress_pct": 35,
  "error_msg": ""
}
```

### ROS Topic / Service Naming Placeholder

Use a stable application-level interface even if the final ROS internals change.

```text
/webapp/commands              backend -> ROS bridge high-level commands
/webapp/command_status        ROS bridge -> backend command status
/webapp/robot_state           ROS bridge -> backend robot heartbeat
/webapp/events                ROS bridge -> backend operational events
```

If ROS services/actions are preferred later, keep the same command payload shape and replace only the transport adapter.

## Role-Based Management Actions

### Roles

| Role | Purpose |
| --- | --- |
| `admin` | Full system configuration, users, emergency controls |
| `manager` | Operational control, ROS commands, overrides, reports |
| `operator` | Front-of-house actions, seating, order handling |
| `kitchen` | Order preparation state only |
| `viewer` | Read-only monitoring |

### Permission Matrix

| Action | Viewer | Kitchen | Operator | Manager | Admin |
| --- | --- | --- | --- | --- | --- |
| View dashboard | yes | yes | yes | yes | yes |
| View activity log | yes | yes | yes | yes | yes |
| Add/update entrance party | no | no | yes | yes | yes |
| Assign party to table | no | no | yes | yes | yes |
| Update table status | no | no | yes | yes | yes |
| Create/edit order | no | limited | yes | yes | yes |
| Mark order ready | no | yes | no | yes | yes |
| Request order delivery | no | no | yes | yes | yes |
| Execute normal ROS command | no | no | no | yes | yes |
| Pause/resume robot | no | no | no | yes | yes |
| Emergency stop | no | no | no | no | yes |
| Manage menu | no | no | no | yes | yes |
| Manage users/roles | no | no | no | no | yes |

### Action Guarding

Every privileged action should be guarded in three places:

- UI hides or disables unavailable actions based on role.
- Backend rejects unauthorized requests.
- Firestore security rules prevent direct unauthorized writes.

## State Transitions

### Customer Party

```text
waiting -> assigned -> seating -> seated
waiting -> no_show
assigned -> waiting
any active state -> cancelled
```

### Table

```text
empty -> assigned -> occupied -> needs_cleaning -> empty
empty -> reserved -> occupied
any state -> unavailable
unavailable -> empty
```

### Order

```text
draft -> confirmed -> preparing -> ready -> collecting -> delivering -> delivered
detected -> confirmed
any active state -> cancelled
any active state -> failed
```

### Command / Task

```text
queued -> sent -> accepted -> running -> succeeded
queued -> cancelled
sent -> failed
accepted -> failed
running -> failed
running -> cancelled
```

## Prototype Build Plan

### Phase 1: Static Prototype

Deliver a clickable UI shell with mock data shaped like Firestore documents.

- Main operations dashboard
- Floor-plan table cards
- Customer queue
- Orders board
- Robot panel
- Command deck
- Role-based disabled states

### Phase 2: Firestore Read Integration

Connect realtime listeners.

- Listen to `tables`, `entrance`, `orders`, `robots`, `menu`, `commands`, `tasks`, `events`
- Normalize old order item formats on read
- Add loading, empty, offline, and error states

### Phase 3: Backend Mutations

Add backend API for privileged writes.

- Entrance create/update
- Table status updates
- Order create/update
- Command creation
- Event creation
- User role lookup

### Phase 4: ROS Bridge Adapter

Connect commands to ROS.

- Backend sends command payload to ROS bridge
- ROS bridge publishes status back
- Robot heartbeat updates `robots`
- Task status updates `tasks`
- Event stream records operational history

### Phase 5: Competition Hardening

- Confirmation flows for high-risk commands
- Retry/cancel command support
- Offline/degraded mode indicators
- Firestore security rules
- Seed data and local demo mode
- End-to-end operator rehearsal scripts

## Frontend Component Plan

```text
src/app/(ops)/dashboard/page.tsx
src/app/(ops)/orders/page.tsx
src/app/(ops)/commands/page.tsx
src/components/ops/TopBar.tsx
src/components/ops/KpiStrip.tsx
src/components/ops/FloorPlan.tsx
src/components/ops/TableCard.tsx
src/components/ops/TableDetailDrawer.tsx
src/components/ops/CustomerQueue.tsx
src/components/ops/RobotPanel.tsx
src/components/ops/OrdersBoard.tsx
src/components/ops/CommandDeck.tsx
src/components/ops/ActivityLog.tsx
src/lib/firebase/client.ts
src/lib/firestore/converters.ts
src/lib/api/client.ts
src/lib/rbac.ts
src/types/firestore.ts
src/types/commands.ts
```

## Backend Module Plan

```text
server/routes/health.ts
server/routes/bootstrap.ts
server/routes/entrance.ts
server/routes/tables.ts
server/routes/orders.ts
server/routes/commands.ts
server/routes/robots.ts
server/services/authz.ts
server/services/firestore.ts
server/services/events.ts
server/services/command-validator.ts
server/services/ros-bridge.ts
server/types/firestore.ts
server/types/commands.ts
```

## Validation Rules

### Entrance

- `party_size` must be integer `1..12` for prototype.
- Cannot assign a party to an unavailable or occupied table without manager/admin override.
- `seated_at` requires `assigned_table`.

### Tables

- `occupied` requires either `current_party` or manager/admin override.
- `empty` should clear `current_order`, `current_party`, and `occupied_since`.
- `needs_cleaning` blocks assignment.

### Orders

- `table_id` must exist.
- New writes should use normalized item objects.
- `confirmed` requires at least one item.
- `ready` requires kitchen, manager, or admin role.
- `delivered` should set `delivered_at` and clear table `current_order` if no active order remains.

### Commands

- `robot_id` must exist and not be offline for movement commands.
- `table_id` must exist for table commands.
- `order_id` must exist for collect/deliver commands.
- Emergency stop requires admin role and reason.

## Open Implementation Decisions

- Final frontend framework: Next.js is recommended, but the current repo does not yet contain the web app scaffold.
- Final backend runtime: Node/Express or Next.js route handlers are both compatible with the existing Firebase Admin dependency.
- Final ROS transport: topic, service, action, or websocket bridge can be selected once ROS nodes are implemented.
- Firebase credentials should not be committed long term; move service account usage to environment variables before deployment.

## Immediate Next Steps

1. Scaffold the web prototype app.
2. Define shared TypeScript types for Firestore documents and commands.
3. Build the static dashboard using the current export as seed data.
4. Add Firestore realtime reads.
5. Add backend write routes and RBAC checks.
6. Implement the ROS bridge adapter behind the `/api/commands` route.
