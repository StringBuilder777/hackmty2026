import { describe, expect, it } from "vitest";
import { groupStops, totals, safeHref } from "../src/lib/shopping";
import type { Product, ProductId, BranchId, Selection } from "../src/lib/types";
const branch = {
  id: "centro" as BranchId,
  name: "Centro",
  address: "Demo",
  lat: 25.67,
  lng: -100.31,
  source: "https://example.com",
  inventory: "pending" as const,
  inventory_checked_at: null,
};
const product: Product = {
  id: "one" as ProductId,
  name: "Audífonos",
  url: "https://example.com",
  store: "Demo",
  image: null,
  images: [],
  description: null,
  specifications: [],
  brand: null,
  model: null,
  variant: null,
  condition: null,
  sku: null,
  gtin: null,
  price: 100,
  currency: "MXN",
  shipping: null,
  total: null,
  availability: "pending",
  checked_at: "2026-09-12T12:00:00Z",
  match: "similar",
  match_reason: "",
  branches: [branch],
  evidence: [],
  demo: true,
};
const selection: Selection = { product, branchId: branch.id };
describe("shopping list", () => {
  it("groups products at the same branch and excludes online-only items", () => {
    const stops = groupStops([
      selection,
      { ...selection, product: { ...product, id: "two" as ProductId } },
      { ...selection, branchId: null },
    ]);
    expect(stops).toHaveLength(1);
    expect(stops[0].products).toHaveLength(2);
  });
  it("keeps unknown costs pending and does not convert foreign currency", () => {
    expect(totals([selection])).toEqual({ known: 100, pending: 1, foreign: 0 });
    expect(
      totals([
        { ...selection, product: { ...product, currency: "USD", shipping: 0 } },
      ]),
    ).toEqual({ known: 0, pending: 1, foreign: 1 });
    expect(
      totals([{ ...selection, product: { ...product, shipping: 0 } }]),
    ).toEqual({ known: 100, pending: 0, foreign: 0 });
  });
  it("rejects executable source links", () => {
    expect(safeHref("javascript:alert(1)")).toBeUndefined();
  });
});
