const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const num = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** Values from the API are often decimal strings ("1234.50"). */
function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function money(value: string | number | null | undefined, currency?: string): string {
  const n = toNumber(value);
  if (n === null) return "—";
  if (currency && currency !== "INR") {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(n);
  }
  return inr.format(n);
}

export function qty(value: string | number | null | undefined): string {
  const n = toNumber(value);
  return n === null ? "—" : num.format(n);
}

export function date(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const inrWhole = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

/** Whole rupees, for headline figures (KPI tiles, chart axes). */
export function moneyWhole(value: string | number | null | undefined): string {
  const n = toNumber(value);
  return n === null ? "—" : inrWhole.format(n);
}
