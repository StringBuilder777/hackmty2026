import asyncio
import socket
import pytest
from pydantic import ValidationError
from app.models import Product, Stop, Point, RouteInput, AnalysisInput
from app.services.fetch import HARD_MAX_BYTES, MIN_MAX_BYTES, max_html_bytes, validate_url, is_public, PublicResolver
from app.services.search import canonical_url, classify, related
from app.services.routing import group_stops, recommend, calculate_route
from app.services.extraction import extract
from app.services.risk import audit_consistency, comparable_host, evaluate
from app.services.domain import _creation_date
from app.services.agent import _parse, _payload
from app.services.store import inspect_store
from app.services.website import extract_website
from app.services.phishing import evaluate_website

@pytest.mark.parametrize('url', [
    'file:///etc/passwd', 'ftp://example.com', 'http://localhost/', 'http://127.0.0.1/',
    'http://127.1/', 'http://2130706433/', 'http://10.0.0.1/', 'http://169.254.169.254/latest/meta-data/',
    'http://[::1]/', 'http://[::ffff:127.0.0.1]/', 'http://192.168.1.3/',
    'https://example.com:8080', 'https://user:pass@example.com/', 'https://x.local/',
    'https://example.com\\@127.0.0.1', 'http://224.0.0.1/', 'http://100.64.0.1/',
])
def test_reject_unsafe_url(url):
    with pytest.raises(ValueError): validate_url(url)

@pytest.mark.parametrize('url', ['https://example.com/product', 'http://example.org/', 'https://example.com:443'])
def test_accept_public_url(url):
    assert validate_url(url)

@pytest.mark.parametrize('ip', ['::1', '::ffff:8.8.8.8', '2002:7f00:1::', '192.0.2.1', '0.0.0.0', '169.254.169.254', '100.64.1.1'])
def test_reject_reserved_ip(ip):
    assert not is_public(ip)


