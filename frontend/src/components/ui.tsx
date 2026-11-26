"use client";

import clsx from "clsx";
import { useEffect, useId, useState, type ReactNode } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Inbox, Search, X, type LucideIcon } from "@/lib/icons";

/* ---------- Status badges (same tones as core/templatetags/ui.py) ---------- */

const TONES: Record<string, string[]> = {
  gray: ["DRAFT", "NOT_STARTED", "INACTIVE", "UNVERIFIED", "QUOTATION", "QUEUED", "HELD", "AUTO_CREATED"],
  blue: ["CONFIRMED", "ORDER_CONFIRMED", "ORDER_APPROVED", "SENT", "DISPATCHED", "SHIPPED", "SHIPMENT_DISPATCHED",
    "DOCUMENTS_SUBMITTED", "INVOICE_GENERATED", "PROCESSING", "UPDATED"],
  indigo: ["IN_PROGRESS", "IN_TRANSIT", "AT_PORT", "UNDER_REVIEW", "ORDER_CREATED", "DOCUMENT_UPLOADED", "STATUS_CHANGED"],
  purple: ["CUSTOMS", "CUSTOMS_DECLARATION", "STOCK_ADJUSTED"],
  amber: ["PENDING", "PARTIALLY_DELIVERED", "PARTIALLY_RECEIVED", "OVERDUE", "PRICE_CHANGED"],
  green: ["DONE", "COMPLETED", "DELIVERED", "FULLY_DELIVERED", "FULLY_RECEIVED", "RECEIVED", "VERIFIED",
    "DOCUMENT_VERIFIED", "PAID", "PAYMENT_RECEIVED", "CLEARED", "CUSTOMS_CLEARED", "SHIPMENT_DELIVERED", "ACTIVE", "CREATED"],
  red: ["CANCELLED", "FAILED", "TAMPERED", "REJECTED", "DELETED"],
};
const TONE_LOOKUP = new Map(Object.entries(TONES).flatMap(([tone, values]) => values.map((v) => [v, tone])));

export type Tone = "gray" | "blue" | "indigo" | "purple" | "amber" | "green" | "red";

export function Badge({ tone = "gray", children, plain }: { tone?: Tone; children: ReactNode; plain?: boolean }) {
  return <span className={clsx("badge", `badge-${tone}`, plain && "badge-plain")}>{children}</span>;
}

export function StatusBadge({ status, label }: { status?: string | null; label?: string | null }) {
  const value = String(status ?? "").toUpperCase();
  const tone = (TONE_LOOKUP.get(value) ?? "gray") as Tone;
  const text = label || value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  return <Badge tone={tone}>{text || "—"}</Badge>;
}

/* ---------- Page structure ---------- */

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, text, action }: {
  icon?: LucideIcon; title: string; text?: ReactNode; action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon"><Icon /></div>
      <p className="empty-state-title">{title}</p>
      {text && <p className="empty-state-text">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorAlert({ error, className }: { error: unknown; className?: string }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className={clsx("alert alert-danger", className)} role="alert">
      <AlertTriangle />
      <div>{message}</div>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={clsx("spinner", className)} aria-hidden="true" />;
}

/** Placeholder rows for a loading table. */
export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <tbody aria-busy="true">
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r}>
          {Array.from({ length: cols }, (_, c) => (
            <td key={c}><div className="skeleton h-4 w-full max-w-40" /></td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

export function KpiTile({ label, value, meta, icon: Icon }: { label: string; value: ReactNode; meta?: ReactNode; icon?: LucideIcon }) {
  return (
    <div className="kpi">
      <p className="kpi-label">
        {label}
        {Icon && <span className="kpi-icon"><Icon /></span>}
      </p>
      <p className="kpi-value">{value}</p>
      {meta && <div className="kpi-meta">{meta}</div>}
    </div>
  );
}

/* ---------- Lists ---------- */

export const PAGE_SIZE = 20;

export function Pagination({ offset, count, pageSize = PAGE_SIZE, onChange }: {
  offset: number; count: number; pageSize?: number; onChange: (offset: number) => void;
}) {
  if (count <= pageSize) return null;
  const from = offset + 1;
  const to = Math.min(offset + pageSize, count);
  return (
    <div className="pagination">
      <span>Showing <strong className="text-slate-700">{from}–{to}</strong> of <strong className="text-slate-700">{count}</strong></span>
      <div className="flex gap-2">
        <button className="btn btn-secondary btn-sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - pageSize))}>
          <ChevronLeft /> Previous
        </button>
        <button className="btn btn-secondary btn-sm" disabled={to >= count} onClick={() => onChange(offset + pageSize)}>
          Next <ChevronRight />
        </button>
      </div>
    </div>
  );
}

/** Search box that reports its value after the user pauses typing. */
export function SearchInput({ value, onChange, placeholder = "Search…", className }: {
  value: string; onChange: (value: string) => void; placeholder?: string; className?: string;
}) {
  const [text, setText] = useState(value);
  // Follow outside changes (e.g. "Clear filters") without an extra effect render.
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setText(value);
  }
  useEffect(() => {
    if (text === value) return;
    const t = setTimeout(() => onChange(text), 300);
    return () => clearTimeout(t);
  }, [text, value, onChange]);
  return (
    <div className={clsx("search-field", className)}>
      <Search />
      <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} aria-label={placeholder} />
    </div>
  );
}

/* ---------- Forms ---------- */

export function Field({ label, error, help, required, children, className }: {
  label: string; error?: string[] | string; help?: ReactNode; required?: boolean;
  children: (id: string) => ReactNode; className?: string;
}) {
  const id = useId();
  const errors = typeof error === "string" ? [error] : error;
  return (
    <div className={clsx(errors?.length && "has-error", className)}>
      <label htmlFor={id} className="form-label">
        {label}{required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children(id)}
      {help && !errors?.length && <p className="form-help">{help}</p>}
      {errors?.map((e) => <p key={e} className="form-error">{e}</p>)}
    </div>
  );
}

export function Modal({ open, title, onClose, children, footer }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <>
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal-wrap" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-panel fade-in">
          <div className="card-header">
            <h2 className="card-title">{title}</h2>
            <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Close"><X /></button>
          </div>
          <div className="card-body">{children}</div>
          {footer && <div className="card-footer">{footer}</div>}
        </div>
      </div>
    </>
  );
}
