"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import type { ReactNode } from "react";
import { BarChart } from "@/components/bar-chart";
import { Badge, EmptyState, ErrorAlert, PageHeader, StatusBadge } from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import { useMe } from "@/lib/auth";
import { moneyWhole, qty } from "@/lib/format";
import {
  AlertTriangle, Boxes, ChartColumn, CheckCircle2, ClipboardList, Factory, Globe, History, Package,
  ShoppingCart, Bag, Truck, Warehouse, type LucideIcon,
} from "@/lib/icons";

type Widget = Schema<"DashboardWidget">;
const REFRESH_MS = 30_000;

const WIDGET_ICONS: Record<string, LucideIcon> = {
  ProductWidget: Package, InventoryWidget: Warehouse, SalesWidget: ShoppingCart, PurchaseWidget: Bag,
  ManufacturingWidget: Factory, ProcurementWidget: ClipboardList, DeliveryWidget: Truck,
  ReportsWidget: ChartColumn, AuditWidget: History, ForeignTradeWidget: Globe,
};

const n = (data: Widget["data"], key: string) => Number(data[key] ?? 0);
const M = ({ children }: { children: ReactNode }) => <strong className="font-semibold text-slate-700">{children}</strong>;
const Unit = ({ children }: { children: ReactNode }) => <span className="text-sm font-medium text-slate-500">{children}</span>;

/** Value + meta line for each widget type (mirrors dashboard_live.html). */
function widgetBody(w: Widget): { value: ReactNode; meta: ReactNode } {
  const d = w.data;
  switch (w.class_name) {
    case "ProductWidget":
      return { value: n(d, "total_products"), meta: <><span><M>{n(d, "active_products")}</M> active</span><span><M>{n(d, "inactive_products")}</M> inactive</span></> };
    case "InventoryWidget":
      return {
        value: moneyWhole(n(d, "inventory_value")),
        meta: <>
          <span><M>{qty(n(d, "total_stock"))}</M> on hand</span>
          <span><M>{qty(n(d, "reserved_stock"))}</M> reserved</span>
          {n(d, "low_stock_count") > 0 && <Link href="/inventory/?stock=low_stock"><Badge tone="red">{n(d, "low_stock_count")} low stock</Badge></Link>}
        </>,
      };
    case "SalesWidget":
      return {
        value: moneyWhole(n(d, "monthly_sales")),
        meta: <>
          <span>This month</span>
          <span>Today <M>{moneyWhole(n(d, "today_sales_value"))}</M> ({n(d, "today_sales_count")})</span>
          <span><M>{n(d, "pending_orders")}</M> open · <M>{n(d, "delivered_orders")}</M> delivered</span>
        </>,
      };
    case "PurchaseWidget":
      return { value: moneyWhole(n(d, "total_purchases_value")), meta: <><span>Total spend</span><span><M>{n(d, "pending_pos")}</M> pending POs</span><span><M>{n(d, "received_pos")}</M> received</span></> };
    case "ManufacturingWidget":
      return { value: <>{n(d, "active_mos")} <Unit>in progress</Unit></>, meta: <><span><M>{n(d, "planned_mos")}</M> planned</span><span><M>{n(d, "completed_mos")}</M> completed</span></> };
    case "ProcurementWidget":
      return {
        value: <>{n(d, "open_requisitions")} <Unit>open requests</Unit></>,
        meta: <><span><M>{n(d, "open_pos")}</M> open POs</span>{n(d, "delayed_orders") ? <Badge tone="red">{n(d, "delayed_orders")} delayed</Badge> : <span>None delayed</span>}</>,
      };
    case "DeliveryWidget":
      return { value: <>{n(d, "pending_deliveries")} <Unit>pending</Unit></>, meta: <><span><M>{n(d, "dispatched")}</M> dispatched</span><span><M>{n(d, "delivered")}</M> delivered</span></> };
    case "ReportsWidget":
      return { value: <>{n(d, "generated_reports")} <Unit>report categories</Unit></>, meta: <span><M>{n(d, "recent_exports_count")}</M> report events logged</span> };
    case "AuditWidget":
      return { value: <>{n(d, "today_activities")} <Unit>events today</Unit></>, meta: <><span><M>{n(d, "create_actions")}</M> creates</span><span><M>{n(d, "update_actions")}</M> updates</span><span><M>{n(d, "login_count")}</M> logins</span></> };
    case "ForeignTradeWidget":
      return { value: <>{n(d, "exports")} <Unit>exports</Unit> · {n(d, "imports")} <Unit>imports</Unit></>, meta: <><span><M>{n(d, "bc_total")}</M> docs anchored</span><span><M>{n(d, "bc_verified")}</M> verified</span></> };
    default:
      return { value: "—", meta: null };
  }
}

