"""Extract public store and seller context from already fetched HTML.

This deliberately records declarations and links, not an asserted merchant identity.
"""
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..models import Evidence, StoreProfile
from .extraction import safe_link, scalar


def _nodes(value: object, depth: int = 0) -> list[dict]:
    if depth > 10:
        return []
    if isinstance(value, list):
        return [node for item in value for node in _nodes(item, depth + 1)]
    if isinstance(value, dict):
        found = [value]
        for key in ('@graph', 'publisher', 'seller', 'brand', 'provider', 'organization'):
            found.extend(_nodes(value.get(key), depth + 1))
        return found
    return []


def inspect_store(html: str, url: str) -> StoreProfile:
    soup = BeautifulSoup(html, 'html.parser')
    declared: dict = {}
    seller: dict = {}
    for script in soup.find_all('script', type='application/ld+json')[:30]:
        try:
            payload = json.loads(script.get_text())
            for item in _nodes(payload):
                candidate = item.get('seller')
                if isinstance(candidate, dict) and not seller:
                    seller = candidate
                kind = item.get('@type', [])
                kinds = {kind} if isinstance(kind, str) else set(kind) if isinstance(kind, list) else set()
                if not declared and kinds & {'Organization', 'OnlineStore', 'LocalBusiness', 'Store', 'Corporation'}:
                    declared = item
        except (ValueError, RecursionError):
            continue

    def meta(*names: str) -> str | None:
        for name in names:
            tag = soup.find('meta', property=name) or soup.find('meta', attrs={'name': name})
            if tag:
                value = scalar(tag.get('content'))
                if value:
                    return value
        return None

    domain = urlsplit(url).hostname or ''
    name = scalar(declared.get('name')) or meta('og:site_name', 'application-name') or domain
    logo = declared.get('logo') or meta('og:logo')
    if isinstance(logo, dict):
        logo = logo.get('url')
    if not logo:
        icon = soup.find('link', rel=lambda value: value and 'icon' in ' '.join(value if isinstance(value, list) else [value]).lower())
        logo = icon.get('href') if icon else None
    if not logo and domain:
        parsed = urlsplit(url)
        logo = f'{parsed.scheme}://{domain}/favicon.ico'
    links = [safe_link(a.get('href'), url) for a in soup.find_all('a', href=True)]
    public_links = list(dict.fromkeys(item for item in links if item))
    contacts = [item for item in public_links if any(token in item.lower() for token in ('contact', 'contacto', 'support', 'ayuda', 'about', 'nosotros'))][:8]
    policies = [item for item in public_links if any(token in item.lower() for token in ('return', 'devolu', 'refund', 'reembolso', 'privacy', 'privacidad', 'shipping', 'envio', 'envío', 'terms', 'terminos', 'términos'))][:8]
    social = [item for item in public_links if any(host in item.lower() for host in ('facebook.com', 'instagram.com', 'x.com/', 'twitter.com', 'tiktok.com', 'youtube.com', 'linkedin.com'))][:8]
    seller_link = soup.select_one('#merchantInfo a[href], #sellerProfileTriggerId[href], #tabular-buybox-truncate-1 a[href], [data-feature-name="shipsFromSoldBy"] a[href]')
    seller_text = soup.select_one('#merchantInfo, #sellerProfileTriggerId, #tabular-buybox-truncate-1, [data-feature-name="shipsFromSoldBy"]')
    seller_name = scalar(seller.get('name'))
    if not seller_name and seller_text:
        raw = seller_text.get_text(' ', strip=True)
        match = re.search(r'(?:vendido|enviado)\s+por\s+(.+?)(?:\.|\||$)', raw, re.I)
        if match:
            seller_name = match.group(1).strip()[:300]
        elif seller_link:
            seller_name = scalar(seller_link.get_text(' ', strip=True))
    seller_url = safe_link(seller.get('url'), url)
    if not seller_url and seller_link:
        seller_url = safe_link(seller_link.get('href'), url)
    evidence = [
        Evidence(title='Perfil público de la tienda', status='observed' if declared else 'unavailable', source=url,
                 detail='Se encontró identidad comercial declarada en datos estructurados.' if declared else 'No se encontró identidad comercial estructurada en el HTML accesible.'),
        Evidence(title='Canales de contacto', status='observed' if contacts else 'unavailable', source=url,
                 detail=f'Se encontraron {len(contacts)} enlaces públicos de contacto o soporte.' if contacts else 'No se detectaron enlaces de contacto en el HTML accesible.'),
        Evidence(title='Políticas públicas', status='observed' if policies else 'unavailable', source=url,
                 detail=f'Se encontraron {len(policies)} enlaces de envío, devolución, privacidad o términos; su contenido no fue validado.' if policies else 'No se detectaron enlaces de políticas en el HTML accesible.'),
    ]
    return StoreProfile(name=name, domain=domain, url=url, description=scalar(declared.get('description')) or meta('description', 'og:description'), image=safe_link(logo, url), seller_name=seller_name, seller_url=seller_url, contacts=contacts, policy_links=policies, social_links=social, evidence=evidence)
