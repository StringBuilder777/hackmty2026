import asyncio
import base64
import logging
import os
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from .models import AnalysisInput, Analysis, AuditDemoInput, AuditPreflight, AuditRunInput, AuditUploadInput, RouteInput, Submission
from .services.fetch import fetch_html
from .services.extraction import extract
from .services.store import inspect_store
from .services.risk import audit_consistency, evaluate, compare_price
from .services.domain import registration_profile
from .services.website import extract_website
from .services.phishing import evaluate_website
from .services.agent import assess
from .services.search import alternatives
from .services.branches import resolve
from .services.routing import calculate_route
from .services.demo import populate
from .services.forensic import create_demo_estate, inspect_forensic_estate, render_case_file, run_forensic_audit
from .services.estate_ingest import uploaded_estate
from .services.pickup import fetch_real_pickup_points

jobs: dict[str, tuple[float, Analysis]] = {}
last_case_file: str | None = None
rate: dict[str, deque] = defaultdict(deque)
semaphore = asyncio.Semaphore(3)
MAX_AUDIT_FILE_BYTES = 14 * 1024 * 1024


def _decode_audit_upload(payload: AuditUploadInput) -> list[tuple[str, bytes]]:
    encoded = (
        [(payload.estate_filename, payload.estate_base64)]
        if payload.estate_base64 is not None
        else [(item.filename, item.content_base64) for item in payload.estate_files]
    )
    files: list[tuple[str, bytes]] = []
    total = 0
    for filename, content in encoded:
        try:
            raw = base64.b64decode(content, validate=True)
        except ValueError as exc:
            raise ValueError(f'{filename}: contenido base64 inválido.') from exc
        if not raw:
            raise ValueError(f'{filename}: el archivo está vacío.')
        total += len(raw)
        if total > MAX_AUDIT_FILE_BYTES:
            raise ValueError('La carga total excede 14 MB.')
        files.append((filename, raw))
    return files


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    jobs.clear()
    rate.clear()


app = FastAPI(title='SynchroData API', version='0.1.0', lifespan=lifespan)
# The development server may select the next free port. Keep the local origins
# explicit instead of using a wildcard, so a browser cannot read this API from
# an unrelated site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        'CORS_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001',
    ).split(','),
    allow_methods=['GET', 'POST'],
    allow_headers=['Content-Type'],
)


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
            audit_upload = request.url.path in ('/audit/upload', '/audit/preflight/upload')
            max_body = 20 * 1024 * 1024 if audit_upload else 16384
            if len(body) > max_body:
                return JSONResponse(status_code=413, content={'error': {'code': 'size', 'message': f'Solicitud demasiado grande (máximo {max_body // 1024 // 1024 if audit_upload else 16} {"MB" if audit_upload else "KB"}).'}})
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
                analysis.store_profile = inspect_store(html, final)
                analysis.status = 'evaluating'
                analysis.domain_registration, domain_evidence = await registration_profile(final)
                if analysis.target == 'website':
                    analysis.website_profile = extract_website(html, final)
                    analysis.risk = evaluate_website(html, url, final, analysis.website_profile)
                    analysis.risk.evidence.append(domain_evidence)
                    analysis.risk.evidence.extend(analysis.store_profile.evidence)
                    analysis.status = 'searching'
                    analysis.risk.agent_assessment, agent_note = await assess(
                        analysis.risk, None, website=analysis.website_profile,
                    )
                    if agent_note:
                        analysis.limitations.append(agent_note)
                    analysis.limitations.append('El análisis revisa HTML accesible, dominio y RDAP. No ejecuta JavaScript, no inspecciona infraestructura interna y no puede garantizar que un sitio sea legítimo o fraudulento.')
                    analysis.status = 'completed'
                    return
                analysis.product = extract(html, final)
                analysis.product.branches = resolve(analysis.product)
                analysis.risk = evaluate(html, url, final)
                analysis.risk.evidence.append(domain_evidence)
                analysis.risk.evidence.extend(analysis.store_profile.evidence)
                analysis.product.evidence = analysis.risk.evidence[:2]
                analysis.status = 'searching'
                try:
                    analysis.alternatives, notes = await alternatives(analysis.product)
                    analysis.limitations.extend(notes)
                except Exception as exc:
                    analysis.limitations.append(str(exc) if isinstance(exc, ValueError) else 'La búsqueda externa no está disponible. Reintenta el análisis.')
                compare_price(analysis.risk, analysis.product, analysis.alternatives)
                audit_consistency(analysis.risk, analysis.product, analysis.alternatives)
                analysis.risk.agent_assessment, agent_note = await assess(
                    analysis.risk, analysis.product, analysis.alternatives,
                )
                if agent_note:
                    analysis.limitations.append(agent_note)
                analysis.limitations.append('El análisis extrae HTML y JSON-LD sin ejecutar JavaScript. La identidad, las reseñas y el inventario que publique el sitio son declaraciones no verificadas de forma independiente; no garantiza seguridad.')
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
    analysis = Analysis(id=uuid4().hex, mode=payload.mode, target=payload.target)
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
        # 1. Obtenemos puntos de entrega reales (Lockers, DHL, etc.) usando el radio del slider
        real_points = await fetch_real_pickup_points(
            origin=payload.origin,
            max_radius_km=payload.max_radius_km
        )
        # 2. Si el usuario aún no ha seleccionado paradas específicas,
        # rellenamos automáticamente con los puntos reales encontrados en su radio
        if not payload.stops and real_points:
            payload.stops = [
                {
                    "id": p.id,
                    "name": p.name,
                    "lat": p.lat,
                    "lng": p.lng
                }
                for p in real_points[:5]  # Toma hasta 5 puntos reales cercanos dentro del radio
            ]
        # 3. Calcula y regresa la ruta optimizada con datos reales
        return await calculate_route(payload, max_radius_km=payload.max_radius_km)

    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/audit/run', response_model=Submission)
