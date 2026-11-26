"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorAlert, Field, Spinner } from "@/components/ui";
import { api, ApiError, unwrap } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import { PROCUREMENT_TYPE, UNIT_OF_MEASURE } from "@/lib/choices";
import { ArrowLeft, Check } from "@/lib/icons";

type Product = Schema<"Product">;

/** Some BOMs have no name/reference; fall back to the product they build. */
export function bomLabel(b: { name: string; reference: string; product_name?: string | null }) {
  const main = b.name || (b.product_name ? `BOM for ${b.product_name}` : "Untitled BOM");
  return b.reference ? `${main} (${b.reference})` : main;
}
type ProductInput = Schema<"ProductRequest">;

const EMPTY: ProductInput = {
  name: "", sku: "", category: "", unit_of_measure: "PCS", cost_price: "", selling_price: "",
  procure_on_demand: false, procurement_type: "PURCHASE", default_vendor: null, default_bom: null, is_active: true,
};

/** Lookup list that may be forbidden for this role (e.g. vendors for a sales user). */
function useOptions(key: string, load: () => Promise<{ id: string; name: string }[]>) {
  return useQuery({ queryKey: ["options", key], queryFn: load, staleTime: 5 * 60_000 });
}

export function ProductForm({ product }: { product?: Product }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState<ProductInput>(() =>
    product
      ? {
          name: product.name, sku: product.sku, category: product.category, unit_of_measure: product.unit_of_measure,
          cost_price: product.cost_price, selling_price: product.selling_price, procure_on_demand: product.procure_on_demand,
          procurement_type: product.procurement_type, default_vendor: product.default_vendor ?? null,
          default_bom: product.default_bom ?? null, is_active: product.is_active,
        }
      : EMPTY,
  );

  const categories = useOptions("categories", async () =>
    (await unwrap(api.GET("/api/categories/", { params: { query: { limit: 500 } } }))).results);
  const vendors = useOptions("vendors", async () =>
    (await unwrap(api.GET("/api/vendors/", { params: { query: { limit: 500 } } }))).results);
  const boms = useOptions("boms", async () =>
    (await unwrap(api.GET("/api/boms/", { params: { query: { limit: 500 } } }))).results.map((b) => ({ id: b.id, name: bomLabel(b) })));

  const save = useMutation({
    mutationFn: () =>
      product
        ? unwrap(api.PUT("/api/products/{id}/", { params: { path: { id: product.id } }, body: form }))
        : unwrap(api.POST("/api/products/", { body: form })),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ["products"] });
      router.push(`/products/${saved.id}/`);
    },
  });
  const errors = save.error instanceof ApiError ? save.error.fieldErrors : {};
  const set = <K extends keyof ProductInput>(key: K, value: ProductInput[K]) => setForm((f) => ({ ...f, [key]: value }));
  const cancelHref = product ? `/products/${product.id}/` : "/products/list/";

  /** A lookup select; if the role can't load the list, keep the current value visible. */
  const lookup = (id: string, key: "default_vendor" | "default_bom", q: typeof vendors, currentName?: string | null) => (
    <select id={id} value={form[key] ?? ""} disabled={!!q.error} onChange={(e) => set(key, e.target.value || null)}>
      <option value="">— None —</option>
      {q.data?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      {q.error && form[key] && <option value={form[key]!}>{currentName ?? "Current selection"}</option>}
    </select>
  );

  return (
    <form className="card max-w-4xl" noValidate onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <div className="card-body space-y-6">
        {save.error && (errors.detail || !Object.keys(errors).length) && <ErrorAlert error={save.error} />}
        <div>
          <h2 className="form-section-title">General</h2>
          <p className="mt-0.5 text-xs text-slate-500">How the product is identified and counted.</p>
          <div className="form-grid mt-4">
            <Field label="Product name" required error={errors.name}>
              {(id) => <input id={id} type="text" value={form.name} onChange={(e) => set("name", e.target.value)} />}
            </Field>
            <Field label="SKU" required error={errors.sku} help="Unique stock-keeping code, e.g. WCH-001.">
              {(id) => <input id={id} type="text" value={form.sku} onChange={(e) => set("sku", e.target.value)} className="font-mono" />}
            </Field>
            <Field label="Category" required error={errors.category}>
              {(id) => (
                <select id={id} value={form.category} onChange={(e) => set("category", e.target.value)}>
                  <option value="">Select a category…</option>
                  {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              )}
            </Field>
            <Field label="Unit of measure" error={errors.unit_of_measure}>
              {(id) => (
                <select id={id} value={form.unit_of_measure} onChange={(e) => set("unit_of_measure", e.target.value as ProductInput["unit_of_measure"])}>
                  {UNIT_OF_MEASURE.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                </select>
              )}
            </Field>
          </div>
        </div>
        <div className="form-section">
          <h2 className="form-section-title">Pricing</h2>
          <p className="mt-0.5 text-xs text-slate-500">Prices in Indian Rupees (₹).</p>
          <div className="form-grid mt-4">
            <Field label="Cost price (₹)" required error={errors.cost_price}>
              {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={form.cost_price} onChange={(e) => set("cost_price", e.target.value)} />}
            </Field>
            <Field label="Selling price (₹)" required error={errors.selling_price}>
              {(id) => <input id={id} type="number" min="0" step="0.01" inputMode="decimal" value={form.selling_price} onChange={(e) => set("selling_price", e.target.value)} />}
            </Field>
          </div>
        </div>
        <div className="form-section">
          <h2 className="form-section-title">Procurement &amp; sourcing</h2>
          <p className="mt-0.5 text-xs text-slate-500">Controls automatic replenishment when orders exceed available stock.</p>
          <div className="form-grid mt-4">
            <Field label="Procurement route" error={errors.procurement_type}>
              {(id) => (
                <select id={id} value={form.procurement_type} onChange={(e) => set("procurement_type", e.target.value as ProductInput["procurement_type"])}>
                  {PROCUREMENT_TYPE.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              )}
            </Field>
            <label className="flex items-start gap-3 sm:pt-7">
              <input type="checkbox" className="mt-0.5" checked={!!form.procure_on_demand} onChange={(e) => set("procure_on_demand", e.target.checked)} />
              <span>
                <span className="block text-sm font-medium text-slate-700">Procure on demand</span>
                <span className="block text-xs text-slate-500">Automatically create a procurement request when stock is insufficient.</span>
              </span>
            </label>
            <Field label="Default vendor" error={errors.default_vendor} help="Used when the route is Purchase.">
              {(id) => lookup(id, "default_vendor", vendors, product?.default_vendor_name)}
            </Field>
            <Field label="Default bill of materials" error={errors.default_bom} help="Used when the route is Manufacturing.">
              {(id) => lookup(id, "default_bom", boms, product?.default_bom_name)}
            </Field>
          </div>
        </div>
        <div className="form-section">
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-0.5" checked={!!form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
            <span>
              <span className="block text-sm font-medium text-slate-700">Active</span>
              <span className="block text-xs text-slate-500">Inactive products are hidden from new sales and purchase orders.</span>
            </span>
          </label>
        </div>
      </div>
      <div className="card-footer">
        <Link href={cancelHref} className="btn btn-secondary">Cancel</Link>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {save.isPending ? <Spinner /> : <Check />} {product ? "Save changes" : "Create product"}
        </button>
      </div>
    </form>
  );
}

export function BackButton({ href }: { href: string }) {
  return <Link href={href} className="btn btn-secondary"><ArrowLeft /> Back</Link>;
}
