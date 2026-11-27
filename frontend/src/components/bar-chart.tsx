"use client";

import { useState } from "react";

/**
 * Single-series bar chart: one hue (the title names the series, so no legend),
 * thin bars with 4px rounded data-ends on the baseline, recessive grid,
 * a hover tooltip per bar and a table view for screen readers / exact values.
 */
export function BarChart({ labels, data, format = (v) => v.toLocaleString("en-IN") }: {
  labels: string[];
  data: number[];
  format?: (value: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const max = Math.max(0, ...data);
  const top = niceCeil(max);
  const ticks = [1, 0.5, 0].map((f) => top * f);

  if (!data.length || max === 0) {
    return <p className="flex h-48 items-center justify-center text-sm text-slate-500">No data yet.</p>;
  }

  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button className="text-xs font-medium text-slate-500 hover:text-slate-900" onClick={() => setAsTable((t) => !t)}>
          {asTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {asTable ? (
        <table className="table table-compact">
          <thead><tr><th>Label</th><th className="num">Value</th></tr></thead>
          <tbody>{labels.map((l, i) => <tr key={l}><td>{l}</td><td className="num">{format(data[i] ?? 0)}</td></tr>)}</tbody>
        </table>
      ) : (
        <div className="flex gap-3" role="img" aria-label={labels.map((l, i) => `${l}: ${format(data[i] ?? 0)}`).join(", ")}>
          {/* y-axis labels */}
          <div className="flex h-48 flex-col justify-between py-0 text-right text-2xs text-slate-500 tabular-nums">
            {ticks.map((t) => <span key={t} className="-translate-y-1/2 first:translate-y-0 last:translate-y-0">{format(t)}</span>)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="relative h-48">
              {/* recessive gridlines */}
              {ticks.map((t) => (
                <div key={t} className="absolute inset-x-0 border-t border-slate-100" style={{ bottom: `${(t / top) * 100}%` }} />
              ))}
              <div className="absolute inset-0 flex items-end gap-[2px]">
                {data.map((value, i) => (
                  <div key={labels[i]} className="relative flex h-full flex-1 items-end justify-center"
                    onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                    <div
                      className={`w-full max-w-10 rounded-t-[4px] transition-colors ${hover === i ? "bg-brand-700" : "bg-brand-600"}`}
                      style={{ height: `${Math.max((value / top) * 100, value > 0 ? 1 : 0)}%` }}
                    />
                    {hover === i && (
                      <div className="pointer-events-none absolute bottom-full z-10 mb-1 rounded-md bg-slate-900 px-2 py-1 text-xs whitespace-nowrap text-white shadow-pop">
                        <span className="text-slate-300">{labels[i]}</span> <span className="font-semibold tabular-nums">{format(value)}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-2 flex gap-[2px]">
              {labels.map((l) => <span key={l} className="flex-1 truncate text-center text-2xs text-slate-500" title={l}>{l}</span>)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Round up to 1/2/5 × 10^n so gridlines land on readable values. */
function niceCeil(value: number): number {
  if (value <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(value));
  const f = value / exp;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * exp;
}