def test_dns_mixed_public_private_rejected(monkeypatch):
    async def run():
        async def fake(*args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443)), (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
        monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', fake)
        with pytest.raises(ValueError, match='DNS bloqueado'):
            await PublicResolver().resolve('rebind.example.com', 443)
    asyncio.run(run())


def test_resolver_pins_validated_addresses(monkeypatch):
    async def run():
        async def fake(*args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
        monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', fake)
        resolved = await PublicResolver().resolve('shop.example.com', 443)
        assert resolved[0]['host'] == '8.8.8.8'
        assert resolved[0]['hostname'] == 'shop.example.com'
    asyncio.run(run())


def test_html_limit_is_configurable_but_safely_bounded(monkeypatch):
    monkeypatch.setenv('MAX_HTML_BYTES', 'not-a-number')
    assert max_html_bytes() == 8 * 1024 * 1024
    monkeypatch.setenv('MAX_HTML_BYTES', '1')
    assert max_html_bytes() == MIN_MAX_BYTES
    monkeypatch.setenv('MAX_HTML_BYTES', str(100 * 1024 * 1024))
    assert max_html_bytes() == HARD_MAX_BYTES


def product(**changes):
    data = dict(id='a', name='Headphones', url='https://example.com', store='example.com', brand='Sony', model='WH-1000XM5', variant='Negro', condition='NewCondition')
    return Product(**(data | changes))


def test_identical_requires_variant_and_condition():
    original = product()
    assert classify(original, product(id='b'))[0] == 'identical'
    for changes in [{'variant': 'Plata'}, {'variant': None}, {'condition': 'UsedCondition'}, {'model': 'WH-1000XM4'}, {'model': None}]:
        assert classify(original, product(**changes))[0] == 'similar'


def test_sku_is_not_cross_store_identifier():
    assert classify(product(sku='123', model=None), product(sku='123'))[0] == 'similar'


def test_generic_product_similarity_is_not_limited_to_headphones():
    nas = product(name='Ugreen NAS 6-Bahías i5-1235U 8GB RAM M.2 128GB SATA III', model=None)
    same_family = product(name='NAS Ugreen DXP6800 Pro Intel Core i5-1235U 6 Bahías SATA 8GB RAM', model=None)
    unrelated = product(name='Mesa de comedor de madera para seis personas', brand=None, model=None)
    assert related(nas, same_family)
    assert not related(nas, unrelated)


def test_search_deduplicates_tracking_variants_of_original_url():
    assert canonical_url('https://shop.example/item?a=1') == canonical_url('https://shop.example/item?b=2')


def test_gtin_conflicts_and_unknown_condition():
    assert classify(product(gtin='123'), product(gtin='456'))[0] == 'similar'
    assert classify(product(gtin='123', condition=None), product(gtin='123', condition=None))[0] == 'similar'


def test_branch_grouping_and_conflict():
    a = Stop(id='a', name='Centro', lat=25.67, lng=-100.31)
    b = Stop(id='b', name='Otra', lat=25.65, lng=-100.36)
    assert group_stops([a, a, b]) == [a, b]
    with pytest.raises(ValueError): group_stops([a, a.model_copy(update={'lat': 25.0})])
    assert recommend(Point(lat=25.67, lng=-100.31), [b, a]) == [a, b]


def test_provider_failure_has_no_fake_line():
    class Broken:
        name = 'test'
        async def calculate(self, points, mode): raise ValueError('Proveedor no disponible')
    req = RouteInput(origin=Point(lat=25.67, lng=-100.31), stops=[Stop(id='a', name='Centro', lat=25.68, lng=-100.32)])
    result = asyncio.run(calculate_route(req, Broken()))
    assert result.status == 'unavailable' and result.coordinates == []
    assert len(result.ordered_stops) == 1


def test_extraction_preserves_unknown_shipping_and_unsafe_image():
    html = '''<script type="application/ld+json">{"@type":"Product","name":"Audífonos","brand":{"name":"Sony"},"color":"Negro","image":"javascript:alert(1)","offers":{"price":"5999","priceCurrency":"MXN"}}</script>'''
    p = extract(html, 'https://example.com')
    assert p.price == 5999 and p.shipping is None and p.total is None and p.image is None


def test_extraction_keeps_image_gallery_description_and_declared_specifications():
    html = '''<script type="application/ld+json">{"@type":"Product","name":"Audífonos","description":"Cancelación de ruido","image":["/one.jpg", "/two.jpg"],"offers":{"price":"100","priceCurrency":"MXN"}}</script><table><tr><th>Impedancia</th><td>32 ohms</td></tr></table>'''
    p = extract(html, 'https://shop.example/item')
    assert p.images == ['https://shop.example/one.jpg', 'https://shop.example/two.jpg']
    assert p.description == 'Cancelación de ruido' and p.specifications[0].name == 'impedancia'


def test_store_profile_labels_declarations_without_claiming_identity():
    html = '''<script type="application/ld+json">{"@type":"Organization","name":"Tienda Ejemplo","description":"Comercio de tecnología","logo":"/logo.png"}</script><a href="/contacto">Contacto</a><a href="/devoluciones">Devoluciones</a><a href="https://instagram.com/tienda">Instagram</a>'''
    store = inspect_store(html, 'https://shop.example/product')
    assert store.name == 'Tienda Ejemplo' and store.image == 'https://shop.example/logo.png'
    assert len(store.contacts) == 1 and len(store.policy_links) == 1 and len(store.social_links) == 1


def test_store_profile_extracts_a_publicly_declared_marketplace_seller():
    html = '''<script type="application/ld+json">{"@type":"Product","offers":{"seller":{"name":"Vendedor MX","url":"/seller/mx"}}}</script><div id="merchantInfo">Vendido por <a href="/seller/mx">Vendedor MX</a></div>'''
    store = inspect_store(html, 'https://market.example/product')
    assert store.seller_name == 'Vendedor MX'
    assert store.seller_url == 'https://market.example/seller/mx'


def test_store_profile_uses_marketplace_seller_dom_fallback():
    html = '''<div id="tabular-buybox-truncate-1">Vendido por <a href="/sp?seller=ABC">Comercializadora Norte</a></div>'''
    store = inspect_store(html, 'https://www.amazon.com.mx/product')
    assert store.seller_name == 'Comercializadora Norte'
    assert store.seller_url == 'https://www.amazon.com.mx/sp?seller=ABC'


def test_store_profile_uses_the_store_published_icon():
    html = '''<link rel="icon" href="/assets/store-icon.png"><meta property="og:site_name" content="Walmart México">'''
    store = inspect_store(html, 'https://www.walmart.com.mx/product')
    assert store.name == 'Walmart México'
    assert store.image == 'https://www.walmart.com.mx/assets/store-icon.png'


def test_amazon_style_html_fallback_extracts_commercial_fields():
    html = '''<html><span id="productTitle">AOC Monitor 22 Pulgadas</span>
    <a id="bylineInfo">Visita la tienda de AOC</a><div class="a-price"><span class="a-offscreen">$1,300.00</span></div>
    <input id="ASIN" value="B0DY99NW1N"><table><tr><th>Modelo</th><td>22B35HM23</td></tr></table></html>'''
    result = extract(html, 'https://www.amazon.com.mx/dp/B0DY99NW1N')
    assert result.name == 'AOC Monitor 22 Pulgadas'
    assert result.brand == 'AOC' and result.model == '22B35HM23' and result.sku == 'B0DY99NW1N'
    assert result.price == 1300 and result.currency == 'MXN'


def test_https_alone_does_not_prove_trust():
    result = evaluate('<p>Perfectly safe shop</p>', 'https://example.com', 'https://example.com')
    assert result.level == 'información insuficiente'
    assert any(e.status == 'unavailable' for e in result.evidence)


def test_www_redirect_is_same_domain_and_store_reviews_are_detected():
    html = '<div id="averageCustomerReviews">4.4 de 5 estrellas (294)</div>'
    result = evaluate(html, 'https://amazon.com.mx/item', 'https://www.amazon.com.mx/item')
    assert comparable_host('www.amazon.com.mx') == comparable_host('amazon.com.mx')
    assert next(e for e in result.evidence if e.title == 'Consistencia del dominio').status == 'observed'
    review = next(e for e in result.evidence if e.title == 'Reseñas en la tienda')
    assert review.status == 'observed' and '294' in review.detail


def test_amazon_short_link_is_resolved_without_false_domain_warning():
    result = evaluate('<p>shop</p>', 'https://a.co/d/example', 'https://www.amazon.com.mx/dp/example')
    domain = next(e for e in result.evidence if e.title == 'Consistencia del dominio')
    assert domain.status == 'observed' and result.level == 'información insuficiente'


def test_return_to_query_is_not_mistaken_for_refund_policy():
    html = '<a href="/signin?openid.return_to=/product">Iniciar sesión</a>'
    result = evaluate(html, 'https://example.com/item', 'https://example.com/item')
    assert next(e for e in result.evidence if e.title == 'Devoluciones').status == 'unavailable'


def test_html_security_and_product_metadata_checks():
    html = '<script src="http://cdn.example.org/app.js"></script><script type="application/ld+json">{"@type":"Product"}</script>'
    result = evaluate(html, 'https://example.com', 'https://example.com')
    assert next(e for e in result.evidence if e.title == 'Contenido mixto').status == 'warning'
    assert next(e for e in result.evidence if e.title == 'Datos estructurados del producto').status == 'observed'


def test_website_profile_and_government_impersonation_signal():
    html = '''<title>Trámites Gobierno</title><meta name="description" content="Paga tu trámite"><a href="https://www.gob.mx/a">Gobierno</a><a href="https://www.gob.mx/b">SAT</a><a href="https://www.gob.mx/c">Trámites</a><a href="https://www.gob.mx/d">Secretaría</a><form action="http://collector.example"><input type="password"></form>'''
    profile = extract_website(html, 'https://tienda-ejemplo.com')
    risk = evaluate_website(html, 'https://tienda-ejemplo.com', 'https://tienda-ejemplo.com', profile)
    assert profile.title == 'Trámites Gobierno' and profile.sensitive_forms == 1
    assert next(e for e in risk.evidence if e.title == 'Posible suplantación gubernamental').status == 'warning'
    assert next(e for e in risk.evidence if e.title == 'Formularios y credenciales').status == 'warning'
    assert risk.level == 'alto'


def test_consistency_audit_reports_missing_identity_and_spec_changes():
    original = product(name='Ugreen NAS 6 bahías i5-1235U 8GB', model=None, variant=None, gtin=None)
    option = product(id='b', name='Ugreen NAS 4 bahías i5-1235U 8GB', model=None, variant=None, gtin=None, match='similar')
    risk = evaluate('<p>shop</p>', original.url, original.url)
    audit_consistency(risk, original, [option])
    assert next(e for e in risk.evidence if e.title == 'Identificadores del producto').status == 'unavailable'
    assert next(e for e in risk.evidence if e.title == 'Inconsistencias entre opciones').status == 'warning'


def test_rdap_registration_date_is_read_without_treating_domain_as_trusted():
    created = _creation_date({'events': [{'eventAction': 'registration', 'eventDate': '2024-01-02T03:04:05Z'}]})
    assert created is not None and created.year == 2024


def test_agent_contract_uses_only_bounded_evidence_and_validates_its_json():
    risk = evaluate('<p>shop</p>', 'https://example.com', 'https://example.com')
    payload = _payload(risk, product(), [product(id=str(index)) for index in range(8)])
    assert len(payload['contents'][0]['parts'][0]['text']) < 10_000
    assert len(__import__('json').loads(payload['contents'][0]['parts'][0]['text'])['alternatives']) == 5
    assert payload['generationConfig']['thinkingConfig']['thinkingBudget'] == 0
    assessment = _parse({'candidates': [{'content': {'parts': [{'text': '{"level":"medio","explanation":"Revisa las señales disponibles.","limitations":["No confirma identidad."]}'}]}}]})
    assert assessment.level == 'medio'


def test_invalid_coordinates_and_nan():
    for lat in [91, float('nan'), float('inf')]:
        with pytest.raises(ValidationError): Point(lat=lat, lng=0)


def test_known_mexican_shipping_is_included():
    html = '''<script type="application/ld+json">{"@type":"Product","name":"Audífonos","offers":{"price":"100","priceCurrency":"MXN","shippingDetails":{"shippingDestination":{"addressCountry":"MX"},"shippingRate":{"value":25,"currency":"MXN"}}}}</script>'''
    p = extract(html, 'https://example.com')
    assert p.shipping == 25 and p.total == 125


def test_redirect_to_private_host_is_never_fetched(monkeypatch):
    from app.services import fetch
    requested = []
    class Response:
        status = 302
        headers = {'Location': 'http://169.254.169.254/latest/meta-data/'}
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    class Session:
        def __init__(self, **kwargs): self.connector = kwargs['connector']
        async def __aenter__(self): return self
        async def __aexit__(self, *args): await self.connector.close()
        def get(self, url, **kwargs):
            requested.append(url)
            return Response()
    monkeypatch.setattr(fetch.aiohttp, 'ClientSession', Session)
    with pytest.raises(ValueError, match='privada|reservada'):
        asyncio.run(fetch.fetch_html('https://example.com'))
    assert requested == ['https://example.com']


def test_search_adapter_extracts_only_related_products(monkeypatch):
    from app.services import search
    class Provider:
        async def urls(self, query): return ['https://shop.example.com/headphones', 'https://shop.example.com/other']
    async def fake_fetch(url):
        name = 'Sony WH-1000XM5 audífonos' if url.endswith('headphones') else 'Mesa de comedor'
        model = 'WH-1000XM5' if url.endswith('headphones') else 'TABLE'
        return f'<script type="application/ld+json">{{"@type":"Product","name":"{name}","brand":"Sony","model":"{model}","color":"Negro","offers":{{"price":100,"priceCurrency":"MXN","itemCondition":"NewCondition"}}}}</script>', url
    monkeypatch.setattr(search, 'fetch_html', fake_fetch)
    monkeypatch.delenv('BRANCH_CATALOG_PATH', raising=False)
    found, notes = asyncio.run(search.alternatives(product(), Provider()))
    assert len(found) == 1 and found[0].match == 'identical' and found[0].shipping is None


def test_search_rejects_non_commercial_article_without_price(monkeypatch):
    from app.services import search
    class Provider:
        async def urls(self, query): return ['https://news.example.com/article']
    async def fake_fetch(url):
        return '<html><title>Sony WH-1000XM5 audífonos: presentación y noticias</title></html>', url
    monkeypatch.setattr(search, 'fetch_html', fake_fetch)
    found, _ = asyncio.run(search.alternatives(product(), Provider()))
    assert found == []


def test_catalog_never_infers_inventory_from_domain(tmp_path, monkeypatch):
    import json
    from app.services.branches import resolve
    catalog = tmp_path / 'branches.json'
    catalog.write_text(json.dumps([{'domain': 'example.com', 'gtin': 'other', 'branch': {'id': 'a', 'name': 'Centro', 'address': 'Example', 'source': 'https://example.com/branch', 'lat': 25.67, 'lng': -100.31, 'inventory': 'confirmed', 'inventory_checked_at': '2026-09-12T00:00:00Z'}}]))
    monkeypatch.setenv('BRANCH_CATALOG_PATH', str(catalog))
    branch = resolve(product(gtin='123'))[0]
    assert branch.inventory == 'pending' and branch.inventory_checked_at is None


def test_provider_json_reads_all_chunks_and_caps_size():
    from app.services.http_client import bounded_json
    class Content:
        async def iter_chunked(self, size):
            for chunk in [b'{"ok":', b'true}']: yield chunk
    class Response:
        content = Content()
    assert asyncio.run(bounded_json(Response())) == {'ok': True}
    with pytest.raises(ValueError, match='límite'):
        asyncio.run(bounded_json(Response(), 3))


def test_bedrock_assessment_accepts_a_markdown_json_fence():
    from app.services.agent import _parse_assessment_text
    assessment = _parse_assessment_text('```json\n{"level":"bajo","explanation":"Señales disponibles.","limitations":[]}\n```')
    assert assessment.level == 'bajo'
