from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from ..models import Evidence, Product, Risk
from .extraction import safe_link


def evaluate(html: str, original: str, final: str) -> Risk:
    soup = BeautifulSoup(html, 'html.parser')
    https = urlsplit(final).scheme == 'https'
    same = urlsplit(original).hostname == urlsplit(final).hostname
    evidence = [
        Evidence(title='Conexión HTTPS', status='observed' if https else 'warning', source=final,
                 detail='La conexión está cifrada. HTTPS por sí solo no demuestra confiabilidad.' if https else 'La página no utiliza HTTPS.'),
        Evidence(title='Consistencia del dominio', status='observed' if same else 'warning', source=final,
                 detail='El dominio final coincide con el solicitado; esto no autentica al vendedor.' if same else 'La página redirigió a otro dominio. Comprueba que corresponde al vendedor.'),
    ]
    for title, words in [('Contacto e identidad', ('contacto', 'contact', 'nosotros', 'about')),
                          ('Devoluciones', ('devoluc', 'return', 'reembolso')),
                          ('Envío', ('envío', 'envio', 'shipping', 'entrega'))]:
        link = next((a for a in soup.find_all('a', href=True) if any(word in (a.get_text() + str(a['href'])).lower() for word in words)
                     and safe_link(a['href'], final)), None)
        evidence.append(Evidence(title=title, status='observed' if link else 'unavailable',
            source=urljoin(final, str(link['href'])) if link else final,
            detail='Se encontró un enlace. Su contenido y la identidad del vendedor no están verificados.' if link else 'No se encontró evidencia en el HTML accesible; no prueba que no exista.'))
    for title in ['Reputación y reseñas externas', 'Antigüedad del dominio', 'Posibles suplantaciones']:
        evidence.append(Evidence(title=title, status='unavailable', detail='No hay una fuente independiente verificada en este MVP.'))
    return Risk(level='medio' if not https or not same else 'información insuficiente',
                explanation='Se detectaron señales que requieren atención; no constituyen una prueba de fraude.' if not https or not same else 'La información técnica disponible no permite confirmar la confiabilidad del vendedor.', evidence=evidence)


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
