# SynchroData · HackMTY 2026

PWA en español para revisar señales de riesgo de una tienda, comparar audífonos y organizar un recorrido de compras en Monterrey. Monorepo Next.js/React/TypeScript estricto + Tailwind y FastAPI/Pydantic, con Leaflet/OpenStreetMap.

## Ejecutar

Requisitos: Node.js 22+, npm, Podman y un proveedor de `podman compose` (por ejemplo `podman-compose`). En macOS debe estar activa la máquina de Podman.

```bash
# Desde la raíz; no reemplaces .env si ya contiene tu configuración.
cp -n backend/.env.example backend/.env
podman machine start                  # solo si está apagada, en macOS
podman compose up -d --build
curl --fail http://localhost:8000/health

cd frontend
npm ci
npm run dev
```

- Aplicación: [localhost:3000](http://localhost:3000).
- Salud: [localhost:8000/health](http://localhost:8000/health).
- Contratos interactivos: [localhost:8000/docs](http://localhost:8000/docs).
- Detener backend: `podman compose down`.

Para probar la instalación y el funcionamiento sin conexión, usar la compilación de producción:

```bash
cd frontend
npm run build
npm start
```

Abrir la aplicación una vez con red antes de probar sin conexión. El service worker solo se registra en producción. Chromium muestra Instalar cuando el navegador emite el evento correspondiente; en iOS, usar Compartir → Agregar a inicio. HTTPS es necesario fuera de localhost. No se verificó instalación en un teléfono físico.

## Demo de punta a punta

En **Explorar** se elige primero una de dos tarjetas: **Producto** para revisar artículo, vendedor, alternativas y carrito; o **Sitio web** para revisar identidad, dominio, registro RDAP/WHOIS y señales de phishing. El demo web usa exclusivamente un dominio reservado `.example` y evidencia ficticia claramente etiquetada.

1. Seleccionar **Demo** y pulsar **Analizar** (la URL `https://example.com/audifonos` se completa automáticamente).
2. Revisar el riesgo y desplegar evidencias.
3. Agregar Demo Centro, Demo San Pedro y Demo Online.
4. La lista contiene tres productos y el mapa dos paradas; el producto online no genera parada.
5. Cambiar Demo Centro por Demo Obispado, quitar productos o modificar el origen; la ruta se recalcula.
6. Elegir otro origen con coordenadas, un clic en el mapa o geolocalización con permiso.
7. Recargar sin red para recuperar la lista y el análisis guardados, identificados por fecha.

Los datos demo residen exclusivamente en `backend/app/services/demo.py`: tiendas, precios, ubicaciones e inventario son **ejemplos ficticios**. La imagen generada es ilustrativa, también para la variante plata. No representa una fotografía comercial verificada. El caso demo es determinista y no requiere credenciales. Sí requiere que el backend esté activo; la ruta en auto consulta OSRM por calles reales y el mapa necesita red. Si un proveedor falla, no se reemplaza por una ruta inventada. El modo sin conexión sirve para consultar datos guardados, no para ejecutar de nuevo el demo.

## Demo de auditoría forense

El repositorio incluye un estate SQLite sintético para probar Track 2 sin datos externos. Cubre proveedor fantasma, kickback, round-tripping, fraccionamiento de umbral y revenue inflation. Generarlo y validarlo:

```bash
cd backend
.venv/bin/python scripts/create_forensic_demo.py
.venv/bin/python scripts/run_forensic_demo.py
.venv/bin/python /Users/stringbuilder/Downloads/student-materials/forensic-auditor/validate_format.py \
  --submission /tmp/forensic-demo-submission.json --estate data/forensic-demo.db
.venv/bin/python -m evaluation.run_benchmark
.venv/bin/python scripts/export_forensic_inputs.py data/forensic-demo.db --output ../deliverables/forensic-inputs
.venv/bin/python scripts/run_submission.py data/forensic-demo.db --seed 2026 --output /tmp/forensic-package \
  --validator /Users/stringbuilder/Downloads/student-materials/forensic-auditor/validate_format.py
```

En la interfaz, abrir **Auditoría** y seleccionar `backend/data/forensic-demo.db`, o pulsar **Probar caso demostrativo (5 esquemas)**. Todos sus datos son ficticios y se usan únicamente para demostración. El benchmark genera cinco estates separados con señales positivas y señuelos; deja sus métricas reproducibles en `backend/evaluation/results.csv`. Sus resultados validan esta batería local, no predicen la calificación sobre los estates ocultos de los jueces.

Para presentar sin ejecutar primero el sistema, el repositorio conserva un paquete ya generado en [`deliverables/forensic-demo`](deliverables/forensic-demo): contiene el JSON oficial, Case File, Results, manifest y la salida aprobatoria del validador. La demostración en vivo debe regenerarlo con `run_submission.py` para probar que no es un archivo preparado manualmente.

La carga desde navegador admite: un `.db`/`.sqlite`; un ZIP que contenga exactamente una base SQLite; las ocho tablas CSV oficiales seleccionadas al mismo tiempo; o un ZIP con esos ocho CSV. Los CSV deben llamarse `vendors.csv`, `invoices.csv`, `ledger.csv`, `bank_txns.csv`, `purchase_orders.csv`, `contracts.csv`, `employees.csv` y `efos_list.csv`, usar UTF-8 y conservar las columnas de `estate_schema.sql`. Hay ejemplos listos en [`deliverables/forensic-inputs`](deliverables/forensic-inputs).

Antes de ejecutar, **Verificar dataset antes de auditar** genera un preflight local: hash SHA-256, tamaño, conteos de tablas, periodo, tablas vacías, fechas e importes inválidos, posibles duplicados y relaciones huérfanas. `run_submission.py` también lo incorpora al `manifest.json`, junto con seed, versión de reglas, métricas y resultado del validador cuando se proporciona `--validator`. El paquete incluye `submission.json`, `case_file.md`, `results.csv`, `manifest.json` y la salida del validador oficial. Por seguridad no sobrescribe un paquete existente salvo con `--overwrite`.

La implementación actual funciona sin LLM y sin red. Cada detector genera un candidato interno; antes de publicar una acusación, un hard validator independiente vuelve a comprobar registros, entidades, regla, confianza, importes, conciliación por tabla, money trail e invariantes propios del esquema. Un rechazo se conserva como `lead_not_pursued` con la razón y los checks ejecutados. El diseño opcional de LLM permanece documentado en [`docs/forensic-llm-validation-plan.md`](docs/forensic-llm-validation-plan.md), pero no forma parte de la ruta evaluada ni tiene autoridad factual.

Con el mismo estate y seed, los hallazgos, leads, importes, exhibits y narrativa son deterministas. `wall_clock_seconds` es la medición real de cada ejecución y, por definición, puede variar; para un replay byte a byte debe conservarse el paquete generado en vez de volver a medir el proceso.

## Qué funciona con datos reales

- Descarga limitada de HTML público y extracción de Product/Offer en JSON-LD, título y metadatos. No ejecuta JavaScript ni evade autenticación o antibots.
- Marca, modelo, color/variante, condición, SKU/GTIN, precio, moneda, disponibilidad, descripción, galería y especificaciones **declaradas** cuando la página los publica. Cada especificación conserva la URL de la página que la declaró.
- Perfil público de tienda/vendedor: nombre y descripción estructurados, logo, dominio final, enlaces de contacto, políticas y redes sociales. Encontrar esos datos no verifica la identidad legal, el contenido de las políticas ni la reputación externa.
- Envío extraído únicamente de una tarifa estructurada inequívoca para México y en la misma moneda. Precio y envío desconocidos permanecen `null`; nunca se interpretan como cero. Otras monedas se muestran en su moneda original y se excluyen del total en MXN, sin conversión inventada.
- HTTPS, dominio final y presencia de enlaces de contacto, devoluciones y envío. Encontrar un enlace no verifica su contenido ni la identidad del vendedor.
- Comparación de precio con ofertas idénticas en la misma moneda, si se obtienen. El umbral del 40% inferior a la mediana es una señal heurística, no prueba de fraude.
- Rutas en auto con OSRM; orden por vecino más cercano y trazado real por calles. Se llama **ruta recomendada**, sin garantía de optimalidad ni tráfico en vivo.
- Lista local, selección de sucursal, agrupación de paradas, origen manual/geolocalizado y mapa sincronizado.

La antigüedad, registrador, fechas, nameservers y estados del dominio se consultan mediante RDAP, el reemplazo estandarizado de WHOIS, cuando el registro público los publica. Son señales técnicas: un dominio reciente requiere cautela, pero uno antiguo no acredita al operador ni evita que un sitio haya sido comprometido. La auditoría web también revisa redirecciones, forma del dominio, formularios sensibles, destinos externos y posibles inconsistencias con contenido gubernamental. Son heurísticas explicables, no una acusación ni una garantía. HTTPS nunca equivale a sitio seguro.

Sin `BEDROCK_MODEL_ID`, el análisis conserva el flujo determinista de extracción → RDAP → señales → búsqueda/comparación. Con Bedrock configurado, el modelo únicamente interpreta el expediente estructurado y validado; no recibe herramientas de red ni instrucciones ejecutables del sitio analizado.

## Integraciones y variables

Credenciales exclusivamente en `backend/.env`, ignorado por Git y excluido de la imagen.

| Variable | Uso | Predeterminado / pendiente |
|---|---|---|
| `BRAVE_SEARCH_API_KEY` | Búsqueda real mediante Brave Search | Sin clave: análisis funciona y explica exactamente qué falta; no se fabrican alternativas. |
| `AI_PROVIDER` | Proveedor opcional para interpretar evidencia verificada | `bedrock`; usar `gemini` sólo para la integración heredada. Nunca hace scraping ni decide hechos. |
| `BEDROCK_MODEL_ID` | Modelo de Amazon Bedrock para explicación estructurada | Requerido si `AI_PROVIDER=bedrock`; habilitar el modelo y permisos IAM en la región elegida. |
| `AWS_REGION` | Región de Bedrock | `us-east-1`. Las credenciales se obtienen del rol IAM/entorno de AWS y nunca llegan al frontend. |
| `GEMINI_API_KEY` | Explicación complementaria heredada | Opcional; nunca se expone al frontend. |
| `GEMINI_MODEL` | Modelo Gemini autorizado para la explicación | `gemini-2.5-flash` o `gemini-2.5-flash-lite`. |
| `MAX_HTML_BYTES` | Límite del HTML descomprimido por página | `8388608` (8 MiB), limitado internamente al rango de 1–16 MiB. |
| `ROUTE_PROVIDER` | `osrm` u `ors` | `osrm` |
| `OSRM_BASE_URL` | Servidor OSRM con perfil de auto | `https://router.project-osrm.org` |
| `ORS_API_KEY` | OpenRouteService para auto, a pie y bicicleta | Para caminar/ciclismo configurar además `ROUTE_PROVIDER=ors`. |
| `BRANCH_CATALOG_PATH` | Catálogo curado de sucursales dentro del contenedor | Vacío: no se inventan ubicaciones de ofertas reales. |
| `CORS_ORIGINS` | Orígenes frontend admitidos, separados por coma | Incluye `localhost` y `127.0.0.1` en puertos 3000 y 3001 para desarrollo. |
| `NEXT_PUBLIC_API_URL` | URL pública del backend, en `frontend/.env.local` | `http://localhost:8000`; no es una credencial. |

Para sucursales reales, crear `backend/data/branches.json` usando el esquema de `branches.example.json`, reemplazando TODOS los valores ilustrativos por datos y enlaces documentados. Configurar `/app/data/branches.json` como `BRANCH_CATALOG_PATH` y reconstruir el contenedor. Asociar una sucursal a una tienda no confirma inventario. Solo se conserva `confirmed` si existe un GTIN coincidente y fecha de comprobación; aun así la interfaz pide confirmar antes de salir. El MVP no dispone de un servicio de inventario ni de geocodificación automática. Con catálogo vacío no hay paradas reales verificadas.

Los adaptadores de búsqueda y rutas usan interfaces (`SearchProvider`, `RouteProvider`) reemplazables. Brave consulta hasta diez resultados y extrae sus páginas públicas; conserva hasta ocho opciones relacionadas mediante identificadores y similitud de nombre. Una opción sin precio solo se conserva cuando la página publica metadatos comerciales como marca, SKU, GTIN o condición, para evitar presentar artículos informativos como tiendas. La coincidencia idéntica exige marca/modelo/variante/condición completos, o GTIN y condición compatibles, sin contradicciones; un SKU aislado no identifica un producto entre tiendas.

Para la explicación IA en Bedrock, usar `bedrock-runtime` y `Converse`, con salida JSON validada por el backend. Recomendación operativa: Claude Sonnet 4.5 para investigaciones ambiguas y reportes completos; Claude Haiku 4.5 para el resumen normal de cada búsqueda; Amazon Nova Lite para clasificación/normalización económica y Nova Premier sólo para investigación excepcional. El modelo recibe hechos delimitados y no tiene herramientas de red: el trabajo investigable se refleja en fuentes, señales y limitaciones, no en texto persuasivo.

## API y límites

| Método | Endpoint | Resultado |
|---|---|---|
| GET | `/health` | Salud del proceso e integraciones configuradas; no prueba disponibilidad externa. |
| POST | `/analyses` | `{url, mode: "real" \| "demo", target: "product" \| "website"}` → HTTP 202, identificador y estado. |
| GET | `/analyses/{id}` | Estado real: queued, extracting, evaluating, searching, completed/error; resultado y limitaciones. |
| GET | `/analyses/{id}/alternatives` | Alternativas y estado del análisis. |
| POST | `/routes` | Origen `{lat,lng}`, hasta diez paradas `{id,name,lat,lng}`, modo driving/walking/cycling y flag demo. |

Los errores usan `{ "error": { "code": "...", "message": "..." } }`. Un proveedor de rutas caído devuelve un resultado `status=unavailable`, sin geometría, preservando las paradas. Contratos completos en OpenAPI.

- Solo HTTP/HTTPS, puertos 80/443, sin credenciales en URLs.
- Bloqueo de redes locales, privadas, reservadas, multicast y metadatos; también IPs IPv4 no canónicas y túneles IPv6.
- Validación de **todas** las IPs resueltas al conectar. Se conectan esas direcciones validadas manteniendo SNI/TLS; no existe una segunda resolución libre entre validación y conexión.
- Redirecciones manuales (máximo tres), con validación en cada salto. Sin proxies del entorno.
- HTML descomprimido hasta 8 MiB por defecto y 18 s globales; DNS hasta 4 s. Se acepta `gzip`/`deflate` y el límite se aplica después de descomprimir para contener respuestas excesivas.
- Hasta tres análisis simultáneos, doce pendientes, doscientos resultados retenidos y una hora de vida. Solicitudes POST hasta 16 KB y treinta por minuto por IP.
- Un worker de Uvicorn: los trabajos están en memoria; reiniciar pierde los análisis del servidor, pero no la lista local. No es una cola distribuida ni un servicio público endurecido para producción. Backend publicado solo en loopback por compose.

## PWA, privacidad y mapas

El service worker almacena únicamente el shell público de la aplicación y assets estáticos del mismo origen. **No** almacena respuestas API, páginas de terceros ni teselas. El navegador puede mantener su caché HTTP normal de mapas. No hay precarga masiva, descargas offline de mapas ni scraping de teselas. Se conserva atribución visible a OpenStreetMap. La aplicación respeta la política de referrer para identificar el sitio ante el servidor de teselas.

`localStorage` conserva la última lista y resultado completo por modo, con versión y fecha. Se valida su estructura al recuperar. No guarda HTML bruto ni claves. No hay sincronización entre dispositivos; borrar los datos del navegador borra la lista. La red es obligatoria para nuevas búsquedas, análisis y rutas. La ubicación solo se solicita tras pulsar el control, se envía al backend/proveedor para calcular el recorrido y no se conserva en el snapshot local.

Los servidores públicos de OSM y OSRM se usan para demostración de bajo volumen y no ofrecen un SLA para este proyecto. Antes de escalar, configurar un proveedor apropiado y revisar sus términos/cuotas:

- [Política de teselas OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/).
- [Documentación OSRM](https://project-osrm.org/docs/v5.7.0/api/).
- [OpenRouteService](https://openrouteservice.org/dev/).
- [Brave Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get).
- [Next.js y ESLint](https://nextjs.org/docs/app/api-reference/config/eslint).

## Verificación

```bash
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
# Con npm start y backend activos; Chrome instalado:
npm run test:e2e

cd ../backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Las pruebas cubren URLs/SSRF, DNS público/privado, comparación estricta, costos desconocidos, agrupación de sucursales, geometría vacía ante fallo, extracción y contratos HTTP. E2E usa el backend real en modo demo y OSRM real (requiere red), verifica 1536×1024 y 390×844, cambios de sucursal, cantidades, rutas, error de caminar sin clave, ausencia de desbordamiento y restauración al recargar offline. Esta prueba asume `ROUTE_PROVIDER=osrm` y ausencia de ORS; no usarla contra un backend de producción.

Se verificaron salud HTTP del backend en Podman, flujo demo y rutas OSRM. Brave y OpenRouteService no se probaron con credenciales reales; tampoco inventario de comercios, pagos, navegación paso a paso, instalación en dispositivo físico ni backend de producción.

## Estructura

- `frontend/src/components/`: workspace, ofertas, evidencias, lista, mapa y ruta.
- `frontend/src/lib/`: contratos TypeScript, totales, agrupación, API y persistencia.
- `frontend/public/`: manifest, service worker, iconos y producto ilustrativo.
- `backend/app/services/`: descarga segura, extracción, riesgo, búsqueda, sucursales, rutas y demo separado.
- `backend/tests/`, `frontend/tests/`: pruebas de dominio, API y recorrido.
- `docs/design-concept.png`: referencia visual generada; la implementación sustituye afirmaciones de stock del concepto por datos pendientes y muestra solo paradas seleccionadas.
