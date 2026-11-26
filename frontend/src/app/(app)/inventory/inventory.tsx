"use client";

import Link from "next/link";
import clsx from "clsx";
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge, EmptyState, ErrorAlert, Field, Modal, PAGE_SIZE, PageHeader, Pagination, SearchInput, Spinner, TableSkeleton,
} from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import { date, money, moneyWhole, qty } from "@/lib/format";
import { AlertTriangle, History, Package, Search, SlidersHorizontal, Warehouse, X, XCircle } from "@/lib/icons";
import { useUrlState } from "@/lib/url-state";

type StockLevel = Schema<"StockLevel">;

const ENTRY_TYPES = [
  { value: "RECEIPT", label: "Receipt (Stock In)", tone: "green", sign: "+" },
  { value: "ISSUE", label: "Issue (Stock Out)", tone: "red", sign: "−" },
  { value: "RESERVATION", label: "Reservation", tone: "blue", sign: "−" },
  { value: "RELEASE", label: "Reservation Release", tone: "purple", sign: "+" },
] as const;
const SHORT_LABEL: Record<string, string> = { RECEIPT: "Receipt", ISSUE: "Issue", RESERVATION: "Reservation", RELEASE: "Release" };

const KEYS = ["tab", "search", "category", "stock", "offset", "product", "entry_type", "reference"] as const;

export function InventoryPage() {
  const [f, setF] = useUrlState(KEYS);
  const tab = f.tab === "ledger" ? "ledger" : "stock";
  const [adjusting, setAdjusting] = useState<{ id: string; name: string } | null>(null);

  const stats = useQuery({ queryKey: ["inventory", "stats"], queryFn: () => unwrap(api.GET("/api/inventory/stock/summary/")) });
  const s = stats.data;

  const tile = (key: "low_stock" | "out_of_stock", label: string, sub: string, count: number | undefined, tone: "amber" | "red") => (
    <button type="button" onClick={() => setF({ tab: "", stock: f.stock === key ? "" : key })}
      className={clsx("kpi text-left transition-colors", tone === "amber" ? "hover:border-amber-300" : "hover:border-red-300",
        f.stock === key && (tone === "amber" ? "border-amber-300 ring-2 ring-amber-400/40" : "border-red-300 ring-2 ring-red-400/40"))}
      aria-pressed={f.stock === key}>
      <div className="kpi-label">{label}
        <span className={clsx("kpi-icon", count ? (tone === "amber" ? "bg-amber-50 text-amber-600" : "bg-red-50 text-red-600") : "")}>
          {tone === "amber" ? <AlertTriangle /> : <XCircle />}
        </span>
      </div>
      <p className={clsx("kpi-value", count ? (tone === "amber" ? "text-amber-600" : "text-red-600") : "")}>{count ?? "—"}</p>
      <p className="kpi-meta">{sub}</p>
    </button>
  );

  return (
    <>
      <PageHeader title="Inventory" description="Stock on hand, reservations and every stock movement recorded in the ledger."
        actions={<button className="btn btn-primary" onClick={() => setAdjusting({ id: "", name: "" })}><SlidersHorizontal /> Adjust stock</button>} />

      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <div className="kpi"><div className="kpi-label">Active SKUs <span className="kpi-icon"><Package /></span></div><p className="kpi-value">{s?.total_skus ?? "—"}</p></div>
          <div className="kpi"><div className="kpi-label">Units on hand <span className="kpi-icon"><Warehouse /></span></div><p className="kpi-value">{s ? qty(Math.round(Number(s.total_items))) : "—"}</p></div>
          <div className="kpi col-span-2 lg:col-span-1"><div className="kpi-label">Stock value <span className="kpi-icon"><Package /></span></div><p className="kpi-value">{s ? moneyWhole(s.total_value) : "—"}</p><p className="kpi-meta">At standard cost</p></div>
          {tile("low_stock", "Low stock", "1–5 units available", s?.low_stock, "amber")}
          {tile("out_of_stock", "Out of stock", "0 or fewer available", s?.out_of_stock, "red")}
        </div>

        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <div className="tabs" role="tablist">
              <button role="tab" aria-selected={tab === "stock"} className={clsx("tab", tab === "stock" && "tab-active")}
                onClick={() => setF({ tab: "" })}><Warehouse className="h-3.5 w-3.5" /> Stock levels</button>
              <button role="tab" aria-selected={tab === "ledger"} className={clsx("tab", tab === "ledger" && "tab-active")}
                onClick={() => setF({ tab: "ledger" })}><History className="h-3.5 w-3.5" /> Movement ledger</button>
            </div>
            {tab === "stock" && f.stock && (
              <span className="inline-flex items-center gap-2 text-xs text-slate-500">
                Showing <Badge tone={f.stock === "out_of_stock" ? "red" : "amber"}>{f.stock === "out_of_stock" ? "Out of stock" : "Low stock"}</Badge>
                <button className="link" onClick={() => setF({ stock: "" })}>Clear</button>
              </span>
            )}
          </div>
          {tab === "stock"
            ? <StockTab f={f} setF={setF} onAdjust={(p) => setAdjusting({ id: p.id, name: p.name })} />
            : <LedgerTab f={f} setF={setF} />}
        </div>
      </div>

      {adjusting && <AdjustModal initial={adjusting} onClose={() => setAdjusting(null)} />}
    </>
  );
}

