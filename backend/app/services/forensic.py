"""Deterministic, read-only forensic analysis over a supplied SQLite estate.

Facts and amounts are derived only from SQL rows.  Narrative text is supplied
by the bounded formatter in ``agent.py`` and never changes the findings.
"""
from __future__ import annotations

import sqlite3
import time
import hashlib
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable

from ..models import AuditPeriod, AuditPreflight, CandidateFinding, Exhibit, Finding, LeadNotPursued, MoneyTrailStep, RunMetadata, Submission
from .forensic_validation import publish_candidate, rejected_candidate_lead, validate_candidate

AMOUNT_TABLES = {'invoices': 'total', 'bank_txns': 'amount', 'purchase_orders': 'amount', 'contracts': 'value'}
RULESET_VERSION = '2026.09.12.3'
ROUND_TRIP_MAX_DAYS = 14
ROUND_TRIP_AMOUNT_VARIANCE = 0.02
SPLIT_WINDOW_DAYS = 14
SPLIT_MIN_INVOICES = 3
REQUIRED_COLUMNS = {
    'vendors': {'rfc', 'bank_clabe'}, 'invoices': {'uuid', 'issuer_rfc', 'issue_date', 'total', 'status'},
    'ledger': {'entry_id', 'invoice_uuid'}, 'bank_txns': {'txn_id', 'date', 'from_clabe', 'to_clabe', 'amount'},
    'purchase_orders': {'po_id', 'vendor_rfc'}, 'contracts': {'contract_id', 'vendor_rfc'},
    'employees': {'emp_id', 'bank_clabe'}, 'efos_list': {'rfc', 'status'},
}


