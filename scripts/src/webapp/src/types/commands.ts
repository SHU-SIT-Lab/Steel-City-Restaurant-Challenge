import type { Role } from "./firestore";

export type CommandType =
  | "CHECK_CUSTOMER"
  | "UPDATE_CUSTOMER_COUNT"
  | "INTRODUCE_TABLE"
  | "CHECK_EMPTY_TABLE"
  | "TAKE_ORDER"
  | "COLLECT_ORDER"
  | "DELIVER_ORDER"
  | "GO_TO_LOCATION"
  | "PAUSE_ROBOT"
  | "RESUME_ROBOT"
  | "EMERGENCY_STOP";

export interface CommandDefinition {
  type: CommandType;
  label: string;
  group: "customer" | "table" | "order" | "robot" | "recovery";
  description: string;
  requiredParams: string[];
  roles: Role[];
  highRisk?: boolean;
}

export interface CommandRequest {
  command_type: CommandType;
  robot_id?: string | null;
  target: {
    table_id?: string;
    order_id?: string;
    party_id?: string;
    waypoint?: string;
  };
  params: Record<string, unknown>;
  idempotency_key: string;
}
