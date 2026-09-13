# Plan funcional local para resolver el dataset forense

## Resultado esperado

Una persona entrega una SQLite compatible con el esquema del reto y ejecuta un
solo comando local. El sistema valida el archivo, encuentra únicamente señales
sostenibles con registros, genera un expediente y deja un paquete reproducible
para revisar o enviar.

```text
estate.db
  -> preflight de integridad
  -> índice de evidencia SQLite (solo lectura)
  -> reglas por esquema y validación adversarial
  -> submission.json + Case File + manifest
  -> validador oficial
```

No se entrena ni se ajusta un modelo para decidir acusaciones. El dataset se
resuelve con consultas y reglas deterministas; una narrativa opcional solo puede
describir hallazgos que ya pasaron las validaciones.

## Flujo natural para una demo local

1. Abrir SynchroData y entrar a **Auditoría**.
2. Seleccionar `estate.db` o arrastrarlo al área de carga.
3. El sistema muestra una pantalla de preflight: tablas reconocidas, filas,
   periodo, nulos relevantes y hash del archivo.
4. Elegir la seed mostrada o una seed acordada y pulsar **Ejecutar auditoría**.
5. Ver el resumen: hallazgos, leads cerrados, exposición y tiempo local.
6. Abrir un finding para ver regla, entidades, rastro y exhibits.
7. Descargar `submission.json`, `case_file.md` y `manifest.json`.
8. Ejecutar o mostrar el validador oficial sobre esos mismos artefactos.

El flujo debe funcionar sin servicios externos. La UI es una interfaz del motor
local; no es una simulación que inventa resultados.

## Módulo A — contrato e ingestión SQLite

### Implementación

- Aceptar archivo `.db` por UI y ruta por CLI/API local.
- Abrirlo con URI SQLite `mode=ro`; nunca crear, modificar ni migrar tablas.
- Calcular SHA-256, tamaño y nombre del archivo antes de analizar.
- Verificar las ocho tablas requeridas y columnas mínimas.
- Rechazar SQLite corrupta, esquema incompatible y archivo superior al límite de
  carga web con mensajes accionables.

### Salida de preflight

```json
{
  "estate_sha256": "...",
  "tables": {"invoices": 0, "ledger": 0, "bank_txns": 0},
  "period": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "quality_warnings": ["..."],
  "ready": true
}
```

### Criterio de aceptación

- Una base válida se abre sin escritura.
- Una tabla o columna faltante detiene la ejecución antes de generar findings.
- Hash y conteos visibles coinciden con la SQLite procesada.

## Módulo B — perfil de calidad del dataset

Antes de correr detectores se construye un perfil que no acusa entidades:

| Revisión | Tablas | Acción ante problema |
|---|---|---|
| Tipos y nulos | invoices, ledger, bank_txns | Ignorar fila inválida para esa regla y registrar warning. |
| Duplicados lógicos | invoices, bank_txns, ledger | Evitar contar dos veces; conservar IDs en el diagnóstico. |
| Fechas | invoices, bank_txns, ledger | Excluir de reglas temporales si no son ISO válidas. |
| Montos | invoices, bank_txns, ledger | Excluir monto no positivo/no numérico de conciliación. |
| Relaciones | RFC, CLABE, invoice_uuid | Cerrar como lead si no existe vínculo suficiente. |
| Cobertura | todas | Informar tablas vacías o periodos incompletos. |

El perfil se incluye en el Case File como límite metodológico, no como finding.

## Módulo C — capa canónica de evidencia

Crear índices internos en memoria, ordenados y deterministas:

- `invoice_by_uuid`, `invoices_by_issuer`, `invoices_by_receiver`.
- `vendor_by_rfc`, `vendor_by_clabe`, `employee_by_clabe`.
- `ledger_by_invoice_uuid`.
- Grafo de transferencias `from_clabe -> to_clabe`, ordenado por fecha e ID.

Cada detector consume esos índices y emite solo referencias reales:

```text
finding
  -> entities con RFC:/EMP:
  -> exhibits EX-### con tabla + record_id existentes
  -> peso_amount conciliable contra exhibits monetarios
  -> confidence proven | probable
```

No se permite fabricar RFC, CLABE, IDs de exhibit ni montos.

## Módulo D — reglas por esquema

