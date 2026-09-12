import math
import os
from typing import Protocol
import aiohttp
from ..models import Point, Stop, Route, RouteInput
from .http import bounded_json


def group_stops(stops: list[Stop]) -> list[Stop]:
    groups: dict[str, Stop] = {}
    for stop in stops:
        if stop.id in groups and (groups[stop.id].lat != stop.lat or groups[stop.id].lng != stop.lng):
            raise ValueError('Una sucursal no puede tener coordenadas contradictorias.')
        groups.setdefault(stop.id, stop)
    return list(groups.values())


def distance(a: Point, b: Point) -> float:
    lat = math.radians((a.lat + b.lat) / 2)
    return (a.lat - b.lat) ** 2 + ((a.lng - b.lng) * math.cos(lat)) ** 2


def recommend(origin: Point, stops: list[Stop]) -> list[Stop]:
    pending, ordered, current = group_stops(stops), [], origin
    while pending:
        closest = min(pending, key=lambda stop: distance(current, stop))
        ordered.append(closest)
        pending.remove(closest)
        current = closest
    return ordered


class RouteProvider(Protocol):
    name: str
    async def calculate(self, points: list[Point], mode: str) -> tuple[list, float, float]: ...


async def response_json(response: aiohttp.ClientResponse) -> dict:
    if response.status != 200:
        raise ValueError(f'El proveedor de rutas respondió HTTP {response.status}.')
    return await bounded_json(response)


class OSRM:
    name = 'OSRM · © OpenStreetMap contributors'
    async def calculate(self, points: list[Point], mode: str) -> tuple[list, float, float]:
        if mode != 'driving':
            raise ValueError('Falta ORS_API_KEY y ROUTE_PROVIDER=ors para rutas a pie o en bicicleta. OSRM configurado solo admite auto.')
        coordinates = ';'.join(f'{p.lng},{p.lat}' for p in points)
        base = os.getenv('OSRM_BASE_URL', 'https://router.project-osrm.org').rstrip('/')
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(f'{base}/route/v1/driving/{coordinates}', params={'overview': 'full', 'geometries': 'geojson', 'steps': 'false'}, allow_redirects=False) as response:
                data = await response_json(response)
        if data.get('code') != 'Ok' or not data.get('routes'):
            raise ValueError('El proveedor no encontró un recorrido por calles.')
        route = data['routes'][0]
        return route['geometry']['coordinates'], route['distance'], route['duration']


class ORS:
    name = 'OpenRouteService · © OpenStreetMap contributors'
    async def calculate(self, points: list[Point], mode: str) -> tuple[list, float, float]:
        key = os.getenv('ORS_API_KEY')
        if not key:
            raise ValueError('Falta ORS_API_KEY para OpenRouteService.')
        profile = {'driving': 'driving-car', 'walking': 'foot-walking', 'cycling': 'cycling-regular'}[mode]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(f'https://api.openrouteservice.org/v2/directions/{profile}/geojson', json={'coordinates': [[p.lng, p.lat] for p in points]}, headers={'Authorization': key}, allow_redirects=False) as response:
                data = await response_json(response)
        feature = data['features'][0]
        summary = feature['properties']['summary']
        return feature['geometry']['coordinates'], summary['distance'], summary['duration']


async def calculate_route(request: RouteInput, provider: RouteProvider | None = None) -> Route:
    ordered = recommend(request.origin, request.stops)
    provider = provider or (ORS() if os.getenv('ROUTE_PROVIDER', 'osrm') == 'ors' else OSRM())
    try:
        coordinates, meters, seconds = await provider.calculate([request.origin, *ordered], request.mode)
        if len(coordinates) < 2 or not math.isfinite(meters) or not math.isfinite(seconds) or min(meters, seconds) < 0:
            raise ValueError('El proveedor devolvió una ruta inválida.')
        return Route(status='available', message='Ruta recomendada: orden por cercanía y recorrido real por calles. No garantiza el orden óptimo; sin tráfico en vivo.', ordered_stops=ordered,
                     coordinates=coordinates, distance_m=meters, duration_s=seconds, provider=provider.name, demo=request.demo)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'El proveedor de rutas no está disponible. Intenta nuevamente.'
        return Route(status='unavailable', message=message, ordered_stops=ordered, provider=provider.name, demo=request.demo)