async def audit_run(payload: AuditRunInput):
    """Run the isolated, read-only SQLite audit and retain its case file."""
    global last_case_file
    try:
        submission = await asyncio.to_thread(run_forensic_audit, payload.estate_path, payload.seed)
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    last_case_file = render_case_file(submission, payload.estate_path)
    return submission


@app.post('/audit/preflight', response_model=AuditPreflight)
async def audit_preflight(payload: AuditRunInput):
    try:
        return await asyncio.to_thread(inspect_forensic_estate, payload.estate_path)
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/audit/upload', response_model=Submission)
async def audit_upload(payload: AuditUploadInput):
    """Audit browser-selected DB, ZIP, or official CSV tables without retention."""
    global last_case_file
    try:
        files = _decode_audit_upload(payload)
        with uploaded_estate(files) as (estate_path, _):
            submission = await asyncio.to_thread(run_forensic_audit, estate_path, payload.seed)
            last_case_file = render_case_file(submission, estate_path)
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return submission


@app.post('/audit/preflight/upload', response_model=AuditPreflight)
async def audit_preflight_upload(payload: AuditUploadInput):
    try:
        files = _decode_audit_upload(payload)
        with uploaded_estate(files) as (estate_path, source_name):
            preflight = await asyncio.to_thread(inspect_forensic_estate, estate_path)
            return preflight.model_copy(update={'estate_filename': source_name})
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/audit/demo', response_model=Submission)
async def audit_demo(payload: AuditDemoInput):
    """Run a disposable, clearly synthetic estate for the live product demo."""
    global last_case_file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db') as estate:
        await asyncio.to_thread(create_demo_estate, estate.name)
        submission = await asyncio.to_thread(run_forensic_audit, estate.name, payload.seed)
        last_case_file = render_case_file(submission, estate.name)
    return submission


@app.get('/audit/case-file', response_class=PlainTextResponse)
async def audit_case_file():
    if last_case_file is None:
        raise HTTPException(404, 'No hay un expediente generado todavía.')
    return PlainTextResponse(last_case_file, media_type='text/markdown; charset=utf-8')
