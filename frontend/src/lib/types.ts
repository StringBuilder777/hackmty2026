export type ProductId = string & { readonly __brand: "ProductId" };
export type BranchId = string & { readonly __brand: "BranchId" };
export type Mode = "real" | "demo";
export interface Evidence {
  title: string;
  status: "observed" | "warning" | "unavailable";
  detail: string;
  source: string | null;
}
export interface Risk {
  level: "bajo" | "medio" | "alto" | "información insuficiente";
  explanation: string;
  checked_at: string;
  evidence: Evidence[];
}
export interface Point {
  lat: number;
  lng: number;
}
export interface Branch extends Point {
  id: BranchId;
  name: string;
  address: string;
  source: string;
  inventory: "confirmed" | "pending";
  inventory_checked_at: string | null;
}
export interface Product {
  id: ProductId;
  name: string;
  url: string;
  store: string;
  image: string | null;
  brand: string | null;
  model: string | null;
  variant: string | null;
  condition: string | null;
  sku: string | null;
  gtin: string | null;
  price: number | null;
  currency: string | null;
  shipping: number | null;
  total: number | null;
  availability: string;
  checked_at: string;
  match: "identical" | "similar" | "original";
  match_reason: string;
  branches: Branch[];
  evidence: Evidence[];
  demo: boolean;
}
export interface Analysis {
  id: string;
  mode: Mode;
  status:
    | "queued"
    | "extracting"
    | "evaluating"
    | "searching"
    | "completed"
    | "error";
  created_at: string;
  product: Product | null;
  risk: Risk | null;
  alternatives: Product[];
  limitations: string[];
  error: string | null;
}
export interface Selection {
  product: Product;
  branchId: BranchId | null;
}
export interface Stop extends Point {
  id: BranchId;
  name: string;
  products?: string[];
}
export interface Route {
  status: "available" | "unavailable";
  message: string;
  ordered_stops: Stop[];
  coordinates: [number, number][];
  distance_m: number | null;
  duration_s: number | null;
  provider: string;
  checked_at: string;
  demo: boolean;
}
export type Transport = "driving" | "walking" | "cycling";
export interface Snapshot {
  version: 1;
  mode: Mode;
  savedAt: string;
  items: Selection[];
  analysis: Analysis | null;
}
