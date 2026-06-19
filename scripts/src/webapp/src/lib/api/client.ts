import type {
  LegacyOrderItem,
  OpsSnapshot,
  OrderStatus,
  Role,
  TableStatus,
} from "../../types/firestore";
import type { CommandType } from "../../types/commands";

export interface SnapshotResponse extends OpsSnapshot {
  mode: "live" | "mock";
}

export interface CreatePartyInput {
  party_size: number;
  notes: string;
}

export interface AssignPartyInput {
  party_id: string;
  table_id: string;
}

export interface UpdateTableInput {
  table_id: string;
  status: TableStatus;
}

export interface CreateOrderInput {
  table_id: string;
  items: LegacyOrderItem[];
  notes: string;
}

export interface AdvanceOrderInput {
  order_id: string;
  status?: OrderStatus;
}

export interface QueueCommandInput {
  command_type: CommandType;
  robot_id: string | null;
  target: {
    table_id?: string;
    order_id?: string;
    party_id?: string;
    waypoint?: string;
  };
  params: Record<string, unknown>;
  idempotency_key: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function fetchSnapshot() {
  return request<SnapshotResponse>("/api/snapshot");
}

export function createParty(input: CreatePartyInput) {
  return request<{ id: string }>("/api/entrance", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function assignParty(input: AssignPartyInput) {
  return request<{ ok: true }>("/api/entrance/assign-table", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function seatParty(input: AssignPartyInput) {
  return request<{ ok: true }>("/api/entrance/seat", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTableStatus(input: UpdateTableInput) {
  return request<{ ok: true }>("/api/tables/status", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function createOrder(input: CreateOrderInput) {
  return request<{ id: string }>("/api/orders", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function advanceOrder(input: AdvanceOrderInput) {
  return request<{ ok: true; status: OrderStatus }>("/api/orders/advance", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function queueCommand(input: QueueCommandInput) {
  return request<{ command_id: string; task_id: string; status: string }>("/api/commands", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function envRole(): Role {
  const role = import.meta.env.VITE_DEFAULT_ROLE;

  if (["admin", "manager", "operator", "kitchen", "viewer"].includes(role)) {
    return role;
  }

  return "manager";
}
