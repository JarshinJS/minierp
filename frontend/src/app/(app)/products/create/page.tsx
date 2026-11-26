import { PageHeader } from "@/components/ui";
import { BackButton, ProductForm } from "../product-form";

export const metadata = { title: "New product" };

export default function NewProductPage() {
  return (
    <>
      <PageHeader title="New product" description="Define pricing, units and the default procurement route used when stock runs short."
        actions={<BackButton href="/products/list/" />} />
      <ProductForm />
    </>
  );
}
