"use client";

import { useParams } from "next/navigation";
import { ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { BackButton, ProductForm } from "../../product-form";
import { useProduct } from "../use-product";

export default function EditProductPage() {
  const { id } = useParams<{ id: string }>();
  const product = useProduct(id);
  if (product.error) return <ErrorAlert error={product.error} />;
  if (!product.data) return <Spinner className="text-brand-600" />;
  return (
    <>
      <PageHeader title={`Edit ${product.data.name}`} description="Define pricing, units and the default procurement route used when stock runs short."
        actions={<BackButton href={`/products/${id}/`} />} />
      <ProductForm product={product.data} />
    </>
  );
}