// Which roles see which chart (as in dashboard_live.html).
const CHARTS = [
  { key: "sales_trend", title: "Sales order value", subtitle: "Last 6 months, excluding cancelled orders", money: true, roles: ["SALES_USER"] },
  { key: "purchase_trend", title: "Purchase spend", subtitle: "Last 6 months, excluding cancelled orders", money: true, roles: ["PURCHASE_USER"] },
  { key: "manufacturing_progress", title: "Manufacturing orders by status", subtitle: "All manufacturing orders", money: false, roles: ["MANUFACTURING_USER"] },
  { key: "inventory_movement", title: "Inventory movement", subtitle: "Total quantity by ledger entry type", money: false, roles: ["INVENTORY_MANAGER"] },
] as const;
type Series = { labels: string[]; data: number[] };

function timeAgo(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  const units: [number, string][] = [[86400, "day"], [3600, "hour"], [60, "minute"]];
  const [size, unit] = units.find(([sz]) => s >= sz)!;
  const v = Math.floor(s / size);
  return `${v} ${unit}${v === 1 ? "" : "s"} ago`;
}

function initials(name: string) {
  const p = name.split(/\s+/).filter(Boolean);
  return (p.length > 1 ? p[0]![0]! + p.at(-1)![0]! : (p[0] ?? "?").slice(0, 2)).toUpperCase();
}

const Card = ({ title, subtitle, action, children, className }: {
  title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string;
}) => (
  <div className={clsx("card overflow-hidden", className)}>
    <div className="card-header">
      <div><h2 className="card-title">{title}</h2>{subtitle && <p className="card-subtitle">{subtitle}</p>}</div>
      {action}
    </div>
    {children}
  </div>
);

