# Plan de implementación — Validación forense y LLM acotado

## Objetivo

Completar SynchroData Forensic Auditor para maximizar los cuatro criterios del reto:
Results, Judgment, Feasibility y Clarity. El sistema debe aceptar una SQLite
desconocida, producir acusaciones sustentadas y reproducibles, explicar también
los leads descartados y generar un paquete que funcione sin red.

El LLM es un complemento opcional. El contrato oficial no exige que valide los
hechos: exige que toda acusación se valide antes de imprimirse y que se reporten
las llamadas, el costo en MXN y el tiempo. Por ello, la decisión final permanece
en código determinista.

## Principio de autoridad

```text
SQLite solo lectura
  -> detectores deterministas
  -> candidatos, todavía no publicables
  -> validador determinista previo
  -> investigador/challenger LLM opcional
  -> validador determinista final
       -> finding validado
       -> lead_not_pursued cerrado por validator
  -> submission + Case File + recibos + validador oficial
```

El LLM nunca puede crear o modificar:

- `scheme_type`.
- Entidades, RFC, CLABE o IDs de registros.
- `peso_amount`, importes o fechas.
- Nivel de confianza.
- Exhibits o relaciones entre registros.
- Umbrales y reglas de detección.
- La decisión de publicar o descartar una acusación.

Si la respuesta del modelo es inválida, tarda demasiado, excede el presupuesto o
no hay credenciales, el motor continúa con plantillas deterministas y registra el
fallback.

## Fase 0 — Congelar contrato y corregir defectos actuales

Esta fase bloquea la integración LLM. No se debe enriquecer una conclusión que
todavía puede ser matemáticamente incorrecta.

### Cambios

1. Corregir `revenue_inflation` para restar débitos/reversas de las cuentas de
   ingreso, incluyendo reversas completas y parciales.
2. Identificar de forma determinista el RFC de la empresa auditada; no usar una
   columna no agregada junto con `min()` y `max()`.
3. Separar exposición bruta por findings de exposición única deduplicada para
   esquemas entangled.
4. Agregar exhibits de `vendors` al round-tripping para demostrar la relación
   RFC–CLABE.
5. Generar un diagrama documental para cada finding, aunque no exista una
   transferencia bancaria.
6. Estabilizar el orden de findings, leads, exhibits y pasos del trail.
7. Corregir el import de pytest para que el comando publicado en README pase sin
   `PYTHONPATH` adicional.

### Gate de salida

- Reversa completa no produce finding.
- Reversa parcial reporta únicamente el saldo no revertido si la regla lo permite.
- La empresa del demo se muestra como `COMPANY010101AAA`.
- Los cinco findings del demo tienen diagramas visibles.
- La exposición entangled no cuenta dos veces el mismo registro monetario.
- `cd backend && .venv/bin/python -m pytest -q` termina con exit code 0.

## Fase 1 — Candidato y validador determinista real

### Nuevos contratos

Agregar modelos internos que no alteran `submission_schema.json`:

```python
class CandidateFinding(Model):
    candidate_id: str
    scheme_type: ForensicScheme
    entities: list[str]
    rule_id: str
    peso_amount: Decimal
    exhibits: list[Exhibit]
    money_trail: list[MoneyTrailStep]
    detector_facts: list[VerifiedFact]

class ValidationReport(Model):
    candidate_id: str
    passed: bool
    checks: list[CheckResult]
    action: Literal['publish', 'close_as_lead']
```

Los detectores producirán `CandidateFinding`; únicamente el nuevo módulo
`backend/app/services/forensic_validation.py` podrá crear un `Finding` publicable.

### Controles obligatorios

- Todos los `record_id` existen en la SQLite.
- Cada entidad acusada está respaldada por uno o más exhibits.
- Hay al menos tres exhibits y sus IDs son únicos.
- Cada monto es finito, positivo y procede del campo monetario correcto.
- `peso_amount` reconcilia por tabla con tolerancia máxima de 2%.
- El money trail cita exhibits existentes, está conectado y es cronológico.
- No se reutiliza evidencia duplicada como corroboración independiente.
- La regla tiene un identificador normativo o de política versionado.
- La confianza es compatible con las pruebas observadas.
- La narrativa tiene como máximo 150 palabras.

