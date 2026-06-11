export type Role = "admin" | "manager" | "operator" | "kitchen" | "viewer";

export type Severity = "info" | "warning" | "error" | "critical";

export type TableStatus =
  | "empty"
  | "reserved"
  | "assigned"
  | "occupied"
  | "needs_cleaning"
  | "unavailable";

export type PartyStatus =
  | "waiting"
  | "assigned"
  | "seating"
  | "seated"
  | "cancelled"
  | "no_show";

export type OrderStatus =
  | "detected"
  | "draft"
  | "confirmed"
  | "preparing"
  | "ready"
  | "collecting"
  | "delivering"
  | "delivered"
  | "cancelled"
  | "failed";

export type RobotStatus =
  | "idle"
  | "busy"
  | "paused"
  | "charging"
  | "error"
  | "offline";

export type TaskStatus =
  | "queued"
  | "running"
  | "blocked"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface FirestoreTimestamp {
  _seconds: number;
  _nanoseconds: number;
}

export interface EntranceParty {
  id: string;
  party_size: number;
  status: PartyStatus;
  detected_by: "robot" | "manual" | "sensor";
  assigned_table: string | null;
  arrived_at: FirestoreTimestamp;
  assigned_at?: FirestoreTimestamp | null;
  seated_at?: FirestoreTimestamp | null;
  notes: string;
  created_by?: string;
  updated_at?: FirestoreTimestamp;
}

export interface Table {
  id: string;
  table_number: number;
  status: TableStatus;
  pose_x: number;
  pose_y: number;
  pose_theta: number;
  current_order: string | null;
  current_party?: string | null;
  occupied_since?: FirestoreTimestamp | null;
  last_updated: FirestoreTimestamp;
}

export interface MenuItem {
  id: string;
  name: string;
  category: string;
  available?: boolean;
  display_order?: number;
  graspable?: boolean;
  yolo_class?: number | null;
}

export interface NormalizedOrderItem {
  item_id: string;
  name: string;
  quantity: number;
  notes?: string;
  graspable?: boolean;
}

export type LegacyOrderItem = string | NormalizedOrderItem;

export interface Order {
  id: string;
  table_id: string;
  status: OrderStatus;
  items: LegacyOrderItem[];
  assigned_robot?: string | null;
  used_tray?: boolean | null;
  customer_gesture?: string | null;
  notes?: string;
  created_at?: FirestoreTimestamp;
  confirmed_at?: FirestoreTimestamp | null;
  ready_at?: FirestoreTimestamp | null;
  collected_at?: FirestoreTimestamp | null;
  delivered_at?: FirestoreTimestamp | null;
  created_by?: string;
  updated_at?: FirestoreTimestamp;
}

export interface Robot {
  id: string;
  name: string;
  model: string;
  status: RobotStatus;
  battery_pct: number;
  current_location: string;
  current_task: string | null;
  last_seen: FirestoreTimestamp;
  error_msg: string;
}

export interface Task {
  id: string;
  command_id: string;
  task_type: string;
  status: TaskStatus;
  robot_id: string;
  current_step: string | null;
  progress_pct: number | null;
  started_at?: FirestoreTimestamp | null;
  completed_at?: FirestoreTimestamp | null;
  error_msg: string;
}

export interface Event {
  id: string;
  type: string;
  severity: Severity;
  message: string;
  entity_type: "table" | "order" | "robot" | "command" | "party" | "system";
  entity_id: string | null;
  created_at: FirestoreTimestamp;
  created_by: string;
  metadata?: Record<string, unknown>;
}

export interface OpsSnapshot {
  role: Role;
  entrance: EntranceParty[];
  tables: Table[];
  menu: MenuItem[];
  orders: Order[];
  robots: Robot[];
  tasks: Task[];
  events: Event[];
}