def create_demo_estate(path: str) -> None:
    """Create an isolated disposable estate that exercises all five detectors."""
    conn = sqlite3.connect(path)
    conn.executescript('''
    CREATE TABLE vendors (rfc TEXT PRIMARY KEY, legal_name TEXT, registered_date TEXT, address TEXT, bank_clabe TEXT, category TEXT, contact_email TEXT);
    CREATE TABLE invoices (uuid TEXT PRIMARY KEY, issuer_rfc TEXT, receiver_rfc TEXT, issue_date TEXT, subtotal REAL, iva REAL, total REAL, concepto_text TEXT, uso_cfdi TEXT, forma_pago TEXT, metodo_pago TEXT, status TEXT);
    CREATE TABLE ledger (entry_id INTEGER PRIMARY KEY, date TEXT, account_code TEXT, account_name TEXT, debit REAL, credit REAL, description TEXT, invoice_uuid TEXT, cost_center TEXT, approver TEXT);
    CREATE TABLE bank_txns (txn_id TEXT PRIMARY KEY, date TEXT, from_clabe TEXT, to_clabe TEXT, amount REAL, reference TEXT, channel TEXT);
    CREATE TABLE purchase_orders (po_id TEXT PRIMARY KEY, vendor_rfc TEXT, date TEXT, amount REAL, requester TEXT, approver TEXT, description TEXT);
    CREATE TABLE contracts (contract_id TEXT PRIMARY KEY, vendor_rfc TEXT, start_date TEXT, value REAL, scope_text TEXT);
    CREATE TABLE employees (emp_id TEXT PRIMARY KEY, name TEXT, role TEXT, bank_clabe TEXT, hire_date TEXT);
    CREATE TABLE efos_list (rfc TEXT PRIMARY KEY, legal_name TEXT, status TEXT, publication_date TEXT);
    INSERT INTO vendors VALUES ('EFOS010101AAA','Servicios Fantasma SA','2020-01-01','Monterrey','111111111111111111','Consultoría','efos@example.mx');
    INSERT INTO vendors VALUES ('SPLIT010101BBB','Proveedora Fraccionada SA','2021-01-01','Monterrey','222222222222222222','Mantenimiento','split@example.mx');
    INSERT INTO vendors VALUES ('VENDORA0101','Proveedor A SA','2021-01-01','Monterrey','VENDOR-A','Servicios','a@example.mx');
    INSERT INTO vendors VALUES ('VENDORB0101','Proveedor B SA','2021-01-01','Monterrey','VENDOR-B','Servicios','b@example.mx');
    INSERT INTO vendors VALUES ('DECOY010101AAA','Proveedor con compras espaciadas SA','2021-01-01','Monterrey','333333333333333333','Mantenimiento','decoy@example.mx');
    INSERT INTO employees VALUES ('EMP:0001','Ana Ejemplo','Compras','111111111111111111','2020-01-01');
    INSERT INTO efos_list VALUES ('EFOS010101AAA','Servicios Fantasma SA','definitivo','2025-01-01');
    INSERT INTO invoices VALUES ('EFOS-001','EFOS010101AAA','COMPANY010101AAA','2026-01-01',100000,16000,116000,'Consultoría','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('SPLIT-001','SPLIT010101BBB','COMPANY010101AAA','2026-01-02',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('SPLIT-002','SPLIT010101BBB','COMPANY010101AAA','2026-01-03',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('SPLIT-003','SPLIT010101BBB','COMPANY010101AAA','2026-01-04',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('DECOY-001','DECOY010101AAA','COMPANY010101AAA','2025-01-02',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('DECOY-002','DECOY010101AAA','COMPANY010101AAA','2025-07-02',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('REV-001','COMPANY010101AAA','CLIENT010101AAA','2026-01-31',100000,16000,116000,'Venta','G03','03','PUE','cancelado');
    INSERT INTO ledger VALUES (1,'2026-01-31','4000','Ingresos',0,116000,'Ingreso registrado','REV-001','CC-01','Ana Ejemplo');
    INSERT INTO ledger VALUES (2,'2026-01-31','1100','Clientes',116000,0,'Cuenta cliente','REV-001','CC-01','Ana Ejemplo');
    INSERT INTO bank_txns VALUES ('CYCLE-001','2026-01-01','COMPANY-CLABE','VENDOR-A',100000,'Salida','SPEI');
    INSERT INTO bank_txns VALUES ('CYCLE-002','2026-01-02','VENDOR-A','VENDOR-B',100000,'Intermediación','SPEI');
    INSERT INTO bank_txns VALUES ('CYCLE-003','2026-01-03','VENDOR-B','COMPANY-CLABE',100000,'Retorno','SPEI');
    ''')
    conn.commit()
    conn.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_forensic_estate(estate_path: str) -> AuditPreflight:
    """Read-only schema and quality profile shown before an audit is run."""
    auditor = ForensicAuditor(estate_path, seed=0)
    warnings: list[str] = []
    with auditor._connection() as conn:
        tables = auditor._tables(conn)
        auditor._validate_estate(conn, tables)
        counts = {table: int(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]) for table in sorted(REQUIRED_COLUMNS)}
        dates = [auditor._date(row[0]) for row in conn.execute('SELECT issue_date FROM invoices')]
        valid_dates = sorted(value for value in dates if value is not None)
        invalid_dates = sum(value is None for value in dates)
        if invalid_dates:
            warnings.append(f'invoices.issue_date: {invalid_dates} fecha(s) inválida(s) se excluirán de reglas temporales.')
        for table, column in (
            ('invoices', 'total'), ('bank_txns', 'amount'), ('purchase_orders', 'amount'),
            ('contracts', 'value'), ('ledger', 'debit'), ('ledger', 'credit'),
        ):
            raw_values = [row[0] for row in conn.execute(f'SELECT {column} FROM {table}')]
            invalid = sum(
                not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0
                for value in raw_values
            )
            if invalid:
                warnings.append(f'{table}.{column}: {invalid} valor(es) nulo(s), no numérico(s) o negativo(s).')
        for table, column in (('bank_txns', 'date'), ('ledger', 'date')):
            values = [auditor._date(row[0]) for row in conn.execute(f'SELECT {column} FROM {table}')]
            invalid = sum(value is None for value in values)
            if invalid:
                warnings.append(f'{table}.{column}: {invalid} fecha(s) inválida(s) se excluirán de reglas temporales.')
        for table, count in counts.items():
            if count == 0:
                warnings.append(f'{table}: tabla vacía; los detectores relacionados no tendrán evidencia.')
        duplicate_invoices = int(conn.execute('''SELECT COUNT(*) FROM (
            SELECT issuer_rfc, receiver_rfc, issue_date, total, concepto_text
            FROM invoices GROUP BY issuer_rfc, receiver_rfc, issue_date, total, concepto_text HAVING COUNT(*) > 1
        )''').fetchone()[0])
        if duplicate_invoices:
            warnings.append(f'invoices: {duplicate_invoices} grupo(s) de factura potencialmente duplicado(s).')
        duplicate_bank = int(conn.execute('''SELECT COUNT(*) FROM (
            SELECT date, from_clabe, to_clabe, amount, reference
            FROM bank_txns GROUP BY date, from_clabe, to_clabe, amount, reference HAVING COUNT(*) > 1
        )''').fetchone()[0])
        if duplicate_bank:
            warnings.append(f'bank_txns: {duplicate_bank} grupo(s) de transferencia potencialmente duplicado(s).')
        principal = conn.execute('''SELECT receiver_rfc FROM invoices
            WHERE trim(coalesce(receiver_rfc,''))<>'' GROUP BY receiver_rfc
            ORDER BY COUNT(*) DESC, receiver_rfc LIMIT 1''').fetchone()
        orphan_invoices = int(conn.execute('''SELECT COUNT(*) FROM invoices i
            LEFT JOIN vendors v ON v.rfc=i.issuer_rfc
            WHERE i.receiver_rfc=? AND v.rfc IS NULL''', (principal[0] if principal else '',)).fetchone()[0])
        orphan_ledger = int(conn.execute('''SELECT COUNT(*) FROM ledger l LEFT JOIN invoices i
            ON i.uuid=l.invoice_uuid WHERE l.invoice_uuid IS NOT NULL AND trim(l.invoice_uuid)<>'' AND i.uuid IS NULL''').fetchone()[0])
        orphan_procurement = int(conn.execute('''SELECT
            (SELECT COUNT(*) FROM purchase_orders p LEFT JOIN vendors v ON v.rfc=p.vendor_rfc WHERE v.rfc IS NULL) +
            (SELECT COUNT(*) FROM contracts c LEFT JOIN vendors v ON v.rfc=c.vendor_rfc WHERE v.rfc IS NULL)''').fetchone()[0])
        if orphan_invoices:
            warnings.append(f'invoices: {orphan_invoices} emisor(es) sin registro maestro de proveedor.')
        if orphan_ledger:
            warnings.append(f'ledger: {orphan_ledger} asiento(s) con invoice_uuid huérfano.')
        if orphan_procurement:
            warnings.append(f'procurement: {orphan_procurement} orden(es) o contrato(s) con proveedor huérfano.')
        if not valid_dates:
            warnings.append('invoices: no hay fechas ISO válidas; reglas temporales quedarán limitadas.')
    return AuditPreflight(
        estate_filename=auditor.path.name,
        estate_sha256=_sha256(auditor.path),
        estate_bytes=auditor.path.stat().st_size,
        tables=counts,
        period=AuditPeriod(
            from_date=valid_dates[0].isoformat() if valid_dates else None,
            to_date=valid_dates[-1].isoformat() if valid_dates else None,
        ),
        quality_warnings=warnings,
        ready=True,
    )


