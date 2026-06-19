import type { Role } from "../types/firestore";

const roleRank: Record<Role, number> = {
  viewer: 0,
  kitchen: 1,
  operator: 2,
  manager: 3,
  admin: 4,
};

export function hasRole(currentRole: Role, allowedRoles: Role[]) {
  return allowedRoles.includes(currentRole);
}

export function hasMinimumRole(currentRole: Role, minimumRole: Role) {
  return roleRank[currentRole] >= roleRank[minimumRole];
}

export function canUpdateOrders(role: Role) {
  return role === "kitchen" || hasMinimumRole(role, "operator");
}
