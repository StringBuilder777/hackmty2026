"""Adversarial contract tests for the deterministic forensic auditor.

These cases intentionally exercise judge-facing boundaries instead of the
benchmark generator.  The estates contain only the records needed by each
case, so a failure points to a detector or hard-validator invariant rather
than to a planted answer key.
"""
from __future__ import annotations

from datetime import date, timedelta
import sqlite3
from pathlib import Path

import pytest

from app.models import CandidateFinding, Exhibit
from app.services.forensic import create_demo_estate, render_case_file, run_forensic_audit
from app.services.forensic_validation import validate_candidate


SCHEMA = """
CREATE TABLE vendors (rfc TEXT PRIMARY KEY, legal_name TEXT, registered_date TEXT, address TEXT, bank_clabe TEXT, category TEXT, contact_email TEXT);
CREATE TABLE invoices (uuid TEXT PRIMARY KEY, issuer_rfc TEXT, receiver_rfc TEXT, issue_date TEXT, subtotal REAL, iva REAL, total REAL, concepto_text TEXT, uso_cfdi TEXT, forma_pago TEXT, metodo_pago TEXT, status TEXT);
CREATE TABLE ledger (entry_id INTEGER PRIMARY KEY, date TEXT, account_code TEXT, account_name TEXT, debit REAL, credit REAL, description TEXT, invoice_uuid TEXT, cost_center TEXT, approver TEXT);
CREATE TABLE bank_txns (txn_id TEXT PRIMARY KEY, date TEXT, from_clabe TEXT, to_clabe TEXT, amount REAL, reference TEXT, channel TEXT);
CREATE TABLE purchase_orders (po_id TEXT PRIMARY KEY, vendor_rfc TEXT, date TEXT, amount REAL, requester TEXT, approver TEXT, description TEXT);
CREATE TABLE contracts (contract_id TEXT PRIMARY KEY, vendor_rfc TEXT, start_date TEXT, value REAL, scope_text TEXT);
CREATE TABLE employees (emp_id TEXT PRIMARY KEY, name TEXT, role TEXT, bank_clabe TEXT, hire_date TEXT);
CREATE TABLE efos_list (rfc TEXT PRIMARY KEY, legal_name TEXT, status TEXT, publication_date TEXT);
"""


def _empty_estate(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _scheme(submission, scheme_type: str):
    return [finding for finding in submission.findings if finding.scheme_type == scheme_type]


def _revenue_estate(path: Path, reversal: float) -> None:
    conn = _empty_estate(path)
    conn.execute(
        "INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "REV-001", "COMPANY010101AAA", "CUSTOMER010101AAA", "2026-01-31",
            100.0, 16.0, 116.0, "Venta cancelada", "G03", "03", "PUE", "cancelado",
        ),
    )
    conn.executemany(
        "INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "2026-01-31", "4000", "Ingresos", 0.0, 116.0, "Ingreso registrado", "REV-001", "CC-01", "Ana"),
            (2, "2026-01-31", "1100", "Clientes", 116.0, 0.0, "Cuenta por cobrar", "REV-001", "CC-01", "Ana"),
            (3, "2026-02-01", "4000", "Ingresos", reversal, 0.0, "Reversa de ingreso", "REV-001", "CC-01", "Ana"),
        ],
    )
    conn.commit()
    conn.close()


def _round_trip_estate(path: Path, *, span_days: int, last_amount: float) -> None:
    conn = _empty_estate(path)
    conn.executemany(
        "INSERT INTO vendors VALUES (?,?,?,?,?,?,?)",
        [
            ("VENDORA0101AAA", "Proveedor A", "2020-01-01", "A", "CLABE-A", "Servicios", "a@example.mx"),
            ("VENDORB0101BBB", "Proveedor B", "2020-01-01", "B", "CLABE-B", "Servicios", "b@example.mx"),
        ],
    )
    # The receiver identifies the audited company; this invoice is otherwise
    # ordinary and must not trigger any of the five detectors.
    conn.execute(
        "INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "ANCHOR-001", "VENDORA0101AAA", "COMPANY010101AAA", "2025-12-01",
            1000.0, 160.0, 1160.0, "Servicio ordinario", "G03", "03", "PUE", "vigente",
        ),
    )
    start = date(2026, 1, 1)
    conn.executemany(
        "INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)",
        [
            ("RT-001", start.isoformat(), "COMPANY-CLABE", "CLABE-A", 100.0, "Salida", "SPEI"),
            ("RT-002", (start + timedelta(days=7)).isoformat(), "CLABE-A", "CLABE-B", 100.0, "Intermediario", "SPEI"),
            ("RT-003", (start + timedelta(days=span_days)).isoformat(), "CLABE-B", "COMPANY-CLABE", last_amount, "Retorno", "SPEI"),
        ],
    )
    conn.commit()
    conn.close()


