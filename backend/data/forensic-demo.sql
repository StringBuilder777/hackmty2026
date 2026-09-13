-- Demonstration estate for the HackMTY 2026 Forensic Auditor track.
-- Synthetic data only. It deliberately triggers each deterministic detector.
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

-- Phantom vendor and kickback: EFOS invoice plus a shared employee CLABE.
INSERT INTO invoices VALUES ('EFOS-001','EFOS010101AAA','COMPANY010101AAA','2026-01-01',100000,16000,116000,'Consultoría','G03','03','PUE','vigente');
-- Threshold splitting: three invoices just below MXN 50,000.
INSERT INTO invoices VALUES ('SPLIT-001','SPLIT010101BBB','COMPANY010101AAA','2026-01-02',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
INSERT INTO invoices VALUES ('SPLIT-002','SPLIT010101BBB','COMPANY010101AAA','2026-01-03',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
INSERT INTO invoices VALUES ('SPLIT-003','SPLIT010101BBB','COMPANY010101AAA','2026-01-04',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
-- Decoy: same amount band, but dates too far apart to support splitting.
INSERT INTO invoices VALUES ('DECOY-001','DECOY010101AAA','COMPANY010101AAA','2025-01-02',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
INSERT INTO invoices VALUES ('DECOY-002','DECOY010101AAA','COMPANY010101AAA','2025-07-02',42000,6720,48720,'Servicio','G03','03','PUE','vigente');
-- Revenue inflation: cancellation with two unreversed revenue entries.
INSERT INTO invoices VALUES ('REV-001','COMPANY010101AAA','CLIENT010101AAA','2026-01-31',100000,16000,116000,'Venta','G03','03','PUE','cancelado');
INSERT INTO ledger VALUES (1,'2026-01-31','4000','Ingresos',0,116000,'Ingreso registrado','REV-001','CC-01','Ana Ejemplo');
INSERT INTO ledger VALUES (2,'2026-01-31','1100','Clientes',116000,0,'Cuenta cliente','REV-001','CC-01','Ana Ejemplo');
-- Round-tripping: a three-step circular SPEI path.
INSERT INTO bank_txns VALUES ('CYCLE-001','2026-01-01','COMPANY-CLABE','VENDOR-A',100000,'Salida','SPEI');
INSERT INTO bank_txns VALUES ('CYCLE-002','2026-01-02','VENDOR-A','VENDOR-B',100000,'Intermediación','SPEI');
INSERT INTO bank_txns VALUES ('CYCLE-003','2026-01-03','VENDOR-B','COMPANY-CLABE',100000,'Retorno','SPEI');
