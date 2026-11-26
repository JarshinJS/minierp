import type { components } from "./schema";

/** Shorthand for a schema component, e.g. Schema<"Product">. */
export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];