def _validator_estate(path: Path) -> sqlite3.Connection:
    conn = _empty_estate(path)
    conn.execute(
        "INSERT INTO vendors VALUES ('EFOS010101AAA','EFOS SA','2020-01-01','A','CLABE-EFOS','Servicios','e@example.mx')"
    )
    conn.execute(
        "INSERT INTO efos_list VALUES ('EFOS010101AAA','EFOS SA','definitivo','2025-01-01')"
    )
    conn.execute(
        "INSERT INTO invoices VALUES ('INV-001','EFOS010101AAA','COMPANY010101AAA','2026-01-01',86.21,13.79,100.0,'Servicio','G03','03','PUE','vigente')"
    )
    conn.commit()
    return conn


def _reconciliation_candidate(amount: float) -> CandidateFinding:
    return CandidateFinding(
        candidate_id=f"CANDIDATE-{amount}",
        scheme_type="phantom_vendor",
        entities=["RFC:EFOS010101AAA"],
        rule_broken="CFF Art. 69-B",
        peso_amount=amount,
        confidence="proven",
        exhibits=[
            Exhibit(exhibit_id="EX-001", source_table="invoices", record_id="INV-001", note="Factura revisada."),
            Exhibit(exhibit_id="EX-002", source_table="vendors", record_id="EFOS010101AAA", note="Proveedor identificado."),
            Exhibit(exhibit_id="EX-003", source_table="efos_list", record_id="EFOS010101AAA", note="Estatus definitivo."),
        ],
        detector_facts=["El total de invoices citado es 100.00."],
    )


def test_full_revenue_reversal_is_closed_without_an_accusation(tmp_path: Path) -> None:
    path = tmp_path / "full-reversal.db"
    _revenue_estate(path, reversal=116.0)

    submission = run_forensic_audit(str(path), seed=8101)

    assert not _scheme(submission, "revenue_inflation")
    lead = next(lead for lead in submission.leads_not_pursued if lead.signal == "revenue_inflation")
    assert lead.entity == "RFC:COMPANY010101AAA"
    assert "REV-001" in lead.reason
    assert "revers" in lead.reason.lower()


def test_partial_revenue_reversal_is_explicitly_cited_and_not_treated_as_absent(tmp_path: Path) -> None:
    path = tmp_path / "partial-reversal.db"
    _revenue_estate(path, reversal=100.0)

    submission = run_forensic_audit(str(path), seed=8102)
    findings = _scheme(submission, "revenue_inflation")

    # The official validator can reconcile only the cancelled invoice total,
    # not a ledger-only residual.  The finding therefore keeps the 116.00 CFDI
    # exposure, but it must cite and explain the debit that leaves 16.00 net.
    assert len(findings) == 1
    assert findings[0].peso_amount == pytest.approx(116.0)
    reversal = next(
        exhibit
        for exhibit in findings[0].exhibits
        if exhibit.source_table == "ledger" and exhibit.record_id == "3"
    )
    assert "revers" in reversal.note.lower()
    assert "16" in reversal.note


@pytest.mark.parametrize(("span_days", "expected"), [(14, True), (15, False)])
def test_round_trip_date_boundary_is_inclusive_only_through_day_14(
    tmp_path: Path, span_days: int, expected: bool
) -> None:
    path = tmp_path / f"round-trip-{span_days}-days.db"
    _round_trip_estate(path, span_days=span_days, last_amount=100.0)

    submission = run_forensic_audit(str(path), seed=8200 + span_days)

    assert bool(_scheme(submission, "round_tripping")) is expected


@pytest.mark.parametrize(("last_amount", "expected"), [(98.01, True), (97.99, False)])
def test_round_trip_amount_boundary_accepts_1_99_percent_and_rejects_2_01_percent(
    tmp_path: Path, last_amount: float, expected: bool
) -> None:
    path = tmp_path / f"round-trip-{last_amount}.db"
    _round_trip_estate(path, span_days=14, last_amount=last_amount)

    submission = run_forensic_audit(str(path), seed=8300)

    assert bool(_scheme(submission, "round_tripping")) is expected


@pytest.mark.parametrize(("claimed", "expected"), [(101.99, True), (102.01, False)])
def test_hard_validator_reconciliation_boundary_is_two_percent(
    tmp_path: Path, claimed: float, expected: bool
) -> None:
    path = tmp_path / f"reconciliation-{claimed}.db"
    conn = _validator_estate(path)

    report = validate_candidate(conn, _reconciliation_candidate(claimed))
    conn.close()

    reconciliation = next(check for check in report.checks if check.code == "peso_reconciliation")
    assert reconciliation.passed is expected
    assert report.passed is expected
    assert report.action == ("publish" if expected else "close_as_lead")


def test_every_published_entity_has_a_resolvable_exhibit(tmp_path: Path) -> None:
    path = tmp_path / "entity-evidence.db"
    create_demo_estate(str(path))

    submission = run_forensic_audit(str(path), seed=8401)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        for finding in submission.findings:
            candidate = CandidateFinding(
                candidate_id=f"REDTEAM-{finding.scheme_type}",
                scheme_type=finding.scheme_type,
                entities=finding.entities,
                rule_broken=finding.rule_broken,
                peso_amount=finding.peso_amount,
                confidence=finding.confidence,
                exhibits=finding.exhibits,
                money_trail=finding.money_trail,
            )
            report = validate_candidate(conn, candidate)
            entity_support = next(check for check in report.checks if check.code == "entity_support")
            assert entity_support.passed, f"{finding.scheme_type}: {entity_support.detail}"
    finally:
        conn.close()


