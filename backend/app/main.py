import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .models import AnalysisInput, Analysis, RouteInput
from .services.fetch import fetch_html
from .services.extraction import extract
from .services.risk import evaluate, compare_price
from .services.search import alternatives
from .services.branches import resolve
from .services.routing import calculate_route
from .services.demo import populate

jobs: dict[str, tuple[float, Analysis]] = {}
rate: dict[str, deque] = defaultdict(deque)
semaphore = asyncio.Semaphore(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    jobs.clear()
    rate.clear()


app = FastAPI(title='BuenPaso API', version='0.1.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(','), allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={'error': {'code': str(exc.status_code), 'message': str(exc.detail)}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={'error': {'code': 'validation', 'message': 'Entrada inválida: ' + '; '.join(e['msg'] for e in exc.errors())}})


@app.middleware('http')
async def limits(request: Request, call_next):
    if request.method == 'POST':
        # Bound actual ASGI chunks; Content-Length is not trusted.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                return JSONResponse(status_code=413, content={'error': {'code': 'size', 'message': 'Solicitud demasiado grande (máximo 16 KB).'}})
        request._body = bytes(body)
        ip = request.client.host if request.client else 'unknown'
        clock = time.monotonic()
        # Bound retained clients, including clients that never return.
        for client in list(rate):
            if not rate[client] or rate[client][-1] < clock - 60:
                del rate[client]
        bucket = rate[ip]
        while bucket and bucket[0] < clock - 60:
            bucket.popleft()
        if len(bucket) >= 30 or len(rate) > 1000:
            return JSONResponse(status_code=429, content={'error': {'code': 'rate_limit', 'message': 'Demasiadas solicitudes. Espera un minuto.'}})
        bucket.append(clock)
    return await call_next(request)


@app.get('/health')
async def health():
    return {'status': 'ok', 'search': 'brave' if os.getenv('BRAVE_SEARCH_API_KEY') else 'missing: BRAVE_SEARCH_API_KEY',
            'routes': os.getenv('ROUTE_PROVIDER', 'osrm'), 'branches': bool(os.getenv('BRANCH_CATALOG_PATH'))}


async def run_analysis(analysis: Analysis, url: str):
    async with semaphore:
        try:
            async with asyncio.timeout(65):
                if analysis.mode == 'demo':
                    populate(analysis)
                    return
                analysis.status = 'extracting'
                html, final = await fetch_html(url)
                analysis.product = extract(html, final)
                analysis.product.branches = resolve(analysis.product)
                analysis.status = 'evaluating'
                analysis.risk = evaluate(html, url, final)
                analysis.product.evidence = analysis.risk.evidence[:2]
                analysis.status = 'searching'
                try:
                    analysis.alternatives, notes = await alternatives(analysis.product)
                    analysis.limitations.extend(notes)
                except Exception as exc:
                    analysis.limitations.append(str(exc) if isinstance(exc, ValueError) else 'La búsqueda externa no está disponible. Reintenta el análisis.')
                compare_price(analysis.risk, analysis.product, analysis.alternatives)
                analysis.limitations.append('Extracción de HTML y JSON-LD sin ejecutar JavaScript. No verifica identidad, reseñas ni inventario; no garantiza seguridad.')
                analysis.status = 'completed'
        except Exception as exc:
            analysis.status = 'error'
            analysis.error = str(exc) if isinstance(exc, ValueError) else 'No se pudo consultar la página dentro de los límites del servicio. Reintenta o usa otra URL.'
            logging.getLogger('buenpaso').info('Analysis failed: %s', type(exc).__name__)


@app.post('/analyses', status_code=202, response_model=Analysis)
async def start(payload: AnalysisInput, tasks: BackgroundTasks):
    clock = time.monotonic()
    for key, (created, _) in list(jobs.items()):
        if clock - created > 3600:
            del jobs[key]
    if sum(a.status not in ('completed', 'error') for _, a in jobs.values()) >= 12:
        raise HTTPException(429, 'Hay demasiados análisis en curso. Intenta nuevamente.')
    if len(jobs) >= 200:
        oldest = next((key for key, (_, a) in jobs.items() if a.status in ('completed', 'error')), None)
        if oldest:
            del jobs[oldest]
    analysis = Analysis(id=uuid4().hex, mode=payload.mode)
    jobs[analysis.id] = (clock, analysis)
    tasks.add_task(run_analysis, analysis, payload.url)
    return analysis


@app.get('/analyses/{analysis_id}', response_model=Analysis)
async def get_analysis(analysis_id: str):
    if analysis_id not in jobs or time.monotonic() - jobs[analysis_id][0] > 3600:
        raise HTTPException(404, 'Análisis no encontrado o expirado; inicia uno nuevo.')
    return jobs[analysis_id][1]


@app.get('/analyses/{analysis_id}/alternatives')
async def get_alternatives(analysis_id: str):
    analysis = await get_analysis(analysis_id)
    return {'status': analysis.status, 'mode': analysis.mode, 'alternatives': analysis.alternatives, 'limitations': analysis.limitations}


@app.post('/routes')
async def route(payload: RouteInput):
    try:
        return await calculate_route(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
