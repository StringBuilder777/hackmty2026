"""Safely materialize uploaded SQLite, ZIP, or official-table CSV inputs."""
from __future__ import annotations

import csv
import io
import sqlite3
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator


MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100

TABLES: dict[str, tuple[tuple[str, str], ...]] = {
    'vendors': (
        ('rfc', 'TEXT PRIMARY KEY'), ('legal_name', 'TEXT'), ('registered_date', 'TEXT'),
        ('address', 'TEXT'), ('bank_clabe', 'TEXT'), ('category', 'TEXT'), ('contact_email', 'TEXT'),
    ),
    'invoices': (
        ('uuid', 'TEXT PRIMARY KEY'), ('issuer_rfc', 'TEXT'), ('receiver_rfc', 'TEXT'),
        ('issue_date', 'TEXT'), ('subtotal', 'REAL'), ('iva', 'REAL'), ('total', 'REAL'),
        ('concepto_text', 'TEXT'), ('uso_cfdi', 'TEXT'), ('forma_pago', 'TEXT'),
        ('metodo_pago', 'TEXT'), ('status', 'TEXT'),
    ),
    'ledger': (
        ('entry_id', 'INTEGER PRIMARY KEY'), ('date', 'TEXT'), ('account_code', 'TEXT'),
        ('account_name', 'TEXT'), ('debit', 'REAL'), ('credit', 'REAL'), ('description', 'TEXT'),
        ('invoice_uuid', 'TEXT'), ('cost_center', 'TEXT'), ('approver', 'TEXT'),
    ),
    'bank_txns': (
        ('txn_id', 'TEXT PRIMARY KEY'), ('date', 'TEXT'), ('from_clabe', 'TEXT'),
        ('to_clabe', 'TEXT'), ('amount', 'REAL'), ('reference', 'TEXT'), ('channel', 'TEXT'),
    ),
    'purchase_orders': (
        ('po_id', 'TEXT PRIMARY KEY'), ('vendor_rfc', 'TEXT'), ('date', 'TEXT'),
        ('amount', 'REAL'), ('requester', 'TEXT'), ('approver', 'TEXT'), ('description', 'TEXT'),
    ),
    'contracts': (
        ('contract_id', 'TEXT PRIMARY KEY'), ('vendor_rfc', 'TEXT'), ('start_date', 'TEXT'),
        ('value', 'REAL'), ('scope_text', 'TEXT'),
    ),
    'employees': (
        ('emp_id', 'TEXT PRIMARY KEY'), ('name', 'TEXT'), ('role', 'TEXT'),
        ('bank_clabe', 'TEXT'), ('hire_date', 'TEXT'),
    ),
    'efos_list': (
        ('rfc', 'TEXT PRIMARY KEY'), ('legal_name', 'TEXT'), ('status', 'TEXT'),
        ('publication_date', 'TEXT'),
    ),
}


def _safe_name(raw_name: str) -> str:
    normalized = raw_name.replace('\\', '/')
    path = PurePosixPath(normalized)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Nombre de archivo inseguro: {raw_name}.')
    name = path.name
    if not name or name.startswith('.'):
        raise ValueError(f'Nombre de archivo inválido: {raw_name}.')
    return name


