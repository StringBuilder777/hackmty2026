"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  ArrowRight,
  Check,
  Download,
  Headphones,
  Link2,
  LocateFixed,
  MapPin,
  Navigation,
  Route as RouteIcon,
  Search,
  ShieldQuestion,
  TriangleAlert,
  WifiOff,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Analysis,
  BranchId,
  Mode,
  Point,
  Product,
  Route,
  Selection,
  Snapshot,
  Transport,
} from "@/lib/types";
import { dateLabel, groupStops } from "@/lib/shopping";
import { readSnapshot } from "@/lib/storage";
import EvidenceList from "./EvidenceList";
import ProductCard, { ProductImage } from "./ProductCard";
import ShoppingList from "./ShoppingList";
import RoutePanel from "./RoutePanel";
const ShoppingMap = dynamic(() => import("./Map"), {
  ssr: false,
  loading: () => <div className="map-loading">Cargando mapa de Monterrey…</div>,
});
const DEFAULT_ORIGIN = { lat: 25.669, lng: -100.309 };
const STAGES = [
  "queued",
  "extracting",
  "evaluating",
  "searching",
  "completed",
] as const;
const STAGE_LABELS = [
  "En cola",
  "Leyendo la página",
  "Evaluando señales",
  "Buscando alternativas",
  "Análisis listo",
];
function subscribeOnline(callback: () => void) {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}
interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}
export default function Workspace() {
  const online = useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
  const [mode, setMode] = useState<Mode>("real");
  const [url, setUrl] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [items, setItems] = useState<Selection[]>([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [ready, setReady] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [origin, setOrigin] = useState<Point>(DEFAULT_ORIGIN);
  const [originName, setOriginName] = useState("Macroplaza");
  const [transport, setTransport] = useState<Transport>("driving");
  const [picking, setPicking] = useState(false);
  const [active, setActive] = useState<BranchId | null>(null);
  const [retry, setRetry] = useState(0);
  const [routeResult, setRouteResult] = useState<{
    key: string;
    data: Route;
  } | null>(null);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [locationError, setLocationError] = useState("");
  const [manual, setManual] = useState(false);
  const generation = useRef(0);
  const alive = useRef(true);
  const stops = useMemo(() => groupStops(items), [items]);
  const routeKey = JSON.stringify({ stops, origin, transport, mode, retry });
  const route = routeResult?.key === routeKey ? routeResult.data : null;
  const orderedStops = useMemo(
    () =>
      route
        ? route.ordered_stops.map((s) => ({
            ...s,
            products: stops.find((p) => p.id === s.id)?.products,
          }))
        : stops,
    [route, stops],
  );
  useEffect(() => {
    alive.current = true;
    const timer = setTimeout(() => {
      let lastMode: Mode = "real";
      try {
        if (localStorage.getItem("buenpaso-last-mode") === "demo")
          lastMode = "demo";
      } catch {
        /* Storage may be disabled; keep the app usable. */
      }
      setMode(lastMode);
      if (lastMode === "demo") setUrl("https://example.com/audifonos");
      const snapshot = readSnapshot(lastMode);
      if (snapshot) {
        setItems(snapshot.items);
        setAnalysis(snapshot.analysis);
        setSavedAt(snapshot.savedAt);
      }
      setReady(true);
    }, 0);
    const handler = (event: Event) => {
      event.preventDefault();
      setInstall(event as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production")
      navigator.serviceWorker
        .register("/sw.js")
        .catch(() =>
          setError(
            "No fue posible activar el soporte sin conexión. Reintenta recargando.",
          ),
        );
    return () => {
      alive.current = false;
      clearTimeout(timer);
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, []);
  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => {
      try {
        const stamp = new Date().toISOString();
        const snapshot: Snapshot = {
          version: 1,
          mode,
          savedAt: stamp,
          items,
          analysis: analysis?.status === "completed" ? analysis : null,
        };
        localStorage.setItem(`buenpaso-v1-${mode}`, JSON.stringify(snapshot));
        localStorage.setItem("buenpaso-last-mode", mode);
      } catch {
        setError(
          "El navegador no pudo guardar la lista. Revisa el almacenamiento disponible.",
        );
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [items, analysis, mode, ready]);
  useEffect(() => {
    if (!online || !stops.length) return;
    let cancelled = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 21000);
    const timer = setTimeout(async () => {
      setRouteResult(null);
      try {
        const data = await api<Route>(
          "/routes",
          {
            origin,
            stops: stops.map(({ id, name, lat, lng }) => ({
              id,
              name,
              lat,
              lng,
            })),
            mode: transport,
            demo: mode === "demo",
          },
          controller.signal,
        );
        if (!controller.signal.aborted) setRouteResult({ key: routeKey, data });
      } catch {
        if (alive.current && !cancelled)
          setRouteResult({
            key: routeKey,
            data: {
              status: "unavailable",
              message:
                "No se pudo conectar con el proveedor de rutas. Reintenta.",
              coordinates: [],
              ordered_stops: stops,
              distance_m: null,
              duration_s: null,
              provider: "No disponible",
              checked_at: new Date().toISOString(),
              demo: mode === "demo",
            },
          });
      } finally {
        clearTimeout(timeout);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      clearTimeout(timeout);
      controller.abort();
    };
  }, [routeKey, origin, stops, transport, mode, online]);
  function switchMode(next: Mode) {
    if (next === mode) return;
    generation.current++;
    setRunning(false);
    setError("");
    setActive(null);
    setRouteResult(null);
    const snapshot = readSnapshot(next);
    setMode(next);
    setItems(snapshot?.items || []);
    setAnalysis(snapshot?.analysis || null);
    setSavedAt(snapshot?.savedAt || null);
    setUrl(next === "demo" ? "https://example.com/audifonos" : "");
  }
  async function analyze(event: React.FormEvent) {
    event.preventDefault();
    if (!online) return;
    const current = ++generation.current;
    setRunning(true);
    setError("");
    setAnalysis(null);
    setSavedAt(null);
    try {
      let result = await api<Analysis>("/analyses", { url, mode });
      for (let attempt = 0; attempt < 160; attempt++) {
        if (current !== generation.current || !alive.current) return;
        setAnalysis(result);
        if (result.status === "error")
          throw new Error(result.error || "No se pudo completar el análisis.");
        if (result.status === "completed") return;
        await new Promise((resolve) => setTimeout(resolve, 650));
        if (!navigator.onLine)
          throw new Error(
            "Se perdió la conexión. Tus productos guardados siguen disponibles.",
          );
        if (current !== generation.current || !alive.current) return;
        result = await api<Analysis>(`/analyses/${result.id}`);
      }
      throw new Error(
        "El análisis sigue en curso. Reintenta en unos momentos.",
      );
    } catch (cause) {
      if (current === generation.current && alive.current)
        setError(
          cause instanceof Error
            ? cause.message
            : "No se pudo conectar con FastAPI. Verifica que esté activo.",
        );
    } finally {
      if (current === generation.current && alive.current) setRunning(false);
    }
  }
  const chooseOrigin = useCallback((point: Point) => {
    setOrigin({ lat: point.lat, lng: point.lng });
    setOriginName("Punto personalizado");
    setPicking(false);
    setLocationError("");
  }, []);
  function geolocate() {
    if (!navigator.geolocation) {
      setLocationError(
        "La geolocalización no está disponible. Elige un punto manualmente.",
      );
      return;
    }
    setLocationError("Solicitando ubicación…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        chooseOrigin({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
        setOriginName("Mi ubicación");
      },
      () =>
        setLocationError(
          "No se pudo obtener permiso o ubicación. Puedes elegir el origen en el mapa o con coordenadas.",
        ),
      { timeout: 8000, maximumAge: 60000 },
    );
  }
  function add(product: Product) {
    setItems((current) =>
      current.some((item) => item.product.id === product.id) ||
      current.length >= 30
        ? current
        : [...current, { product, branchId: product.branches[0]?.id || null }],
    );
  }
  const complete = analysis?.status === "completed";
  return (
    <>
      <a href="#resultados" className="skip-link">
        Saltar a resultados
      </a>
      <header className="header">
        <Link className="brand" href="/" aria-label="BuenPaso, inicio">
          <RouteIcon size={30} />
          <span>BuenPaso</span>
        </Link>
        <nav aria-label="Principal">
          <a className="nav-active" href="#explorar">
            Explorar
          </a>
          <a href="#mi-lista">
            Mi lista
            {items.length > 0 && (
              <span className="nav-count">{items.length}</span>
            )}
          </a>
        </nav>
        <div className="header-location">
          <MapPin size={16} />
          <span>Monterrey, NL</span>
        </div>
        {install && (
          <button
            className="text-button install"
            onClick={async () => {
              await install.prompt();
              await install.userChoice;
              setInstall(null);
            }}
          >
            <Download size={15} /> Instalar
          </button>
        )}
      </header>
      <div className={`mode-bar ${mode}`}>
        <span>
          {mode === "demo" ? (
            <TriangleAlert size={14} />
          ) : (
            <ShieldQuestion size={14} />
          )}
          {mode === "demo"
            ? "Modo demo · Datos de ejemplo, no verificados."
            : "Análisis real · Evidencia disponible, sin garantías de seguridad."}
        </span>
        <div className="mode-switch" aria-label="Modo de datos">
          <button
            aria-pressed={mode === "real"}
            onClick={() => switchMode("real")}
          >
            Real
          </button>
          <button
            aria-pressed={mode === "demo"}
            onClick={() => switchMode("demo")}
          >
            Demo
          </button>
        </div>
      </div>
      {!online && (
        <div className="offline-bar" role="status">
          <WifiOff size={16} /> Sin conexión · Consulta tu lista guardada.
          Análisis y rutas requieren red.
        </div>
      )}
      <section id="explorar" className="search-section">
        <div>
          <h1>Compra con más contexto.</h1>
          <p>Revisa una tienda, compara opciones y planea tu recorrido.</p>
        </div>
        <form onSubmit={analyze} className="search-form">
          <label htmlFor="product-url" className="sr-only">
            URL de producto o tienda
          </label>
          <div className="url-field">
            <Link2 size={18} />
            <input
              id="product-url"
              type="url"
              required
              maxLength={2048}
              placeholder="Pega el enlace de un producto o tienda"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={running || !online}
            />
          </div>
          <button
            className="primary"
            type="submit"
            disabled={running || !online || !ready}
          >
            {running ? "Analizando…" : "Analizar"}
            <ArrowRight size={16} />
          </button>
        </form>
      </section>
      <main className="workspace">
        <section
          className="results"
          id="resultados"
          aria-label="Resultados y lista de compras"
        >
          {savedAt && (
            <p className="saved-note">
              Datos guardados · {dateLabel(savedAt)}. Pueden haber cambiado.
            </p>
          )}
          {error && (
            <div className="error-box" role="alert">
              <TriangleAlert size={18} />
              <p>
                {error}
                <br />
                Puedes reintentar con el botón Analizar.
              </p>
            </div>
          )}
          {running && (
            <div className="analysis-progress" role="status">
              <h2>Revisando tu enlace</h2>
              <ol>
                {STAGES.slice(0, 4).map((stage, i) => (
                  <li
                    key={stage}
                    className={
                      analysis &&
                      STAGES.indexOf(
                        analysis.status as (typeof STAGES)[number],
                      ) >= i
                        ? "current"
                        : ""
                    }
                  >
                    <span>
                      {analysis &&
                      STAGES.indexOf(
                        analysis.status as (typeof STAGES)[number],
                      ) > i ? (
                        <Check size={12} />
                      ) : (
                        i + 1
                      )}
                    </span>
                    {STAGE_LABELS[i]}
                  </li>
                ))}
              </ol>
              <small>Las etapas reflejan el estado del backend.</small>
            </div>
          )}
          {!analysis && !running && (
            <div className="welcome">
              <div className="welcome-icon">
                <Headphones size={40} strokeWidth={1.4} />
              </div>
              <h2>
                Encuentra una mejor
                <br />
                forma de comprar.
              </h2>
              <p>
                Empezamos con audífonos en Monterrey.
                <br />
                Un enlace es el primer paso.
              </p>
              <div className="welcome-steps">
                <span>
                  <ShieldQuestion size={17} /> Revisa señales
                </span>
                <span>
                  <Search size={17} /> Compara opciones
                </span>
                <span>
                  <Navigation size={17} /> Organiza paradas
                </span>
              </div>
              <button
                className="text-button"
                onClick={() => {
                  switchMode("demo");
                  setUrl("https://example.com/audifonos");
                }}
              >
                Explorar el modo demo <ArrowRight size={15} />
              </button>
              <small>
                Selecciona Demo y pulsa Analizar. Tiendas y precios ficticios.
              </small>
            </div>
          )}
          {complete && analysis.product && (
            <>
              <div className="section-heading result-label">
                <span>Resultado del análisis</span>
                <small>
                  {mode === "demo" ? "Ejemplo · " : ""}
                  {dateLabel(analysis.product.checked_at)}
                </small>
              </div>
              <div className="result-summary">
                <div className="result-overview">
                  <ProductImage product={analysis.product} online={online} />
                  <div>
                    <h2>{analysis.product.name}</h2>
                    <p>
                      {analysis.product.variant || "Variante por identificar"}
                    </p>
                    <small>{analysis.product.store}</small>
                  </div>
                </div>
                {analysis.risk && (
                  <div className="risk-box">
                    <TriangleAlert size={21} />
                    <div>
                      <strong>Riesgo: {analysis.risk.level}</strong>
                      <p>{analysis.risk.explanation}</p>
                    </div>
                  </div>
                )}
              </div>
              {analysis.risk && (
                <EvidenceList
                  evidence={analysis.risk.evidence}
                  label="Verificaciones y evidencias"
                />
              )}
              <section className="comparison">
                <div className="section-heading">
                  <h2>Compara tus opciones</h2>
                  <span>{analysis.alternatives.length} alternativas</span>
                </div>
                <p className="section-description">
                  Mismo producto, distintas tiendas. Revisa también la variante.
                </p>
                {analysis.alternatives.length === 0 && (
                  <p className="empty-notice">
                    No hay alternativas disponibles. Puedes guardar el producto
                    consultado.
                  </p>
                )}
                {(analysis.alternatives.length
                  ? analysis.alternatives
                  : [analysis.product]
                ).map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    added={items.some((item) => item.product.id === product.id)}
                    online={online}
                    onAdd={() => add(product)}
                  />
                ))}
                {analysis.limitations.length > 0 && (
                  <details className="limitations">
                    <summary>Alcance y verificaciones no disponibles</summary>
                    <ul>
                      {analysis.limitations.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </section>
            </>
          )}
          <ShoppingList
            items={items}
            active={active}
            onRemove={(id) =>
              setItems((current) =>
                current.filter((item) => item.product.id !== id),
              )
            }
            onBranch={(id, branchId) =>
              setItems((current) =>
                current.map((item) =>
                  item.product.id === id ? { ...item, branchId } : item,
                ),
              )
            }
            onFocus={setActive}
          />
          <footer className="panel-footer">
            {mode === "demo"
              ? "Demo · tiendas, precios y ubicaciones de ejemplo."
              : "Las señales orientan; confirma las condiciones antes de comprar."}
            <br />
            Tu lista se guarda en este navegador.{" "}
            <span>BuenPaso · HackMTY 2026</span>
          </footer>
        </section>
        <section
          className="map-section"
          aria-label="Mapa de tiendas en Monterrey"
        >
          <ShoppingMap
            stops={orderedStops}
            origin={origin}
            route={online ? route : null}
            online={online}
            active={active}
            picking={picking}
            onOrigin={chooseOrigin}
            onFocus={setActive}
          />
          <div className="map-controls">
            <div className="origin-control">
              <label htmlFor="origin">Origen</label>
              <div>
                <MapPin size={15} />
                <select
                  id="origin"
                  value={originName === "Macroplaza" ? "macroplaza" : "custom"}
                  onChange={(e) => {
                    if (e.target.value === "macroplaza") {
                      setOrigin(DEFAULT_ORIGIN);
                      setOriginName("Macroplaza");
                    } else setManual(true);
                  }}
                >
                  <option value="macroplaza">Macroplaza</option>
                  <option value="custom">
                    {originName === "Macroplaza"
                      ? "Elegir otro punto"
                      : originName}
                  </option>
                </select>
                <button
                  className="icon-button"
                  aria-label="Usar mi ubicación"
                  onClick={geolocate}
                >
                  <LocateFixed size={16} />
                </button>
              </div>
            </div>
            <label className="transport-control">
              Transporte
              <select
                aria-label="Modo de transporte"
                value={transport}
                onChange={(e) => setTransport(e.target.value as Transport)}
              >
                <option value="driving">Auto</option>
                <option value="walking">A pie</option>
                <option value="cycling">Bicicleta</option>
              </select>
            </label>
            <button
              className={`text-button choose-point ${picking ? "selected" : ""}`}
              onClick={() => setPicking(!picking)}
            >
              {picking ? "Toca el mapa · Cancelar" : "Elegir origen en el mapa"}
            </button>
            <button
              className="text-button coordinates-toggle"
              onClick={() => setManual(!manual)}
            >
              Coordenadas
            </button>
            {locationError && <p role="status">{locationError}</p>}
            {manual && (
              <form
                className="coordinates-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  const data = new FormData(event.currentTarget);
                  chooseOrigin({
                    lat: Number(data.get("lat")),
                    lng: Number(data.get("lng")),
                  });
                  setManual(false);
                }}
              >
                <label>
                  Latitud
                  <input
                    name="lat"
                    aria-label="Latitud"
                    type="number"
                    step="any"
                    min="-90"
                    max="90"
                    required
                    defaultValue={origin.lat}
                  />
                </label>
                <label>
                  Longitud
                  <input
                    name="lng"
                    aria-label="Longitud"
                    type="number"
                    step="any"
                    min="-180"
                    max="180"
                    required
                    defaultValue={origin.lng}
                  />
                </label>
                <button className="primary" type="submit">
                  Aplicar
                </button>
              </form>
            )}
          </div>
          {!online && (
            <div className="map-offline">
              <WifiOff size={16} /> Mapa base sin conexión · paradas guardadas
            </div>
          )}
          <RoutePanel
            route={route}
            stops={stops}
            loading={online && stops.length > 0 && !route}
            online={online}
            retry={() => setRetry((value) => value + 1)}
          />
        </section>
      </main>
    </>
  );
}