| Esquema | Señal mínima | Controles anti-falso-positivo | Resultado |
|---|---|---|---|
| `phantom_vendor` | RFC proveedor con factura y estatus EFOS. | `definitivo` es proven; `presunto` es probable. | Exhibits: invoice + EFOS + vendor. |
| `kickback` | Proveedor facturado comparte CLABE exacta con empleado. | Exigir CLABE no vacía y factura monetaria válida. | Exhibits: invoice + vendor + employee. |
| `round_tripping` | Ciclo bancario cerrado con importes equivalentes en <=14 días. | RFC verificable por vendor/invoice; excluir ciclo tardío o de montos dispares. | Tres transfers y money trail. |
| `threshold_splitting` | Tres facturas de MXN 45k–<50k al mismo emisor en <=14 días. | Compras separadas se cierran como lead. | Facturas de la ventana exacta. |
| `revenue_inflation` | Factura cancelada con crédito de ingreso sin reversa. | Excluir pólizas sin ingreso o reversadas. | Invoice + dos asientos. |

Toda regla debe ser configurable como constantes documentadas, no una inferencia
oculta de un modelo.

## Módulo E — challenger y clasificación de resultados

Después de detectar, un validador adversarial rechaza el finding si falla uno de
estos controles:

- Menos de tres exhibits.
- Entidad sin prefijo o sin relación documentada.
- Peso sin evidencia monetaria conciliable dentro de 2%.
- Fecha/monto corrupto usado como soporte.
- Evidencia repetida que no agrega corroboración.

Si falla, se transforma en `leads_not_pursued` con señal, razón, consultas
realizadas y responsable de cierre. Esto hace natural explicar por qué el motor
**no** acusó algo parecido a un fraude.

## Módulo F — evaluación sin contaminar el motor

Separar físicamente:

```text
backend/app/           # motor: no conoce etiquetas de evaluación
backend/evaluation/    # generadores, etiquetas, métricas y resultados locales
```

Crear dos particiones:

- **Tuning:** seeds permitidos para modificar reglas.
- **Held-out:** cinco seeds reservados; no se cambian reglas después de medirlos
  sin registrar una nueva versión.

Cada held-out combina los cinco esquemas con decoys: compras periódicas válidas,
ciclos tardíos, importes desiguales, cancelaciones reversadas, RFC/CLABE
incompletos y datos fuera de orden.

`results.csv` por seed incluye `true_positive`, `false_positive`,
`false_negative`, `precision`, `recall` y una nota de causa cuando haya error.

## Módulo G — paquete local de entrega

Comando objetivo:

```bash
cd backend
.venv/bin/python scripts/run_submission.py /ruta/estate.db \
  --seed 2026 \
  --output /tmp/forensic-package \
  --validator /ruta/validate_format.py
```

Salida:

```text
forensic-package/
  submission.json
  case_file.md
  manifest.json
  validator-output.txt
```

`manifest.json` conserva hash, tamaño, seed, versión de reglas, número de
hallazgos/leads, costo, tiempo y resultado del validador. Si el directorio ya
contiene artefactos, el comando se detiene salvo que se use `--overwrite`.

## Módulo H — UX, pruebas y demo final

### Casos UI obligatorios

- Carga real de la demo `.db` y de una SQLite incompatible.
- Archivo mayor al límite web.
- Backend no disponible y mensaje recuperable.
- Demo de cinco esquemas, lead cerrado y descargas.
- Vista desktop y 390 px móvil, sin hidratación, recorte ni controles tapados.

### Pruebas automáticas mínimas

- Una prueba por detector positivo.
- Un decoy negativo por detector.
- Base con valores nulos/no numéricos/fechas inválidas.
- Volumen alto de facturas fuera de la ventana.
- Misma SQLite + seed produce mismos facts y exhibits.
- E2E: Auditoría -> demo/carga -> finding -> lead -> exportación.
- Validador oficial PASS para el paquete demo.

## Secuencia de implementación

1. Completar preflight y mostrarlo en CLI/UI.
2. Añadir deduplicación lógica y warnings de calidad.
3. Endurecer y medir detectores con casos mezclados held-out.
4. Integrar carga real de `.db` con backend local en la E2E.
5. Ejecutar paquete desde un clon limpio sin red.
6. Ensayar presentación con demo y archivo alterno inválido.

## Definición de terminado

El proyecto queda listo para entregar cuando una persona ajena puede, desde un
clon limpio y sin red: ejecutar el backend y frontend localmente, cargar una
SQLite, entender qué se revisó, distinguir hallazgos de leads, descargar el
expediente, reproducirlo con hash/seed y obtener PASS del validador oficial.
