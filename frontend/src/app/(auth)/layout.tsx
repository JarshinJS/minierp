import { CheckCircle2, Layers } from "@/lib/icons";

const POINTS = [
  "Live stock levels with reservations and a full movement ledger",
  "Order-to-delivery and procure-to-receive workflows",
  "Manufacturing orders driven by bills of materials",
  "Role-based access and a complete audit trail",
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-navy-900 p-10 text-slate-300 lg:flex">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white"><Layers className="h-5 w-5" /></span>
          <div className="leading-tight">
            <p className="text-base font-semibold text-white">MiniERP</p>
            <p className="text-xs text-slate-400">Shiv Furniture Works</p>
          </div>
        </div>
        <div className="max-w-md">
          <h2 className="text-3xl leading-tight font-semibold tracking-tight text-white">Run sales, stock, production and trade from one place.</h2>
          <ul className="mt-8 space-y-4 text-sm">
            {POINTS.map((p) => (
              <li key={p} className="flex gap-3"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />{p}</li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-slate-500">MiniERP · Inventory &amp; enterprise resource planning</p>
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-brand-600/10 blur-3xl" aria-hidden="true" />
      </aside>
      <div className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white"><Layers className="h-4 w-4" /></span>
            <span className="text-sm font-semibold">MiniERP <span className="font-normal text-slate-500">· Shiv Furniture Works</span></span>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
