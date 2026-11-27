/** Accounts created by `manage.py seed_demo` (backend/core/management/commands/seed_demo.py). */
export const DEMO_PASSWORD = "Demo-pass-2026!";
const DOMAIN = "demo.minierp.dev";

export const USERS = {
  admin: { email: `admin@${DOMAIN}`, name: "Asha Admin" },
  owner: { email: `owner@${DOMAIN}`, name: "Omar Owner" },
  sales: { email: `sales@${DOMAIN}`, name: "Sara Sales" },
  purchase: { email: `purchase@${DOMAIN}`, name: "Paul Purchase" },
  inventory: { email: `inventory@${DOMAIN}`, name: "Ines Inventory" },
  accountant: { email: `accountant@${DOMAIN}`, name: "Arjun Accountant" },
  trade: { email: `trade@${DOMAIN}`, name: "Tara Trade" },
  auditor: { email: `auditor@${DOMAIN}`, name: "Ali Auditor" },
  pending: { email: `pending@${DOMAIN}`, name: "Priya Pending" },
} as const;

export type Role = Exclude<keyof typeof USERS, "pending">;
export const ROLES = Object.keys(USERS).filter((r) => r !== "pending") as Role[];

/** Saved browser session (cookies) for a role, written by global.setup.ts. */
export const authFile = (role: Role) => `e2e/.auth/${role}.json`;

/** Unique suffix so tests never collide with each other or with seed data. */
export const uid = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`.toUpperCase();