class ForensicAuditor:
    def __init__(self, estate_path: str, seed: int):
        self.path = Path(estate_path).expanduser().resolve()
        if not self.path.is_file():
            raise ValueError('estate_path debe apuntar a una base SQLite existente.')
        self.seed = seed
        self._index = 0
        self._candidate_index = 0

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
        return round(sum(ForensicAuditor._number(row[column]) for row in rows), 2)

    @staticmethod
    def _number(value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _date(value: object) -> date | None:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _similar_amounts(rows: Iterable[sqlite3.Row], variance: float = ROUND_TRIP_AMOUNT_VARIANCE) -> bool:
        values = [abs(ForensicAuditor._number(row['amount'])) for row in rows]
        return bool(values) and min(values) > 0 and (max(values) - min(values)) / max(values) <= variance

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

    def _candidate(self, scheme: str, entities: list[str], rule: str, confidence: str,
                   exhibits: list[Exhibit], peso: float,
                   trail: list[MoneyTrailStep] | None = None,
                   facts: list[str] | None = None) -> CandidateFinding:
        self._candidate_index += 1
        return CandidateFinding(
            candidate_id=f'CAND-{self._candidate_index:03d}', scheme_type=scheme,
            entities=entities, rule_broken=rule, peso_amount=peso,
            confidence=confidence, exhibits=exhibits, money_trail=trail or [],
            detector_facts=facts or [],
        )

    def detect_phantom_vendor(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[CandidateFinding], list[LeadNotPursued]]:
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
            invoices = [row for row in invoices if self._number(row['total']) > 0]
            if not invoices:
                continue
            exhibits = [self._exhibit('invoices', row['uuid'], f"Factura emitida por {rfc} por ${self._number(row['total']):,.2f}.") for row in invoices]
            exhibits.append(self._exhibit('efos_list', rfc, f"RFC {rfc} aparece en la lista EFOS con estatus {invoices[0]['efos_status']} ."))
            exhibits.append(self._exhibit('vendors', rfc, f"Registro maestro del proveedor {rfc} revisado contra la lista EFOS."))
            status = str(invoices[0]['efos_status']).strip().lower()
            confidence = 'proven' if status == 'definitivo' else 'probable'
            findings.append(self._candidate('phantom_vendor', [f'RFC:{rfc}'], 'CFF Art. 69-B: operaciones con EFOS.', confidence, exhibits, self._amount(invoices, 'total')))
        return findings, []

    def detect_kickback(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[CandidateFinding], list[LeadNotPursued]]:
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
            invoices = [row for row in invoices if self._number(row['total']) > 0]
            if not invoices:
                continue
            exhibits = [self._exhibit('invoices', row['uuid'], f"Factura del proveedor {rfc} vinculada al flujo bajo revisión.") for row in invoices]
            exhibits.extend([self._exhibit('vendors', rfc, f'Proveedor {rfc} comparte CLABE con un empleado.'), self._exhibit('employees', emp, f'Empleado {emp} comparte la CLABE registrada con el proveedor.')])
            employee_entity = str(emp) if str(emp).startswith('EMP:') else f'EMP:{emp}'
            findings.append(self._candidate('kickback', [f'RFC:{rfc}', employee_entity], 'Políticas internas de compras: conflicto de interés y pago a tercero relacionado.', 'proven', exhibits, self._amount(invoices, 'total')))
        return findings, []

    def detect_round_tripping(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[CandidateFinding], list[LeadNotPursued]]:
        if 'bank_txns' not in tables:
            return [], []
        txns = [
            row for row in conn.execute('SELECT * FROM bank_txns WHERE amount > 0 ORDER BY date, txn_id').fetchall()
            if math.isfinite(self._number(row['amount']))
        ]
        vendor_by_clabe = {
            str(row['bank_clabe']).strip(): str(row['rfc']).strip()
            for row in conn.execute("SELECT rfc, bank_clabe FROM vendors WHERE trim(coalesce(bank_clabe, '')) <> '' ORDER BY rfc")
        }
        clabe_by_vendor = {rfc: clabe for clabe, rfc in vendor_by_clabe.items()}
        company_rfcs = {
            str(row['receiver_rfc']).strip()
            for row in conn.execute("SELECT DISTINCT receiver_rfc FROM invoices WHERE trim(coalesce(receiver_rfc, '')) <> ''")
        }
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
                    rows = [first, second, third]
                    dates = [self._date(row['date']) for row in rows]
                    if None in dates or (max(dates) - min(dates)).days > ROUND_TRIP_MAX_DAYS:
                        continue
                    if not self._similar_amounts(rows):
                        continue
                    entity_rfcs = []
                    for clabe in (str(first['from_clabe']).strip(), str(first['to_clabe']).strip(), str(second['to_clabe']).strip()):
                        if clabe in vendor_by_clabe:
                            entity_rfcs.append(vendor_by_clabe[clabe])
                        elif clabe in company_rfcs:
                            entity_rfcs.append(clabe)
                    entities = [f'RFC:{rfc}' for rfc in dict.fromkeys(entity_rfcs)]
                    if not entities:
                        continue
                    seen.add(key)
                    exhibits = [self._exhibit('bank_txns', row['txn_id'], f"Transferencia {row['from_clabe']} a {row['to_clabe']}.") for row in rows]
                    for rfc in dict.fromkeys(entity_rfcs):
                        if rfc in clabe_by_vendor:
                            exhibits.append(self._exhibit(
                                'vendors', rfc,
                                f'El registro maestro vincula RFC {rfc} con la CLABE {clabe_by_vendor[rfc]} citada en el ciclo.',
                            ))
                        elif rfc in company_rfcs:
                            support = conn.execute(
                                'SELECT * FROM invoices WHERE issuer_rfc=? OR receiver_rfc=? ORDER BY issue_date, uuid LIMIT 1',
                                (rfc, rfc),
                            ).fetchone()
                            if support is not None:
                                exhibits.append(self._exhibit(
                                    'invoices', support['uuid'],
                                    f'La factura identifica al RFC {rfc} dentro del estate auditado.',
                                ))
                    trail = [MoneyTrailStep(**{'from': row['from_clabe'], 'to': row['to_clabe'], 'amount': self._number(row['amount']), 'date': row['date'], 'exhibit_id': exhibit.exhibit_id}) for row, exhibit in zip(rows, exhibits)]
                    findings.append(self._candidate('round_tripping', entities, 'Políticas internas de tesorería: flujo circular concentrado en 14 días y con importes equivalentes, sin justificación comercial.', 'probable', exhibits, self._amount(rows, 'amount'), trail))
        return findings, []

    def detect_threshold_splitting(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[CandidateFinding], list[LeadNotPursued]]:
        if 'invoices' not in tables:
            return [], []
        rows = conn.execute('''SELECT * FROM invoices WHERE total > 0 AND total < 50000 AND total >= 45000
            ORDER BY issuer_rfc, issue_date, uuid''').fetchall()
        grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in rows: grouped[row['issuer_rfc']].append(row)
        findings, leads = [], []
        for rfc, invoices in grouped.items():
            dated = [(self._date(row['issue_date']), row) for row in invoices]
            dated = [(value, row) for value, row in dated if value is not None]
            selected: list[sqlite3.Row] = []
            window_end = 0
            for window_start, (start_date, _) in enumerate(dated):
                window_end = max(window_end, window_start)
                while window_end < len(dated) and (dated[window_end][0] - start_date).days <= SPLIT_WINDOW_DAYS:
                    window_end += 1
                if window_end - window_start >= SPLIT_MIN_INVOICES:
                    selected = [row for _, row in dated[window_start:window_end]]
                    break
            if not selected:
                if invoices:
                    leads.append(LeadNotPursued(entity=f'RFC:{rfc}', signal='threshold_splitting', reason=f"Se revisaron {len(invoices)} factura(s) de $45,000 a menos de $50,000; no hay tres operaciones dentro de una ventana de {SPLIT_WINDOW_DAYS} días.", tool_calls_made=['SQL invoices by issuer, amount and issue_date'], closed_by='investigator'))
                continue
            exhibits = [self._exhibit('invoices', row['uuid'], f"Factura por ${self._number(row['total']):,.2f}, inmediatamente debajo del umbral de $50,000 y dentro de una ventana de {SPLIT_WINDOW_DAYS} días.") for row in selected]
            findings.append(self._candidate('threshold_splitting', [f'RFC:{rfc}'], 'Políticas internas de compras: prohibición de fraccionar adquisiciones para evadir el umbral de autorización.', 'probable', exhibits, self._amount(selected, 'total')))
        return findings, leads

    def detect_revenue_inflation(self, conn: sqlite3.Connection, tables: set[str]) -> tuple[list[CandidateFinding], list[LeadNotPursued]]:
        if not {'invoices', 'ledger'} <= tables:
            return [], []
        invoices = conn.execute("SELECT * FROM invoices WHERE lower(coalesce(status,'')) = 'cancelado' ORDER BY issuer_rfc, issue_date, uuid").fetchall()
        findings, leads = [], []
        for invoice in invoices:
            ledger = conn.execute('SELECT * FROM ledger WHERE invoice_uuid=? ORDER BY entry_id', (invoice['uuid'],)).fetchall()
            revenue_rows = [row for row in ledger if (
                str(row['account_code'] or '').startswith('4') or
                any(token in str(row['account_name'] or '').lower() + ' ' + str(row['description'] or '').lower() for token in ('ingreso', 'revenue', 'venta'))
            )]
            unreversed_revenue = round(sum(self._number(row['credit']) - self._number(row['debit']) for row in revenue_rows), 2)
            original_credits = [row for row in revenue_rows if self._number(row['credit']) > 0]
            reversal_rows = [row for row in revenue_rows if self._number(row['debit']) > 0]
            if self._number(invoice['total']) <= 0 or len(ledger) < 2 or not original_credits or unreversed_revenue <= 0:
                leads.append(LeadNotPursued(entity=f'RFC:{invoice["issuer_rfc"]}', signal='revenue_inflation', reason=f"La factura cancelada {invoice['uuid']} fue revisada, pero no conserva al menos un crédito positivo de ingresos sin reversa verificable.", tool_calls_made=['SQL invoices status', 'SQL ledger by invoice_uuid'], closed_by='challenger'))
                continue
            credit_row = original_credits[0]
            support = reversal_rows[0] if reversal_rows else next(
                (row for row in ledger if row['entry_id'] != credit_row['entry_id']), credit_row,
            )
            exhibits = [
                self._exhibit('invoices', invoice['uuid'], 'Factura cancelada que fue registrada como ingreso.'),
                self._exhibit('ledger', credit_row['entry_id'], f"Crédito de ingreso asociado a la factura {invoice['uuid']} que permanece sin reversa completa."),
                self._exhibit(
                    'ledger', support['entry_id'],
                    (f"Reversa parcial asociada a la factura {invoice['uuid']}; queda un saldo de ingreso de ${unreversed_revenue:,.2f}."
                     if reversal_rows else f"Asiento de contrapartida asociado a la factura {invoice['uuid']} sin reversa de ingresos."),
                ),
            ]
            # The exposed amount is the cancelled CFDI total.  The revenue entry
            # establishes that recognition persisted; the invoice exhibit makes
            # the reported peso independently reconcilable by the validator.
            findings.append(self._candidate(
                'revenue_inflation', [f'RFC:{invoice["issuer_rfc"]}'],
                'NIF C-3 y políticas de cierre contable: ingresos cancelados no deben mantenerse reconocidos.',
                'proven', exhibits, round(self._number(invoice['total']), 2),
                facts=[f'ingreso_neto_no_revertido={unreversed_revenue:.2f}'],
            ))
        return findings, leads

    def run(self) -> Submission:
        started = time.perf_counter()
        with self._connection() as conn:
            tables = self._tables(conn)
            self._validate_estate(conn, tables)
            candidates: list[CandidateFinding] = []
            findings: list[Finding] = []
            leads: list[LeadNotPursued] = []
            for detector in (self.detect_phantom_vendor, self.detect_kickback, self.detect_round_tripping, self.detect_threshold_splitting, self.detect_revenue_inflation):
                detected, closed = detector(conn, tables)
                candidates.extend(detected)
                leads.extend(closed)
            for candidate in candidates:
                report = validate_candidate(conn, candidate)
                if report.passed:
                    findings.append(publish_candidate(candidate, report))
                else:
                    leads.append(rejected_candidate_lead(candidate, report))
            scheme_order = {
                name: index for index, name in enumerate(
                    ('phantom_vendor', 'kickback', 'round_tripping', 'threshold_splitting', 'revenue_inflation')
                )
            }
            findings.sort(key=lambda finding: (
                scheme_order[finding.scheme_type], tuple(finding.entities),
                tuple((exhibit.source_table, exhibit.record_id) for exhibit in finding.exhibits),
            ))
            leads.sort(key=lambda lead: (lead.signal, lead.entity, lead.reason))
        return Submission(seed=self.seed, findings=findings, leads_not_pursued=leads,
                          run_metadata=RunMetadata(llm_calls=0, mxn_cost=0.0,
                          wall_clock_seconds=round(time.perf_counter() - started, 6), cost_by_role={}, deterministic=True))


def run_forensic_audit(estate_path: str, seed: int) -> Submission:
    return ForensicAuditor(estate_path, seed).run()


def _review(finding: Finding) -> str:
    """State the strongest deterministic counter-hypothesis and why it failed."""
    monetary = [e for e in finding.exhibits if e.source_table in AMOUNT_TABLES]
    if len(finding.exhibits) < 3 or not monetary:
        return 'El hard validator habría cerrado este candidato por evidencia o conciliación insuficiente.'
    challenges = {
        'phantom_vendor': 'Objeción: coincidir con una lista no bastaría si la factura perteneciera a otro RFC o el estatus no fuera aplicable. Sobrevivió porque el emisor, la factura, el maestro de proveedor y el registro EFOS definitivo/presunto enlazan al mismo RFC.',
        'kickback': 'Objeción: usar el mismo banco no implica conflicto. Sobrevivió porque no se comparó la institución, sino la CLABE completa, no vacía y exactamente igual entre el proveedor y el empleado exhibidos.',
        'round_tripping': 'Objeción: tres transferencias parecidas podrían ser operaciones independientes. Sobrevivió como probable —no proven— porque los pasos conectan y cierran el ciclo, están ordenados, ocurren dentro de 14 días y sus importes varían como máximo 2%.',
        'threshold_splitting': 'Objeción: una factura bajo el umbral puede ser ordinaria. Sobrevivió como probable porque el mismo emisor acumuló al menos tres facturas de $45,000 a menos de $50,000 dentro de 14 días.',
        'revenue_inflation': 'Objeción: una factura cancelada pudo haberse revertido correctamente. Sobrevivió porque el hard validator volvió a calcular los asientos de ingreso y confirmó que permanece un saldo neto positivo no revertido.',
    }
    gate = f' El hard validator además confirmó existencia, unicidad, entidades, importes y conciliación en {len(finding.exhibits)} exhibits ({len(monetary)} monetario(s)).'
    return challenges[finding.scheme_type] + gate


def _monetary_evidence(finding: Finding, estate_path: str | None) -> dict[str, list[tuple[str, str, float]]]:
    if not estate_path:
        return {}
    grouped: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    ids = {'invoices': 'uuid', 'bank_txns': 'txn_id', 'purchase_orders': 'po_id', 'contracts': 'contract_id'}
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f'file:{Path(estate_path).resolve()}?mode=ro', uri=True)
        for exhibit in finding.exhibits:
            column = AMOUNT_TABLES.get(exhibit.source_table)
            if not column:
                continue
            row = conn.execute(
                f'SELECT {column} FROM {exhibit.source_table} WHERE {ids[exhibit.source_table]}=?',
                (exhibit.record_id,),
            ).fetchone()
            if row is not None and math.isfinite(float(row[0] or 0)):
                grouped[exhibit.source_table].append((exhibit.exhibit_id, exhibit.record_id, float(row[0] or 0)))
    except (sqlite3.Error, TypeError, ValueError):
        return {}
    finally:
        if conn is not None:
            conn.close()
    return grouped


