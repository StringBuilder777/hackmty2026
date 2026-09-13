"""Bounded JSON reads for trusted, configured provider endpoints."""
import json
import aiohttp


async def bounded_json(response: aiohttp.ClientResponse, limit: int = 2_000_000) -> dict:
    body = bytearray()
    async for chunk in response.content.iter_chunked(32768):
        body.extend(chunk)
        if len(body) > limit:
            raise ValueError('La respuesta del proveedor excede el límite permitido.')
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError('El proveedor devolvió un formato inesperado.')
    return data
