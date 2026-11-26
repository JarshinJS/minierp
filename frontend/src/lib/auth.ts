"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "./api/client";
import type { Schema } from "./api/types";

export type CurrentUser = Schema<"CurrentUser">;

/** The logged-in user, or `null` when not logged in. */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<CurrentUser | null> => {
      try {
        return await unwrap(api.GET("/api/auth/me/"));
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return null;
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

/** Only allow same-site relative redirects after login (no open redirects). */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/dashboard/";
  return next;
}
