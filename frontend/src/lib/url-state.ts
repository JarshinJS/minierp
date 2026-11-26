"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * List filters live in the URL query string (like the Django pages), so filtered
 * views can be bookmarked/shared and the back button works.
 */
export function useUrlState<K extends string>(keys: readonly K[]) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const values = Object.fromEntries(keys.map((k) => [k, params.get(k) ?? ""])) as Record<K, string>;

  const set = useCallback(
    (changes: Partial<Record<K, string | number>>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(changes)) {
        if (v === "" || v === undefined || v === null || v === 0) next.delete(k);
        else next.set(k, String(v));
      }
      // Changing any filter returns to the first page.
      if (!("offset" in changes)) next.delete("offset");
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return [values, set] as const;
}