def _reconciliation_expression(finding: Finding, estate_path: str | None) -> str:
    if not estate_path:
        return f'${finding.peso_amount:,.2f} (verificado durante la ejecución)'
    grouped = _monetary_evidence(finding, estate_path)
    if not grouped:
        return f'${finding.peso_amount:,.2f} (verificado durante la ejecución)'
    _, values = min(grouped.items(), key=lambda item: abs(finding.peso_amount - sum(value for _, _, value in item[1])))
    return ' + '.join(f'{exhibit_id} (${amount:,.2f})' for exhibit_id, _, amount in values) + f' = ${sum(amount for _, _, amount in values):,.2f}'


def _unique_exposure(findings: list[Finding], estate_path: str | None) -> float:
    """Deduplicate overlapping monetary records across published findings."""
    unique: dict[tuple[str, str], float] = {}
    for finding in findings:
        grouped = _monetary_evidence(finding, estate_path)
        if not grouped:
            continue
        table, values = min(grouped.items(), key=lambda item: abs(finding.peso_amount - sum(v for _, _, v in item[1])))
        for _, record_id, amount in values:
            unique[(table, record_id)] = amount
    return round(sum(unique.values()), 2) if unique else round(sum(f.peso_amount for f in findings), 2)


def _case_context(estate_path: str | None) -> tuple[str, str]:
    if not estate_path:
        return 'No disponible', 'No disponible'
    try:
        conn = sqlite3.connect(f'file:{Path(estate_path).resolve()}?mode=ro', uri=True)
        company_row = conn.execute('''SELECT receiver_rfc, COUNT(*) AS uses FROM invoices
            WHERE trim(coalesce(receiver_rfc,''))<>'' GROUP BY receiver_rfc
            ORDER BY uses DESC, receiver_rfc LIMIT 1''').fetchone()
        dates = [value[0] for value in conn.execute("SELECT issue_date FROM invoices WHERE date(issue_date) IS NOT NULL ORDER BY issue_date")]
        conn.close()
        if company_row is None:
            return 'No disponible', 'No disponible'
        period = f'{dates[0]} a {dates[-1]}' if dates else 'No disponible'
        return str(company_row[0] or 'No disponible'), period
    except sqlite3.Error:
        return 'No disponible', 'No disponible'


