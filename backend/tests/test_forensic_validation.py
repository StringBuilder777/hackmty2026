import sqlite3

import pytest

from app.models import CandidateFinding, Exhibit
from app.services.forensic import create_demo_estate, inspect_forensic_estate, render_case_file, run_forensic_audit
from app.services.forensic_validation import publish_candidate, rejected_candidate_lead, validate_candidate


def _candidate(claimed: float, *, entity: str = 'RFC:SPLIT010101BBB') -> CandidateFinding:
    return CandidateFinding(
        candidate_id='CAND-TEST',
        scheme_type='threshold_splitting',
        entities=[entity],
        rule_broken='Política interna de compras v1: umbral de autorización.',
        peso_amount=claimed,
        confidence='probable',
        exhibits=[
            Exhibit(exhibit_id=f'EX-{index}', source_table='invoices', record_id=f'SPLIT-00{index}', note='Factura bajo el umbral.')
            for index in range(1, 4)
        ],
    )


def _read_only(path):
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_hard_validator_enforces_the_two_percent_reconciliation_boundary(tmp_path):
    path = tmp_path / 'estate.db'
    create_demo_estate(str(path))
    invoice_total = 3 * 48_720
    with _read_only(path) as conn:
        passing = validate_candidate(conn, _candidate(invoice_total * 1.0199))
        failing = validate_candidate(conn, _candidate(invoice_total * 1.0201))

    assert passing.passed is True
    assert passing.action == 'publish'
    assert failing.passed is False
    assert failing.action == 'close_as_lead'
    assert 'peso_reconciliation' in {check.code for check in failing.checks if not check.passed}
    with pytest.raises(ValueError, match='No se puede publicar'):
        publish_candidate(_candidate(invoice_total * 1.0201), failing)
    assert rejected_candidate_lead(_candidate(invoice_total * 1.0201), failing).closed_by == 'validator'


def test_hard_validator_rejects_an_entity_without_direct_exhibit_support(tmp_path):
    path = tmp_path / 'estate.db'
    create_demo_estate(str(path))
    with _read_only(path) as conn:
        report = validate_candidate(conn, _candidate(3 * 48_720, entity='RFC:UNSUPPORTED'))

    assert report.passed is False
    entity_check = next(check for check in report.checks if check.code == 'entity_support')
    assert entity_check.passed is False
    assert 'RFC:UNSUPPORTED' in entity_check.detail


def test_complete_reversal_closes_revenue_case_and_partial_reversal_is_exhibited(tmp_path):
    complete_path = tmp_path / 'complete.db'
    create_demo_estate(str(complete_path))
    conn = sqlite3.connect(complete_path)
    conn.execute("INSERT INTO ledger VALUES (3,'2026-02-01','4000','Ingresos',116000,0,'Reversa total','REV-001','CC-01','Ana Ejemplo')")
    conn.commit()
    conn.close()
    complete = run_forensic_audit(str(complete_path), 2026)
    assert 'revenue_inflation' not in {finding.scheme_type for finding in complete.findings}
    assert any(lead.signal == 'revenue_inflation' for lead in complete.leads_not_pursued)

    partial_path = tmp_path / 'partial.db'
    create_demo_estate(str(partial_path))
    conn = sqlite3.connect(partial_path)
    conn.execute("INSERT INTO ledger VALUES (3,'2026-02-01','4000','Ingresos',40000,0,'Reversa parcial','REV-001','CC-01','Ana Ejemplo')")
    conn.commit()
    conn.close()
    partial = run_forensic_audit(str(partial_path), 2026)
    finding = next(item for item in partial.findings if item.scheme_type == 'revenue_inflation')
    assert finding.peso_amount == 116_000
    assert any(exhibit.record_id == '3' and 'saldo de ingreso de $76,000.00' in exhibit.note for exhibit in finding.exhibits)


def test_round_tripping_exhibits_the_rfc_to_clabe_relationship(tmp_path):
    path = tmp_path / 'estate.db'
    create_demo_estate(str(path))
    finding = next(
        item for item in run_forensic_audit(str(path), 2026).findings
        if item.scheme_type == 'round_tripping'
    )
    vendor_records = {
        exhibit.record_id for exhibit in finding.exhibits if exhibit.source_table == 'vendors'
    }
    assert vendor_records == {'VENDORA0101', 'VENDORB0101'}
    assert all(any(entity.removeprefix('RFC:') == record for record in vendor_records) for entity in finding.entities)


def test_case_file_has_one_diagram_per_finding_and_deduplicated_exposure(tmp_path):
    path = tmp_path / 'estate.db'
    create_demo_estate(str(path))
    submission = run_forensic_audit(str(path), 2026)

    case_file = render_case_file(submission, str(path))

    assert case_file.count('```mermaid') == len(submission.findings)
    assert 'Empresa auditada: COMPANY010101AAA.' in case_file
    assert '| Total exposure | $678,160.00 MXN |' in case_file


def test_preflight_reports_empty_tables_invalid_dates_and_orphans(tmp_path):
    path = tmp_path / 'estate.db'
    create_demo_estate(str(path))
    conn = sqlite3.connect(path)
    conn.execute("UPDATE bank_txns SET date='not-a-date' WHERE txn_id='CYCLE-001'")
    conn.execute("INSERT INTO ledger VALUES (99,'bad-date','4000','Ingresos',0,1,'Huérfano','MISSING','CC','Ana')")
    conn.commit()
    conn.close()

    preflight = inspect_forensic_estate(str(path))
    warnings = '\n'.join(preflight.quality_warnings)

    assert 'purchase_orders: tabla vacía' in warnings
    assert 'bank_txns.date: 1 fecha(s) inválida(s)' in warnings
    assert 'ledger.date: 1 fecha(s) inválida(s)' in warnings
    assert 'ledger: 1 asiento(s) con invoice_uuid huérfano' in warnings
