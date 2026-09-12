"""Fictional offers and branches, never fed into real analyses."""
from ..models import AgentAssessment, Analysis, Product, Branch, Risk, Evidence, ProductAttribute, StoreProfile, WebsiteProfile, DomainRegistration


def populate(analysis: Analysis) -> None:
    stamp = '2026-09-12T12:00:00+00:00'
    evidence = [Evidence(title='Datos de ejemplo', status='unavailable', detail='Tiendas, precios e inventario ficticios. Las coordenadas son puntos ilustrativos en Monterrey, no sucursales reales.')]
    if analysis.target == 'website':
        analysis.website_profile = WebsiteProfile(
            url='https://tienda-tramites.example', domain='tienda-tramites.example', title='Ofertas del Gobierno - Tienda Demo',
            description='Ejemplo ficticio de un comercio que copia lenguaje institucional.', image='/demo-store.svg',
            declared_organization='Apoyos Gobierno MX', sensitive_forms=1,
        )
        analysis.store_profile = StoreProfile(
            name='Tienda institucional no verificada', domain='tienda-tramites.example', url='https://tienda-tramites.example',
            description='Identidad ficticia para demostrar señales de posible suplantación.', image='/demo-store.svg',
            seller_name='Operador no identificado', evidence=evidence,
        )
        analysis.domain_registration = DomainRegistration(
            domain='tienda-tramites.example', lookup_url='https://rdap.org/domain/tienda-tramites.example', status='available',
            created_at='2026-08-20T00:00:00Z', age_days=23, registrar='Registrador Demo', nameservers=['ns1.example'],
            domain_statuses=['client transfer prohibited'], note='Datos RDAP ficticios para mostrar la interfaz; no corresponden a un dominio real.',
        )
        analysis.risk = Risk(level='alto', checked_at=stamp, explanation='El demo combina dominio reciente, lenguaje gubernamental en un dominio no oficial y captura de datos. Son señales ficticias para explicar el análisis.', evidence=[
            Evidence(title='Conexión HTTPS', status='observed', source='https://tienda-tramites.example', detail='HTTPS ficticio; no demuestra legitimidad.'),
            Evidence(title='Antigüedad del dominio', status='warning', source='https://rdap.org/domain/tienda-tramites.example', detail='El registro ficticio indica creación hace 23 días.'),
            Evidence(title='Posible suplantación gubernamental', status='warning', source='https://tienda-tramites.example', detail='El contenido usa lenguaje gubernamental, pero el dominio no pertenece a una terminación oficial.'),
            Evidence(title='Formularios y credenciales', status='warning', source='https://tienda-tramites.example', detail='El demo incluye un formulario sensible que requeriría verificar destino y operador.'),
        ], agent_assessment=AgentAssessment(
            level='alto',
            explanation='La combinación de identidad gubernamental no comprobada, dominio reciente y solicitud de datos sensibles amerita detenerse y verificar el sitio por un canal oficial.',
            limitations=['Evaluación demostrativa sobre evidencia ficticia; no representa una consulta real a Amazon Bedrock.'],
        ))
        analysis.limitations = ['Demo ficticio: no se consultó ningún dominio ni organismo real.', 'Las señales requieren confirmación humana y no equivalen a una acusación de fraude.']
        analysis.status = 'completed'
        return
    base = dict(name='Sony WH-1000XM5', brand='Sony', model='WH-1000XM5', variant='Negro', condition='NewCondition', currency='MXN', checked_at=stamp, demo=True, evidence=evidence, image='/headphones.png', images=['/headphones.png'], description='Ejemplo ficticio para visualizar la ficha de producto y sus fuentes.', specifications=[ProductAttribute(name='cancelación de ruido', value='Declaración de ejemplo', source='https://example.com/audifonos'), ProductAttribute(name='conectividad', value='Declaración de ejemplo', source='https://example.com/audifonos')])
    analysis.product = Product(**base, id='demo-original', url='https://example.com/audifonos', store='Tienda de ejemplo', price=7999)
    analysis.store_profile = StoreProfile(name='Marketplace Demo', domain='demo.buenpaso.mx', url='https://example.com', description='Perfil ficticio que muestra cómo se presentan la empresa, la tienda y el vendedor.', image='/demo-store.svg', seller_name='Vendedor de ejemplo', seller_url='https://example.com/vendedor', contacts=['https://example.com/contacto'], policy_links=['https://example.com/devoluciones'], evidence=evidence)
    analysis.risk = Risk(level='información insuficiente', checked_at=stamp, explanation='Este ejemplo muestra cómo leer las señales. No es una evaluación de una tienda real.', evidence=[
        Evidence(title='Conexión HTTPS', status='observed', source='https://example.com', detail='Señal ilustrativa. HTTPS por sí solo no demuestra confiabilidad.'), *evidence,
        Evidence(title='Reputación, identidad y políticas', status='unavailable', detail='Sin verificaciones reales en modo demo.')])
    branches = [Branch(id='demo-centro', name='Demo Centro', address='Punto ilustrativo · Centro, Monterrey', lat=25.6714, lng=-100.3105, source='https://www.openstreetmap.org/?mlat=25.6714&mlon=-100.3105'),
                Branch(id='demo-obispado', name='Demo Obispado', address='Punto ilustrativo · Obispado, Monterrey', lat=25.6763, lng=-100.3456, source='https://www.openstreetmap.org/?mlat=25.6763&mlon=-100.3456'),
                Branch(id='demo-sanpedro', name='Demo San Pedro', address='Punto ilustrativo · San Pedro Garza García', lat=25.6525, lng=-100.3668, source='https://www.openstreetmap.org/?mlat=25.6525&mlon=-100.3668')]
    analysis.alternatives = [
        Product(**base, id='demo-1', url='https://example.com/centro', store='Demo Centro', price=7499, match='identical', match_reason='Coinciden marca, modelo, variante y condición de ejemplo.', branches=branches[:2]),
        Product(**base, id='demo-2', url='https://example.com/sanpedro', store='Demo San Pedro', price=7799, match='identical', match_reason='Coinciden marca, modelo, variante y condición de ejemplo.', branches=[branches[2]]),
        Product(**{**base, 'variant': 'Plata'}, id='demo-3', url='https://example.com/online', store='Demo Online', price=6999, shipping=149, total=7148, match='similar', match_reason='La variante de color es diferente. Oferta ficticia exclusivamente en línea.'),
    ]
    analysis.limitations = ['Demo reproducible: ningún precio, vendedor o inventario es real.', 'Las rutas se consultan a OSRM por calles reales; requieren red, pero no credenciales.']
    analysis.status = 'completed'
