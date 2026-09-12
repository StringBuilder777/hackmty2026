"""Public domain-registration lookup used as a bounded, non-authoritative signal."""
import asyncio
import ipaddress
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import aiohttp

from ..models import Evidence
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
    host = urlsplit(url).hostname
    if not host:
        return Evidence(title='Antigüedad del dominio', status='unavailable', detail='No se pudo identificar el dominio para consultar su registro público.')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return Evidence(title='Antigüedad del dominio', status='unavailable', detail='La antigüedad RDAP se consulta para dominios, no para direcciones IP.')

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
                created = _creation_date(await bounded_json(response, limit=128_000))
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return Evidence(title='Antigüedad del dominio', status='unavailable', detail='El registro RDAP no respondió con una fecha pública verificable. Esto no es una señal de fraude.')

    if not created:
        return Evidence(title='Antigüedad del dominio', status='unavailable', detail='El registro RDAP no publica una fecha de creación verificable. Esto no es una señal de fraude.')
    age_days = max(0, (datetime.now(timezone.utc) - created).days)
    if age_days < 180:
        return Evidence(title='Antigüedad del dominio', status='warning', source=RDAP_URL + quote(host, safe=''), detail=f'El registro público indica creación hace aproximadamente {age_days} días. Revisa identidad, políticas y métodos de pago; la antigüedad no prueba fraude.')
    return Evidence(title='Antigüedad del dominio', status='observed', source=RDAP_URL + quote(host, safe=''), detail=f'El registro público indica creación hace aproximadamente {age_days // 365} años. La antigüedad no autentica al vendedor ni evita suplantaciones.')
