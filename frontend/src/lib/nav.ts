import {
  Bag, ChartColumn, ClipboardList, Factory, Globe, History, LayoutDashboard, Package,
  ShieldCheck, ShoppingCart, Truck, Users, Warehouse, type LucideIcon,
} from "./icons";

/**
 * Sidebar definition, mirroring backend/apps/accounts/templatetags/navigation.py.
 *
 * `next: true` marks pages already rebuilt in Next.js (client-side navigation).
 * Everything else is a plain link: Next.js proxies it to the Django page, so the
 * whole app keeps working while modules are migrated one at a time.
 */
export type NavLink = { label: string; href: string; next?: boolean; roles?: string[] };
export type NavItem = NavLink & {
  module: string;
  icon: LucideIcon;
  children?: NavLink[];
};

const TRADE_FULL = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"];

export const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Overview",
    items: [{ module: "dashboard", label: "Dashboard", icon: LayoutDashboard, href: "/dashboard/", next: true }],
  },
  {
    title: "Operations",
    items: [
      { module: "products", label: "Products", icon: Package, href: "/products/list/", next: true },
      { module: "inventory", label: "Inventory", icon: Warehouse, href: "/inventory/", next: true },
      {
        module: "sales", label: "Sales", icon: ShoppingCart, href: "/sales/list/",
        children: [
          { label: "Sales orders", href: "/sales/list/" },
          { label: "Pipeline board", href: "/sales/kanban/" },
        ],
      },
      {
        module: "purchase", label: "Purchase", icon: Bag, href: "/purchase/orders/",
        children: [
          { label: "Purchase orders", href: "/purchase/orders/" },
          { label: "Vendors", href: "/purchase/vendors/" },
        ],
      },
      { module: "procurement", label: "Procurement", icon: ClipboardList, href: "/procurement/trigger-dashboard/" },
      {
        module: "manufacturing", label: "Manufacturing", icon: Factory, href: "/manufacturing/orders/",
        children: [
          { label: "Manufacturing orders", href: "/manufacturing/orders/" },
          { label: "Bills of materials", href: "/manufacturing/boms/" },
          { label: "Work centers", href: "/manufacturing/workcenters/" },
        ],
      },
      { module: "delivery", label: "Delivery", icon: Truck, href: "/delivery/" },
    ],
  },
  {
    title: "Trade & Compliance",
    items: [
      {
        module: "foreign_trade", label: "Foreign Trade", icon: Globe, href: "/trade/exports/",
        children: [
          { label: "Export orders", href: "/trade/exports/" },
          { label: "Import orders", href: "/trade/imports/" },
          { label: "Shipments", href: "/trade/shipments/", roles: [...TRADE_FULL, "DOCUMENTATION_OFFICER", "AUDITOR"] },
          { label: "Trade customers", href: "/trade/customers/", roles: TRADE_FULL },
          { label: "Trade suppliers", href: "/trade/suppliers/", roles: TRADE_FULL },
        ],
      },
      {
        module: "blockchain", label: "Blockchain", icon: ShieldCheck, href: "/blockchain/",
        children: [
          { label: "Overview", href: "/blockchain/" },
          { label: "Anchored documents", href: "/blockchain/documents/" },
          { label: "Ledger audit", href: "/blockchain/audit-logs/", roles: [...TRADE_FULL, "AUDITOR"] },
        ],
      },
    ],
  },
  {
    title: "Insights",
    items: [
      { module: "reports", label: "Reports", icon: ChartColumn, href: "/reports/" },
      { module: "audit_logs", label: "Audit Logs", icon: History, href: "/audit/" },
    ],
  },
  {
    title: "Administration",
    items: [{ module: "accounts", label: "Users & Roles", icon: Users, href: "/accounts/users/" }],
  },
];

/** Sections and items visible to a user, given `modules` from /api/auth/me/. */
export function visibleNav(modules: readonly string[], role: string) {
  const allowed = new Set(modules);
  const canSee = (link: NavLink) => !link.roles || role === "ADMIN" || link.roles.includes(role);
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items
      .filter((item) => allowed.has(item.module))
      .map((item) => ({ ...item, children: item.children?.filter(canSee) })),
  })).filter((section) => section.items.length > 0);
}

/** URL prefix that marks an item as active. */
export function itemPrefix(item: NavItem): string {
  const first = item.href.split("/").filter(Boolean)[0];
  return first ? `/${first}/` : item.href;
}
