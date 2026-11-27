"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "./api/client";
import type { Schema } from "./api/types";

export { safeNext } from "./safe-redirect";

export type CurrentUser = Schema<"CurrentUser">;

/**
 * Why the backend refused an authenticated account (403 with `code`). The backend
 * enforces this on every request; these messages only explain it to the user.
 */
export const ACCOUNT_STATUS_MESSAGES: Record<string, { title: string; body: string }> = {
  account_pending: {
    title: "Waiting for approval",
    body: "Your account has been created and is waiting for an administrator to approve it. You'll be able to sign in once it is approved.",
  },
  account_rejected: {
    title: "Account request not approved",
    body: "An administrator did not approve this account. Contact your administrator if you think this is a mistake.",
  },
  account_suspended: {
    title: "Account suspended",
    body: "Your account has been suspended. Contact your administrator.",
  },
  account_disabled: {
    title: "Account disabled",
    body: "Your account has been disabled. Contact your administrator.",
  },
};

/** The account-status code from an API error (e.g. "account_pending"), if any. */
export function accountBlockCode(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.status !== 403) return null;
  const code = (error.body as { code?: unknown } | null)?.code;
  return typeof code === "string" && code in ACCOUNT_STATUS_MESSAGES ? code : null;
}

// Set when /api/auth/me/ was refused because of the account's status.
let lastBlockCode: string | null = null;
export function lastAccountBlockCode() {
  return lastBlockCode;
}

/** The logged-in user, or `null` when not logged in (or the account is blocked). */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<CurrentUser | null> => {
      try {
        const me = await unwrap(api.GET("/api/auth/me/"));
        lastBlockCode = null;
        return me;
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          lastBlockCode = accountBlockCode(e);
          return null;
        }
        throw e;
      }
    },
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => unwrap(api.POST("/api/auth/login/", { body })),
    onSuccess: (user) => {
      qc.clear();
      qc.setQueryData(["me"], user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/logout/")),
    onSettled: () => {
      qc.clear();
      // Full page load on purpose: also resets any Django-rendered state.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login/");
    },
  });
}

/** Whether the user's role may use `module` (mirrors the backend's MODULE_ACCESS). */
export function canAccess(user: CurrentUser | null | undefined, module: string) {
  return !!user && (user.role === "ADMIN" || user.modules.includes(module));
}

/** Whether the user may perform a write action such as "products.write" (UI hint; the API enforces it). */
export function can(user: CurrentUser | null | undefined, capability: string) {
  return !!user && user.capabilities.includes(capability);
}
