"""Fictional offers and branches, never fed into real analyses."""
from ..models import Analysis, Product, Branch, Risk, Evidence


def populate(analysis: Analysis) -> None:
    stamp = '2026-09-12T12:00:00+00:00'
    evidence = [Evidence(title='Datos de ejemplo', status='unavailable', detail='Tiendas, precios e inventario ficticios. Las coordenadas son puntos ilustrativos en Monterrey, no sucursales reales.')]
    base = dict(name='Sony WH-1000XM5', brand='Sony', model='WH-1000XM5', variant='Negro', condition='NewCondition', currency='MXN', checked_at=stamp, demo=True, evidence=evidence, image='/headphones.png')
    analysis.product = Product(**base, id='demo-original', url='https://example.com/audifonos', store='Tienda de ejemplo', price=7999)
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