export default function DashboardPage() {
  const { data: me } = useMe();
  const overview = useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: () => unwrap(api.GET("/api/dashboard/")),
    refetchInterval: REFRESH_MS,
  });
  const role = me?.role ?? "";
  const charts = CHARTS.filter((c) => ["ADMIN", "BUSINESS_OWNER", ...c.roles].includes(role));
  const analytics = useQuery({
    queryKey: ["dashboard", "analytics"],
    queryFn: async () => (await unwrap(api.GET("/api/dashboard/analytics/"))) as Record<string, Series>,
    refetchInterval: REFRESH_MS,
    enabled: charts.length > 0,
  });

  const d = overview.data;
  const modules = new Set(d?.allowed_modules ?? []);
  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <>
      <PageHeader
        title={`Welcome back, ${me?.full_name || "there"}`}
        description={`Business overview for Shiv Furniture Works · ${today}`}
        actions={<>
          <span className="hidden text-xs text-slate-500 sm:inline">Auto-refreshes every 30s</span>
          {modules.has("reports") && role !== "TRADE_MANAGER" && <a href="/reports/" className="btn btn-primary"><ChartColumn /> Reports</a>}
        </>}
      />
      {overview.error && <ErrorAlert error={overview.error} className="mb-6" />}

      <div className="space-y-6">
        <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {!d && Array.from({ length: 4 }, (_, i) => <div key={i} className="kpi"><div className="skeleton h-4 w-24" /><div className="skeleton h-7 w-32" /><div className="skeleton h-3 w-40" /></div>)}
          {d?.widgets.map((w) => {
            const Icon = WIDGET_ICONS[w.class_name] ?? Boxes;
            const { value, meta } = widgetBody(w);
            return (
              <div key={w.class_name} className="kpi">
                <div className="kpi-label"><span>{w.title}</span><span className="kpi-icon"><Icon /></span></div>
                <p className="kpi-value">{value}</p>
                <div className="kpi-meta">{meta}</div>
              </div>
            );
          })}
          {d && d.widgets.length === 0 && (
            <div className="card sm:col-span-2 xl:col-span-4">
              <EmptyState title="No metrics for your role" text="Your role does not have any dashboard widgets assigned." />
            </div>
          )}
        </section>

        {charts.length > 0 && (
          <section aria-label="Analytics" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {charts.map((c) => {
              const series = analytics.data?.[c.key];
              return (
                <Card key={c.key} title={c.title} subtitle={c.subtitle}>
                  <div className="card-body">
                    {series
                      ? <BarChart labels={series.labels} data={series.data} format={c.money ? moneyWhole : undefined} />
                      : <div className="skeleton h-48 w-full" />}
                  </div>
                </Card>
              );
            })}
          </section>
        )}

        <section aria-label="Operations" className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card title="Needs attention">
            <ul className="divide-y divide-slate-100">
              {d?.intelligence_alerts.map((a) => (
                <li key={a.text} className="flex items-start gap-3 px-5 py-3">
                  {a.type === "warning" ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-label="Warning" />
                    : <CheckCircle2 className={clsx("mt-0.5 h-4 w-4 shrink-0", a.type === "success" ? "text-emerald-500" : "text-sky-500")} aria-label={a.type} />}
                  <p className="text-sm text-slate-700">{a.text}</p>
                </li>
              ))}
              {d && !d.intelligence_alerts.length && <li><EmptyState icon={CheckCircle2} title="All clear" text="No operational issues detected." /></li>}
            </ul>
          </Card>

          {modules.has("manufacturing") && (
            <Card title="Production in progress" action={<a href="/manufacturing/orders/" className="link text-xs">View all</a>}>
              <ul className="divide-y divide-slate-100">
                {d?.manufacturing_progress.map((mo) => (
                  <li key={mo.id} className="px-5 py-3">
                    <div className="mb-2 flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <a href={`/manufacturing/orders/${mo.id}/`} className="cell-mono hover:text-brand-600">{mo.number}</a>
                        <p className="truncate text-sm font-medium text-slate-900">{mo.product}</p>
                      </div>
                      <StatusBadge status={mo.status} label={mo.status_label} />
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="progress flex-1"><span style={{ width: `${mo.percentage}%` }} /></div>
                      <span className="w-9 text-right text-xs font-semibold text-slate-700 tabular-nums">{mo.percentage}%</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{mo.detail}</p>
                  </li>
                ))}
                {d && !d.manufacturing_progress.length && <li><EmptyState icon={Factory} title="No active production" text="Confirmed and in-progress manufacturing orders appear here." /></li>}
              </ul>
            </Card>
          )}

          <Card title="Recent activity" className={clsx(!modules.has("manufacturing") && "lg:col-span-2")}
            action={modules.has("audit_logs") ? <a href="/audit/" className="link text-xs">Audit log</a> : undefined}>
            <ul className="divide-y divide-slate-100">
              {d?.recent_activities.map((a) => (
                <li key={a.id} className="flex items-start gap-3 px-5 py-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-2xs font-semibold text-slate-600">{initials(a.user || "System")}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-700">
                      <span className="font-medium text-slate-900">{a.user || "System"}</span> {a.action.toLowerCase()} <span className="font-medium text-slate-900">{a.record_type}</span>
                    </p>
                    <p className="text-xs text-slate-500">{a.module.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())} · {timeAgo(a.timestamp)}</p>
                  </div>
                </li>
              ))}
              {d && !d.recent_activities.length && <li><EmptyState icon={History} title="No activity yet" text="Changes made across modules will show up here." /></li>}
            </ul>
          </Card>
        </section>

        {(modules.has("inventory") || modules.has("products") || modules.has("delivery")) && (
          <section aria-label="Stock and deliveries" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {(modules.has("inventory") || modules.has("products")) && (
              <Card title="Low stock" subtitle="Active products with 5 or fewer units available"
                action={modules.has("inventory") ? <Link href="/inventory/?stock=low_stock" className="link text-xs">View inventory</Link> : undefined}>
                {d?.low_stock.length ? (
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Product</th><th>SKU</th><th className="num">Available</th></tr></thead>
                      <tbody>
                        {d.low_stock.map((p) => (
                          <tr key={p.sku}>
                            <td className="cell-primary">{p.name}</td>
                            <td className="cell-mono">{p.sku}</td>
                            <td className={clsx("num font-semibold", p.available_qty <= 0 ? "text-red-600" : "text-amber-600")}>{qty(p.available_qty)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : d && <EmptyState icon={Package} title="Stock levels healthy" text="No active product is at or below the reorder level." />}
              </Card>
            )}
            {modules.has("delivery") && (
              <Card title="Pending deliveries" subtitle="Delivery notes waiting to be dispatched" action={<a href="/delivery/" className="link text-xs">View all</a>}>
                {d?.pending_deliveries.length ? (
                  <div className="table-wrap">
                    <table className="table">
                      <thead><tr><th>Delivery</th><th>Customer</th><th className="text-right">Created</th></tr></thead>
                      <tbody>
                        {d.pending_deliveries.map((dn) => (
                          <tr key={dn.id}>
                            <td><a href={`/delivery/${dn.id}/`} className="cell-primary hover:text-brand-600">{dn.delivery_number}</a><p className="cell-sub">{dn.order_number}</p></td>
                            <td>{dn.customer_name}</td>
                            <td className="text-right text-xs whitespace-nowrap text-slate-500">{dn.created_at}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : d && <EmptyState icon={Truck} title="Nothing waiting" text="All delivery notes have been dispatched." />}
              </Card>
            )}
          </section>
        )}
      </div>
    </>
  );
}