Todo candidato que falle se transforma en `LeadNotPursued` con una razón concreta,
los checks ejecutados y `closed_by='validator'`.

### Gate de salida

- Alterar independientemente ID, monto, entidad o trail impide publicar el finding.
- Los límites de reconciliación 1.99% y más de 2% están probados.
- El validador oficial pasa después del gate interno, no en sustitución de él.
- La API nunca serializa un candidato no validado.

## Fase 2 — LLM forense opcional y tipado

### Separación de módulos

- `forensic.py`: detectores y orquestación principal.
- `forensic_validation.py`: única autoridad de publicación.
- `forensic_agents.py`: investigador, challenger y fallback.
- `forensic_case.py`: Case File, diagramas, exposición y conciliación.
- `llm/base.py`: protocolo de proveedor y recibos.
- `llm/prompts.py`: prompts versionados.
- `llm/replay.py`: cache content-addressed y replay sin red.

No se reutilizará directamente el `assess()` comercial. Se podrá compartir la
configuración `AI_PROVIDER`, pero el dominio, los prompts y los contratos forenses
serán independientes.

### Roles LLM

1. **Investigator:** redacta una explicación clara a partir de hechos ya
   validados y señala incertidumbres.
2. **Challenger:** intenta refutar el candidato usando códigos cerrados; no decide
   el resultado.

Para limitar costo se procesarán los candidatos en lotes ordenados. El objetivo
operativo será un máximo de dos llamadas por auditoría: una por rol.

### Respuesta tipada

```python
class InvestigatorAssessment(Model):
    candidate_id: str
    summary: str
    uncertainty_codes: list[UncertaintyCode]
    cited_exhibit_ids: list[str]

class ChallengerAssessment(Model):
    candidate_id: str
    disposition: Literal['support', 'challenge', 'insufficient']
    challenge_codes: list[ChallengeCode]
    cited_exhibit_ids: list[str]
    rationale: str
```

Los códigos del challenger serán enums, por ejemplo:

- `missing_entity_support`
- `amount_mismatch`
- `disconnected_trail`
- `possible_reversal`
- `contradictory_status`
- `duplicate_evidence`
- `weak_rule_basis`
- `none`

Un código del LLM solo tendrá efecto si el validador determinista confirma el
problema en la SQLite. Por ejemplo, `possible_reversal` no cierra un caso hasta
que código SQL encuentre la reversa.

### Entrada acotada

Cada llamada recibe solo un `EvidencePack` serializado:

- ID del candidato y tipo ya detectado.
- Alias de entidades; no se requiere enviar CLABEs completas.
- Regla versionada, monto, fechas y estados ya observados.
- IDs de exhibits, notas acotadas y resultados de checks.
- Máximo 10 candidatos, 10 exhibits y 20 facts por candidato.
- Máximo 500 caracteres por texto libre de SQLite y 64 KiB por request.

No recibe:

- La SQLite, su ruta o una conexión SQL.
- Ground truth, labels o código del benchmark.
- Credenciales.
- Herramientas de red, filesystem, shell o escritura.
- Tablas completas.

`concepto_text`, descripciones y nombres se consideran datos no confiables:
se serializan como JSON, se truncan y se etiquetan como evidencia, nunca como
instrucciones.

### Modos

```text
off     cero llamadas; narrativa y challenger deterministas
auto    usa receipt compatible; si no existe, fallback local
live    llama al proveedor y genera receipts
replay  prohíbe red y exige receipts con hashes válidos
```

El proveedor será intercambiable y reutilizará inicialmente Bedrock/Gemini, que
ya existen en el proyecto. El modelo concreto queda en configuración del backend,
no en el payload del navegador. No se añadirá otra dependencia de IA hasta que
una necesidad de demo la justifique.

### Gate de salida

- LLM encendido, apagado o caído produce exactamente los mismos findings,
  entidades, montos, confianza y exhibits.
- Un ID inventado, monto nuevo, campo extra o narrativa de 151 palabras activa
  fallback.
- Un prompt injection dentro de SQLite no cambia instrucciones ni resultados.
- Un estate sin candidatos realiza cero llamadas.
- El fallo del LLM nunca bloquea la auditoría.

## Fase 3 — Recibos, costo y replay

### Recibo por llamada

