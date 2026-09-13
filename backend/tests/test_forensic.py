import base64
from datetime import date, timedelta
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.forensic import run_forensic_audit
from evaluation.benchmark import HELD_OUT_SEEDS, TUNING_SEEDS, create_held_out_estate, create_tuning_estate, expected_findings


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


def estate(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executescript('''
    INSERT INTO vendors VALUES ('EFOS1','EFOS SA','2020-01-01','A','111','Servicios','e@x.mx');
    INSERT INTO vendors VALUES ('SPLIT1','Split SA','2020-01-01','B','222','Servicios','s@x.mx');
    INSERT INTO vendors VALUES ('VENDORA','Proveedor A','2020-01-01','C','A','Servicios','a@x.mx');
    INSERT INTO vendors VALUES ('VENDORB','Proveedor B','2020-01-01','D','B','Servicios','b@x.mx');
    INSERT INTO employees VALUES ('EMP:1','Ana','Compras','111','2020-01-01');
    INSERT INTO efos_list VALUES ('EFOS1','EFOS SA','definitivo','2025-01-01');
    INSERT INTO invoices VALUES ('EF-1','EFOS1','COMPANY','2026-01-01',100,16,116,'x','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('SP-1','SPLIT1','COMPANY','2026-01-02',42000,6720,48720,'x','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('SP-2','SPLIT1','COMPANY','2026-01-03',42000,6720,48720,'x','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('SP-3','SPLIT1','COMPANY','2026-01-04',42000,6720,48720,'x','G03','03','PUE','vigente');
    INSERT INTO invoices VALUES ('REV-1','COMPANY','CLIENT','2026-01-31',100,16,116,'x','G03','03','PUE','cancelado');
    INSERT INTO ledger VALUES (1,'2026-01-31','4000','Ingresos',0,116,'Ingreso','REV-1','CC','Ana');
    INSERT INTO ledger VALUES (2,'2026-01-31','1100','Clientes',116,0,'Cliente','REV-1','CC','Ana');
    INSERT INTO bank_txns VALUES ('B1','2026-01-01','COMP','A',100,'x','SPEI');
    INSERT INTO bank_txns VALUES ('B2','2026-01-02','A','B',100,'x','SPEI');
    INSERT INTO bank_txns VALUES ('B3','2026-01-03','B','COMP',100,'x','SPEI');
    ''')
    conn.commit(); conn.close()


def test_all_forensic_detectors_and_upload_contract(tmp_path):
    path = tmp_path / 'estate.db'
    estate(path)
    submission = run_forensic_audit(str(path), 2026)
    assert {finding.scheme_type for finding in submission.findings} == {
        'phantom_vendor', 'kickback', 'round_tripping', 'threshold_splitting', 'revenue_inflation',
    }
    assert all(len(finding.exhibits) >= 3 and finding.peso_amount > 0 for finding in submission.findings)
    with TestClient(app) as client:
        preflight = client.post('/audit/preflight', json={'estate_path': str(path), 'seed': 2026})
        assert preflight.status_code == 200
        assert preflight.json()['ready'] is True
        assert preflight.json()['tables']['invoices'] == 5
        assert len(preflight.json()['estate_sha256']) == 64
        uploaded = client.post('/audit/upload', json={
            'estate_base64': base64.b64encode(path.read_bytes()).decode(), 'seed': 2026,
        })
        assert uploaded.status_code == 200
        assert len(uploaded.json()['findings']) == 5
        upload_preflight = client.post('/audit/preflight/upload', json={
            'estate_base64': base64.b64encode(path.read_bytes()).decode(), 'seed': 2026,
        })
        assert upload_preflight.status_code == 200
        assert upload_preflight.json()['tables']['bank_txns'] == 3
        case_file = client.get('/audit/case-file')
        assert case_file.status_code == 200 and '```mermaid' in case_file.text and 'Adversarial review' in case_file.text
        demo = client.post('/audit/demo', json={'seed': 2026})
        assert demo.status_code == 200
        assert {item['scheme_type'] for item in demo.json()['findings']} == {
            'phantom_vendor', 'kickback', 'round_tripping', 'threshold_splitting', 'revenue_inflation',
        }


def test_conservative_rules_close_decoys_instead_of_accusing(tmp_path):
    path = tmp_path / 'decoys.db'
    estate(path)
    conn = sqlite3.connect(path)
    conn.executescript('''
        UPDATE efos_list SET status='presunto' WHERE rfc='EFOS1';
        INSERT INTO vendors VALUES ('DECOY','Proveedor ordinario','2020-01-01','E','333','Servicios','d@x.mx');
        INSERT INTO invoices VALUES ('D-1','DECOY','COMPANY','2024-01-01',42000,6720,48720,'x','G03','03','PUE','vigente');
        INSERT INTO invoices VALUES ('D-2','DECOY','COMPANY','2025-01-01',42000,6720,48720,'x','G03','03','PUE','vigente');
        INSERT INTO invoices VALUES ('D-3','DECOY','COMPANY','2026-01-01',42000,6720,48720,'x','G03','03','PUE','vigente');
        DELETE FROM bank_txns;
        INSERT INTO bank_txns VALUES ('LATE-1','2026-01-01','COMP','A',100,'x','SPEI');
        INSERT INTO bank_txns VALUES ('LATE-2','2026-02-01','A','B',100,'x','SPEI');
        INSERT INTO bank_txns VALUES ('LATE-3','2026-03-01','B','COMP',100,'x','SPEI');
        UPDATE ledger SET account_code='1100', account_name='Clientes', credit=0, debit=116, description='Ajuste de cliente' WHERE invoice_uuid='REV-1';
    ''')
    conn.commit()
    conn.close()

    submission = run_forensic_audit(str(path), 2026)
    by_scheme = {finding.scheme_type: finding for finding in submission.findings}
    assert by_scheme['phantom_vendor'].confidence == 'probable'
    assert 'round_tripping' not in by_scheme
    assert 'revenue_inflation' not in by_scheme
    closed = {(lead.entity, lead.signal) for lead in submission.leads_not_pursued}
    assert ('RFC:DECOY', 'threshold_splitting') in closed
    assert ('RFC:COMPANY', 'revenue_inflation') in closed


def test_held_out_benchmark_estates_have_only_the_planted_findings(tmp_path):
    for seed in HELD_OUT_SEEDS:
        path = tmp_path / f'{seed}.db'
        create_held_out_estate(path, seed)
        predicted = {(finding.scheme_type, tuple(sorted(finding.entities))) for finding in run_forensic_audit(str(path), seed).findings}
        assert predicted == expected_findings(seed)


def test_tuning_and_held_out_estates_are_disjoint(tmp_path):
    tuning = tmp_path / 'tuning.db'
    held_out = tmp_path / 'held-out.db'
    create_tuning_estate(tuning, TUNING_SEEDS[0])
    create_held_out_estate(held_out, HELD_OUT_SEEDS[0])
    assert expected_findings(TUNING_SEEDS[0]).isdisjoint(expected_findings(HELD_OUT_SEEDS[0]))


def test_malformed_optional_values_do_not_crash_or_create_a_finding(tmp_path):
    path = tmp_path / 'imperfect.db'
    estate(path)
    conn = sqlite3.connect(path)
    conn.executescript("""
        UPDATE invoices SET total='not-a-number' WHERE uuid='EF-1';
        UPDATE invoices SET issue_date='not-a-date' WHERE uuid='SP-2';
        UPDATE bank_txns SET date='not-a-date' WHERE txn_id='B2';
    """)
    conn.commit()
    conn.close()
    submission = run_forensic_audit(str(path), 2026)
    schemes = {finding.scheme_type for finding in submission.findings}
    assert 'phantom_vendor' not in schemes
    assert 'kickback' not in schemes
    assert 'round_tripping' not in schemes
    assert 'threshold_splitting' not in schemes
    assert 'revenue_inflation' in schemes


def test_submission_packager_writes_a_reproducible_manifest(tmp_path):
    estate_path = tmp_path / 'estate.db'
    output = tmp_path / 'package'
    estate(estate_path)
    backend_root = Path(__file__).resolve().parents[1]
    result = subprocess.run([
        sys.executable, str(backend_root / 'scripts' / 'run_submission.py'), str(estate_path),
        '--seed', '2026', '--output', str(output),
    ], cwd=backend_root, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['seed'] == 2026
    assert manifest['finding_count'] == 5
    assert len(manifest['estate_sha256']) == 64
    assert manifest['preflight']['ready'] is True
    assert manifest['preflight']['tables']['invoices'] == 5
    assert manifest['official_format_validation']['executed'] is False
    assert (output / 'submission.json').is_file()
    assert (output / 'case_file.md').is_file()


def test_large_population_of_spaced_near_threshold_invoices_is_not_a_finding(tmp_path):
    path = tmp_path / 'volume.db'
    estate(path)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO vendors VALUES ('VOLUME','Proveedor de alto volumen','2020-01-01','E','999','Servicios','v@x.mx')")
    start = date(2020, 1, 1)
    rows = []
    for index in range(2_000):
        issued = start + timedelta(days=index * 30)
        rows.append((f'VOL-{index}', 'VOLUME', 'COMPANY', issued.isoformat(), 42_000, 6_720, 48_720, 'Servicio periódico', 'G03', '03', 'PUE', 'vigente'))
    conn.executemany('INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    conn.commit()
    conn.close()
    submission = run_forensic_audit(str(path), 2026)
    splitting = [finding for finding in submission.findings if finding.scheme_type == 'threshold_splitting']
    assert [finding.entities for finding in splitting] == [['RFC:SPLIT1']]
    assert ('RFC:VOLUME', 'threshold_splitting') in {(lead.entity, lead.signal) for lead in submission.leads_not_pursued}


def test_same_estate_and_seed_produce_the_same_audit_evidence(tmp_path):
    path = tmp_path / 'repeatable.db'
    estate(path)
    first = run_forensic_audit(str(path), 2026)
    second = run_forensic_audit(str(path), 2026)
    assert first.model_dump(exclude={'run_metadata'}) == second.model_dump(exclude={'run_metadata'})
    assert first.run_metadata.llm_calls == second.run_metadata.llm_calls == 0
    assert first.run_metadata.mxn_cost == second.run_metadata.mxn_cost == 0
