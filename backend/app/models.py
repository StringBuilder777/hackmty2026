from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


# The forensic contract is intentionally independent from the shopping models
# below.  Judges validate this shape directly, so these models are strict and
# never silently discard fields.
ForensicSourceTable = Literal['ledger', 'invoices', 'bank_txns', 'vendors', 'efos_list', 'purchase_orders', 'contracts', 'employees']
ForensicScheme = Literal['phantom_vendor', 'kickback', 'round_tripping', 'threshold_splitting', 'revenue_inflation']


class Exhibit(Model):
    exhibit_id: str = Field(min_length=1)
    source_table: ForensicSourceTable
    record_id: str = Field(min_length=1)
    note: str = Field(min_length=1, max_length=600)


class MoneyTrailStep(Model):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)
    from_: str = Field(alias='from', min_length=1)
    to: str = Field(min_length=1)
    amount: float = Field(gt=0)
    date: str = Field(min_length=1)
    exhibit_id: str = Field(min_length=1)


class Finding(Model):
    scheme_type: ForensicScheme
    entities: list[str] = Field(min_length=1)
    narrative: str = Field(min_length=1, max_length=1500)
    rule_broken: str = Field(min_length=1, max_length=400)
    peso_amount: float = Field(gt=0)
    confidence: Literal['proven', 'probable']
    money_trail: list[MoneyTrailStep] = Field(default_factory=list)
    exhibits: list[Exhibit] = Field(min_length=3)

    @field_validator('entities')
    @classmethod
    def prefixed_entities(cls, values: list[str]) -> list[str]:
        if any(':' not in value for value in values):
            raise ValueError('Cada entidad debe incluir un prefijo, por ejemplo RFC: o EMP:.')
        return values

    @field_validator('narrative')
    @classmethod
    def bounded_narrative(cls, value: str) -> str:
        if len(value.split()) > 150:
            raise ValueError('La narrativa no puede superar 150 palabras.')
        return value


class LeadNotPursued(Model):
    entity: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    tool_calls_made: list[str] = Field(default_factory=list)
    closed_by: Literal['investigator', 'challenger', 'validator'] = 'investigator'


class RunMetadata(Model):
    llm_calls: int = Field(ge=0)
    mxn_cost: float = Field(ge=0)
    wall_clock_seconds: float = Field(ge=0)
    cost_by_role: dict[str, float] = Field(default_factory=dict)
    deterministic: bool = True


class Submission(Model):
    seed: int
    findings: list[Finding] = Field(default_factory=list)
    leads_not_pursued: list[LeadNotPursued] = Field(default_factory=list)
    run_metadata: RunMetadata


class AuditRunInput(Model):
    estate_path: str = Field(min_length=1, max_length=4096)
    seed: int


class AuditUploadInput(Model):
    """Base64 is used instead of multipart to keep one explicit API contract."""
    estate_base64: str = Field(min_length=24, max_length=24 * 1024 * 1024)
    seed: int


class AuditDemoInput(Model):
    seed: int = 2026


class AuditPeriod(Model):
    from_date: str | None = None
    to_date: str | None = None


class AuditPreflight(Model):
    estate_filename: str = Field(min_length=1)
    estate_sha256: str = Field(min_length=64, max_length=64)
    estate_bytes: int = Field(ge=0)
    tables: dict[str, int]
    period: AuditPeriod
    quality_warnings: list[str] = Field(default_factory=list)
    ready: bool


class Evidence(Model):
    title: str
    status: Literal['observed', 'warning', 'unavailable']
    detail: str
    source: str | None = None


class ProductAttribute(Model):
    """A declared specification, keeping the page that supplied it."""
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)
    source: str


class StoreProfile(Model):
    """Publicly declared store and seller context; it is not an identity proof."""
    name: str
    domain: str
    url: str
    description: str | None = None
    image: str | None = None
    seller_name: str | None = None
    seller_url: str | None = None
    contacts: list[str] = Field(default_factory=list, max_length=8)
    policy_links: list[str] = Field(default_factory=list, max_length=8)
    social_links: list[str] = Field(default_factory=list, max_length=8)
    evidence: list[Evidence] = Field(default_factory=list)


