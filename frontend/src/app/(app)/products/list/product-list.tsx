"use client";

import Link from "next/link";
import clsx from "clsx";
import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import {
  Badge, EmptyState, ErrorAlert, Modal, PAGE_SIZE, PageHeader, Pagination, SearchInput, Spinner, TableSkeleton,
} from "@/components/ui";
import { api, unwrap } from "@/lib/api/client";
import { can, useMe } from "@/lib/auth";
import type { Schema } from "@/lib/api/types";
import { money, qty } from "@/lib/format";
import { Package, Pencil, Plus, Search, X, XCircle } from "@/lib/icons";
import { useUrlState } from "@/lib/url-state";

type Product = Schema<"Product">;

export function StockCell({ product }: { product: Product }) {
  const available = Number(product.available_qty);
  return (
    <>
      <span className={clsx("font-semibold", available <= 0 ? "text-red-700" : available <= 5 ? "text-amber-700" : "text-slate-900")}>
        {qty(product.available_qty)}
      </span>
      {available <= 5 && <p className={clsx("cell-sub", available <= 0 ? "text-red-700" : "text-amber-700")}>{available <= 0 ? "Out of stock" : "Low stock"}</p>}
    </>
  );
}

export function ProductList() {
  const [filters, setFilters] = useUrlState(["search", "category", "status", "offset"] as const);
  const offset = Number(filters.offset) || 0;
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState<Product | null>(null);
  // UI hint only: the API refuses catalogue changes without products.write.
  const { data: me } = useMe();
  const canWrite = can(me, "products.write");

  const categories = useQuery({
    queryKey: ["options", "categories"],
    queryFn: async () => (await unwrap(api.GET("/api/categories/", { params: { query: { limit: 500 } } }))).results,
    staleTime: 5 * 60_000,
  });
  const products = useQuery({
    queryKey: ["products", "list", filters],
    queryFn: () => unwrap(api.GET("/api/products/", {
      params: {
        query: {
          limit: PAGE_SIZE, offset,
          search: filters.search || undefined,
          category: filters.category || undefined,
          status: (filters.status || undefined) as "active" | "inactive" | undefined,
        },
      },
    })),
    placeholderData: keepPreviousData,
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/products/{id}/deactivate/", { params: { path: { id } } })),
    onSuccess: () => {
      setConfirm(null);
      qc.invalidateQueries({ queryKey: ["products"] });
    },
  });

  const filtered = !!(filters.search || filters.category || filters.status);
  const rows = products.data?.results ?? [];

  return (
    <>
      <PageHeader
        title="Products"
        description="Raw materials, sub-assemblies and finished furniture in your catalog."
        actions={canWrite && <Link href="/products/create/" className="btn btn-primary"><Plus /> New product</Link>}
      />
      <div className="card">
        <div className="filter-bar" role="search">
          <SearchInput className="w-full sm:max-w-xs" value={filters.search} onChange={(search) => setFilters({ search })} placeholder="Search name or SKU…" />
          <select aria-label="Category" className="sm:w-48" value={filters.category} onChange={(e) => setFilters({ category: e.target.value })}>
            <option value="">All categories</option>
            {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select aria-label="Status" className="sm:w-40" value={filters.status} onChange={(e) => setFilters({ status: e.target.value })}>
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          {filtered && (
            <button className="btn btn-ghost btn-sm" onClick={() => setFilters({ search: "", category: "", status: "" })}><X /> Clear filters</button>
          )}
        </div>
        {products.error && <ErrorAlert error={products.error} className="m-4" />}
        {products.data && rows.length === 0 ? (
          filtered
            ? <EmptyState icon={Search} title="No matching products" text="Try a different search term or clear the filters." />
            : <EmptyState icon={Package} title="No products yet" text="Add your first product to start tracking stock, sales and purchases."
                action={canWrite && <Link href="/products/create/" className="btn btn-primary"><Plus /> New product</Link>} />
        ) : (
          <div className={clsx("table-wrap transition-opacity", products.isPlaceholderData && "opacity-60")}>
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="hidden md:table-cell">Category</th>
                  <th className="num">Price</th>
                  <th className="num">Available</th>
                  <th className="num hidden lg:table-cell">On hand</th>
                  <th>Status</th>
                  <th className="w-px"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              {!products.data ? <TableSkeleton cols={7} /> : (
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <Link href={`/products/${p.id}/`} className="cell-primary hover:text-brand-600">{p.name}</Link>
                        <p className="cell-sub"><span className="font-mono">{p.sku}</span> · {p.unit_of_measure_display}</p>
                      </td>
                      <td className="hidden md:table-cell">{p.category_name}</td>
                      <td className="num">
                        <p className="font-medium text-slate-900">{money(p.selling_price)}</p>
                        <p className="cell-sub">Cost {money(p.cost_price)}</p>
                      </td>
                      <td className="num"><StockCell product={p} /></td>
                      <td className="num hidden text-slate-500 lg:table-cell">{qty(p.on_hand_qty)}</td>
                      <td>{p.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}</td>
                      <td>
                        {canWrite && <div className="flex items-center justify-end gap-1">
                          <Link href={`/products/${p.id}/edit/`} className="btn btn-ghost btn-icon btn-sm" title={`Edit ${p.name}`}>
                            <span className="sr-only">Edit {p.name}</span><Pencil />
                          </Link>
                          {p.is_active && (
                            <button className="btn btn-ghost btn-icon btn-sm text-red-600 hover:bg-red-50 hover:text-red-700"
                              title={`Deactivate ${p.name}`} onClick={() => setConfirm(p)}>
                              <span className="sr-only">Deactivate {p.name}</span><XCircle />
                            </button>
                          )}
                        </div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              )}
            </table>
          </div>
        )}
        <Pagination offset={offset} count={products.data?.count ?? 0} onChange={(o) => setFilters({ offset: o })} />
      </div>

      <Modal open={!!confirm} title="Deactivate product" onClose={() => { setConfirm(null); deactivate.reset(); }}
        footer={<>
          <button className="btn btn-secondary" onClick={() => setConfirm(null)}>Cancel</button>
          <button className="btn btn-danger" disabled={deactivate.isPending} onClick={() => confirm && deactivate.mutate(confirm.id)}>
            {deactivate.isPending && <Spinner />} Deactivate
          </button>
        </>}>
        <p className="text-sm text-slate-600">Deactivate <strong className="text-slate-900">{confirm?.name}</strong>? It will be hidden from new sales and purchase orders.</p>
        {deactivate.error && <ErrorAlert error={deactivate.error} className="mt-4" />}
      </Modal>
    </>
  );
}