def test_empty_estate_legitimately_produces_no_findings(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    conn = _empty_estate(path)
    conn.commit()
    conn.close()

    submission = run_forensic_audit(str(path), seed=8501)

    assert submission.findings == []
    assert submission.leads_not_pursued == []
    assert submission.run_metadata.llm_calls == 0
    assert submission.run_metadata.mxn_cost == 0


def _mixed_estate(path: Path, *, reverse_rows: bool) -> None:
    conn = _empty_estate(path)
    tables_and_rows = [
        (
            "vendors",
            [
                ("EFOS010101AAA", "EFOS SA", "2020-01-01", "A", "CLABE-E", "Servicios", "e@example.mx"),
                ("SPLIT010101BBB", "Split SA", "2020-01-01", "B", "CLABE-S", "Servicios", "s@example.mx"),
                ("VENDORA0101AAA", "Proveedor A", "2020-01-01", "C", "CLABE-A", "Servicios", "a@example.mx"),
                ("VENDORB0101BBB", "Proveedor B", "2020-01-01", "D", "CLABE-B", "Servicios", "b@example.mx"),
            ],
            "INSERT INTO vendors VALUES (?,?,?,?,?,?,?)",
        ),
        (
            "employees",
            [("EMP:0001", "Ana", "Compras", "CLABE-E", "2020-01-01")],
            "INSERT INTO employees VALUES (?,?,?,?,?)",
        ),
        (
            "efos_list",
            [("EFOS010101AAA", "EFOS SA", "definitivo", "2025-01-01")],
            "INSERT INTO efos_list VALUES (?,?,?,?)",
        ),
        (
            "invoices",
            [
                ("EF-001", "EFOS010101AAA", "COMPANY010101AAA", "2026-01-01", 100.0, 16.0, 116.0, "Servicio", "G03", "03", "PUE", "vigente"),
                ("SP-001", "SPLIT010101BBB", "COMPANY010101AAA", "2026-01-02", 42000.0, 6720.0, 48720.0, "Servicio", "G03", "03", "PUE", "vigente"),
                ("SP-002", "SPLIT010101BBB", "COMPANY010101AAA", "2026-01-03", 42000.0, 6720.0, 48720.0, "Servicio", "G03", "03", "PUE", "vigente"),
                ("SP-003", "SPLIT010101BBB", "COMPANY010101AAA", "2026-01-04", 42000.0, 6720.0, 48720.0, "Servicio", "G03", "03", "PUE", "vigente"),
                ("REV-001", "COMPANY010101AAA", "CUSTOMER010101AAA", "2026-01-31", 100.0, 16.0, 116.0, "Venta", "G03", "03", "PUE", "cancelado"),
            ],
            "INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ),
        (
            "ledger",
            [
                (1, "2026-01-31", "4000", "Ingresos", 0.0, 116.0, "Ingreso", "REV-001", "CC", "Ana"),
                (2, "2026-01-31", "1100", "Clientes", 116.0, 0.0, "Cliente", "REV-001", "CC", "Ana"),
            ],
            "INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?)",
        ),
        (
            "bank_txns",
            [
                ("RT-001", "2026-01-01", "COMPANY-CLABE", "CLABE-A", 100.0, "Salida", "SPEI"),
                ("RT-002", "2026-01-02", "CLABE-A", "CLABE-B", 100.0, "Paso", "SPEI"),
                ("RT-003", "2026-01-03", "CLABE-B", "COMPANY-CLABE", 100.0, "Retorno", "SPEI"),
            ],
            "INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)",
        ),
    ]
    for _, rows, sql in tables_and_rows:
        ordered = list(reversed(rows)) if reverse_rows else rows
        conn.executemany(sql, ordered)
    conn.commit()
    conn.close()


def test_physical_row_order_does_not_change_semantic_output(tmp_path: Path) -> None:
    ordered_path = tmp_path / "ordered.db"
    reversed_path = tmp_path / "reversed.db"
    _mixed_estate(ordered_path, reverse_rows=False)
    _mixed_estate(reversed_path, reverse_rows=True)

    ordered = run_forensic_audit(str(ordered_path), seed=8601)
    reversed_submission = run_forensic_audit(str(reversed_path), seed=8601)

    assert ordered.model_dump(exclude={"run_metadata"}) == reversed_submission.model_dump(exclude={"run_metadata"})


def test_same_seed_reproduces_the_exact_case_file(tmp_path: Path) -> None:
    path = tmp_path / "deterministic.db"
    _mixed_estate(path, reverse_rows=False)

    rendered = [render_case_file(run_forensic_audit(str(path), seed=8701), str(path)) for _ in range(3)]

    assert rendered[0] == rendered[1] == rendered[2]
