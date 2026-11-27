"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import clsx from "clsx";
import { Badge, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { can, canAccess, useMe } from "@/lib/auth";
import { money, qty } from "@/lib/format";
import { History, Pencil } from "@/lib/icons";
import { useProduct } from "./use-product";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: me } = useMe();
  const { data: p, error } = useProduct(id);
  if (error) return <ErrorAlert error={error} />;
  if (!p) return <Spinner className="text-brand-600" />;

  const available = Number(p.available_qty);
  return (
    <>
      <p className="mb-1 font-mono text-xs text-slate-500">{p.sku}</p>
      <PageHeader
        title={p.name}
        description={<span className="inline-flex items-center gap-2">{p.category_name} · {p.unit_of_measure_display} · {p.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}</span>}
        actions={<>
          {canAccess(me, "audit_logs") && <a href={`/audit/?record_type=Product&record_id=${p.id}`} className="btn btn-secondary"><History /> History</a>}
          {can(me, "products.write") && <Link href={`/products/${p.id}/edit/`} className="btn btn-primary"><Pencil /> Edit</Link>}
        </>}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="card">
            <div className="card-header"><h2 className="card-title">Pricing</h2></div>
            <dl className="dl-grid card-body sm:grid-cols-3">
              <div><dt>Selling price</dt><dd className="text-base">{money(p.selling_price)}</dd></div>
              <div><dt>Cost price</dt><dd className="text-base">{money(p.cost_price)}</dd></div>
              <div><dt>Unit of measure</dt><dd>{p.unit_of_measure_display}</dd></div>
            </dl>
          </div>
          <div className="card">
            <div className="card-header"><h2 className="card-title">Procurement</h2></div>
            <dl className="dl-grid card-body">
              <div><dt>Procurement route</dt><dd>{p.procurement_type_display}</dd></div>
              <div><dt>Procure on demand</dt><dd>{p.procure_on_demand ? <Badge tone="indigo">Enabled</Badge> : <Badge>Disabled</Badge>}</dd></div>
              <div><dt>Default vendor</dt><dd>{p.default_vendor_name ?? "—"}</dd></div>
              <div><dt>Default bill of materials</dt><dd>{p.default_bom ? <a className="link" href={`/manufacturing/boms/${p.default_bom}/`}>{p.default_bom_name || `BOM for ${p.name}`}</a> : "—"}</dd></div>
            </dl>
          </div>
        </div>
        <div className="card h-fit">
          <div className="card-header">
            <h2 className="card-title">Stock</h2>
            {available <= 0 ? <Badge tone="red">Out of stock</Badge> : available <= 5 ? <Badge tone="amber">Low stock</Badge> : <Badge tone="green">In stock</Badge>}
          </div>
          <div className="card-body">
            <p className="text-xs font-medium text-slate-500">Available</p>
            <p className={clsx("mt-1 text-3xl font-semibold tabular-nums", available <= 0 ? "text-red-600" : "text-slate-900")}>{qty(p.available_qty)}</p>
            <dl className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">On hand</dt><dd className="font-medium tabular-nums">{qty(p.on_hand_qty)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Reserved for orders</dt><dd className="font-medium tabular-nums">{qty(p.reserved_qty)}</dd></div>
            </dl>
          </div>
          <div className="card-footer justify-start text-xs text-slate-500">
            {canAccess(me, "inventory") ? <Link href="/inventory/" className="link">Adjust stock in Inventory</Link> : "Adjust stock from the Inventory module."}
          </div>
        </div>
      </div>
    </>
  );
}
