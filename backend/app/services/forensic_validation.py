"""Hard, deterministic gate between detector candidates and accusations."""
from __future__ import annotations

import math
import sqlite3
from datetime import date

from ..models import CandidateFinding, CheckResult, Finding, LeadNotPursued, ValidationReport
from .agent import forensic_narrative

ID_COLUMNS = {
    'ledger': 'entry_id',
    'invoices': 'uuid',
    'bank_txns': 'txn_id',
    'vendors': 'rfc',
    'efos_list': 'rfc',
    'purchase_orders': 'po_id',
    'contracts': 'contract_id',
    'employees': 'emp_id',
}
AMOUNT_COLUMNS = {
    'invoices': 'total',
    'bank_txns': 'amount',
    'purchase_orders': 'amount',
    'contracts': 'value',
}
PESO_TOLERANCE = 0.02


def _check(code: str, passed: bool, success: str, failure: str) -> CheckResult:
    return CheckResult(code=code, passed=passed, detail=success if passed else failure)


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def _finite_nonnegative(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _supports_entity(entity: str, rows: list[tuple[object, sqlite3.Row]]) -> bool:
    prefix, _, raw_id = entity.partition(':')
    if not raw_id:
        return False
    for exhibit, row in rows:
        table = exhibit.source_table
        if prefix == 'RFC':
            if table in {'vendors', 'efos_list'} and str(row['rfc']) == raw_id:
                return True
            if table == 'invoices' and raw_id in {str(row['issuer_rfc']), str(row['receiver_rfc'])}:
                return True
            if table in {'purchase_orders', 'contracts'} and str(row['vendor_rfc']) == raw_id:
                return True
        elif prefix == 'EMP' and table == 'employees':
            stored_id = str(row['emp_id'])
            if stored_id in {entity, raw_id}:
                return True
    return False


def _scheme_errors(candidate: CandidateFinding, rows: list[tuple[object, sqlite3.Row]]) -> list[str]:
    """Independently re-check the detector-specific accusation predicate."""
    by_table: dict[str, list[sqlite3.Row]] = {}
    for exhibit, row in rows:
        by_table.setdefault(exhibit.source_table, []).append(row)
    errors: list[str] = []
    entity_rfcs = {entity.removeprefix('RFC:') for entity in candidate.entities if entity.startswith('RFC:')}
    entity_employees = {entity.removeprefix('EMP:') for entity in candidate.entities if entity.startswith('EMP:')}

    if candidate.scheme_type == 'phantom_vendor':
        efos_rows = by_table.get('efos_list', [])
        statuses = {str(row['status'] or '').strip().lower() for row in efos_rows}
        accepted = statuses & {'definitivo', 'presunto'}
        if not accepted:
            errors.append('no existe estatus EFOS definitivo o presunto')
        efos_rfcs = {str(row['rfc']) for row in efos_rows if str(row['status'] or '').strip().lower() in accepted}
        invoice_issuers = {str(row['issuer_rfc']) for row in by_table.get('invoices', [])}
        if not (entity_rfcs & efos_rfcs & invoice_issuers):
            errors.append('el RFC acusado no enlaza simultáneamente factura y registro EFOS')
        expected = 'proven' if 'definitivo' in accepted else 'probable'
        if accepted and candidate.confidence != expected:
            errors.append(f'confidence debe ser {expected} para el estatus EFOS observado')
    elif candidate.scheme_type == 'kickback':
        vendor_accounts = {str(row['bank_clabe']).strip() for row in by_table.get('vendors', [])}
        employee_accounts = {str(row['bank_clabe']).strip() for row in by_table.get('employees', [])}
        if not ((vendor_accounts & employee_accounts) - {''}):
            errors.append('proveedor y empleado no comparten una CLABE no vacía')
        vendor_rfcs = {str(row['rfc']) for row in by_table.get('vendors', [])}
        employee_ids = {str(row['emp_id']).removeprefix('EMP:') for row in by_table.get('employees', [])}
        if not (entity_rfcs & vendor_rfcs) or not (entity_employees & employee_ids):
            errors.append('las entidades acusadas no corresponden al proveedor y empleado exhibidos')
        if candidate.confidence != 'proven':
            errors.append('una coincidencia exacta de CLABE debe publicarse como proven')
    elif candidate.scheme_type == 'round_tripping':
        bank_rows = by_table.get('bank_txns', [])
        if len(bank_rows) < 3 or not candidate.money_trail:
            errors.append('el ciclo requiere al menos tres transferencias y un money trail')
        dates = [_iso_date(row['date']) for row in bank_rows]
        amounts = [float(row['amount']) for row in bank_rows if _finite_positive(row['amount'])]
        if any(value is None for value in dates) or (dates and (max(dates) - min(dates)).days > 14):
            errors.append('las transferencias no caben en una ventana válida de 14 días')
        if amounts and (max(amounts) - min(amounts)) / max(amounts) > PESO_TOLERANCE:
            errors.append('los importes del ciclo difieren por más de 2%')
        if bank_rows and str(bank_rows[0]['from_clabe']) != str(bank_rows[-1]['to_clabe']):
            errors.append('las transferencias exhibidas no cierran el ciclo')
        if candidate.confidence != 'probable':
            errors.append('el flujo circular es una señal probable, no prueba de intención')
    elif candidate.scheme_type == 'threshold_splitting':
        invoices = by_table.get('invoices', [])
        dates = [_iso_date(row['issue_date']) for row in invoices]
        issuers = {str(row['issuer_rfc']) for row in invoices}
        if len(invoices) < 3:
            errors.append('se requieren al menos tres facturas')
        if any(not (45000 <= float(row['total']) < 50000) for row in invoices if _finite_positive(row['total'])):
            errors.append('hay facturas fuera de la banda de 45,000 a menos de 50,000')
        if any(value is None for value in dates) or (dates and (max(dates) - min(dates)).days > 14):
            errors.append('las facturas no forman una ventana temporal válida de 14 días')
        if len(issuers) != 1:
            errors.append('las facturas no pertenecen a un único emisor')
        if not (entity_rfcs & issuers):
            errors.append('el RFC acusado no es el emisor de las facturas exhibidas')
        if candidate.confidence != 'probable':
            errors.append('el fraccionamiento por umbral debe publicarse como probable')
    elif candidate.scheme_type == 'revenue_inflation':
        invoices = by_table.get('invoices', [])
        ledger = by_table.get('ledger', [])
        revenue = [row for row in ledger if (
            str(row['account_code'] or '').startswith('4') or
            any(token in (str(row['account_name'] or '') + ' ' + str(row['description'] or '')).lower()
                for token in ('ingreso', 'revenue', 'venta'))
        )]
        net_revenue = sum(float(row['credit'] or 0) - float(row['debit'] or 0) for row in revenue)
        if not invoices or any(str(row['status'] or '').lower() != 'cancelado' for row in invoices):
            errors.append('no hay una factura cancelada respaldando el caso')
        invoice_issuers = {str(row['issuer_rfc']) for row in invoices}
        if not (entity_rfcs & invoice_issuers):
            errors.append('el RFC acusado no es el emisor de la factura cancelada')
        if net_revenue <= 0:
            errors.append('el ingreso citado fue revertido completamente o no es positivo')
        if candidate.confidence != 'proven':
            errors.append('el registro contable no revertido debe publicarse como proven')
    else:
        errors.append('scheme_type no reconocido por el hard validator')
    return errors


def validate_candidate(conn: sqlite3.Connection, candidate: CandidateFinding) -> ValidationReport:
    """Validate facts against the open read-only estate connection."""
    checks: list[CheckResult] = []
    exhibit_ids = [exhibit.exhibit_id for exhibit in candidate.exhibits]
    evidence_keys = [(exhibit.source_table, exhibit.record_id) for exhibit in candidate.exhibits]

    checks.append(_check(
        'minimum_exhibits', len(candidate.exhibits) >= 3,
        f'{len(candidate.exhibits)} exhibits disponibles.',
        f'Solo hay {len(candidate.exhibits)} exhibits; se requieren al menos 3.',
    ))
    checks.append(_check(
        'unique_exhibit_ids', len(exhibit_ids) == len(set(exhibit_ids)),
        'Los exhibit_id son únicos.', 'Hay exhibit_id duplicados.',
    ))
    checks.append(_check(
        'unique_evidence_records', len(evidence_keys) == len(set(evidence_keys)),
        'Cada registro se usa una sola vez como evidencia.',
        'Un mismo registro se reutiliza como corroboración independiente.',
    ))

    resolved: list[tuple[object, sqlite3.Row]] = []
    missing: list[str] = []
    for exhibit in candidate.exhibits:
        id_column = ID_COLUMNS[exhibit.source_table]
        row = conn.execute(
            f'SELECT * FROM {exhibit.source_table} WHERE {id_column}=?',
            (exhibit.record_id,),
        ).fetchone()
        if row is None:
            missing.append(f'{exhibit.source_table}:{exhibit.record_id}')
        else:
            resolved.append((exhibit, row))
    checks.append(_check(
        'record_ids_exist', not missing,
        'Todos los record_id existen en el estate.',
        f'No existen estos registros: {", ".join(missing)}.',
    ))

    unsupported = [entity for entity in candidate.entities if not _supports_entity(entity, resolved)]
    checks.append(_check(
        'entity_support', bool(candidate.entities) and not unsupported,
        'Cada entidad está respaldada por al menos un exhibit.',
        f'Entidades sin soporte directo: {", ".join(unsupported) or "lista vacía"}.',
    ))
    rule = candidate.rule_broken.strip().lower()
    specific_rule = bool(rule) and any(token in rule for token in ('art.', 'nif', 'política'))
    checks.append(_check(
        'specific_rule', specific_rule,
        'La regla citada identifica una norma o política específica.',
        'La regla citada es vacía o demasiado genérica.',
    ))

    claimed_valid = _finite_positive(candidate.peso_amount)
    checks.append(_check(
        'positive_finite_claim', claimed_valid,
        'peso_amount es finito y positivo.', 'peso_amount no es finito y positivo.',
    ))
    per_table: dict[str, float] = {}
    invalid_amounts: list[str] = []
    for exhibit, row in resolved:
        amount_column = AMOUNT_COLUMNS.get(exhibit.source_table)
        if exhibit.source_table == 'ledger':
            debit, credit = row['debit'], row['credit']
            if (
                not _finite_nonnegative(debit) or not _finite_nonnegative(credit)
                or (float(debit) == 0 and float(credit) == 0)
            ):
                invalid_amounts.append(f'ledger:{exhibit.record_id}')
            continue
        if not amount_column:
            continue
        amount = row[amount_column]
        if not _finite_positive(amount):
            invalid_amounts.append(f'{exhibit.source_table}:{exhibit.record_id}')
            continue
        per_table[exhibit.source_table] = per_table.get(exhibit.source_table, 0.0) + float(amount)
    checks.append(_check(
        'positive_finite_evidence_amounts', not invalid_amounts,
        'Los importes citados son finitos y positivos.',
        f'Importes inválidos en: {", ".join(invalid_amounts)}.',
    ))
    reconciles = False
    if claimed_valid and per_table:
        claimed = float(candidate.peso_amount)
        reconciles = any(
            abs(claimed - table_total) <= PESO_TOLERANCE * max(abs(table_total), 1.0)
            for table_total in per_table.values()
        )
    totals = ', '.join(f'{table}={amount:.2f}' for table, amount in sorted(per_table.items()))
    checks.append(_check(
        'peso_reconciliation', reconciles,
        f'peso_amount reconcilia por tabla dentro de 2% ({totals}).',
        f'peso_amount no reconcilia por tabla dentro de 2% ({totals or "sin tabla monetaria"}).',
    ))

    exhibits_by_id = {exhibit.exhibit_id: (exhibit, row) for exhibit, row in resolved}
    trail_errors: list[str] = []
    prior_date: date | None = None
    for index, step in enumerate(candidate.money_trail):
        resolved_exhibit = exhibits_by_id.get(step.exhibit_id)
        if resolved_exhibit is None:
            trail_errors.append(f'paso {index + 1} cita un exhibit inexistente')
            continue
        exhibit, row = resolved_exhibit
        if exhibit.source_table != 'bank_txns':
            trail_errors.append(f'paso {index + 1} no cita bank_txns')
            continue
        step_date = _iso_date(step.date)
        row_date = _iso_date(row['date'])
        if step_date is None or row_date is None or step_date != row_date:
            trail_errors.append(f'paso {index + 1} tiene fecha inválida o distinta al exhibit')
        if prior_date is not None and (step_date is None or step_date < prior_date):
            trail_errors.append(f'paso {index + 1} rompe el orden cronológico')
        if step_date is not None:
            prior_date = step_date
        if index and candidate.money_trail[index - 1].to != step.from_:
            trail_errors.append(f'paso {index + 1} no conecta con el anterior')
        if str(row['from_clabe']) != step.from_ or str(row['to_clabe']) != step.to:
            trail_errors.append(f'paso {index + 1} no coincide con las cuentas del exhibit')
        if not _finite_positive(step.amount) or not _finite_positive(row['amount']):
            trail_errors.append(f'paso {index + 1} tiene importe no positivo o no finito')
        elif abs(float(step.amount) - float(row['amount'])) > 0.01:
            trail_errors.append(f'paso {index + 1} no coincide con el importe del exhibit')
    checks.append(_check(
        'money_trail_integrity', not trail_errors,
        'El money trail está referenciado, conectado y en orden cronológico.',
        '; '.join(trail_errors),
    ))

    scheme_errors = _scheme_errors(candidate, resolved) if not missing else ['faltan registros para validar el esquema']
    checks.append(_check(
        'scheme_invariants', not scheme_errors,
        'La evidencia satisface de forma independiente la regla y confianza del esquema.',
        '; '.join(scheme_errors),
    ))

    passed = all(check.passed for check in checks)
    return ValidationReport(
        candidate_id=candidate.candidate_id,
        passed=passed,
        checks=checks,
        action='publish' if passed else 'close_as_lead',
    )


def publish_candidate(candidate: CandidateFinding, report: ValidationReport) -> Finding:
    """Create the public contract only after a successful hard validation."""
    if not report.passed or report.candidate_id != candidate.candidate_id:
        raise ValueError('No se puede publicar un candidato que no pasó la validación determinista.')
    narrative = forensic_narrative(
        candidate.scheme_type,
        candidate.entities,
        candidate.rule_broken,
        candidate.peso_amount,
        candidate.exhibits,
    )
    return Finding(
        scheme_type=candidate.scheme_type,
        entities=candidate.entities,
        narrative=narrative,
        rule_broken=candidate.rule_broken,
        peso_amount=candidate.peso_amount,
        confidence=candidate.confidence,
        exhibits=candidate.exhibits,
        money_trail=candidate.money_trail,
    )


def rejected_candidate_lead(candidate: CandidateFinding, report: ValidationReport) -> LeadNotPursued:
    failures = [check for check in report.checks if not check.passed]
    return LeadNotPursued(
        entity=', '.join(candidate.entities) or f'CANDIDATE:{candidate.candidate_id}',
        signal=candidate.scheme_type,
        reason='Validación determinista rechazó el candidato: ' + ' '.join(check.detail for check in failures),
        tool_calls_made=[f'deterministic:{check.code}' for check in report.checks],
        closed_by='validator',
    )