```python
class LLMCallReceipt(Model):
    role: Literal['investigator', 'challenger']
    provider: str
    model: str
    prompt_version: str
    request_sha256: str
    response_sha256: str
    input_tokens: int
    output_tokens: int
    mxn_cost: Decimal
    latency_seconds: float
    cache_hit: bool
    fallback_used: bool
```

Se cuenta cada solicitud que alcance al proveedor, aunque falle. Un cache hit no
incrementa `llm_calls`. El costo se calcula con `Decimal`, tokens reales y un
catálogo local versionado de precios y tipo de cambio fijo. La auditoría nunca
consulta precios ni tipo de cambio por red.

Invariantes:

- `sum(cost_by_role) == mxn_cost`.
- Costos y tokens nunca son negativos.
- Máximo de llamadas y presupuesto MXN configurables.
- Al exceder el presupuesto se activa fallback.

La clave de replay incluye:

```text
estate_sha256 + seed + ruleset_version + prompt_versions + provider + model + pricing_version
```

El tiempo real del replay se registra fuera del artefacto canónico. Así se puede
preservar un Case File byte-identical sin afirmar que el tiempo de ejecución es
constante.

### Gate de salida

- Replay con sockets bloqueados reproduce los mismos bytes.
- Cache corrupta falla de forma explícita en `replay` y usa fallback en `auto`.
- El manifest explica llamadas originales, llamadas de replay, cache hits y
  autoridad de decisión.
- No hay secretos ni contenido bruto sensible en receipts o logs.

## Fase 4 — Benchmark y Results con forma oficial

Separar físicamente:

```text
backend/app/          motor sin labels
backend/evaluation/   generadores, answer keys y scorer
```

Particiones:

- Tuning: seeds visibles usadas para modificar reglas.
- Held-out: mínimo cinco seeds que no se abren mientras las reglas están en
  desarrollo.
- Red-team: estates creados por un revisor distinto después de congelar reglas.

Crear entre 8 y 10 estates de reporte:

- Un estate sin fraude y diez decoys.
- Escenarios con 1, 2, 3, 4 y 5 esquemas.
- Cinco esquemas, diez decoys y entidades compartidas.
- Múltiples findings del mismo tipo.
- Reversas reales, límites 1.99%/2.01%, datos fuera de orden y relaciones
  incompletas.
- Escenarios medium/hard y combinaciones que el autor del detector no haya visto.

El scorer usará matching uno-a-uno; no convertirá predicciones a `set`. Un TP
requiere tipo, entidades, evidencia compatible y monto dentro de 2%.

`results.csv` debe usar exactamente:

```text
seed,schemes_planted,schemes_found,recall_pct,decoys_planted,
decoys_accused,false_accusation_rate_pct,peso_claimed,peso_actual,
peso_reconciles,llm_calls,mxn_cost,wall_clock_s
```

También tendrá la fila `TOTAL`. Un segundo artefacto podrá desglosar resultados
por tipo, dificultad y causa de error.

### Gate de salida

- Al menos cinco seeds realmente no usadas para tuning.
- Tuning y reporting son disjuntos y el CI lo comprueba.
- Cero ground truth o imports de evaluation en `backend/app`.
- Resultados comparados con LLM `off` y `live` son idénticos.
- CSV compatible con la plantilla oficial y claramente etiquetado como benchmark
  local, no como predicción del set secreto.

## Fase 5 — Paquete, Case File y UI

Paquete final:

```text
forensic-package/
  README.md
  submission.json
  case_file.md
  case_file.html
  manifest.json
  validation-report.json
  validator-output.txt
  results.csv
  demo/forensic-demo.db
  llm/*.receipt.json
```

El Case File debe incluir:

- Empresa, periodo, seed, costos, llamadas y modo determinista/replay.
- Resumen con exposición bruta y exposición única.
- Un diagrama visible por finding.
- Exhibits, conciliación y revisión adversarial específica.
- Leads cerrados con evidencia y responsable.
- Método, límites, recortes y reproducción.

Agregar E2E real además del mock actual:

