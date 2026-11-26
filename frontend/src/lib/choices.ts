// Labels for enum values (the OpenAPI schema carries values, not labels).
export const UNIT_OF_MEASURE = [
  { value: "PCS", label: "Pieces" },
  { value: "KG", label: "Kilograms" },
  { value: "M", label: "Meters" },
  { value: "BOX", label: "Boxes" },
] as const;

export const PROCUREMENT_TYPE = [
  { value: "PURCHASE", label: "Purchase" },
  { value: "MANUFACTURING", label: "Manufacturing" },
] as const;