def render_case_file(submission: Submission, estate_path: str | None = None) -> str:
    proven = sum(f.confidence == 'proven' for f in submission.findings)
    exposure = _unique_exposure(submission.findings, estate_path)
    company, period = _case_context(estate_path)
    lines = ['# Case File — Forensic Auditor', '', '## 1. Header', f'Empresa auditada: {company}. Periodo auditado: {period}. Estate seed: {submission.seed}. LLM calls: {submission.run_metadata.llm_calls}; MXN cost: ${submission.run_metadata.mxn_cost:,.2f}; wall-clock: {submission.run_metadata.wall_clock_seconds:.3f}s; deterministic: {submission.run_metadata.deterministic}.', '', '## 2. Executive summary', f'El análisis determinista identificó {len(submission.findings)} hallazgo(s) a partir de registros SQLite y cerró {len(submission.leads_not_pursued)} lead(s) sin acusación.', '', '| | |', '|---|---|', f'| Findings | {len(submission.findings)} ({proven} proven, {len(submission.findings)-proven} probable) |', f'| Total exposure | ${exposure:,.2f} MXN |', f'| Leads investigated and closed | {len(submission.leads_not_pursued)} |']
    for finding in submission.findings:
        lines += ['', f'## 3. {", ".join(finding.entities)} — {finding.scheme_type}', f'**Rule broken:** {finding.rule_broken}', f'**Amount and confidence:** ${finding.peso_amount:,.2f} MXN — {finding.confidence}', '', f'**What happened:** {finding.narrative}', '', '**Money trail:**']
        lines += ['```mermaid', 'flowchart LR']
        if finding.money_trail:
            lines += [f'  N{index}["{step.from_}"] -->|"${step.amount:,.2f} · {step.exhibit_id}"| N{index + 1}["{step.to}"]' for index, step in enumerate(finding.money_trail)]
        else:
            entity = (finding.entities[0] if finding.entities else 'Entidad').replace('"', "'")
            lines += [f'  ENT["{entity}"] --> EX0["{finding.exhibits[0].exhibit_id} · {finding.exhibits[0].source_table}"]']
            lines += [f'  EX{index - 1} --> EX{index}["{exhibit.exhibit_id} · {exhibit.source_table}"]' for index, exhibit in enumerate(finding.exhibits[1:], start=1)]
        lines += ['```']
        lines += ['', '**Exhibits:**', '', '| ID | Source | Record | What it proves |', '|---|---|---|---|']
        lines += [f'| {e.exhibit_id} | {e.source_table} | {e.record_id} | {e.note} |' for e in finding.exhibits]
        amount_exhibits = [e for e in finding.exhibits if e.source_table in AMOUNT_TABLES]
        lines += ['', f'**Reconciliation:** peso_amount = ${finding.peso_amount:,.2f}; {_reconciliation_expression(finding, estate_path)}. Exhibits monetarios: {", ".join(e.exhibit_id for e in amount_exhibits)}.', '', f'**Adversarial review / deterministic validation:** {_review(finding)}']
    lines += ['', '## 4. Leads not pursued']
    lines += [f'- **{lead.entity}** — Signal: {lead.signal}. Closed because: {lead.reason} Tools: {", ".join(lead.tool_calls_made) or "none"}. Closed by: {lead.closed_by}.' for lead in submission.leads_not_pursued] or ['No leads met the preliminary signal threshold and were closed in this run.']
    lines += ['', '## 5. Method and limits', 'Los detectores consultan SQLite en modo read-only y publican un candidato solo después de un hard validator determinista. No se usa LLM: la narrativa se forma únicamente con evidencia ya validada. Total exposure deduplica registros monetarios compartidos entre hallazgos; peso_amount conserva la exposición propia conciliable de cada caso. La auditoría no consulta fuentes externas, no atribuye identidades fuera del estate y no prueba intención. Los patrones marcados probable requieren investigación humana. Reproduce mediante POST /audit/run con el mismo estate y seed; el wall-clock es una medición operativa y puede variar entre ejecuciones.']
    return '\n'.join(lines) + '\n'
