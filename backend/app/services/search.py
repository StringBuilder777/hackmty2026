import asyncio
import os
import re
import unicodedata
from typing import Protocol
from urllib.parse import urlsplit
import aiohttp
from ..models import Product, Evidence
from .extraction import extract
from .fetch import fetch_html
from .branches import resolve
from .http_client import bounded_json


def norm(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())


STOP_WORDS = {
    'con', 'para', 'por', 'sin', 'del', 'las', 'los', 'una', 'uno', 'the', 'and',
    'comprar', 'mexico', 'nuevo', 'nueva', 'incluye', 'producto', 'tienda',
}


def tokens(value: str | None) -> set[str]:
    plain = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode().lower()
    return {part for part in re.findall(r'[a-z0-9]+', plain) if len(part) > 1 and part not in STOP_WORDS}


def canonical_url(value: str) -> tuple[str, str]:
    parts = urlsplit(value)
    return (parts.hostname or '').lower(), parts.path.rstrip('/') or '/'


def related(original: Product, other: Product) -> bool:
    """Accept broadly related products without hard-coding a product category."""
    if original.gtin and other.gtin and norm(original.gtin) == norm(other.gtin):
        return True
    if original.brand and other.brand and norm(original.brand) != norm(other.brand):
        return False
    if original.model and other.model and norm(original.model) == norm(other.model):
        return True
    expected, candidate = tokens(original.name), tokens(other.name)
    if not expected or not candidate:
        return False
    overlap = expected & candidate
    coverage = len(overlap) / min(len(expected), len(candidate))
    # Numbers and model-like tokens reduce false matches between generic names.
    identity_overlap = any(any(char.isdigit() for char in part) for part in overlap)
    return len(overlap) >= 3 and coverage >= 0.45 and (identity_overlap or len(overlap) >= 5)


def classify(original: Product, other: Product) -> tuple[str, str]:
    for field in ('brand', 'model', 'variant', 'condition', 'gtin'):
        a, b = getattr(original, field), getattr(other, field)
        if a and b and norm(a) != norm(b):
            return 'similar', f'Diferencia en {field}; no se considera idéntico.'
    same_gtin = bool(original.gtin and other.gtin and norm(original.gtin) == norm(other.gtin))
    attributes = ('brand', 'model', 'variant', 'condition')
    same_fields = all(getattr(original, f) and getattr(other, f) and norm(getattr(original, f)) == norm(getattr(other, f)) for f in attributes)
    same_condition = original.condition and other.condition and norm(original.condition) == norm(other.condition)
    if same_fields or (same_gtin and same_condition):
        return 'identical', 'Coinciden GTIN y condición, o marca, modelo, variante y condición.'
    return 'similar', 'Coincidencia parcial; faltan identificadores, variante o condición. El SKU puede ser propio de cada tienda.'


class SearchProvider(Protocol):
    async def urls(self, query: str) -> list[str]: ...


def queries(product: Product) -> list[str]:
    """Use stable identifiers first, then progressively broader product queries."""
    values: list[str] = []
    if product.gtin:
        values.append(f'{product.gtin} comprar México')
    if product.sku:
        values.append(f'{product.brand or ""} {product.sku} comprar México'.strip())
    identity = ' '.join(filter(None, [product.brand, product.model, product.variant, 'comprar México']))
    if identity:
        values.append(identity)
    name_tokens = [part for part in re.findall(r'[A-Za-z0-9-]+', product.name) if len(part) > 2]
    values.append(' '.join(name_tokens[:10] + ['comprar', 'México']))
    return list(dict.fromkeys(value for value in values if value))[:4]


class BraveSearch:
    async def urls(self, query: str) -> list[str]:
        key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not key:
            raise ValueError('Falta BRAVE_SEARCH_API_KEY para buscar alternativas reales con Brave Search.')
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), trust_env=False) as session:
            async with session.get('https://api.search.brave.com/res/v1/web/search', params={'q': query, 'count': 10, 'country': 'MX', 'search_lang': 'es'}, headers={'X-Subscription-Token': key}) as response:
                if response.status != 200:
                    raise ValueError(f'Brave Search respondió HTTP {response.status}. Revisa la integración.')
                body = await bounded_json(response, 1_000_000)
                return [r['url'] for r in body.get('web', {}).get('results', [])[:10] if isinstance(r.get('url'), str)]


async def alternatives(product: Product, provider: SearchProvider | None = None) -> tuple[list[Product], list[str]]:
    provider = provider or BraveSearch()
    results = await asyncio.gather(*(provider.urls(query) for query in queries(product)), return_exceptions=True)
    urls = list(dict.fromkeys(url for batch in results if isinstance(batch, list) for url in batch if isinstance(url, str)))
    async def one(url: str) -> Product | None:
        if canonical_url(url) == canonical_url(product.url):
            return None
        html, final = await fetch_html(url)
        other = extract(html, final)
        if other.price is None and not any((other.brand, other.sku, other.gtin, other.condition)):
            return None
        if not related(product, other):
            return None
        other.match, other.match_reason = classify(product, other)
        other.branches = resolve(other)
        other.evidence = [Evidence(title='Fuente de la oferta', status='observed', source=final, detail='Datos publicados por la tienda, no verificados de forma independiente.')]
        return other
    results = await asyncio.gather(*(one(url) for url in urls), return_exceptions=True)
    found = [r for r in results if isinstance(r, Product)][:8]
    skipped = sum(isinstance(r, Exception) for r in results)
    notes = [f'{skipped} páginas no pudieron consultarse; no se evadieron sus restricciones.'] if skipped else []
    if not found:
        notes.append('No se encontraron opciones suficientemente relacionadas. Prueba otra URL de producto.')
    if not os.getenv('BRANCH_CATALOG_PATH'):
        notes.append('No hay sucursales verificadas en el catálogo configurado; las ofertas no añaden una parada al recorrido.')
    return found, notes
