import type { Selection, Stop } from "./types";
export function groupStops(items: Selection[]): Stop[] {
  const stops = new Map<string, Stop>();
  for (const { product, branchId } of items) {
    const branch = product.branches.find((b) => b.id === branchId);
    if (!branch) continue;
    const prior = stops.get(branch.id);
    if (prior) prior.products?.push(product.name);
    else
      stops.set(branch.id, {
        id: branch.id,
        name: branch.name,
        lat: branch.lat,
        lng: branch.lng,
        products: [product.name],
      });
  }
  return [...stops.values()];
}
export function totals(items: Selection[]) {
  let known = 0,
    pending = 0,
    foreign = 0;
  for (const { product: p } of items) {
    if (p.currency !== "MXN") {
      foreign++;
      pending++;
      continue;
    }
    if (p.price === null) pending++;
    else known += p.price;
    if (p.shipping === null) pending++;
    else known += p.shipping;
  }
  return { known, pending, foreign };
}
export function formatMoney(
  price: number | null,
  currency: string | null = "MXN",
): string {
  if (price === null || !currency) return "Precio pendiente";
  try {
    return (
      new Intl.NumberFormat("es-MX", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(price) +
      " " +
      currency
    );
  } catch {
    return `${price} · moneda sin verificar`;
  }
}
export function dateLabel(value: string): string {
  return new Date(value).toLocaleString("es-MX", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
export function safeHref(value: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const parsed = new URL(value);
    return ["https:", "http:"].includes(parsed.protocol)
      ? parsed.href
      : undefined;
  } catch {
    return undefined;
  }
}
