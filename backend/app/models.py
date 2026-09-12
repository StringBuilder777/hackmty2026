from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Evidence(Model):
    title: str
    status: Literal['observed', 'warning', 'unavailable']
    detail: str
    source: str | None = None


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

    @field_validator('url')
    @classmethod
    def public_url(cls, value: str) -> str:
        from .services.fetch import validate_url
        validate_url(value)
        return value


class Analysis(Model):
    id: str
    mode: Literal['real', 'demo']
    status: Literal['queued', 'extracting', 'evaluating', 'searching', 'completed', 'error'] = 'queued'
    created_at: str = Field(default_factory=now)
    product: Product | None = None
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
