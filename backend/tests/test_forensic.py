import base64
import sqlite3

from fastapi.testclient import TestClient

from app.main import app
from app.services.forensic import run_forensic_audit


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
        uploaded = client.post('/audit/upload', json={
            'estate_base64': base64.b64encode(path.read_bytes()).decode(), 'seed': 2026,
        })
        assert uploaded.status_code == 200
        assert len(uploaded.json()['findings']) == 5
        case_file = client.get('/audit/case-file')
        assert case_file.status_code == 200 and '```mermaid' in case_file.text and 'Adversarial review' in case_file.text
