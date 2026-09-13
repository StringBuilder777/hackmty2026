# Plan de implementación y presentación — SynchroData Forensic Auditor

## Objetivo de entrega

Recibir una ruta SQLite desconocida, analizarla sin red, devolver hallazgos
auditables de los cinco esquemas requeridos y producir un expediente que un
revisor pueda verificar registro por registro. Las reglas deterministas deciden
los hechos y montos; cualquier IA se limita a redactar a partir de evidencia ya
calculada.

## Principios no negociables

- Una acusación necesita regla explícita, entidad identificable, tres exhibits y
  conciliación monetaria verificable.
- Una señal insuficiente se conserva como `lead_not_pursued`, nunca como finding.
- El mismo archivo y seed deben reproducir los mismos hallazgos y exhibits.
- Sin red no significa datos inventados: toda afirmación procede de SQLite.
- Las métricas del benchmark local demuestran robustez local; no se presentan
  como una predicción de los estates ocultos.

## Plan por módulos

| Módulo | Alcance | Evidencia de aceptación | Estado |
|---|---|---|---|
| 0. Contrato | Validar tablas/columnas del esquema, abrir SQLite en modo solo lectura y rechazar entradas malformadas; exponer preflight de hash, periodo y conteos. | Pruebas de esquema incompleto, archivo inválido y SQLite válida. | Hecho |
| 1. Motor forense | Detectar EFOS, CLABE compartida, ciclo de dinero, fraccionamiento e ingreso cancelado con reglas conservadoras. | Prueba por esquema, decoys negativos y validador oficial en PASS. | Hecho |
| 2. Evidencia | IDs de exhibit, diagramas de flujo, conciliación de pesos por tabla y leads cerrados. | Cada finding tiene mínimo 3 exhibits y conciliación dentro de 2%. | Hecho |
| 3. Reproducibilidad | Seed, costo, llamadas LLM, tiempo y prueba de dos ejecuciones iguales. | Comparación de findings/exhibits idénticos con igual estate + seed. | Hecho |
| 4. Benchmark independiente | Separar datos de ajuste de cinco estates held-out con ruido, decoys y combinaciones de esquemas. | `results.csv` con precision, recall, FP, FN y explicación de errores por seed. | Hecho |
| 5. Robustez de datos | Nulos, fechas inválidas, duplicados, montos negativos, tablas grandes y datos incompletos. | Suite de regresión; las señales débiles se cierran como leads. | En curso |
| 6. Entrega de jueces | Un comando que genere JSON, Case File, métricas, hash del estate y ejecute el validador. | Carpeta de salida autocontenida y reproducible. | Hecho |
| 7. UI y demostración | Carga `.db`, preflight, ejecución, evidencia, lead descartado, case file y exportación. | E2E desktop/móvil con respuesta auditada acotada; backend cubre carga binaria real. | Hecho |
| 8. Ensayo final | Ejecutar en un estate limpio, documentar límites y preparar demo cronometrada. | Checklist firmado y video/guion de respaldo. | Pendiente |

## Orden de ejecución recomendado

### Semana / bloque 1 — calidad antes de apariencia

1. Construir los cinco estates held-out sin reutilizar el demo como etiqueta.
2. Agregar casos mezclados: por ejemplo, EFOS + CLABE compartida + facturas
   cercanas al umbral y también variantes legítimas.
3. Registrar por seed: verdaderos positivos, falsos positivos, falsos negativos,
   precision, recall y la causa de cada error.
4. Revisar cada regla que genere un falso positivo: elevar evidencia requerida o
   degradar a lead.

**Criterio de salida:** los cinco seeds se ejecutan con un comando y el CSV se
genera sin modificar el motor durante la medición.

### Semana / bloque 2 — endurecimiento y paquete de entrega

1. Añadir pruebas de calidad de datos y volumen.
2. Crear `run_submission.py` con esta secuencia:

```text
SQLite de entrada
  -> validar esquema y hash SHA-256
  -> ejecutar auditoría con seed
  -> guardar submission.json y case_file.md
  -> validar formato y conciliaciones
  -> guardar manifest.json con versión, hash, seed y métricas
```

3. Documentar instalación mínima y ejecución offline.
4. Confirmar que el código del agente no contiene claves ni conocimiento del
   conjunto de evaluación de jueces.

**Criterio de salida:** otra persona puede clonar, instalar y generar una entrega
válida con un único comando y una SQLite.

### Semana / bloque 3 — experiencia y presentación

1. Probar carga real de archivos en navegador, incluidos errores legibles.
2. Validar visualmente escritorio y móvil: no hay contenido cortado, estilos sin
   cargar ni textos montados.
3. Añadir exportación explícita de expediente y JSON si aún no existe.
4. Ensayar demo con cronómetro y un plan B: demo SQLite incluida si el archivo
   del jurado no puede cargarse en escena.

**Criterio de salida:** demo completa en menos de cuatro minutos y evidencias
visibles sin explicar código internamente.

## Estructura del entregable final

```text
submission/
  submission.json       # contrato para el validador
  case_file.md          # expediente legible
  manifest.json         # hash, seed, versión y métricas de ejecución
  results.csv           # benchmark local held-out
  README.md             # instalación y comando único
  demo/forensic-demo.db # respaldo sintético, claramente etiquetado
```

No se incluirán secretos, datos reales ni etiquetas/respuestas de los estates
de evaluación.

## Guion de presentación (4 minutos)

### 0:00–0:30 — problema y propuesta

“Las revisiones manuales encuentran señales tarde y son difíciles de reproducir.
SynchroData convierte una SQLite en un expediente verificable: no acusa por una
corazonada, sino por una regla, registros y una conciliación.”

### 0:30–1:15 — cargar y ejecutar

Subir una base SQLite. Mostrar validación del esquema, seed y el modo offline.
Decir: “El motor abre la base en solo lectura; no necesita red ni modifica los
datos.”

### 1:15–2:30 — un caso con trazabilidad

Abrir un hallazgo de flujo circular o proveedor EFOS. Recorrer:

1. Regla activada.
2. Entidades reales involucradas.
3. Tres exhibits con IDs.
4. Diagrama de dinero.
5. Conciliación exacta del monto.

### 2:30–3:10 — control de alucinación y falsos positivos

Mostrar un lead descartado. Decir: “La IA no decide hechos ni montos. SQL
determinista encuentra evidencia; el texto solo resume esos campos. Si falta
prueba, el sistema lo cierra como lead y explica por qué.”

### 3:10–3:40 — calidad

Abrir `results.csv`: cinco seeds locales, precisión/recall y decoys. Aclarar que
son métricas reproducibles internas, no una afirmación sobre el set secreto.

### 3:40–4:00 — cierre

Exportar el Case File. “El resultado es un expediente que un auditor puede
repetir con el hash, seed y exhibits, no una caja negra.”

## Checklist antes de enviar

- [ ] La UI permite cargar una SQLite y muestra errores entendibles.
- [ ] Los cinco tipos requeridos aparecen en la demo y en pruebas separadas.
- [ ] Cada finding tiene entidades, tres exhibits y conciliación menor a 2%.
- [ ] Los decoys quedan en `leads_not_pursued` o no generan señal.
- [ ] Los cinco seeds held-out y su `results.csv` están regenerados.
- [ ] El comando único funciona desde un clon limpio y sin red.
- [ ] El validador oficial devuelve PASS para la salida generada.
- [ ] El Case File incluye encabezado, resumen, findings, leads, método y límites.
- [ ] La demo está ensayada en escritorio y móvil con el frontend recién reiniciado.
- [ ] README documenta supuestos, límites y datos sintéticos.
