"""Independent, reproducible estates used only to measure the local audit engine.

This module owns its schema, planted patterns and labels. The production API
never imports it, so the evaluator cannot influence a real audit decision.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


BENCHMARK_VERSION = '2026.09.12.1'
TUNING_SEEDS = (271, 509, 761)
HELD_OUT_SEEDS = (104729, 130363, 155921, 196613, 209759)

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


def _identity(seed: int) -> dict[str, str]:
    token = str(seed)
    return {
        'company': f'COMP{token}', 'efos': f'EFOS{token}', 'split': f'SPLIT{token}',
        'vendor_a': f'VENDA{token}', 'vendor_b': f'VENDB{token}', 'employee': f'E{token}',
        'safe': f'SAFE{token}', 'noise_a': f'NOISEA{token}', 'noise_b': f'NOISEB{token}',
    }


def expected_findings(seed: int) -> set[tuple[str, tuple[str, ...]]]:
    """Labels are authored from planted cases, not read from the audit output."""
    ids = _identity(seed)
    return {
        ('phantom_vendor', (f"RFC:{ids['efos']}",)),
        ('kickback', tuple(sorted((f"RFC:{ids['efos']}", f"EMP:{ids['employee']}")))),
        ('round_tripping', tuple(sorted((f"RFC:{ids['vendor_a']}", f"RFC:{ids['vendor_b']}")))),
        ('threshold_splitting', (f"RFC:{ids['split']}",)),
        ('revenue_inflation', (f"RFC:{ids['company']}",)),
    }


def _create_benchmark_estate(path: Path, seed: int, partition_seeds: tuple[int, ...]) -> None:
    """Build a standalone estate with five positives and four negative controls."""
    if seed not in partition_seeds:
        raise ValueError('seed no pertenece a la partición declarada.')
    ids = _identity(seed)
    offset = partition_seeds.index(seed) + 1
    invoice_total = 100_000.0 + offset * 1_000
    split_total = 48_100.0 + offset * 100
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany('INSERT INTO vendors VALUES (?,?,?,?,?,?,?)', [
            (ids['efos'], 'Servicios sujetos a revisión', '2020-01-01', 'Monterrey', f'CLABE-EFOS-{seed}', 'Consultoría', 'efos@example.mx'),
            (ids['split'], 'Proveedor de compras repetidas', '2021-01-01', 'Monterrey', f'CLABE-SPLIT-{seed}', 'Mantenimiento', 'split@example.mx'),
            (ids['vendor_a'], 'Intermediario A', '2021-01-01', 'Monterrey', f'CLABE-A-{seed}', 'Servicios', 'a@example.mx'),
            (ids['vendor_b'], 'Intermediario B', '2021-01-01', 'Monterrey', f'CLABE-B-{seed}', 'Servicios', 'b@example.mx'),
            (ids['safe'], 'Proveedor ordinario', '2020-01-01', 'Monterrey', f'CLABE-SAFE-{seed}', 'Servicios', 'safe@example.mx'),
            (ids['noise_a'], 'Intermediario normal A', '2020-01-01', 'Monterrey', f'CLABE-NOISE-A-{seed}', 'Servicios', 'noisea@example.mx'),
            (ids['noise_b'], 'Intermediario normal B', '2020-01-01', 'Monterrey', f'CLABE-NOISE-B-{seed}', 'Servicios', 'noiseb@example.mx'),
        ])
        conn.execute('INSERT INTO employees VALUES (?,?,?,?,?)', (ids['employee'], 'Persona de compras', 'Compras', f'CLABE-EFOS-{seed}', '2020-01-01'))
        conn.execute('INSERT INTO efos_list VALUES (?,?,?,?)', (ids['efos'], 'Servicios sujetos a revisión', 'definitivo', '2025-01-01'))
        invoices = [
            (f'EFOS-{seed}', ids['efos'], ids['company'], '2026-01-03', invoice_total / 1.16, invoice_total - invoice_total / 1.16, invoice_total, 'Consultoría', 'G03', '03', 'PUE', 'vigente'),
            (f'SPLIT-{seed}-1', ids['split'], ids['company'], '2026-03-02', split_total / 1.16, split_total - split_total / 1.16, split_total, 'Mantenimiento', 'G03', '03', 'PUE', 'vigente'),
            (f'SPLIT-{seed}-2', ids['split'], ids['company'], '2026-03-06', split_total / 1.16, split_total - split_total / 1.16, split_total, 'Mantenimiento', 'G03', '03', 'PUE', 'vigente'),
            (f'SPLIT-{seed}-3', ids['split'], ids['company'], '2026-03-11', split_total / 1.16, split_total - split_total / 1.16, split_total, 'Mantenimiento', 'G03', '03', 'PUE', 'vigente'),
            (f'REV-{seed}', ids['company'], f'CLIENT{seed}', '2026-04-01', invoice_total / 1.16, invoice_total - invoice_total / 1.16, invoice_total, 'Venta', 'G03', '03', 'PUE', 'cancelado'),
            (f'SAFE-{seed}-1', ids['safe'], ids['company'], '2024-05-01', 42_000, 6_720, 48_720, 'Servicio anual', 'G03', '03', 'PUE', 'vigente'),
            (f'SAFE-{seed}-2', ids['safe'], ids['company'], '2025-05-01', 42_000, 6_720, 48_720, 'Servicio anual', 'G03', '03', 'PUE', 'vigente'),
            (f'SAFE-{seed}-3', ids['safe'], ids['company'], '2026-05-01', 42_000, 6_720, 48_720, 'Servicio anual', 'G03', '03', 'PUE', 'vigente'),
            (f'CANCEL-{seed}', ids['company'], f'CLIENTE{seed}', '2026-06-01', 10_000, 1_600, 11_600, 'Ajuste', 'G03', '03', 'PUE', 'cancelado'),
        ]
        conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', invoices)
        ledger_id = offset * 100
        conn.executemany('INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?)', [
            (ledger_id + 1, '2026-04-01', '4000', 'Ingresos', 0, invoice_total, 'Ingreso registrado', f'REV-{seed}', 'CC-01', 'Revisor'),
            (ledger_id + 2, '2026-04-01', '1100', 'Clientes', invoice_total, 0, 'Cuenta cliente', f'REV-{seed}', 'CC-01', 'Revisor'),
            (ledger_id + 3, '2026-06-01', '1100', 'Clientes', 11_600, 0, 'Ajuste de cliente', f'CANCEL-{seed}', 'CC-01', 'Revisor'),
            (ledger_id + 4, '2026-06-01', '1101', 'Bancos', 0, 11_600, 'Cobro revertido', f'CANCEL-{seed}', 'CC-01', 'Revisor'),
        ])
        conn.executemany('INSERT INTO bank_txns VALUES (?,?,?,?,?,?,?)', [
            (f'ROUND-{seed}-1', '2026-02-02', f'CLABE-COMP-{seed}', f'CLABE-A-{seed}', invoice_total, 'Pago', 'SPEI'),
            (f'ROUND-{seed}-2', '2026-02-04', f'CLABE-A-{seed}', f'CLABE-B-{seed}', invoice_total * 0.995, 'Intermediación', 'SPEI'),
            (f'ROUND-{seed}-3', '2026-02-06', f'CLABE-B-{seed}', f'CLABE-COMP-{seed}', invoice_total, 'Retorno', 'SPEI'),
            (f'NOISE-{seed}-1', '2026-01-01', f'CLABE-COMP-{seed}', f'CLABE-NOISE-A-{seed}', 100_000, 'Pago ordinario', 'SPEI'),
            (f'NOISE-{seed}-2', '2026-02-10', f'CLABE-NOISE-A-{seed}', f'CLABE-NOISE-B-{seed}', 100_000, 'Pago ordinario', 'SPEI'),
            (f'NOISE-{seed}-3', '2026-03-20', f'CLABE-NOISE-B-{seed}', f'CLABE-COMP-{seed}', 65_000, 'Devolución parcial', 'SPEI'),
        ])
        conn.commit()
    finally:
        conn.close()


def create_tuning_estate(path: Path, seed: int) -> None:
    """Create a development-only estate; do not report these metrics as held-out."""
    _create_benchmark_estate(path, seed, TUNING_SEEDS)


def create_held_out_estate(path: Path, seed: int) -> None:
    """Create a reserved evaluation estate for final local measurement."""
    _create_benchmark_estate(path, seed, HELD_OUT_SEEDS)
