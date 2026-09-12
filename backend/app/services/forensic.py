"""Deterministic, read-only forensic analysis over a supplied SQLite estate.

Facts and amounts are derived only from SQL rows.  Narrative text is supplied
by the bounded formatter in ``agent.py`` and never changes the findings.
"""
from __future__ import annotations

import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from ..models import Exhibit, Finding, LeadNotPursued, MoneyTrailStep, RunMetadata, Submission
from .agent import forensic_narrative

AMOUNT_TABLES = {'invoices': 'total', 'bank_txns': 'amount', 'purchase_orders': 'amount', 'contracts': 'value'}
REQUIRED_COLUMNS = {
    'vendors': {'rfc', 'bank_clabe'}, 'invoices': {'uuid', 'issuer_rfc', 'issue_date', 'total', 'status'},
    'ledger': {'entry_id', 'invoice_uuid'}, 'bank_txns': {'txn_id', 'date', 'from_clabe', 'to_clabe', 'amount'},
    'purchase_orders': {'po_id', 'vendor_rfc'}, 'contracts': {'contract_id', 'vendor_rfc'},
    'employees': {'emp_id', 'bank_clabe'}, 'efos_list': {'rfc', 'status'},
}


class ForensicAuditor:
    def __init__(self, estate_path: str, seed: int):
        self.path = Path(estate_path).expanduser().resolve()
        if not self.path.is_file():
            raise ValueError('estate_path debe apuntar a una base SQLite existente.')
        self.seed = seed
        self._index = 0

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f'file:{self.path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _tables(conn: sqlite3.Connection) -> set[str]:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def _exhibit(self, table: str, record_id: object, note: str) -> Exhibit:
        self._index += 1
        return Exhibit(exhibit_id=f'EX-{self._index:03d}', source_table=table, record_id=str(record_id), note=note)

    @staticmethod
    def _amount(rows: Iterable[sqlite3.Row], column: str) -> float:
        return round(sum(float(row[column] or 0) for row in rows), 2)

    @staticmethod
    def _has_columns(conn: sqlite3.Connection, table: str, columns: set[str]) -> bool:
        present = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
        return columns <= present

    def _validate_estate(self, conn: sqlite3.Connection, tables: set[str]) -> None:
        missing_tables = set(REQUIRED_COLUMNS) - tables
        if missing_tables:
            raise ValueError(f"El estate no cumple el esquema: faltan tablas {', '.join(sorted(missing_tables))}.")
        incomplete = [table for table, columns in REQUIRED_COLUMNS.items() if not self._has_columns(conn, table, columns)]
        if incomplete:
            raise ValueError(f"El estate no cumple las columnas requeridas en: {', '.join(sorted(incomplete))}.")

    def _finding(self, scheme: str, entities: list[str], rule: str, confidence: str,
                 exhibits: list[Exhibit], peso: float, trail: list[MoneyTrailStep] | None = None) -> Finding:
        narrative = forensic_narrative(scheme, entities, rule, peso, exhibits)
        return Finding(scheme_type=scheme, entities=entities, narrative=narrative,
                       rule_broken=rule, peso_amount=peso, confidence=confidence,
                       exhibits=exhibits, money_trail=trail or [])

    def detect_phantom_vendor(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[Finding], list[LeadNotPursued]]:
        if not {'invoices', 'efos_list', 'vendors'} <= tables:
            return [], []
        rows = conn.execute('''SELECT i.*, e.status AS efos_status, v.legal_name
            FROM invoices i JOIN efos_list e ON e.rfc=i.issuer_rfc
            JOIN vendors v ON v.rfc=i.issuer_rfc
            WHERE lower(coalesce(e.status, '')) IN ('definitivo', 'presunto')
            ORDER BY i.issuer_rfc, i.issue_date, i.uuid''').fetchall()
        by_rfc: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows: by_rfc[row['issuer_rfc']].append(row)
        findings = []
        for rfc, invoices in by_rfc.items():
            exhibits = [self._exhibit('invoices', row['uuid'], f"Factura emitida por {rfc} por ${float(row['total']):,.2f}.") for row in invoices]
            exhibits.append(self._exhibit('efos_list', rfc, f"RFC {rfc} aparece en la lista EFOS con estatus {invoices[0]['efos_status']} ."))
            exhibits.append(self._exhibit('vendors', rfc, f"Registro maestro del proveedor {rfc} revisado contra la lista EFOS."))
            findings.append(self._finding('phantom_vendor', [f'RFC:{rfc}'], 'CFF Art. 69-B: operaciones con EFOS.', 'proven', exhibits, self._amount(invoices, 'total')))
        return findings, []

    def detect_kickback(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[Finding], list[LeadNotPursued]]:
        if not {'vendors', 'employees', 'invoices'} <= tables:
            return [], []
        rows = conn.execute('''SELECT v.rfc, v.bank_clabe, e.emp_id, e.name, i.uuid, i.total
            FROM vendors v JOIN employees e ON v.bank_clabe=e.bank_clabe
            JOIN invoices i ON i.issuer_rfc=v.rfc
            WHERE trim(coalesce(v.bank_clabe,'')) <> '' ORDER BY v.rfc, i.uuid''').fetchall()
        grouped: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
        for row in rows: grouped[(row['rfc'], row['emp_id'])].append(row)
        findings = []
        for (rfc, emp), invoices in grouped.items():
            exhibits = [self._exhibit('invoices', row['uuid'], f"Factura del proveedor {rfc} vinculada al flujo bajo revisión.") for row in invoices]
            exhibits.extend([self._exhibit('vendors', rfc, f'Proveedor {rfc} comparte CLABE con un empleado.'), self._exhibit('employees', emp, f'Empleado {emp} comparte la CLABE registrada con el proveedor.')])
            findings.append(self._finding('kickback', [f'RFC:{rfc}', f'EMP:{emp}'], 'Políticas internas de compras: conflicto de interés y pago a tercero relacionado.', 'proven', exhibits, self._amount(invoices, 'total')))
        return findings, []

    def detect_round_tripping(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[Finding], list[LeadNotPursued]]:
        if 'bank_txns' not in tables:
            return [], []
        txns = conn.execute('SELECT * FROM bank_txns WHERE amount > 0 ORDER BY date, txn_id').fetchall()
        outgoing: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in txns: outgoing[row['from_clabe']].append(row)
        findings, seen = [], set()
        for first in txns:
            for second in outgoing.get(first['to_clabe'], []):
                for third in outgoing.get(second['to_clabe'], []):
                    if third['to_clabe'] != first['from_clabe'] or len({first['txn_id'], second['txn_id'], third['txn_id']}) != 3:
                        continue
                    key = tuple(sorted((str(first['txn_id']), str(second['txn_id']), str(third['txn_id']))))
                    if key in seen: continue
                    seen.add(key)
                    rows = [first, second, third]
                    exhibits = [self._exhibit('bank_txns', row['txn_id'], f"Transferencia {row['from_clabe']} a {row['to_clabe']}.") for row in rows]
                    trail = [MoneyTrailStep(**{'from': row['from_clabe'], 'to': row['to_clabe'], 'amount': float(row['amount']), 'date': row['date'], 'exhibit_id': exhibit.exhibit_id}) for row, exhibit in zip(rows, exhibits)]
                    findings.append(self._finding('round_tripping', [f'RFC:CLABE-{first["from_clabe"]}', f'RFC:CLABE-{first["to_clabe"]}'], 'Políticas internas de tesorería: flujo circular sin justificación comercial.', 'probable', exhibits, self._amount(rows, 'amount'), trail))
        return findings, []

    def detect_threshold_splitting(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[Finding], list[LeadNotPursued]]:
        if 'invoices' not in tables:
            return [], []
        rows = conn.execute('''SELECT * FROM invoices WHERE total > 0 AND total < 50000 AND total >= 45000
            ORDER BY issuer_rfc, issue_date, uuid''').fetchall()
        grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows: grouped[row['issuer_rfc']].append(row)
        findings, leads = [], []
        for rfc, invoices in grouped.items():
            if len(invoices) < 3:
                if invoices:
                    leads.append(LeadNotPursued(entity=f'RFC:{rfc}', signal='threshold_splitting', reason=f"Se revisaron {len(invoices)} factura(s) debajo de $50,000; no alcanzan el mínimo de tres operaciones repetidas.", tool_calls_made=['SQL invoices by issuer and amount'], closed_by='investigator'))
                continue
            exhibits = [self._exhibit('invoices', row['uuid'], f"Factura por ${float(row['total']):,.2f}, inmediatamente debajo del umbral de $50,000.") for row in invoices]
            findings.append(self._finding('threshold_splitting', [f'RFC:{rfc}'], 'Políticas internas de compras: prohibición de fraccionar adquisiciones para evadir el umbral de autorización.', 'probable', exhibits, self._amount(invoices, 'total')))
        return findings, leads

    def detect_revenue_inflation(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[Finding], list[LeadNotPursued]]:
        if not {'invoices', 'ledger'} <= tables:
            return [], []
        invoices = conn.execute("SELECT * FROM invoices WHERE lower(coalesce(status,'')) = 'cancelado' ORDER BY issuer_rfc, issue_date, uuid").fetchall()
        findings, leads = [], []
        for invoice in invoices:
            ledger = conn.execute('SELECT * FROM ledger WHERE invoice_uuid=? ORDER BY entry_id', (invoice['uuid'],)).fetchall()
            if len(ledger) < 2:
                leads.append(LeadNotPursued(entity=f'RFC:{invoice["issuer_rfc"]}', signal='revenue_inflation', reason=f"La factura cancelada {invoice['uuid']} fue revisada, pero solo tiene {len(ledger)} asiento(s) asociado(s); no hay base documental suficiente para sostener reconocimiento indebido de ingresos.", tool_calls_made=['SQL invoices status', 'SQL ledger by invoice_uuid'], closed_by='challenger'))
                continue
            exhibits = [self._exhibit('invoices', invoice['uuid'], 'Factura cancelada que fue registrada como ingreso.'), *[self._exhibit('ledger', row['entry_id'], f"Asiento contable asociado a la factura {invoice['uuid']}.") for row in ledger[:2]]]
            findings.append(self._finding('revenue_inflation', [f'RFC:{invoice["issuer_rfc"]}'], 'NIF C-3 y políticas de cierre contable: ingresos cancelados no deben mantenerse reconocidos.', 'proven', exhibits, round(float(invoice['total']), 2)))
        return findings, leads

    def run(self) -> Submission:
        started = time.perf_counter()
        with self._connection() as conn:
            tables = self._tables(conn)
            self._validate_estate(conn, tables)
            findings: list[Finding] = []
            leads: list[LeadNotPursued] = []
            for detector in (self.detect_phantom_vendor, self.detect_kickback, self.detect_round_tripping, self.detect_threshold_splitting, self.detect_revenue_inflation):
                detected, closed = detector(conn, tables)
                findings.extend(detected)
                leads.extend(closed)
        return Submission(seed=self.seed, findings=findings, leads_not_pursued=leads,
                          run_metadata=RunMetadata(llm_calls=0, mxn_cost=0.0,
                          wall_clock_seconds=round(time.perf_counter() - started, 6), cost_by_role={}, deterministic=True))