def _expand_zip(name: str, raw: bytes) -> list[tuple[str, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir() and '__MACOSX' not in entry.filename]
            if not entries:
                raise ValueError('El ZIP está vacío.')
            total = sum(entry.file_size for entry in entries)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('El ZIP excede 64 MB después de descomprimir.')
            expanded: list[tuple[str, bytes]] = []
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise ValueError('No se aceptan ZIP cifrados.')
                if entry.compress_size == 0 and entry.file_size > 0:
                    raise ValueError('El ZIP tiene una entrada con compresión inválida.')
                if entry.compress_size and entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO:
                    raise ValueError('El ZIP excede el límite de compresión permitido.')
                expanded.append((_safe_name(entry.filename), archive.read(entry)))
            return expanded
    except zipfile.BadZipFile as exc:
        raise ValueError(f'{name} no es un ZIP válido.') from exc


def _normalize(files: list[tuple[str, bytes]]) -> tuple[str, list[tuple[str, bytes]]]:
    if not files:
        raise ValueError('No se recibió ningún archivo.')
    safe = [(_safe_name(name), raw) for name, raw in files]
    if len(safe) == 1 and Path(safe[0][0]).suffix.lower() == '.zip':
        safe = _expand_zip(*safe[0])
    lowered = [name.lower() for name, _ in safe]
    if len(lowered) != len(set(lowered)):
        raise ValueError('Hay nombres de archivo duplicados.')
    db_files = [(name, raw) for name, raw in safe if Path(name).suffix.lower() in {'.db', '.sqlite', '.sqlite3'}]
    csv_files = [(name, raw) for name, raw in safe if Path(name).suffix.lower() == '.csv']
    if db_files:
        if len(db_files) != 1 or len(safe) != 1:
            raise ValueError('El ZIP debe contener un solo archivo SQLite, sin archivos adicionales.')
        return 'sqlite', db_files
    if len(csv_files) != len(safe):
        raise ValueError('Solo se aceptan .db, .sqlite, .sqlite3, .csv o .zip.')
    by_table = {Path(name).stem.lower(): (name, raw) for name, raw in csv_files}
    missing = sorted(set(TABLES) - set(by_table))
    extra = sorted(set(by_table) - set(TABLES))
    if missing or extra:
        detail = []
        if missing:
            detail.append('faltan ' + ', '.join(f'{table}.csv' for table in missing))
        if extra:
            detail.append('no reconocidos ' + ', '.join(f'{table}.csv' for table in extra))
        raise ValueError('El conjunto CSV debe contener las ocho tablas oficiales: ' + '; '.join(detail) + '.')
    return 'csv', [by_table[table] for table in TABLES]


def _convert(value: str | None, sql_type: str, table: str, column: str, row_number: int) -> object:
    if value is None or value.strip() == '':
        return None
    stripped = value.strip()
    try:
        if sql_type.startswith('INTEGER'):
            return int(stripped)
        if sql_type == 'REAL':
            return float(stripped)
    except ValueError as exc:
        raise ValueError(f'{table}.csv fila {row_number}: {column} debe ser numérico.') from exc
    return stripped


def _load_csv_estate(path: str, files: list[tuple[str, bytes]]) -> None:
    conn = sqlite3.connect(path)
    try:
        for table, columns in TABLES.items():
            definition = ', '.join(f'{name} {sql_type}' for name, sql_type in columns)
            conn.execute(f'CREATE TABLE {table} ({definition})')
        for (table, columns), (_, raw) in zip(TABLES.items(), files, strict=True):
            try:
                text = raw.decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise ValueError(f'{table}.csv debe usar UTF-8.') from exc
            sample = text[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(io.StringIO(text, newline=''), dialect=dialect)
            expected = [name for name, _ in columns]
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)) or set(headers) != set(expected):
                raise ValueError(f'{table}.csv debe tener exactamente estas columnas: {", ".join(expected)}.')
            placeholders = ','.join('?' for _ in columns)
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise ValueError(f'{table}.csv fila {row_number}: contiene columnas adicionales.')
                values = [_convert(row[name], sql_type, table, name, row_number) for name, sql_type in columns]
                try:
                    conn.execute(f'INSERT INTO {table} VALUES ({placeholders})', values)
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f'{table}.csv fila {row_number}: clave primaria duplicada o inválida.') from exc
        conn.commit()
    finally:
        conn.close()


@contextmanager
def uploaded_estate(files: list[tuple[str, bytes]]) -> Iterator[tuple[str, str]]:
    """Yield a temporary SQLite path plus a user-facing source name."""
    kind, normalized = _normalize(files)
    with tempfile.TemporaryDirectory(prefix='forensic-upload-') as directory:
        estate_path = Path(directory) / 'estate.db'
        if kind == 'sqlite':
            raw = normalized[0][1]
            if not raw.startswith(b'SQLite format 3\x00'):
                raise ValueError('El archivo no es una base SQLite válida.')
            estate_path.write_bytes(raw)
            source_name = normalized[0][0]
        else:
            _load_csv_estate(str(estate_path), normalized)
            source_name = 'CSV bundle (8 tablas)'
        yield str(estate_path), source_name
