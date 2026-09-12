"""Public domain-registration lookup used as a bounded, non-authoritative signal."""
import asyncio
import ipaddress
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import aiohttp

from ..models import DomainRegistration, Evidence
from .fetch import PublicResolver
from .http import bounded_json

RDAP_URL = 'https://rdap.org/domain/'


def _creation_date(record: dict) -> datetime | None:
    events = record.get('events')
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict) or event.get('eventAction') not in ('registration', 'registered'):
            continue
        value = event.get('eventDate')
        if not isinstance(value, str):
            continue
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


async def registration_evidence(url: str) -> Evidence:
    """Return a safe RDAP finding; provider failure must never fail an analysis."""
    profile, evidence = await registration_profile(url)
    return evidence


def _event_date(record: dict, actions: tuple[str, ...]) -> str | None:
    events = record.get('events')
    if not isinstance(events, list):
        return None
    for event in events:
        if isinstance(event, dict) and event.get('eventAction') in actions and isinstance(event.get('eventDate'), str):
            return event['eventDate'][:40]
    return None


def _registrar(record: dict) -> str | None:
    for entity in record.get('entities', []) if isinstance(record.get('entities'), list) else []:
        if not isinstance(entity, dict) or 'registrar' not in entity.get('roles', []):
            continue
        card = entity.get('vcardArray')
        if isinstance(card, list) and len(card) > 1 and isinstance(card[1], list):
            for field in card[1]:
                if isinstance(field, list) and len(field) > 3 and field[0] in ('fn', 'org') and isinstance(field[3], str):
                    return field[3][:200]
    return None


async def registration_profile(url: str) -> tuple[DomainRegistration, Evidence]:
    """Return normalized RDAP data and its risk evidence without exposing personal contacts."""
    host = urlsplit(url).hostname
    lookup = RDAP_URL + quote(host or '', safe='')
    if not host:
        detail = 'No se pudo identificar el dominio para consultar su registro público.'
        return DomainRegistration(domain='', lookup_url=lookup, status='unavailable', note=detail), Evidence(title='Antigüedad del dominio', status='unavailable', detail=detail)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        detail = 'La antigüedad RDAP se consulta para dominios, no para direcciones IP.'
        return DomainRegistration(domain=host, lookup_url=lookup, status='unavailable', note=detail), Evidence(title='Antigüedad del dominio', status='unavailable', detail=detail)

    try:
        connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False, limit=1)
        timeout = aiohttp.ClientTimeout(total=4, connect=2, sock_read=2)
        async with asyncio.timeout(5), aiohttp.ClientSession(
            connector=connector, timeout=timeout, trust_env=False,
            headers={'User-Agent': 'BuenPasoMVP/0.1', 'Accept': 'application/rdap+json, application/json'},
        ) as session:
            async with session.get(RDAP_URL + quote(host, safe='')) as response:
                if response.status != 200:
                    raise ValueError('RDAP no disponible')
                record = await bounded_json(response, limit=128_000)
                created = _creation_date(record)
    except (aiohttp.ClientError, TimeoutError, ValueError):
        detail = 'El registro RDAP no respondió con datos públicos verificables. Esto no es una señal de fraude.'
        return DomainRegistration(domain=host, lookup_url=lookup, status='unavailable', note=detail), Evidence(title='Antigüedad del dominio', status='unavailable', detail=detail)

    if not created:
        detail = 'El registro RDAP no publica una fecha de creación verificable. Esto no es una señal de fraude.'
        return DomainRegistration(domain=host, lookup_url=lookup, status='unavailable', registrar=_registrar(record), note=detail), Evidence(title='Antigüedad del dominio', status='unavailable', source=lookup, detail=detail)
    age_days = max(0, (datetime.now(timezone.utc) - created).days)
    nameservers = [str(item.get('ldhName', '')).lower()[:253] for item in record.get('nameservers', []) if isinstance(item, dict) and item.get('ldhName')][:12]
    statuses = [str(item)[:120] for item in record.get('status', []) if isinstance(item, str)][:12]
    profile = DomainRegistration(
        domain=host, lookup_url=lookup, status='available', created_at=_event_date(record, ('registration', 'registered')),
        updated_at=_event_date(record, ('last changed', 'last update of RDAP database', 'changed')),
        expires_at=_event_date(record, ('expiration', 'expiry')), age_days=age_days, registrar=_registrar(record),
        nameservers=nameservers, domain_statuses=statuses,
        note='Datos públicos de registro obtenidos mediante RDAP; no autentican el contenido ni al operador actual.',
    )
    if age_days < 180:
        return profile, Evidence(title='Antigüedad del dominio', status='warning', source=lookup, detail=f'El registro público indica creación hace aproximadamente {age_days} días. Revisa identidad, políticas y métodos de pago; la antigüedad no prueba fraude.')
    return profile, Evidence(title='Antigüedad del dominio', status='observed', source=lookup, detail=f'El registro público indica creación hace aproximadamente {age_days // 365} años. La antigüedad no autentica al vendedor ni evita suplantaciones.')
