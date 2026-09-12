"""Evidence-based phishing and impersonation heuristics for a fetched website."""
import re
from collections import Counter
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..models import Evidence, Risk, WebsiteProfile
from .risk import comparable_host, expected_short_link


GOVERNMENT_WORDS = re.compile(r'\b(gobierno|government|secretar[ií]a|municipio|ayuntamiento|tr[aá]mite|impuesto|sat)\b', re.I)
COMMERCE_WORDS = re.compile(r'\b(comprar|carrito|checkout|oferta|descuento|tarjeta|pago|env[ií]o|tienda)\b', re.I)


def _government_domain(host: str) -> bool:
    host = comparable_host(host)
    return host.endswith('.gob.mx') or host.endswith('.gov') or '.gov.' in host


def evaluate_website(html: str, original: str, final: str, profile: WebsiteProfile) -> Risk:
    soup = BeautifulSoup(html, 'html.parser')
    source_host = comparable_host(urlsplit(original).hostname)
    final_host = comparable_host(urlsplit(final).hostname)
    https = urlsplit(final).scheme == 'https'
    redirected = source_host != final_host
    expected_redirect = redirected and expected_short_link(original, final)
    page_text = soup.get_text(' ', strip=True)[:250_000]
    evidence: list[Evidence] = [
        Evidence(title='Conexión HTTPS', status='observed' if https else 'warning', source=final,
                 detail='La conexión está cifrada; HTTPS no demuestra que la organización sea legítima.' if https else 'El sitio transmite contenido sin HTTPS.'),
        Evidence(title='Destino y redirecciones', status='observed' if not redirected or expected_redirect else 'warning', source=final,
                 detail='El dominio final coincide con el enlace solicitado.' if not redirected else 'El enlace terminó en otro dominio; confirma que el cambio sea esperado.'),
    ]

    host_shape_warning = final_host.startswith('xn--') or final_host.count('.') > 4 or len(final_host) > 70
    evidence.append(Evidence(
        title='Forma del dominio', status='warning' if host_shape_warning else 'observed', source=final,
        detail='El dominio usa punycode, demasiados niveles o una longitud atípica; revisa posibles imitaciones.' if host_shape_warning
        else 'No se detectaron patrones básicos de punycode, longitud extrema o exceso de subdominios.',
    ))

    form_warning = False
    form_detail = 'No se detectaron formularios de contraseña o tarjeta en el HTML accesible.'
    for form in soup.find_all('form')[:40]:
        sensitive = form.select_one('input[type="password"], input[autocomplete="cc-number"], input[name*="card" i]')
        if not sensitive:
            continue
        action = urljoin(final, str(form.get('action') or final))
        external_action = comparable_host(urlsplit(action).hostname) != final_host
        form_warning = not https or external_action
        form_detail = ('Un formulario sensible envía datos a otro dominio o sin HTTPS.' if form_warning
                       else 'Hay un formulario sensible bajo HTTPS; no se verificó quién recibe los datos.')
        break
    evidence.append(Evidence(title='Formularios y credenciales', status='warning' if form_warning else ('observed' if profile.sensitive_forms else 'unavailable'), source=final, detail=form_detail))

    claims_government = bool(GOVERNMENT_WORDS.search(page_text))
    commerce_on_government = _government_domain(final_host) and bool(COMMERCE_WORDS.search(page_text))
    linked_hosts = Counter(
        comparable_host(urlsplit(urljoin(final, str(link.get('href')))).hostname)
        for link in soup.find_all('a', href=True)[:500]
    )
    cloned_government_links = any(_government_domain(host) and host != final_host and count >= 4 for host, count in linked_hosts.items())
    impersonation = commerce_on_government or (claims_government and not _government_domain(final_host)) or cloned_government_links
    evidence.append(Evidence(
        title='Posible suplantación gubernamental', status='warning' if impersonation else 'unavailable', source=final,
        detail=('El contenido comercial o los enlaces gubernamentales no son consistentes con el dominio. Puede tratarse de contenido copiado, una redirección engañosa o un sitio comprometido; requiere revisión humana.' if impersonation
                else 'No se detectó una inconsistencia gubernamental clara con estas reglas; esto no descarta una copia visual cargada por JavaScript.'),
    ))

    identity = profile.declared_organization
    evidence.append(Evidence(
        title='Identidad declarada', status='observed' if identity else 'unavailable', source=final,
        detail=f'El sitio declara la organización “{identity}”; es una declaración propia, no una validación oficial.' if identity else 'No se encontró una organización declarada en metadatos públicos.',
    ))
    warnings = sum(item.status == 'warning' for item in evidence)
    level = 'alto' if warnings >= 2 and (form_warning or impersonation) else 'medio' if warnings else 'información insuficiente'
    explanation = ('Se detectaron varias señales compatibles con suplantación o captura riesgosa de datos; no prueban por sí solas quién opera el sitio.' if level == 'alto'
                   else 'Se detectó una señal que requiere verificación adicional; no constituye prueba de phishing.' if level == 'medio'
                   else 'No hay evidencia técnica suficiente para confirmar que el sitio sea legítimo o fraudulento.')
    return Risk(level=level, explanation=explanation, evidence=evidence)
