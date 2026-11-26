import { Suspense } from "react";
import { InventoryPage } from "./inventory";

export const metadata = { title: "Inventory" };

export default function Page() {
  return <Suspense><InventoryPage /></Suspense>;
}
