import base64
import csv
import io
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.estate_ingest import TABLES, uploaded_estate
from app.services.forensic import create_demo_estate, run_forensic_audit


def _csv_bundle(database: str) -> list[tuple[str, bytes]]:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    files: list[tuple[str, bytes]] = []
    for table, columns in TABLES.items():
        names = [name for name, _ in columns]
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(names)
        for row in conn.execute(f'SELECT * FROM {table}'):
            writer.writerow([row[name] for name in names])
        files.append((f'{table}.csv', buffer.getvalue().encode()))
    conn.close()
    return files


def _zip(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries:
            archive.writestr(name, raw)
    return buffer.getvalue()


def test_complete_csv_set_is_converted_and_analyzed(tmp_path):
    source = tmp_path / 'source.db'
    create_demo_estate(str(source))

    with uploaded_estate(_csv_bundle(str(source))) as (estate, source_name):
        submission = run_forensic_audit(estate, 2026)

    assert source_name == 'CSV bundle (8 tablas)'
    assert {finding.scheme_type for finding in submission.findings} == {
        'phantom_vendor', 'kickback', 'round_tripping', 'threshold_splitting', 'revenue_inflation',
    }


def test_zip_with_one_sqlite_is_accepted_by_upload_api(tmp_path):
    source = tmp_path / 'source.db'
    create_demo_estate(str(source))
    zipped = _zip([('nested/estate.db', source.read_bytes())])

    with TestClient(app) as client:
        preflight = client.post('/audit/preflight/upload', json={
            'estate_files': [{
                'filename': 'estate.zip',
                'content_base64': base64.b64encode(zipped).decode(),
            }],
            'seed': 2026,
        })
        audited = client.post('/audit/upload', json={
            'estate_files': [{
                'filename': 'estate.zip',
                'content_base64': base64.b64encode(zipped).decode(),
            }],
            'seed': 2026,
        })

    assert preflight.status_code == 200
    assert preflight.json()['estate_filename'] == 'estate.db'
    assert audited.status_code == 200
    assert len(audited.json()['findings']) == 5


def test_zip_with_complete_csv_bundle_is_accepted(tmp_path):
    source = tmp_path / 'source.db'
    create_demo_estate(str(source))
    zipped = _zip([(f'csv/{name}', raw) for name, raw in _csv_bundle(str(source))])

    with uploaded_estate([('tables.zip', zipped)]) as (estate, source_name):
        submission = run_forensic_audit(estate, 2026)

    assert source_name == 'CSV bundle (8 tablas)'
    assert len(submission.findings) == 5


def test_incomplete_csv_bundle_and_unsafe_zip_are_rejected(tmp_path):
    with pytest.raises(ValueError, match='ocho tablas oficiales'):
        with uploaded_estate([('invoices.csv', b'uuid\n')]):
            pass

    unsafe = _zip([('../estate.db', b'SQLite format 3\x00')])
    with pytest.raises(ValueError, match='inseguro'):
        with uploaded_estate([('unsafe.zip', unsafe)]):
            pass
