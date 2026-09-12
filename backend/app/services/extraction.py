import hashlib
import json
import math
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from ..models import Product, ProductAttribute


def safe_link(value: object, base: str) -> str | None:
    if not isinstance(value, str):
        return None
    value = urljoin(base, value)
    return value if urlsplit(value).scheme in ('http', 'https') else None


def scalar(value: object) -> str | None:
    if isinstance(value, dict):
        return scalar(value.get('name'))
    return str(value)[:300] if isinstance(value, (str, int, float)) else None


def money(value: object) -> float | None:
    try:
        raw = re.sub(r'[^0-9,.-]', '', str(value)).strip()
        if ',' in raw and '.' in raw:
            raw = raw.replace(',', '')
        elif ',' in raw:
            tail = raw.rsplit(',', 1)[-1]
            raw = raw.replace(',', '.') if len(tail) == 2 else raw.replace(',', '')
        number = float(raw)
        return number if math.isfinite(number) and 0 <= number < 1e10 else None
    except (ValueError, TypeError):
        return None


def product_nodes(value: object, depth: int = 0) -> list[dict]:
    if depth > 12:
        return []
    if isinstance(value, list):
        return [node for item in value for node in product_nodes(item, depth + 1)]
    if isinstance(value, dict):
        types = value.get('@type', [])
        if types == 'Product' or isinstance(types, list) and 'Product' in types:
            return [value]
        return [node for key in ('@graph', 'mainEntity', 'itemListElement', 'item') for node in product_nodes(value.get(key), depth + 1)]
    return []


def extract(html: str, url: str) -> Product:
    soup = BeautifulSoup(html, 'html.parser')
    data: dict = {}
    for script in soup.find_all('script', type='application/ld+json')[:30]:
        try:
            nodes = product_nodes(json.loads(script.get_text()))
            if nodes:
                data = nodes[0]
                break
        except (ValueError, RecursionError):
            continue
    def meta(*names: str) -> str | None:
        for name in names:
            element = soup.find('meta', property=name) or soup.find('meta', attrs={'name': name})
            value = scalar(element.get('content')) if element else None
            if value:
                return value
        return None
    def text(selector: str) -> str | None:
        element = soup.select_one(selector)
        return scalar(element.get_text(' ', strip=True)) if element else None
    table: dict[str, str] = {}
    for row in soup.select('tr')[:200]:
        cells = row.find_all(['th', 'td'])
        if len(cells) >= 2:
            key = re.sub(r'\s+', ' ', cells[0].get_text(' ', strip=True)).lower()
            value = re.sub(r'\s+', ' ', cells[-1].get_text(' ', strip=True))
            if key and value:
                table[key] = value[:300]
    def table_value(*labels: str) -> str | None:
        return next((value for key, value in table.items() if any(label in key for label in labels)), None)
    offer = data.get('offers', {})
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    if not isinstance(offer, dict):
        offer = {}
    # AggregateOffer lowPrice is not an exact variant offer.
    dom_price = text('#corePriceDisplay_desktop_feature_div .a-price .a-offscreen') or text('.a-price .a-offscreen')
    price = money(offer.get('price') or meta('product:price:amount') or dom_price)
    currency = scalar(offer.get('priceCurrency') or meta('product:price:currency'))
    if not currency and dom_price and (urlsplit(url).hostname or '').endswith('.mx'):
        currency = 'MXN'
    dom_images = [tag.get('src') or tag.get('data-old-hires') for tag in soup.select('#landingImage, #imgTagWrapperId img, [data-a-dynamic-image]')[:12]]
    raw_images = data.get('image') or dom_images or meta('og:image')
    image_values = raw_images if isinstance(raw_images, list) else [raw_images]
    images = []
    for candidate in image_values:
        if isinstance(candidate, dict):
            candidate = candidate.get('url')
        link = safe_link(candidate, url)
        if link and link not in images:
            images.append(link)
    if not images:
        og_image = safe_link(meta('og:image'), url)
        if og_image:
            images.append(og_image)
    specs = [ProductAttribute(name=key[:120], value=value[:500], source=url) for key, value in list(table.items())[:40]]
    shipping = None
    shipping_data = offer.get('shippingDetails')
    if isinstance(shipping_data, list) and len(shipping_data) == 1:
        shipping_data = shipping_data[0]
    if isinstance(shipping_data, dict):
        rate, destination = shipping_data.get('shippingRate', {}), shipping_data.get('shippingDestination', {})
        if isinstance(rate, dict) and isinstance(destination, dict) and destination.get('addressCountry') == 'MX' and rate.get('currency') == currency:
            shipping = money(rate.get('value'))
    condition = scalar(offer.get('itemCondition') or data.get('itemCondition'))
    byline = text('#bylineInfo')
    dom_brand = table_value('marca')
    if not dom_brand and byline:
        dom_brand = re.sub(r'^(visita\s+)?la\s+tienda\s+de\s+', '', byline, flags=re.I).strip()
    asin = scalar((soup.select_one('input#ASIN') or {}).get('value'))
    return Product(
        id=hashlib.sha256(url.encode()).hexdigest()[:20], url=url, store=urlsplit(url).hostname or '',
        name=scalar(data.get('name')) or text('#productTitle') or meta('og:title') or (soup.title.get_text()[:300] if soup.title else 'Producto sin identificar'),
        image=images[0] if images else None, images=images, description=scalar(data.get('description')) or meta('description', 'og:description'), specifications=specs, brand=scalar(data.get('brand')) or dom_brand,
        model=scalar(data.get('model')) or table_value('nombre modelo', 'modelo'),
        variant=scalar(data.get('color')), condition=condition.rsplit('/', 1)[-1] if condition else None,
        sku=scalar(data.get('sku')) or asin, gtin=scalar(data.get('gtin') or data.get('gtin13') or data.get('gtin12') or data.get('gtin14')),
        price=price, currency=currency.upper() if currency else None, shipping=shipping, total=round(price + shipping, 2) if price is not None and shipping is not None else None,
        availability=f"Declarada por la página: {str(offer['availability']).rsplit('/', 1)[-1]} (sin confirmar)" if offer.get('availability') else 'Pendiente de verificar',
    )
