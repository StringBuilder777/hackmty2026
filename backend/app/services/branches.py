"""Optional curated branch catalog. Online sales never imply branch inventory."""
import json
import os
from pathlib import Path
from ..models import Branch, Product
from app.models import Point, Branch
import math


def resolve(product: Product) -> list[Branch]:
    path = os.getenv('BRANCH_CATALOG_PATH')
    if not path:
        return []
    entries = json.loads(Path(path).read_text())
    result = []
    for entry in entries:
        if entry.get('domain') != product.store:
            continue
        branch = Branch.model_validate(entry['branch'])
        # A confirmed inventory record must reference this exact GTIN and have a date.
        confirmed = bool(product.gtin and entry.get('gtin') == product.gtin and branch.inventory_checked_at)
        if not confirmed:
            branch.inventory = 'pending'
            branch.inventory_checked_at = None
        result.append(branch)
    return result

def get_nearby_branches(origin: Point, all_branches: list[Branch], max_radius_km: float) -> list[Branch]:
    valid_branches = []
    for branch in all_branches:
        # Fórmula de Haversine para calcular distancia real en km
        lat1, lon1 = math.radians(origin.lat), math.radians(origin.lng)
        lat2, lon2 = math.radians(branch.lat), math.radians(branch.lng)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance_km = 6371 * c # Radio de la tierra en km
        
        # Si la sucursal está dentro del radio que eligió el usuario, la agregamos
        if distance_km <= max_radius_km:
            valid_branches.append(branch)
            
    return valid_branches