type TabProps = {
  f: Record<(typeof KEYS)[number], string>;
  setF: (c: Partial<Record<(typeof KEYS)[number], string | number>>) => void;
};

function useCategories() {
  return useQuery({
    queryKey: ["options", "categories"],
    queryFn: async () => (await unwrap(api.GET("/api/categories/", { params: { query: { limit: 500 } } }))).results,
    staleTime: 5 * 60_000,
  });
}

function StockTab({ f, setF, onAdjust }: TabProps & { onAdjust: (p: StockLevel) => void }) {
  const offset = Number(f.offset) || 0;
  const categories = useCategories();
  const stock = useQuery({
    queryKey: ["inventory", "stock", f.search, f.category, f.stock, offset],
    queryFn: () => unwrap(api.GET("/api/inventory/stock/", {
      params: { query: {
        limit: PAGE_SIZE, offset, search: f.search || undefined, category: f.category || undefined,
        stock: (f.stock || undefined) as "low_stock" | "out_of_stock" | undefined,
      } },
    })),
    placeholderData: keepPreviousData,
  });
  const rows = stock.data?.results ?? [];

  return (
    <div role="tabpanel">
      <div className="filter-bar" role="search">
        <SearchInput className="w-full sm:max-w-xs" value={f.search} onChange={(search) => setF({ search })} placeholder="Search name or SKU…" />
        <select aria-label="Category" className="sm:w-48" value={f.category} onChange={(e) => setF({ category: e.target.value })}>
          <option value="">All categories</option>
          {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {(f.search || f.category) && <button className="btn btn-ghost btn-sm" onClick={() => setF({ search: "", category: "" })}><X /> Clear</button>}
      </div>
      {stock.error && <ErrorAlert error={stock.error} className="m-4" />}
      {stock.data && !rows.length ? (
        <EmptyState icon={Search} title="No products match" text="Adjust your search, category or stock filter." />
      ) : (
        <div className={clsx("table-wrap transition-opacity", stock.isPlaceholderData && "opacity-60")}>
          <table className="table">
            <thead>
              <tr>
                <th>Product</th><th className="hidden md:table-cell">Category</th><th className="num hidden lg:table-cell">Unit cost</th>
                <th className="num">On hand</th><th className="num hidden sm:table-cell">Reserved</th><th className="min-w-36">Available</th>
                <th className="num hidden lg:table-cell">Valuation</th><th className="w-px"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            {!stock.data ? <TableSkeleton cols={8} /> : (
              <tbody>
                {rows.map((p) => {
                  const avail = Number(p.avail_qty);
                  return (
                    <tr key={p.id}>
                      <td>
                        <Link href={`/products/${p.id}/`} className="cell-primary hover:text-brand-600">{p.name}</Link>
                        <p className="cell-sub"><span className="font-mono">{p.sku}</span> · {p.unit_of_measure}</p>
                      </td>
                      <td className="hidden md:table-cell">{p.category_name}</td>
                      <td className="num hidden text-slate-500 lg:table-cell">{money(p.cost_price)}</td>
                      <td className="num font-medium text-slate-900">{qty(p.on_hand_qty)}</td>
                      <td className="num hidden text-slate-500 sm:table-cell">{qty(p.reserved_qty)}</td>
                      <td>
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="font-semibold text-slate-900 tabular-nums">{qty(p.avail_qty)}</span>
                          {avail <= 0 ? <Badge tone="red" plain>Out</Badge> : avail <= 5 ? <Badge tone="amber" plain>Low</Badge> : <Badge tone="green" plain>OK</Badge>}
                        </div>
                        <div className="progress mt-1.5">
                          <span className={avail <= 0 ? "bg-red-500!" : avail <= 5 ? "bg-amber-500!" : "bg-emerald-500!"}
                            style={{ width: `${avail <= 0 ? 100 : avail <= 5 ? 20 : Math.min(100, (avail / 50) * 100)}%` }} />
                        </div>
                      </td>
                      <td className="num hidden font-medium text-slate-900 lg:table-cell">{money(p.cost_value)}</td>
                      <td><button className="btn btn-secondary btn-xs" onClick={() => onAdjust(p)}>Adjust</button></td>
                    </tr>
                  );
                })}
              </tbody>
            )}
          </table>
        </div>
      )}
      <Pagination offset={offset} count={stock.data?.count ?? 0} onChange={(o) => setF({ offset: o })} />
    </div>
  );
}

function useProductOptions() {
  return useQuery({
    queryKey: ["options", "products-active"],
    queryFn: async () => (await unwrap(api.GET("/api/inventory/stock/", { params: { query: { limit: 1000 } } }))).results,
    staleTime: 60_000,
  });
}

function LedgerTab({ f, setF }: TabProps) {
  const offset = Number(f.offset) || 0;
  const products = useProductOptions();
  const ledger = useQuery({
    queryKey: ["inventory", "ledger", f.product, f.entry_type, f.reference, offset],
    queryFn: () => unwrap(api.GET("/api/inventory/ledger/", {
      params: { query: {
        limit: PAGE_SIZE, offset, product: f.product || undefined, reference: f.reference || undefined,
        entry_type: (f.entry_type || undefined) as (typeof ENTRY_TYPES)[number]["value"] | undefined,
      } },
    })),
    placeholderData: keepPreviousData,
  });
  const rows = ledger.data?.results ?? [];
  const filtered = f.product || f.entry_type || f.reference;

  return (
    <div role="tabpanel">
      <div className="filter-bar" role="search">
        <select aria-label="Product" className="sm:w-64" value={f.product} onChange={(e) => setF({ product: e.target.value })}>
          <option value="">All products</option>
          {products.data?.map((p) => <option key={p.id} value={p.id}>{p.sku} — {p.name}</option>)}
        </select>
        <select aria-label="Entry type" className="sm:w-48" value={f.entry_type} onChange={(e) => setF({ entry_type: e.target.value })}>
          <option value="">All entry types</option>
          {ENTRY_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <SearchInput className="w-full sm:max-w-56" value={f.reference} onChange={(reference) => setF({ reference })} placeholder="Reference…" />
        {filtered && <button className="btn btn-ghost btn-sm" onClick={() => setF({ product: "", entry_type: "", reference: "" })}><X /> Clear</button>}
      </div>
      {ledger.error && <ErrorAlert error={ledger.error} className="m-4" />}
      {ledger.data && !rows.length ? (
        <EmptyState icon={History} title="No stock movements" text="Receipts, issues and reservations will be listed here." />
      ) : (
        <div className={clsx("table-wrap transition-opacity", ledger.isPlaceholderData && "opacity-60")}>
          <table className="table">
            <thead><tr><th>Date</th><th>Product</th><th>Movement</th><th className="num">Quantity</th><th className="hidden md:table-cell">Reference</th></tr></thead>
            {!ledger.data ? <TableSkeleton cols={5} /> : (
              <tbody>
                {rows.map((e) => {
                  const t = ENTRY_TYPES.find((x) => x.value === e.entry_type);
                  const time = new Date(e.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
                  return (
                    <tr key={e.id}>
                      <td className="whitespace-nowrap text-slate-500">{date(e.created_at)}<p className="cell-sub">{time}</p></td>
                      <td><p className="cell-primary">{e.product_name}</p><p className="cell-sub font-mono">{e.product_sku}</p></td>
                      <td><Badge tone={t?.tone ?? "gray"}>{SHORT_LABEL[e.entry_type] ?? e.entry_type_display}</Badge></td>
                      <td className="num font-semibold">
                        <span className={t?.sign === "+" ? "text-emerald-600" : "text-red-600"}>{t?.sign}{qty(e.quantity)}</span>
                      </td>
                      <td className="hidden max-w-xs truncate text-slate-600 md:table-cell" title={e.reference}>{e.reference || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            )}
          </table>
        </div>
      )}
      <Pagination offset={offset} count={ledger.data?.count ?? 0} onChange={(o) => setF({ offset: o })} />
    </div>
  );
}

function AdjustModal({ initial, onClose }: { initial: { id: string; name: string }; onClose: () => void }) {
  const qc = useQueryClient();
  const products = useProductOptions();
  const [form, setForm] = useState({ product: initial.id, adjustment_type: "RECEIPT" as "RECEIPT" | "ISSUE", quantity: "", reference: "" });
  const adjust = useMutation({
    mutationFn: () => unwrap(api.POST("/api/inventory/adjustments/", { body: form })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inventory"] });
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });
  const errors = adjust.error instanceof ApiError ? adjust.error.fieldErrors : {};

  return (
    <Modal open title="Adjust stock" onClose={onClose}
      footer={<>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" type="submit" form="adjust-form" disabled={adjust.isPending}>
          {adjust.isPending && <Spinner />} Record {form.adjustment_type === "RECEIPT" ? "receipt" : "issue"}
        </button>
      </>}>
      <form id="adjust-form" className="space-y-4" onSubmit={(e) => { e.preventDefault(); adjust.mutate(); }}>
        <p className="text-xs text-slate-500">Creates a receipt or issue entry in the stock ledger.</p>
        {adjust.error && !Object.keys(errors).length && <ErrorAlert error={adjust.error} />}
        <Field label="Product" required error={errors.product}>
          {(id) => initial.id ? (
            <div id={id} className="flex h-9 items-center rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-medium">{initial.name}</div>
          ) : (
            <select id={id} required value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })}>
              <option value="">Select a product…</option>
              {products.data?.map((p) => <option key={p.id} value={p.id}>{p.sku} — {p.name} ({qty(p.avail_qty)} available)</option>)}
            </select>
          )}
        </Field>
        <fieldset>
          <legend className="form-label">Movement</legend>
          <div className="grid grid-cols-2 gap-2">
            {(["RECEIPT", "ISSUE"] as const).map((t) => (
              <label key={t} className={clsx("flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                form.adjustment_type === t ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500" : "border-slate-300")}>
                <input type="radio" name="adjustment_type" checked={form.adjustment_type === t} onChange={() => setForm({ ...form, adjustment_type: t })} />
                {t === "RECEIPT" ? "Receipt (stock in)" : "Issue (stock out)"}
              </label>
            ))}
          </div>
        </fieldset>
        <Field label="Quantity" required error={errors.quantity}>
          {(id) => <input id={id} type="number" min="0.01" step="0.01" inputMode="decimal" required autoFocus
            value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />}
        </Field>
        <Field label="Reference" error={errors.reference} help="Optional, e.g. a stock-take or GRN number.">
          {(id) => <input id={id} type="text" maxLength={100} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />}
        </Field>
      </form>
    </Modal>
  );
}
