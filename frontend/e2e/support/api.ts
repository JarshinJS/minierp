import { request, type APIRequestContext } from "@playwright/test";
import { authFile, type Role } from "./users";

const BASE = "http://localhost:3100";

/**
 * API client acting as a seeded user (through the Next.js proxy, like the browser).
 * Used to arrange test data quickly and to prove the server, not just the UI,
 * enforces permissions.
 */
export async function apiAs(role: Role): Promise<APIRequestContext & { csrf: string }> {
  const ctx = await request.newContext({ baseURL: BASE, storageState: authFile(role) });
  const state = await ctx.storageState();
  const csrf = state.cookies.find((c) => c.name === "csrftoken")?.value ?? "";
  return Object.assign(ctx, { csrf });
}

/** POST/PATCH with Django's CSRF header. */
export function write(api: APIRequestContext & { csrf: string }, method: "post" | "patch", url: string, data?: unknown) {
  return api[method](url, { data, headers: { "X-CSRFToken": api.csrf } });
}

/** Create a product through the API and return it. */
export async function createProduct(role: Role, fields: { sku: string; name: string; cost?: string; price?: string }) {
  const api = await apiAs(role);
  const categories = await (await api.get("/api/categories/?limit=50")).json();
  const res = await write(api, "post", "/api/products/", {
    name: fields.name, sku: fields.sku, category: categories.results[0].id, unit_of_measure: "PCS",
    cost_price: fields.cost ?? "100.00", selling_price: fields.price ?? "250.00",
  });
  if (!res.ok()) throw new Error(`createProduct failed: ${res.status()} ${await res.text()}`);
  const product = await res.json();
  await api.dispose();
  return product as { id: string; sku: string; name: string };
}
