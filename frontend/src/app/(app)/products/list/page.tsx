import { Suspense } from "react";
import { ProductList } from "./product-list";

export const metadata = { title: "Products" };

export default function ProductsPage() {
  return <Suspense><ProductList /></Suspense>;
}
