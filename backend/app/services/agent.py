"""Optional Gemini explanation over bounded, already-verified evidence."""
import asyncio
import json
import os
import socket

import aiohttp

from ..models import AgentAssessment, Product, Risk
from .http import bounded_json

GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/models/'
ALLOWED_MODELS = {'gemini-2.5-flash', 'gemini-2.5-flash-lite'}


def _payload(risk: Risk, product: Product, alternatives: list[Product] | None = None) -> dict:
    alternatives = alternatives or []
    return {
        'contents': [{'parts': [{'text': json.dumps({
            'task': (
                'Explica la gravedad de riesgo usando exclusivamente las señales recibidas, resume las opciones '
                'encontradas y señala explícitamente sus inconsistencias de modelo, capacidad, condición, disponibilidad '
                'o precio cuando estén presentes. Las opciones son resultados comparativos, no pruebas de confianza. '
                'No inventes hechos, no declares una tienda segura y menciona incertidumbre cuando aplique. '
                'La explicación debe ser clara y no superar 700 caracteres.'
            ),
            'product': {
                'name': product.name[:200], 'store': product.store[:120], 'brand': product.brand,
                'model': product.model, 'variant': product.variant, 'condition': product.condition,
                'gtin': product.gtin, 'price': product.price, 'currency': product.currency,
                'availability': product.availability[:160],
            },
            'heuristic_level': risk.level,
            'evidence': [
                {'title': item.title[:120], 'status': item.status, 'detail': item.detail[:500]}
                for item in risk.evidence[:12]
            ],
            'alternatives': [
                {
                    'store': item.store[:120], 'name': item.name[:200], 'price': item.price,
                    'currency': item.currency, 'match': item.match, 'match_reason': item.match_reason[:300],
                    'condition': item.condition, 'gtin': item.gtin, 'availability': item.availability[:160],
                }
                for item in alternatives[:5]
            ],
        }, ensure_ascii=False)}]}],
        'generationConfig': {
            # Gemini 2.5 Flash otherwise uses dynamic thinking, which adds latency
            # without improving this bounded explanation task.
            'thinkingConfig': {'thinkingBudget': 0},
            'maxOutputTokens': 1200,
            'responseMimeType': 'application/json',
            'responseJsonSchema': {
                'type': 'object',
                'properties': {
                    'level': {'type': 'string', 'enum': ['bajo', 'medio', 'alto', 'información insuficiente']},
                    'explanation': {'type': 'string'},
                    'limitations': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 4},
                },
                'required': ['level', 'explanation'],
            },
        },
    }


def _parse(response: dict) -> AgentAssessment:
    try:
        text = response['candidates'][0]['content']['parts'][0]['text']
        return AgentAssessment.model_validate(json.loads(text))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('La respuesta del agente no respetó el contrato.') from exc


async def assess(
    risk: Risk, product: Product, alternatives: list[Product] | None = None,
) -> tuple[AgentAssessment | None, str | None]:
    """Use Gemini only when explicitly configured; failures never block analysis."""
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        return None, 'La explicación por IA no está configurada (falta GEMINI_API_KEY).'
    model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    if model not in ALLOWED_MODELS:
        return None, 'La explicación por IA no está disponible: GEMINI_MODEL no está permitido.'
    url = f'{GEMINI_BASE_URL}{model}:generateContent'
    try:
        # The provider host is a fixed constant, not user input. The standard
        # resolver is more reliable here and IPv4 avoids slow unreachable IPv6 paths.
        connector = aiohttp.TCPConnector(limit=1, family=socket.AF_INET)
        timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=25)
        async with asyncio.timeout(31), aiohttp.ClientSession(
            connector=connector, timeout=timeout, trust_env=False,
            headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
        ) as session:
            async with session.post(url, json=_payload(risk, product, alternatives)) as response:
                if response.status != 200:
                    raise ValueError(f'Gemini respondió HTTP {response.status}.')
                return _parse(await bounded_json(response, limit=128_000)), None
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return None, 'La explicación por IA no estuvo disponible para este análisis; conserva las señales verificadas.'
