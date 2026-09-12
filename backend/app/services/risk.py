import re
import unicodedata
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from ..models import Evidence, Product, Risk
from .extraction import safe_link


def comparable_host(value: str | None) -> str:
    return (value or '').lower().removeprefix('www.')


def expected_short_link(source: str, final: str) -> bool:
    """Known retailer short links are redirects, not a domain-mismatch warning."""
    source_host, final_host = comparable_host(urlsplit(source).hostname), comparable_host(urlsplit(final).hostname)
    return source_host == 'a.co' and final_host.endswith('amazon.com.mx')


def evaluate(html: str, original: str, final: str) -> Risk:
    soup = BeautifulSoup(html, 'html.parser')
    https = urlsplit(final).scheme == 'https'
    same = comparable_host(urlsplit(original).hostname) == comparable_host(urlsplit(final).hostname)
    redirected = not same
    expected_redirect = redirected and expected_short_link(original, final)
    evidence = [
        Evidence(title='Conexión HTTPS', status='observed' if https else 'warning', source=final,
                 detail='La conexión está cifrada. HTTPS por sí solo no demuestra confiabilidad.' if https else 'La página no utiliza HTTPS.'),
        Evidence(title='Consistencia del dominio', status='observed' if same or expected_redirect else 'warning', source=final,
                 detail=('El enlace corto redirigió al dominio de Amazon; se analizó el destino final. Esto no autentica al vendedor.' if expected_redirect
                         else 'El dominio final coincide con el solicitado; esto no autentica al vendedor.' if same
                         else 'La página redirigió a otro dominio. Comprueba que corresponde al vendedor.')),
    ]
    for title, words in [('Contacto e identidad', ('contacto', 'contact', 'nosotros', 'about')),
                          ('Devoluciones', ('devoluc', 'return', 'reembolso')),
                          ('Envío', ('envío', 'envio', 'shipping', 'entrega'))]:
        link = next((a for a in soup.find_all('a', href=True) if any(word in (a.get_text(' ', strip=True) + urlsplit(str(a['href'])).path).lower() for word in words)
                     and safe_link(a['href'], final)), None)
        evidence.append(Evidence(title=title, status='observed' if link else 'unavailable',
            source=urljoin(final, str(link['href'])) if link else final,
            detail='Se encontró un enlace. Su contenido y la identidad del vendedor no están verificados.' if link else 'No se encontró evidencia en el HTML accesible; no prueba que no exista.'))
    mixed = bool(urlsplit(final).scheme == 'https' and soup.find(
        lambda tag: tag.name in ('script', 'img', 'iframe', 'form')
        and str(tag.get('src') or tag.get('action') or '').lower().startswith('http://')
    ))
    evidence.append(Evidence(
        title='Contenido mixto', status='warning' if mixed else 'observed', source=final,
        detail='La página HTTPS carga o envía datos mediante HTTP sin cifrar.' if mixed
        else 'No se detectaron recursos HTTP explícitos en el HTML accesible; los recursos creados con JavaScript no se inspeccionaron.',
    ))
    sensitive = bool(soup.find('input', attrs={'type': re.compile(r'password|credit-card', re.I)}))
    evidence.append(Evidence(
        title='Formularios sensibles', status='warning' if sensitive and not https else ('observed' if sensitive else 'unavailable'),
        source=final,
        detail='Se detectó un campo sensible en una página sin HTTPS.' if sensitive and not https
        else ('El formulario sensible está bajo HTTPS; no se verificó quién recibe los datos.' if sensitive
              else 'No se encontraron formularios sensibles en el HTML accesible.'),
    ))
    structured = any('Product' in item.get_text() for item in soup.find_all('script', attrs={'type': 'application/ld+json'}))
    evidence.append(Evidence(
        title='Datos estructurados del producto', status='observed' if structured else 'unavailable', source=final,
        detail='La página publica datos Product en JSON-LD; son declaraciones del sitio, no una verificación externa.' if structured
        else 'No se detectaron datos Product en JSON-LD en el HTML accesible.',
    ))
    review_text = soup.select_one('#averageCustomerReviews') or soup.select_one('#acrCustomerReviewText')
    review_value = review_text.get_text(' ', strip=True) if review_text else ''
    review_count = re.search(r'\(([0-9][0-9,.]*)\)', review_value) or re.search(
        r'([0-9][0-9,.]*)\s+calificaciones', review_value, re.I,
    )
    evidence.append(Evidence(
        title='Reseñas en la tienda', status='observed' if review_text else 'unavailable', source=final,
        detail=(f'La página muestra reseñas internas ({review_count.group(1) if review_count else "cantidad no extraída"}) y una calificación declarada. No equivalen a reputación externa independiente.')
        if review_text else 'No se detectó un bloque de reseñas en el HTML accesible; podría cargarse con JavaScript.',
    ))
    for title in ['Reputación y reseñas externas', 'Posibles suplantaciones']:
        evidence.append(Evidence(title=title, status='unavailable', detail='No hay una fuente independiente verificada en este MVP.'))
    suspicious_redirect = redirected and not expected_redirect
    return Risk(level='medio' if not https or suspicious_redirect else 'información insuficiente',
                explanation='Se detectaron señales que requieren atención; no constituyen una prueba de fraude.' if not https or suspicious_redirect else 'La información técnica disponible no permite confirmar la confiabilidad del vendedor.', evidence=evidence)


