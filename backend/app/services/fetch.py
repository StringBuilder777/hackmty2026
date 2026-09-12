"""Bounded HTML fetch with DNS validation at connection time (no re-resolution gap)."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin
import aiohttp
from aiohttp.abc import AbstractResolver

MAX_BYTES = 2 * 1024 * 1024


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        # Reject transition addresses too; their embedded destination can be private.
        if ip.ipv4_mapped or ip.sixtofour or ip.teredo:
            return False
    return ip.is_global and not ip.is_multicast


def validate_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if parts.scheme not in ('https', 'http') or not host:
            raise ValueError('Solo se aceptan URLs HTTP o HTTPS.')
        if parts.username is not None or parts.password is not None or parts.port not in (None, 80, 443):
            raise ValueError('No se permiten credenciales ni puertos personalizados en la URL.')
        host = host.rstrip('.').lower()
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '%' in host or '\\' in url:
            raise ValueError('Destino local o reservado no permitido.')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            try:
                socket.inet_aton(host)
            except OSError:
                pass
            else:
                raise ValueError('Usa un dominio público o una dirección IP canónica pública.')
            if '.' not in host:
                raise ValueError('El destino debe ser un dominio público.')
        else:
            if not is_public(host):
                raise ValueError('Dirección privada o reservada no permitida.')
        return host
    except (TypeError, UnicodeError) as exc:
        raise ValueError('URL inválida.') from exc


class PublicResolver(AbstractResolver):
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        records = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=4
        )
        if not records or not all(is_public(record[4][0]) for record in records):
            raise ValueError('DNS bloqueado: el dominio resuelve a una red privada o reservada.')
        # These exact validated addresses are passed to the connector, retaining TLS SNI.
        return [dict(hostname=host, host=r[4][0], port=port, family=r[0], proto=r[2], flags=socket.AI_NUMERICHOST) for r in records]

    async def close(self) -> None:
        pass


async def fetch_html(url: str) -> tuple[str, str]:
    async with asyncio.timeout(18):
        connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False, limit=4)
        timeout = aiohttp.ClientTimeout(total=12, connect=5, sock_read=5)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, trust_env=False, auto_decompress=False,
                                        headers={'User-Agent': 'BuenPasoMVP/0.1', 'Accept': 'text/html', 'Accept-Encoding': 'identity'}) as session:
            for attempt in range(4):
                validate_url(url)
                async with session.get(url, allow_redirects=False) as response:
                    if response.status in (301, 302, 303, 307, 308):
                        if attempt == 3 or 'Location' not in response.headers:
                            raise ValueError('Demasiadas redirecciones o redirección inválida.')
                        url = urljoin(url, response.headers['Location'])
                        continue
                    if response.status != 200:
                        raise ValueError(f'La página respondió HTTP {response.status}. No se evaden bloqueos ni autenticación.')
                    if 'text/html' not in response.headers.get('Content-Type', '').lower():
                        raise ValueError('El recurso no es una página HTML.')
                    if response.headers.get('Content-Encoding', 'identity') != 'identity':
                        raise ValueError('La página no admite una descarga sin compresión dentro de los límites del MVP.')
                    if response.content_length and response.content_length > MAX_BYTES:
                        raise ValueError('La página excede el límite de 2 MB.')
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(32768):
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise ValueError('La página excede el límite de 2 MB.')
                    return body.decode('utf-8', errors='replace'), str(response.url)
    raise ValueError('No se pudo descargar la página.')