1. Levantar FastAPI y Next.
2. Subir `forensic-demo.db` desde el selector real.
3. Comparar el SHA mostrado.
4. Ejecutar cinco detectores.
5. Abrir un finding y un lead.
6. Descargar JSON, manifest y Case File.
7. Ejecutar el validador oficial sobre la descarga.
8. Repetir en desktop y 390 px móvil.
9. Verificar SQLite inválida, esquema incompleto, archivo grande, cero findings y
   backend no disponible.

### Gate de salida

- Cero interceptaciones `/audit/*` en la suite E2E real.
- HTML y PDF/impresión abren sin red ni assets externos.
- Cinco findings del demo muestran cinco diagramas.
- Descargas pertenecen al mismo `run_id` y hash del estate.
- Otra persona puede generar el paquete con un comando desde un clon limpio.

## Fase 6 — Documentación y demostración

Crear un README específico de Track 2 con:

- Diferencia entre requisito oficial y decisión arquitectónica.
- Comando exacto local/offline.
- Tabla requisito -> código -> prueba -> artefacto.
- Seeds de tuning y reporting.
- Qué hace y qué no hace el LLM.
- Precios/versiones usados para costos.
- Diferencia entre PASS de formato y exactitud de detección.
- Límites, falsos negativos conocidos y recortes.
- Guion de cuatro minutos y preguntas de jueces.

Ensayo mínimo:

- Mostrar un constraint de código y su prueba.
- Mostrar un finding, su diagrama y conciliación.
- Mostrar un lead descartado en menos de diez segundos.
- Mostrar Results, llamadas, costo y tiempo.
- Desconectar red y ejecutar replay.
- Explicar qué se cortó y por qué.

## Organización multiagente

Para la implementación se usarán agentes `gpt-5.6-sol` con razonamiento alto:
son más económicos que el agente principal y adecuados para código, tests y
revisiones acotadas. El agente principal conserva contratos e integración.

| Agente | Propiedad exclusiva | Validación cruzada |
|---|---|---|
| A — Engine | Candidatos, reversas, exposición y hard validator | B genera casos que A no conoce. |
| B — Evaluation | Estates red-team, scorer y Results oficial | C revisa aislamiento y cálculos. |
| C — LLM | DTO, provider, receipts, costos y fault injection | A verifica invariantes factuales. |
| Principal | Modelos compartidos, Case File, API, E2E y README | Reproduce todo el gate final. |

Reglas de colaboración:

- Propiedad de archivos no superpuesta durante cada fase.
- El autor de un módulo no certifica su propia aceptación.
- Los estates red-team no se describen al agente del detector antes de congelar
  la versión.
- El principal inspecciona el diff conjunto y ejecuta las pruebas completas.
- No se marca un módulo como hecho sin evidencia de su gate.

## Orden y estimación

| Bloque | Dependencia | Esfuerzo estimado |
|---|---|---:|
| Fase 0 — correcciones actuales | Ninguna | 0.5–1 día |
| Fase 1 — hard validator | Fase 0 | 1 día |
| Fase 2 — LLM tipado | Fase 1 | 1–1.5 días |
| Fase 3 — receipts y replay | Fase 2 | 0.5–1 día |
| Fase 4 — benchmark ciego | Fase 1; paralelo con 2–3 | 1.5–2 días |
| Fase 5 — Case File y E2E | Fases 1–4 | 1–1.5 días |
| Fase 6 — README y ensayo | Fase 5 | 0.5 día |

Estimación secuencial: 6–8 días. Con tres agentes, propiedad de archivos y gates
claros: 3–4 días calendario más una integración final.

## Definición de terminado

La implementación queda lista para aspirar a los puntos máximos cuando:

1. El validador interno impide imprimir cualquier finding inválido.
2. El validador oficial devuelve PASS con el estate real.
3. LLM encendido, apagado o fallando no cambia hechos ni acusaciones.
4. Replay offline regenera el paquete byte por byte.
5. Cada finding tiene diagrama, exhibits y conciliación visible.
6. Results usa la plantilla oficial sobre cinco o más seeds verdaderamente
   held-out, con recall y falsas acusaciones.
7. El Case File responde “por qué acusó” y “por qué no acusó” sin reejecutar.
8. Una persona ajena puede clonar, ejecutar y presentar el proyecto sin ayuda.

Esto permite aspirar a la máxima puntuación, pero no garantiza el resultado sobre
los estates ocultos: esa incertidumbre debe declararse explícitamente.
