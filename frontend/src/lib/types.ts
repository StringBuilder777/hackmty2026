export type ProductId = string & { readonly __brand: "ProductId" };
export type BranchId = string & { readonly __brand: "BranchId" };
export type Mode = "real" | "demo";
export type AnalysisTarget = "product" | "website";
export interface Evidence {
  title: string;
  status: "observed" | "warning" | "unavailable";
  detail: string;
  source: string | null;
}
export interface ProductAttribute {
  name: string;
  value: string;
  source: string;
}
export interface StoreProfile {
  name: string;
  domain: string;
  url: string;
  description: string | null;
  image: string | null;
  seller_name: string | null;
  seller_url: string | null;
  contacts: string[];
  policy_links: string[];
  social_links: string[];
  evidence: Evidence[];
}
export interface WebsiteProfile {
  url: string;
  domain: string;
  title: string;
  description: string | null;
  image: string | null;
  declared_organization: string | null;
  sensitive_forms: number;
}
export interface DomainRegistration {
  domain: string;
  lookup_url: string;
  status: "available" | "unavailable";
  created_at: string | null;
  updated_at: string | null;
  expires_at: string | null;
  age_days: number | null;
  registrar: string | null;
  nameservers: string[];
  domain_statuses: string[];
  note: string;
}
export interface Risk {
  level: "bajo" | "medio" | "alto" | "información insuficiente";
  explanation: string;
  checked_at: string;
  evidence: Evidence[];
  agent_assessment: AgentAssessment | null;
}
export interface AgentAssessment {
  level: Risk["level"];
  explanation: string;
  limitations: string[];
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
  images: string[];
  description: string | null;
  specifications: ProductAttribute[];
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
  target: AnalysisTarget;
  product: Product | null;
  store_profile: StoreProfile | null;
  website_profile: WebsiteProfile | null;
  domain_registration: DomainRegistration | null;
  risk: Risk | null;
  alternatives: Product[];
  limitations: string[];
  error: string | null;
}

export type ForensicScheme = "phantom_vendor" | "kickback" | "round_tripping" | "threshold_splitting" | "revenue_inflation";
export interface Exhibit { exhibit_id: string; source_table: string; record_id: string; note: string; }
export interface MoneyTrailStep { from: string; to: string; amount: number; date: string; exhibit_id: string; }
export interface ForensicFinding {
  scheme_type: ForensicScheme; entities: string[]; narrative: string; rule_broken: string;
  peso_amount: number; confidence: "proven" | "probable"; money_trail: MoneyTrailStep[]; exhibits: Exhibit[];
}
export interface LeadNotPursued { entity: string; signal: string; reason: string; tool_calls_made: string[]; closed_by: "investigator" | "challenger" | "validator"; }
export interface ForensicSubmission {
  seed: number; findings: ForensicFinding[]; leads_not_pursued: LeadNotPursued[];
  run_metadata: { llm_calls: number; mxn_cost: number; wall_clock_seconds: number; cost_by_role: Record<string, number>; deterministic: boolean; };
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
