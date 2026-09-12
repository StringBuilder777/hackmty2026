"""Optional curated branch catalog. Online sales never imply branch inventory."""
import json
import os
from pathlib import Path
from ..models import Branch, Product


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
