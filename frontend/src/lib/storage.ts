import type { Snapshot, Mode } from "./types";
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function money(value: unknown): boolean {
  return (
    value === null ||
    (typeof value === "number" && Number.isFinite(value) && value >= 0)
  );
}
function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}
function evidence(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (e) =>
        record(e) &&
        typeof e.title === "string" &&
        typeof e.detail === "string" &&
        nullableString(e.source) &&
        ["observed", "warning", "unavailable"].includes(String(e.status)),
    )
  );
}
function product(value: unknown, mode: Mode): boolean {
  if (!record(value)) return false;
  const p = value;
  if (
    ![
      "id",
      "name",
      "url",
      "store",
      "availability",
      "checked_at",
      "match_reason",
    ].every((key) => typeof p[key] === "string")
  )
    return false;
  if (
    ![
      "image",
      "brand",
      "model",
      "variant",
      "condition",
      "sku",
      "gtin",
      "currency",
    ].every((key) => nullableString(p[key]))
  )
    return false;
  if (
    p.demo !== (mode === "demo") ||
    !money(p.price) ||
    !money(p.shipping) ||
    !money(p.total) ||
    !evidence(p.evidence)
  )
    return false;
  if (
    !["original", "identical", "similar"].includes(String(p.match)) ||
    !Array.isArray(p.branches)
  )
    return false;
  return p.branches.every(
    (b) =>
      record(b) &&
      ["id", "name", "address", "source"].every(
        (key) => typeof b[key] === "string",
      ) &&
      typeof b.lat === "number" &&
      typeof b.lng === "number" &&
      Number.isFinite(b.lat) &&
      Number.isFinite(b.lng) &&
      Math.abs(b.lat) <= 90 &&
      Math.abs(b.lng) <= 180 &&
      ["confirmed", "pending"].includes(String(b.inventory)),
  );
}
export function readSnapshot(mode: Mode): Snapshot | null {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem(`buenpaso-v1-${mode}`) || "null",
    );
    if (
      !record(value) ||
      value.version !== 1 ||
      value.mode !== mode ||
      typeof value.savedAt !== "string" ||
      !Array.isArray(value.items) ||
      value.items.length > 30
    )
      return null;
    if (
      !value.items.every(
        (item) =>
          record(item) &&
          product(item.product, mode) &&
          nullableString(item.branchId),
      )
    )
      return null;
    const a = value.analysis;
    if (a !== null) {
      if (
        !record(a) ||
        a.mode !== mode ||
        a.status !== "completed" ||
        !product(a.product, mode) ||
        !Array.isArray(a.alternatives) ||
        !a.alternatives.every((p) => product(p, mode)) ||
        !Array.isArray(a.limitations) ||
        !a.limitations.every((n) => typeof n === "string")
      )
        return null;
      if (
        a.risk !== null &&
        (!record(a.risk) ||
          typeof a.risk.explanation !== "string" ||
          typeof a.risk.level !== "string" ||
          !evidence(a.risk.evidence))
      )
        return null;
    }
    return value as unknown as Snapshot;
  } catch {
    return null;
  }
}
