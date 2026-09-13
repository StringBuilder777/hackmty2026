"""Deterministic estates and labels used only by the evaluation harness.

The production auditor never imports this module. Scenario definitions stay
here so planted schemes and decoys cannot influence audit decisions.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


BENCHMARK_VERSION = '2026.09.12.2'
TUNING_SEEDS = (271, 509, 761)
HELD_OUT_SEEDS = (104729, 130363, 155921, 196613, 209759)
SCHEME_TYPES = ('phantom_vendor', 'kickback', 'round_tripping', 'threshold_splitting', 'revenue_inflation')

SCHEMA = '''
CREATE TABLE vendors (rfc TEXT PRIMARY KEY, legal_name TEXT, registered_date TEXT, address TEXT, bank_clabe TEXT, category TEXT, contact_email TEXT);
CREATE TABLE invoices (uuid TEXT PRIMARY KEY, issuer_rfc TEXT, receiver_rfc TEXT, issue_date TEXT, subtotal REAL, iva REAL, total REAL, concepto_text TEXT, uso_cfdi TEXT, forma_pago TEXT, metodo_pago TEXT, status TEXT);
CREATE TABLE ledger (entry_id INTEGER PRIMARY KEY, date TEXT, account_code TEXT, account_name TEXT, debit REAL, credit REAL, description TEXT, invoice_uuid TEXT, cost_center TEXT, approver TEXT);
CREATE TABLE bank_txns (txn_id TEXT PRIMARY KEY, date TEXT, from_clabe TEXT, to_clabe TEXT, amount REAL, reference TEXT, channel TEXT);
CREATE TABLE purchase_orders (po_id TEXT PRIMARY KEY, vendor_rfc TEXT, date TEXT, amount REAL, requester TEXT, approver TEXT, description TEXT);
CREATE TABLE contracts (contract_id TEXT PRIMARY KEY, vendor_rfc TEXT, start_date TEXT, value REAL, scope_text TEXT);
CREATE TABLE employees (emp_id TEXT PRIMARY KEY, name TEXT, role TEXT, bank_clabe TEXT, hire_date TEXT);
CREATE TABLE efos_list (rfc TEXT PRIMARY KEY, legal_name TEXT, status TEXT, publication_date TEXT);
'''


@dataclass(frozen=True)
class Scenario:
    schemes: tuple[str, ...]
    decoy_count: int
    entangle_kickback: bool = False
    boundary_positive: bool = False


@dataclass(frozen=True)
class SchemeLabel:
    scheme_id: str
    scheme_type: str
    entities: tuple[str, ...]
    peso_amount: float

    @property
    def key(self) -> tuple[str, tuple[str, ...]]:
        return self.scheme_type, tuple(sorted(self.entities))


@dataclass(frozen=True)
class DecoyLabel:
    entity: str
    signal: str
    reason: str


HELD_OUT_SCENARIOS = {
    104729: Scenario((), 0),
    130363: Scenario(('phantom_vendor',), 2),
    155921: Scenario(('kickback', 'round_tripping', 'threshold_splitting'), 4, entangle_kickback=True),
    196613: Scenario(('phantom_vendor', 'round_tripping', 'threshold_splitting', 'revenue_inflation'), 6, boundary_positive=True),
    209759: Scenario(SCHEME_TYPES, 10, entangle_kickback=True, boundary_positive=True),
}
TUNING_SCENARIOS = {
    271: Scenario(('phantom_vendor', 'threshold_splitting'), 3),
    509: Scenario(('kickback', 'round_tripping', 'revenue_inflation'), 5, entangle_kickback=True),
    761: Scenario(SCHEME_TYPES, 7),
}


def _identity(seed: int) -> dict[str, str]:
    token = str(seed)
    return {
        'company': f'COMP{token}', 'efos': f'EFOS{token}', 'kick': f'KICK{token}',
        'split': f'SPLIT{token}', 'vendor_a': f'VENDA{token}',
        'vendor_b': f'VENDB{token}', 'employee': f'E{token}',
    }


def _scenario(seed: int) -> tuple[Scenario, tuple[int, ...]]:
    if seed in HELD_OUT_SCENARIOS:
        return HELD_OUT_SCENARIOS[seed], HELD_OUT_SEEDS
    if seed in TUNING_SCENARIOS:
        return TUNING_SCENARIOS[seed], TUNING_SEEDS
    raise ValueError('seed no pertenece a una partición declarada.')


def _amounts(seed: int, seeds: tuple[int, ...]) -> dict[str, float]:
    offset = seeds.index(seed) + 1
    return {
        'invoice': 100_000.0 + offset * 1_000,
        'kick': 80_000.0 + offset * 500,
        'round': 120_000.0 + offset * 1_000,
        'revenue': 110_000.0 + offset * 1_000,
    }


def _kick_rfc(ids: dict[str, str], scenario: Scenario) -> str:
    if scenario.entangle_kickback:
        return ids['efos'] if 'phantom_vendor' in scenario.schemes else ids['vendor_a']
    return ids['kick']


def expected_schemes(seed: int) -> tuple[SchemeLabel, ...]:
    """Return authored labels in stable order, preserving duplicate keys."""
    scenario, seeds = _scenario(seed)
    ids, amounts = _identity(seed), _amounts(seed, seeds)
    kick_rfc = _kick_rfc(ids, scenario)
    split_total = 45_000.0 if scenario.boundary_positive else 48_000.0
    labels: list[SchemeLabel] = []
    for index, scheme_type in enumerate(scenario.schemes, start=1):
        if scheme_type == 'phantom_vendor':
            entities, peso = (f"RFC:{ids['efos']}",), amounts['invoice']
        elif scheme_type == 'kickback':
            entities = tuple(sorted((f'RFC:{kick_rfc}', f"EMP:{ids['employee']}")))
            peso = amounts['invoice'] if kick_rfc == ids['efos'] else amounts['kick']
        elif scheme_type == 'round_tripping':
            entities = tuple(sorted((f"RFC:{ids['vendor_a']}", f"RFC:{ids['vendor_b']}")))
            peso = amounts['round'] * 2 + amounts['round'] * (0.98 if scenario.boundary_positive else 0.995)
        elif scheme_type == 'threshold_splitting':
            entities, peso = (f"RFC:{ids['split']}",), split_total * 3
        else:
            entities, peso = (f"RFC:{ids['company']}",), amounts['revenue']
        labels.append(SchemeLabel(f'S{index}_{scheme_type}_{seed}', scheme_type, entities, round(peso, 2)))
    return tuple(labels)


def expected_findings(seed: int) -> set[tuple[str, tuple[str, ...]]]:
    """Backward-compatible key view used by existing tests."""
    return {label.key for label in expected_schemes(seed)}


def expected_decoys(seed: int) -> tuple[DecoyLabel, ...]:
    scenario, _ = _scenario(seed)
    token = str(seed)
    candidates = (
        DecoyLabel(f'RFC:REVSAFE{token}', 'revenue_inflation', 'La factura cancelada tiene una reversa completa en la cuenta de ingresos.'),
        DecoyLabel(f'RFC:TWOINV{token}', 'threshold_splitting', 'Solo existen dos facturas cercanas al umbral dentro de 14 días.'),
        DecoyLabel(f'RFC:LATEA{token}', 'round_tripping', 'El ciclo bancario tarda 15 días y excede el máximo de 14.'),
        DecoyLabel(f'RFC:VARA{token}', 'round_tripping', 'Los importes del ciclo difieren 2.1%, por encima de la tolerancia de 2%.'),
        DecoyLabel(f'RFC:SPACED{token}', 'threshold_splitting', 'Las tres facturas cercanas al umbral están separadas por más de 14 días.'),
        DecoyLabel(f'RFC:BELOW{token}', 'threshold_splitting', 'Las facturas son de $44,999, por debajo de la banda de revisión.'),
        DecoyLabel(f'RFC:ATLIMIT{token}', 'threshold_splitting', 'Las facturas son exactamente de $50,000 y requieren autorización ordinaria.'),
        DecoyLabel(f'RFC:CLEAREFOS{token}', 'phantom_vendor', 'El RFC tiene estatus desvirtuado, no presunto ni definitivo.'),
        DecoyLabel(f'RFC:BANKLIKE{token}', 'kickback', 'Proveedor y empleado comparten prefijo bancario, pero no la misma CLABE.'),
        DecoyLabel(f'RFC:ORDERA{token}', 'round_tripping', 'Las transferencias forman un ciclo por IDs, pero el segundo tramo ocurrió antes que el primero.'),
    )
    return candidates[:scenario.decoy_count]


def _vendor(rfc: str, clabe: str) -> tuple[str, str, str, str, str, str, str]:
    return (rfc, f'Proveedor {rfc}', '2020-01-01', 'Monterrey', clabe, 'Servicios', f'{rfc.lower()}@example.mx')


def _invoice(uuid: str, issuer: str, receiver: str, issued: str, total: float, status: str = 'vigente') -> tuple[object, ...]:
    subtotal = total / 1.16
    return (uuid, issuer, receiver, issued, subtotal, total - subtotal, total, 'Servicio', 'G03', '03', 'PUE', status)


def _plant_schemes(conn: sqlite3.Connection, seed: int, scenario: Scenario, seeds: tuple[int, ...]) -> int:
    ids, amounts = _identity(seed), _amounts(seed, seeds)
    vendors: dict[str, tuple[str, str, str, str, str, str, str]] = {}

    def add_vendor(rfc: str, clabe: str) -> None:
        vendors[rfc] = _vendor(rfc, clabe)

    if 'phantom_vendor' in scenario.schemes:
        add_vendor(ids['efos'], f'CLABE-EFOS-{seed}')
        conn.execute('INSERT INTO efos_list VALUES (?,?,?,?)', (ids['efos'], f'Proveedor {ids["efos"]}', 'definitivo', '2025-01-01'))
        conn.execute('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', _invoice(f'EFOS-{seed}', ids['efos'], ids['company'], '2026-01-03', amounts['invoice']))
    if 'round_tripping' in scenario.schemes:
        add_vendor(ids['vendor_a'], f'CLABE-A-{seed}')
        add_vendor(ids['vendor_b'], f'CLABE-B-{seed}')
        last_date = '2026-02-15' if scenario.boundary_positive else '2026-02-10'
        middle = amounts['round'] * (0.98 if scenario.boundary_positive else 0.995)
        conn.executemany('INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)', [
            (f'ROUND-{seed}-1', '2026-02-01', f'CLABE-COMP-{seed}', f'CLABE-A-{seed}', amounts['round'], 'Pago', 'SPEI'),
            (f'ROUND-{seed}-2', '2026-02-07', f'CLABE-A-{seed}', f'CLABE-B-{seed}', middle, 'Intermediación', 'SPEI'),
            (f'ROUND-{seed}-3', last_date, f'CLABE-B-{seed}', f'CLABE-COMP-{seed}', amounts['round'], 'Retorno', 'SPEI'),
        ])
    if 'kickback' in scenario.schemes:
        kick_rfc = _kick_rfc(ids, scenario)
        if kick_rfc == ids['efos']:
            shared_clabe = f'CLABE-EFOS-{seed}'
        elif kick_rfc == ids['vendor_a']:
            shared_clabe = f'CLABE-A-{seed}'
        else:
            shared_clabe = f'CLABE-KICK-{seed}'
        add_vendor(kick_rfc, shared_clabe)
        conn.execute('INSERT INTO employees VALUES (?,?,?,?,?)', (ids['employee'], 'Persona de compras', 'Compras', shared_clabe, '2020-01-01'))
        if kick_rfc != ids['efos']:
            conn.execute('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', _invoice(f'KICK-{seed}', kick_rfc, ids['company'], '2026-01-10', amounts['kick']))
    if 'threshold_splitting' in scenario.schemes:
        add_vendor(ids['split'], f'CLABE-SPLIT-{seed}')
        total = 45_000.0 if scenario.boundary_positive else 48_000.0
        dates = ('2026-03-01', '2026-03-07', '2026-03-15') if scenario.boundary_positive else ('2026-03-02', '2026-03-06', '2026-03-11')
        conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', [
            _invoice(f'SPLIT-{seed}-{index}', ids['split'], ids['company'], issued, total)
            for index, issued in enumerate(dates, start=1)
        ])
    ledger_id = 1
    if 'revenue_inflation' in scenario.schemes:
        uuid = f'REVENUE-{seed}'
        conn.execute('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', _invoice(uuid, ids['company'], f'CLIENT{seed}', '2026-04-01', amounts['revenue'], 'cancelado'))
        conn.executemany('INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?)', [
            (ledger_id, '2026-04-01', '4000', 'Ingresos', 0, amounts['revenue'], 'Ingreso registrado', uuid, 'CC-01', 'Revisor'),
            (ledger_id + 1, '2026-04-01', '1100', 'Clientes', amounts['revenue'], 0, 'Cuenta cliente', uuid, 'CC-01', 'Revisor'),
        ])
        ledger_id += 2
    if vendors:
        conn.executemany('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', vendors.values())
    return ledger_id


def _plant_decoys(conn: sqlite3.Connection, seed: int, count: int, ledger_id: int) -> None:
    """Plant the first ``count`` stable near-misses from a ten-case catalog."""
    token, company = str(seed), f'COMP{seed}'
    if count >= 1:
        issuer, uuid, amount = f'REVSAFE{token}', f'REVSAFE-{token}', 75_000.0
        conn.execute('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', _invoice(uuid, issuer, f'CLIENT-R-{token}', '2026-05-01', amount, 'cancelado'))
        conn.executemany('INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?)', [
            (ledger_id, '2026-05-01', '4000', 'Ingresos', 0, amount, 'Ingreso registrado', uuid, 'CC-02', 'Revisor'),
            (ledger_id + 1, '2026-05-01', '1100', 'Clientes', amount, 0, 'Cuenta cliente', uuid, 'CC-02', 'Revisor'),
            (ledger_id + 2, '2026-05-02', '4000', 'Ingresos', amount, 0, 'Reversa completa de ingreso', uuid, 'CC-02', 'Revisor'),
            (ledger_id + 3, '2026-05-02', '1100', 'Clientes', 0, amount, 'Reversa de cuenta cliente', uuid, 'CC-02', 'Revisor'),
        ])
    if count >= 2:
        rfc = f'TWOINV{token}'
        conn.execute('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', _vendor(rfc, f'CLABE-TWO-{token}'))
        conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', [
            _invoice(f'TWO-{token}-1', rfc, company, '2026-06-01', 48_000.0),
            _invoice(f'TWO-{token}-2', rfc, company, '2026-06-10', 48_000.0),
        ])
    if count >= 3:
        a, b = f'LATEA{token}', f'LATEB{token}'
        conn.executemany('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', [_vendor(a, f'LATE-A-{token}'), _vendor(b, f'LATE-B-{token}')])
        conn.executemany('INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)', [
            (f'LATE-{token}-1', '2026-01-01', f'LATE-COMP-{token}', f'LATE-A-{token}', 90_000.0, 'Pago', 'SPEI'),
            (f'LATE-{token}-2', '2026-01-07', f'LATE-A-{token}', f'LATE-B-{token}', 90_000.0, 'Intermediación', 'SPEI'),
            (f'LATE-{token}-3', '2026-01-16', f'LATE-B-{token}', f'LATE-COMP-{token}', 90_000.0, 'Retorno', 'SPEI'),
        ])
    if count >= 4:
        a, b = f'VARA{token}', f'VARB{token}'
        conn.executemany('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', [_vendor(a, f'VAR-A-{token}'), _vendor(b, f'VAR-B-{token}')])
        conn.executemany('INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)', [
            (f'VAR-{token}-1', '2026-07-01', f'VAR-COMP-{token}', f'VAR-A-{token}', 100_000.0, 'Pago', 'SPEI'),
            (f'VAR-{token}-2', '2026-07-04', f'VAR-A-{token}', f'VAR-B-{token}', 97_900.0, 'Intermediación', 'SPEI'),
            (f'VAR-{token}-3', '2026-07-07', f'VAR-B-{token}', f'VAR-COMP-{token}', 100_000.0, 'Retorno', 'SPEI'),
        ])
    if count >= 5:
        rfc = f'SPACED{token}'
        conn.execute('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', _vendor(rfc, f'SPACED-{token}'))
        conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', [
            _invoice(f'SPACED-{token}-{index}', rfc, company, issued, 48_000.0)
            for index, issued in enumerate(('2026-01-01', '2026-03-05', '2026-05-10'), start=1)
        ])
    if count >= 6:
        rfc = f'BELOW{token}'
        conn.execute('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', _vendor(rfc, f'BELOW-{token}'))
        conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', [
            _invoice(f'BELOW-{token}-{index}', rfc, company, f'2026-08-0{index}', 44_999.0)
            for index in range(1, 4)
        ])
    if count >= 7:
        rfc = f'ATLIMIT{token}'
        conn.execute('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', _vendor(rfc, f'LIMIT-{token}'))
        conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', [
            _invoice(f'LIMIT-{token}-{index}', rfc, company, f'2026-08-1{index}', 50_000.0)
            for index in range(1, 4)
        ])
    if count >= 8:
        rfc = f'CLEAREFOS{token}'
        conn.execute('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', _vendor(rfc, f'CLEAR-{token}'))
        conn.execute('INSERT INTO efos_list VALUES (?,?,?,?)', (rfc, f'Proveedor {rfc}', 'desvirtuado', '2025-01-01'))
        conn.execute('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', _invoice(f'CLEAR-{token}', rfc, company, '2026-09-01', 65_000.0))
    if count >= 9:
        rfc, employee = f'BANKLIKE{token}', f'BANKEMP{token}'
        conn.execute('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', _vendor(rfc, f'BANK-{token}-0001'))
        conn.execute('INSERT INTO employees VALUES (?,?,?,?,?)', (employee, 'Empleado bancario', 'Compras', f'BANK-{token}-9999', '2020-01-01'))
        conn.execute('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', _invoice(f'BANKLIKE-{token}', rfc, company, '2026-09-02', 66_000.0))
    if count >= 10:
        a, b = f'ORDERA{token}', f'ORDERB{token}'
        conn.executemany('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', [_vendor(a, f'ORDER-A-{token}'), _vendor(b, f'ORDER-B-{token}')])
        conn.executemany('INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)', [
            (f'ORDER-{token}-1', '2026-10-10', f'ORDER-COMP-{token}', f'ORDER-A-{token}', 88_000.0, 'Pago', 'SPEI'),
            (f'ORDER-{token}-2', '2026-10-05', f'ORDER-A-{token}', f'ORDER-B-{token}', 88_000.0, 'Intermediación anterior', 'SPEI'),
            (f'ORDER-{token}-3', '2026-10-12', f'ORDER-B-{token}', f'ORDER-COMP-{token}', 88_000.0, 'Retorno', 'SPEI'),
        ])


def _create_benchmark_estate(path: Path, seed: int, allowed_seeds: tuple[int, ...]) -> None:
    scenario, partition_seeds = _scenario(seed)
    if partition_seeds != allowed_seeds:
        raise ValueError('seed no pertenece a la partición declarada.')
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        ledger_id = _plant_schemes(conn, seed, scenario, partition_seeds)
        _plant_decoys(conn, seed, scenario.decoy_count, ledger_id)
        conn.commit()
    finally:
        conn.close()


def create_tuning_estate(path: Path, seed: int) -> None:
    """Create a development-only estate; never report it as held-out."""
    _create_benchmark_estate(path, seed, TUNING_SEEDS)


def create_held_out_estate(path: Path, seed: int) -> None:
    """Create a reserved estate for final local measurement."""
    _create_benchmark_estate(path, seed, HELD_OUT_SEEDS)
