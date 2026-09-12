"""Extract a bounded public website profile from already-fetched HTML."""
import json
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..models import WebsiteProfile
from .extraction import safe_link, scalar


def extract_website(html: str, url: str) -> WebsiteProfile:
    soup = BeautifulSoup(html, 'html.parser')

    def meta(*names: str) -> str | None:
        for name in names:
            tag = soup.find('meta', property=name) or soup.find('meta', attrs={'name': name})
            value = scalar(tag.get('content')) if tag else None
            if value:
                return value
        return None

    organization = None
    for script in soup.find_all('script', type='application/ld+json')[:30]:
        try:
            value = json.loads(script.get_text())
        except ValueError:
            continue
        nodes = value if isinstance(value, list) else value.get('@graph', [value]) if isinstance(value, dict) else []
        for node in nodes:
            if isinstance(node, dict) and node.get('@type') in ('Organization', 'Corporation', 'GovernmentOrganization', 'OnlineStore'):
                organization = scalar(node.get('name'))
                break
        if organization:
            break

    icon = soup.find('link', rel=lambda value: value and 'icon' in ' '.join(value if isinstance(value, list) else [value]).lower())
    image = meta('og:image', 'twitter:image') or (scalar(icon.get('href')) if icon else None)
    title = meta('og:title', 'twitter:title') or (soup.title.get_text(' ', strip=True)[:300] if soup.title else None)
    return WebsiteProfile(
        url=url,
        domain=urlsplit(url).hostname or '',
        title=title or urlsplit(url).hostname or 'Sitio sin título público',
        description=meta('description', 'og:description'),
        image=safe_link(image, url),
        declared_organization=organization or meta('og:site_name', 'application-name'),
        sensitive_forms=len(soup.select('input[type="password"], input[autocomplete="cc-number"], input[name*="card" i]')),
    )
