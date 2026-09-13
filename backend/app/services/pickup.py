import httpx
from app.models import Branch, Point

async def fetch_real_pickup_points(origin: Point, max_radius_km: float, carrier_query: str = "DHL Amazon Locker") -> list[Branch]:
    # Usando OpenStreetMap Overpass API (gratuita y sin tarjeta de crédito) o Google Places API
    # Buscamos puntos de entrega/couriers cercanos al origen del usuario en Monterrey
    radius_meters = int(max_radius_km * 1000)
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Query para buscar paqueterías, lockers o tiendas de conveniencia (ej. OXXO/DHL) en el radio
    query = f"""
    [out:json];
    (
      node["amenity"="parcel_lockers"](around:{radius_meters},{origin.lat},{origin.lng});
      node["brand"~"DHL|Estafeta|Amazon|FedEx", i](around:{radius_meters},{origin.lat},{origin.lng});
    );
    out body;
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(overpass_url, data={"data": query}, timeout=10.0)
        if response.status_code != 200:
            return []
            
        data = response.json()
        real_branches = []
        
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name", tags.get("brand", "Punto de Pickup Real"))
            lat = element.get("lat")
            lng = element.get("lon")
            address = tags.get("addr:street", "Monterrey, N.L.")
            
            real_branches.append(Branch(
                id=f"osm_{element.get('id')}",
                name=name,
                lat=lat,
                lng=lng,
                address=address,
                inventory="confirmed",
                inventory_checked_at=None,
                source="OpenStreetMap / Red Logística Real"
            ))
            
        return real_branches