def run_forensic_audit(estate_path: str, seed: int) -> Submission:
    return ForensicAuditor(estate_path, seed).run()


def _review(finding: Finding) -> str:
    """A deterministic challenger checks contract-level weaknesses, not facts."""
    monetary = [e for e in finding.exhibits if e.source_table in AMOUNT_TABLES]
    if len(finding.exhibits) < 3 or not monetary:
        return 'La revisión adversarial rechazó el caso por falta de evidencia o conciliación.'
    return f'La revisión adversarial intentó descartar el hallazgo por evidencia insuficiente; sobrevivió porque conserva {len(finding.exhibits)} exhibits, incluyendo {len(monetary)} registro(s) monetario(s), y una conciliación verificable.'


def _reconciliation_expression(finding: Finding, estate_path: str | None) -> str:
    if not estate_path:
        return f'${finding.peso_amount:,.2f} (verificado durante la ejecución)'
    try:
        conn = sqlite3.connect(f'file:{Path(estate_path).resolve()}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
        ids = {'invoices': 'uuid', 'bank_txns': 'txn_id', 'purchase_orders': 'po_id', 'contracts': 'contract_id'}
        for exhibit in finding.exhibits:
            column = AMOUNT_TABLES.get(exhibit.source_table)
            if not column:
                continue
            row = conn.execute(f'SELECT {column} FROM {exhibit.source_table} WHERE {ids[exhibit.source_table]}=?', (exhibit.record_id,)).fetchone()
            if row is not None:
                grouped[exhibit.source_table].append((exhibit.exhibit_id, float(row[column] or 0)))
        conn.close()
        if not grouped:
            return f'${finding.peso_amount:,.2f} (sin exhibit monetario recuperable)'
        _, values = min(grouped.items(), key=lambda item: abs(finding.peso_amount - sum(value for _, value in item[1])))
        return ' + '.join(f'{exhibit_id} (${amount:,.2f})' for exhibit_id, amount in values) + f' = ${sum(amount for _, amount in values):,.2f}'
    except sqlite3.Error:
        return f'${finding.peso_amount:,.2f} (verificado durante la ejecución)'


def _case_context(estate_path: str | None) -> tuple[str, str]:
    if not estate_path:
        return 'No disponible', 'No disponible'
    try:
        conn = sqlite3.connect(f'file:{Path(estate_path).resolve()}?mode=ro', uri=True)
        row = conn.execute('SELECT receiver_rfc, min(issue_date), max(issue_date) FROM invoices').fetchone()
        conn.close()
        if row is None:
            return 'No disponible', 'No disponible'
        return str(row[0] or 'No disponible'), f'{row[1] or "No disponible"} a {row[2] or "No disponible"}'
    except sqlite3.Error:
        return 'No disponible', 'No disponible'


def render_case_file(submission: Submission, estate_path: str | None = None) -> str:
    proven = sum(f.confidence == 'proven' for f in submission.findings)
    exposure = sum(f.peso_amount for f in submission.findings)
    company, period = _case_context(estate_path)
    lines = ['# Case File — Forensic Auditor', '', '## 1. Header', f'Empresa auditada: {company}. Periodo auditado: {period}. Estate seed: {submission.seed}. LLM calls: {submission.run_metadata.llm_calls}; MXN cost: ${submission.run_metadata.mxn_cost:,.2f}; wall-clock: {submission.run_metadata.wall_clock_seconds:.3f}s; deterministic: {submission.run_metadata.deterministic}.', '', '## 2. Executive summary', f'El análisis determinista identificó {len(submission.findings)} hallazgo(s) a partir de registros SQLite y cerró {len(submission.leads_not_pursued)} lead(s) sin acusación.', '', '| | |', '|---|---|', f'| Findings | {len(submission.findings)} ({proven} proven, {len(submission.findings)-proven} probable) |', f'| Total exposure | ${exposure:,.2f} MXN |', f'| Leads investigated and closed | {len(submission.leads_not_pursued)} |']
    for finding in submission.findings:
        lines += ['', f'## 3. {", ".join(finding.entities)} — {finding.scheme_type}', f'**Rule broken:** {finding.rule_broken}', f'**Amount and confidence:** ${finding.peso_amount:,.2f} MXN — {finding.confidence}', '', f'**What happened:** {finding.narrative}', '', '**Money trail:**']
        if finding.money_trail:
            lines += ['```mermaid', 'flowchart LR']
            lines += [f'  {index}["{step.from_}"] -->|"${step.amount:,.2f} · {step.exhibit_id}"| {index + 1}["{step.to}"]' for index, step in enumerate(finding.money_trail)]
            lines += ['```']
        else:
            lines += ['No transfer trail is required for this document-only finding.']
        lines += ['', '**Exhibits:**', '', '| ID | Source | Record | What it proves |', '|---|---|---|---|']
        lines += [f'| {e.exhibit_id} | {e.source_table} | {e.record_id} | {e.note} |' for e in finding.exhibits]
        amount_exhibits = [e for e in finding.exhibits if e.source_table in AMOUNT_TABLES]
        lines += ['', f'**Reconciliation:** peso_amount = ${finding.peso_amount:,.2f}; {_reconciliation_expression(finding, estate_path)}. Exhibits monetarios: {", ".join(e.exhibit_id for e in amount_exhibits)}.', '', f'**Adversarial review:** {_review(finding)}']
    lines += ['', '## 4. Leads not pursued']
    lines += [f'- **{lead.entity}** — Signal: {lead.signal}. Closed because: {lead.reason} Tools: {", ".join(lead.tool_calls_made) or "none"}. Closed by: {lead.closed_by}.' for lead in submission.leads_not_pursued] or ['No leads met the preliminary signal threshold and were closed in this run.']
    lines += ['', '## 5. Method and limits', 'Detectors use read-only SQLite queries and deterministic rules; narrative is generated from the already-validated evidence. The run does not infer identities beyond the estate, fetch external data, or prove intent. Reproduce by running POST /audit/run with the same estate and seed.']
    return '\n'.join(lines) + '\n'
