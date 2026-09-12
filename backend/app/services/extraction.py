import hashlib
import json
import math
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from ..models import Product


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
        number = float(str(value))
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
    def meta(name: str) -> str | None:
        element = soup.find('meta', property=name) or soup.find('meta', attrs={'name': name})
        return scalar(element.get('content')) if element else None
    offer = data.get('offers', {})
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    if not isinstance(offer, dict):
        offer = {}
    # AggregateOffer lowPrice is not an exact variant offer.
    price = money(offer.get('price') or meta('product:price:amount'))
    currency = scalar(offer.get('priceCurrency') or meta('product:price:currency'))
    image = data.get('image') or meta('og:image')
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get('url')
    shipping = None
    shipping_data = offer.get('shippingDetails')
    if isinstance(shipping_data, list) and len(shipping_data) == 1:
        shipping_data = shipping_data[0]
    if isinstance(shipping_data, dict):
        rate, destination = shipping_data.get('shippingRate', {}), shipping_data.get('shippingDestination', {})
        if isinstance(rate, dict) and isinstance(destination, dict) and destination.get('addressCountry') == 'MX' and rate.get('currency') == currency:
            shipping = money(rate.get('value'))
    condition = scalar(offer.get('itemCondition') or data.get('itemCondition'))
    return Product(
        id=hashlib.sha256(url.encode()).hexdigest()[:20], url=url, store=urlsplit(url).hostname or '',
        name=scalar(data.get('name')) or meta('og:title') or (soup.title.get_text()[:300] if soup.title else 'Producto sin identificar'),
        image=safe_link(image, url), brand=scalar(data.get('brand')), model=scalar(data.get('model')),
        variant=scalar(data.get('color')), condition=condition.rsplit('/', 1)[-1] if condition else None,
        sku=scalar(data.get('sku')), gtin=scalar(data.get('gtin') or data.get('gtin13') or data.get('gtin12') or data.get('gtin14')),
        price=price, currency=currency.upper() if currency else None, shipping=shipping, total=round(price + shipping, 2) if price is not None and shipping is not None else None,
        availability=f"Declarada por la página: {str(offer['availability']).rsplit('/', 1)[-1]} (sin confirmar)" if offer.get('availability') else 'Pendiente de verificar',
    )