class WebsiteProfile(Model):
    """Public presentation data extracted from a website without executing JavaScript."""
    url: str
    domain: str
    title: str
    description: str | None = None
    image: str | None = None
    declared_organization: str | None = None
    sensitive_forms: int = Field(default=0, ge=0)


class DomainRegistration(Model):
    """Normalized public RDAP/WHOIS-style registration data."""
    domain: str
    lookup_url: str
    status: Literal['available', 'unavailable']
    created_at: str | None = None
    updated_at: str | None = None
    expires_at: str | None = None
    age_days: int | None = Field(default=None, ge=0)
    registrar: str | None = None
    nameservers: list[str] = Field(default_factory=list, max_length=12)
    domain_statuses: list[str] = Field(default_factory=list, max_length=12)
    note: str


class Risk(Model):
    level: Literal['bajo', 'medio', 'alto', 'información insuficiente']
    explanation: str
    checked_at: str = Field(default_factory=now)
    evidence: list[Evidence]
    agent_assessment: 'AgentAssessment | None' = None


class AgentAssessment(Model):
    level: Literal['bajo', 'medio', 'alto', 'información insuficiente']
    explanation: str = Field(min_length=1, max_length=800)
    limitations: list[str] = Field(default_factory=list, max_length=4)


class Point(Model):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Branch(Point):
    id: str
    name: str
    address: str
    source: str
    inventory: Literal['confirmed', 'pending'] = 'pending'
    inventory_checked_at: str | None = None


class Product(Model):
    id: str
    name: str
    url: str
    store: str
    image: str | None = None
    images: list[str] = Field(default_factory=list, max_length=12)
    description: str | None = Field(default=None, max_length=2500)
    specifications: list[ProductAttribute] = Field(default_factory=list, max_length=40)
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    condition: str | None = None
    sku: str | None = None
    gtin: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    shipping: float | None = Field(default=None, ge=0)
    total: float | None = Field(default=None, ge=0)
    availability: str = 'Pendiente de verificar'
    checked_at: str = Field(default_factory=now)
    match: Literal['identical', 'similar', 'original'] = 'original'
    match_reason: str = ''
    branches: list[Branch] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    demo: bool = False


class AnalysisInput(Model):
    url: str = Field(min_length=8, max_length=2048)
    mode: Literal['real', 'demo'] = 'real'
    target: Literal['product', 'website'] = 'product'

    @field_validator('url')
    @classmethod
    def public_url(cls, value: str) -> str:
        from .services.fetch import validate_url
        validate_url(value)
        return value


class Analysis(Model):
    id: str
    mode: Literal['real', 'demo']
    target: Literal['product', 'website'] = 'product'
    status: Literal['queued', 'extracting', 'evaluating', 'searching', 'completed', 'error'] = 'queued'
    created_at: str = Field(default_factory=now)
    product: Product | None = None
    store_profile: StoreProfile | None = None
    website_profile: WebsiteProfile | None = None
    domain_registration: DomainRegistration | None = None
    risk: Risk | None = None
    alternatives: list[Product] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    error: str | None = None


class Stop(Point):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)


class RouteInput(Model):
    origin: Point
    stops: list[Stop] = Field(min_length=1, max_length=10)
    mode: Literal['driving', 'walking', 'cycling'] = 'driving'
    max_radius_km: float | None = Field(default=None, ge=0)
    demo: bool = False


class Route(Model):
    status: Literal['available', 'unavailable']
    message: str
    ordered_stops: list[Stop]
    coordinates: list[tuple[float, float]] = Field(default_factory=list)
    distance_m: float | None = None
    duration_s: float | None = None
    provider: str
    checked_at: str = Field(default_factory=now)
    demo: bool = False
