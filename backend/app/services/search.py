import asyncio
import os
import re
from typing import Protocol
import aiohttp
from ..models import Product, Evidence
from .extraction import extract
from .fetch import fetch_html
from .branches import resolve
from .http import bounded_json


def norm(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())


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


class BraveSearch:
    async def urls(self, query: str) -> list[str]:
        key = os.getenv('BRAVE_SEARCH_API_KEY')
        if not key:
            raise ValueError('Falta BRAVE_SEARCH_API_KEY para buscar alternativas reales con Brave Search.')
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), trust_env=False) as session:
            async with session.get('https://api.search.brave.com/res/v1/web/search', params={'q': query, 'count': 5, 'country': 'MX', 'search_lang': 'es'}, headers={'X-Subscription-Token': key}) as response:
                if response.status != 200:
                    raise ValueError(f'Brave Search respondió HTTP {response.status}. Revisa la integración.')
                body = await bounded_json(response, 1_000_000)
                return [r['url'] for r in body.get('web', {}).get('results', [])[:5] if isinstance(r.get('url'), str)]


async def alternatives(product: Product, provider: SearchProvider | None = None) -> tuple[list[Product], list[str]]:
    provider = provider or BraveSearch()
    query = ' '.join(filter(None, [product.brand, product.model or product.name, product.variant, 'comprar México']))
    urls = list(dict.fromkeys(await provider.urls(query)))
    async def one(url: str) -> Product | None:
        if url == product.url:
            return None
        html, final = await fetch_html(url)
        other = extract(html, final)
        if other.price is None:
            return None
        same_identity = bool(product.model and other.model and norm(product.model) == norm(other.model)) or bool(product.gtin and other.gtin and product.gtin == other.gtin)
        category = r'aud[ií]fonos|headphones|auriculares|headset|earbuds'
        same_category = bool(re.search(category, product.name, re.I) and re.search(category, other.name, re.I))
        if not same_identity and not same_category:
            return None
        other.match, other.match_reason = classify(product, other)
        other.branches = resolve(other)
        other.evidence = [Evidence(title='Fuente de la oferta', status='observed', source=final, detail='Datos publicados por la tienda, no verificados de forma independiente.')]
        return other
    results = await asyncio.gather(*(one(url) for url in urls), return_exceptions=True)
    found = [r for r in results if isinstance(r, Product)]
    skipped = sum(isinstance(r, Exception) for r in results)
    notes = [f'{skipped} páginas no pudieron consultarse; no se evadieron sus restricciones.'] if skipped else []
    if not found:
        notes.append('No se encontraron ofertas con precio extraíble. Prueba otra URL de producto.')
    if not os.getenv('BRANCH_CATALOG_PATH'):
        notes.append('Falta BRANCH_CATALOG_PATH: no hay sucursales documentadas; las ofertas no generan paradas.')
    return found, notes