def _tokens(value: str) -> set[str]:
    plain = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return {part for part in re.findall(r'[a-z0-9]+', plain) if len(part) > 1 or part.isdigit()}


def audit_consistency(risk: Risk, product: Product, alternatives: list[Product]) -> None:
    missing = [label for field, label in (
        (product.model, 'modelo'), (product.variant, 'variante'), (product.gtin, 'GTIN'),
    ) if not field]
    risk.evidence.append(Evidence(
        title='Identificadores del producto', status='unavailable' if missing else 'observed', source=product.url,
        detail=('Faltan ' + ', '.join(missing) + '; aumenta el riesgo de comparar variantes distintas.') if missing
        else 'Modelo, variante y GTIN fueron declarados por la página; todavía requieren confirmación.',
    ))
    if not alternatives:
        risk.evidence.append(Evidence(
            title='Consistencia entre opciones', status='unavailable',
            detail='No hubo opciones relacionadas suficientes para contrastar especificaciones.',
        ))
        return
    expected_numbers = {part for part in _tokens(product.name) if any(char.isdigit() for char in part)}
    inconsistent: list[str] = []
    for item in alternatives:
        candidate_numbers = {part for part in _tokens(item.name) if any(char.isdigit() for char in part)}
        if item.match == 'similar' and expected_numbers != candidate_numbers:
            inconsistent.append(item.store)
    if inconsistent:
        stores = ', '.join(dict.fromkeys(inconsistent[:4]))
        risk.evidence.append(Evidence(
            title='Inconsistencias entre opciones', status='warning',
            detail=f'{len(inconsistent)} opciones cambian números, capacidad o modelo respecto al producto consultado ({stores}). Trátalas como similares, no como el mismo artículo.',
        ))
    else:
        risk.evidence.append(Evidence(
            title='Consistencia entre opciones', status='observed',
            detail='No se detectaron diferencias numéricas evidentes entre las opciones relacionadas; aún deben confirmarse modelo, variante y condición.',
        ))


def compare_price(risk: Risk, product: Product, alternatives: list[Product]) -> None:
    prices = [p.price for p in alternatives if p.match == 'identical' and p.currency == product.currency and p.price is not None]
    if product.price is not None and prices:
        import statistics
        low = product.price < statistics.median(prices) * .6
        risk.evidence.append(Evidence(title='Precio frente a alternativas', status='warning' if low else 'observed', source=product.url,
            detail='Precio al menos 40% inferior a la mediana de productos idénticos encontrados; revisa condiciones y costos.' if low else 'No se detectó una diferencia superior al umbral del 40%; se comparó precio publicado, sin envío desconocido.'))
        if low:
            risk.level = 'medio'
    else:
        risk.evidence.append(Evidence(title='Precio frente a alternativas', status='unavailable', detail='No hay suficientes precios de productos idénticos en la misma moneda.'))
