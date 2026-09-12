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
import { useLang } from "@/lib/i18n";
import EvidenceList from "./EvidenceList";
import FlagSummary from "./FlagSummary";
import ProductCard, { ProductImage } from "./ProductCard";
import ShoppingList from "./ShoppingList";
import RoutePanel from "./RoutePanel";

const ShoppingMap = dynamic(() => import("./Map"), {
  ssr: false,
  loading: () => <div className="map-loading">Cargando mapa... / Loading map...</div>,
});

const DEFAULT_ORIGIN = { lat: 25.669, lng: -100.309 };
const STAGES = [
  "queued",
  "extracting",
  "evaluating",
  "searching",
  "completed",
] as const;

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
  
  const { lang, setLang, t } = useLang();

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

  const STAGE_LABELS_ES = [
    "En cola",
    "Leyendo la página",
    "Evaluando señales",
    "Buscando alternativas",
    "Análisis listo",
  ];
  
  const STAGE_LABELS_EN = [
    "Queued",
    "Reading page",
    "Evaluating signals",
    "Finding alternatives",
    "Analysis ready",
  ];

  const currentStages = lang === "es" ? STAGE_LABELS_ES : STAGE_LABELS_EN;

  useEffect(() => {
    alive.current = true;
    const timer = setTimeout(() => {
      let lastMode: Mode = "real";
      try {
        if (localStorage.getItem("buenpaso-last-mode") === "demo")
          lastMode = "demo";
      } catch {
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
            lang === "es"
              ? "No fue posible activar el soporte sin conexión. Reintenta recargando."
              : "Could not activate offline support. Try reloading."
          ),
        );
    return () => {
      alive.current = false;
      clearTimeout(timer);
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, [lang]);

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
          lang === "es" 
            ? "El navegador no pudo guardar la lista. Revisa el almacenamiento disponible."
            : "The browser couldn't save the list. Check available storage."
        );
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [items, analysis, mode, ready, lang]);

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
              message: lang === "es" ? "No se pudo conectar con el proveedor de rutas. Reintenta." : "Could not connect to the route provider. Retry.",
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
  }, [routeKey, origin, stops, transport, mode, online, lang]);

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
          throw new Error(result.error || (lang === "es" ? "No se pudo completar el análisis." : "Analysis could not be completed."));
        if (result.status === "completed") return;
        await new Promise((resolve) => setTimeout(resolve, 650));
        if (!navigator.onLine)
          throw new Error(
            lang === "es" ? "Se perdió la conexión. Tus productos guardados siguen disponibles." : "Connection lost. Your saved products are still available."
          );
        if (current !== generation.current || !alive.current) return;
        result = await api<Analysis>(`/analyses/${result.id}`);
      }
      throw new Error(
        lang === "es" ? "El análisis sigue en curso. Reintenta en unos momentos." : "Analysis is still ongoing. Retry in a moment."
      );
    } catch (cause) {
      if (current === generation.current && alive.current)
        setError(
          cause instanceof Error
            ? cause.message
            : (lang === "es" ? "No se pudo conectar con FastAPI. Verifica que esté activo." : "Could not connect to FastAPI. Verify it is running.")
        );
    } finally {
      if (current === generation.current && alive.current) setRunning(false);
    }
  }

  const chooseOrigin = useCallback((point: Point) => {
    setOrigin({ lat: point.lat, lng: point.lng });
    setOriginName(lang === "es" ? "Punto personalizado" : "Custom point");
    setPicking(false);
    setLocationError("");
  }, [lang]);

  function geolocate() {
    if (!navigator.geolocation) {
      setLocationError(
        lang === "es" ? "La geolocalización no está disponible. Elige un punto manualmente." : "Geolocation is not available. Choose a point manually."
      );
      return;
    }
    setLocationError(lang === "es" ? "Solicitando ubicación…" : "Requesting location...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        chooseOrigin({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
        setOriginName(lang === "es" ? "Mi ubicación" : "My location");
      },
      () =>
        setLocationError(
          lang === "es" ? "No se pudo obtener permiso o ubicación. Puedes elegir el origen en el mapa o con coordenadas." : "Could not get permission or location. Choose origin on the map or via coordinates."
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
        {lang === "es" ? "Saltar a resultados" : "Skip to results"}
      </a>
      
      <header className="header">
        <Link className="brand" href="/" aria-label="BuenPaso, inicio">
          <RouteIcon size={30} />
          <span>BuenPaso</span>
        </Link>
        <nav aria-label="Principal">
          <a className="nav-active" href="#explorar">
            {lang === "es" ? "Explorar" : "Explore"}
          </a>
          <a href="#mi-lista">
            {lang === "es" ? "Mi lista" : "My list"}
            {items.length > 0 && (
              <span className="nav-count">{items.length}</span>
            )}
          </a>
        </nav>
        
        <div className="header-actions" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            className="text-button lang-switcher"
            onClick={() => setLang(lang === "es" ? "en" : "es")}
            aria-label="Cambiar idioma / Switch language"
          >
            🌐 {lang === "es" ? "EN" : "ES"}
          </button>

          <div className="header-location">
            <MapPin size={16} />
            <span>Monterrey, NL</span>
          </div>
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
            <Download size={15} /> {lang === "es" ? "Instalar" : "Install"}
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
            ? (lang === "es" ? "Modo demo · Datos de ejemplo, no verificados." : "Demo mode · Example data, not verified.")
            : (lang === "es" ? "Análisis real · Evidencia disponible, sin garantías de seguridad." : "Real analysis · Evidence available, no safety guarantees.")}
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
          <WifiOff size={16} /> {lang === "es" ? "Sin conexión · Consulta tu lista guardada. Análisis y rutas requieren red." : "Offline · Check your saved list. Analysis and routes require network."}
        </div>
      )}
      <section id="explorar" className="search-section">
        <div>
          <h1>{lang === "es" ? "Compra con más contexto." : "Shop with more context."}</h1>
          <p>{lang === "es" ? "Revisa una tienda, compara opciones y planea tu recorrido." : "Check a store, compare options and plan your route."}</p>
        </div>
        <form onSubmit={analyze} className="search-form">
          <label htmlFor="product-url" className="sr-only">
            {lang === "es" ? "URL de producto o tienda" : "Product or store URL"}
          </label>
          <div className="url-field">
            <Link2 size={18} />
            <input
              id="product-url"
              type="url"
              required
              maxLength={2048}
              placeholder={lang === "es" ? "Pega el enlace de un producto o tienda" : "Paste a product or store link"}
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
            {running ? (lang === "es" ? "Analizando…" : "Analyzing...") : (lang === "es" ? "Analizar" : "Analyze")}
            <ArrowRight size={16} />
          </button>
        </form>
      </section>
      <main className={`workspace ${items.length === 0 ? "workspace-no-map" : ""}`}>
        <section
          className="results"
          id="resultados"
          aria-label="Resultados y lista de compras"
        >
          {savedAt && (
            <p className="saved-note">
              {lang === "es" ? "Datos guardados · " : "Saved data · "}{dateLabel(savedAt)}. {lang === "es" ? "Pueden haber cambiado." : "May have changed."}
            </p>
          )}
          {error && (
            <div className="error-box" role="alert">
              <TriangleAlert size={18} />
              <p>
                {error}
                <br />
                {lang === "es" ? "Puedes reintentar con el botón Analizar." : "You can retry with the Analyze button."}
              </p>
            </div>
          )}
          {running && (
            <div className="analysis-progress" role="status">
              <h2>{lang === "es" ? "Revisando tu enlace" : "Checking your link"}</h2>
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
                    {currentStages[i]}
                  </li>
                ))}
              </ol>
              <small>{lang === "es" ? "Las etapas reflejan el estado del backend." : "Stages reflect backend status."}</small>
            </div>
          )}
          {!analysis && !running && (
            <div className="welcome">
              <div className="welcome-icon">
                <Headphones size={40} strokeWidth={1.4} />
              </div>
              <h2>
                {lang === "es" ? "Encuentra una mejor" : "Find a better"}
                <br />
                {lang === "es" ? "forma de comprar." : "way to shop."}
              </h2>
              <p>
                {lang === "es" ? "Empezamos con audífonos en Monterrey." : "We start with headphones in Monterrey."}
                <br />
                {lang === "es" ? "Un enlace es el primer paso." : "A link is the first step."}
              </p>
              <div className="welcome-steps">
                <span>
                  <ShieldQuestion size={17} /> {lang === "es" ? "Revisa señales" : "Check signals"}
                </span>
                <span>
                  <Search size={17} /> {lang === "es" ? "Compara opciones" : "Compare options"}
                </span>
                <span>
                  <Navigation size={17} /> {lang === "es" ? "Organiza paradas" : "Organize stops"}
                </span>
              </div>
              <button
                className="text-button"
                onClick={() => {
                  switchMode("demo");
                  setUrl("https://example.com/audifonos");
                }}
              >
                {lang === "es" ? "Explorar el modo demo" : "Explore demo mode"} <ArrowRight size={15} />
              </button>
              <small>
                {lang === "es" ? "Selecciona Demo y pulsa Analizar. Tiendas y precios ficticios." : "Select Demo and click Analyze. Fictitious stores and prices."}
              </small>
            </div>
          )}
          {complete && analysis.product && (
            <>
              <div className="section-heading result-label">
                <span>{lang === "es" ? "Resultado del análisis" : "Analysis result"}</span>
                <small>
                  {mode === "demo" ? (lang === "es" ? "Ejemplo · " : "Example · ") : ""}
                  {dateLabel(analysis.product.checked_at)}
                </small>
              </div>
              <div className="result-summary">
                <div className="result-overview">
                  <ProductImage product={analysis.product} online={online} />
                  <div>
                    <h2>{analysis.product.name}</h2>
                    <p>
                      {analysis.product.variant || (lang === "es" ? "Variante por identificar" : "Variant to be identified")}
                    </p>
                    <small>{analysis.product.store}</small>
                  </div>
                </div>
                {analysis.risk && (
                  <div className="risk-box">
                    <TriangleAlert size={21} />
                    <div>
                      <strong>{lang === "es" ? "Riesgo:" : "Risk:"} {analysis.risk.level}</strong>
                      <p>{analysis.risk.explanation}</p>
                    </div>
                  </div>
                )}
              </div>
              {analysis.risk && (
                <>
                  {analysis.risk.agent_assessment && (
                    <section className="agent-assessment" aria-label={lang === "es" ? "Explicación del agente de riesgo" : "Risk agent explanation"}>
                      <div>
                        <span>{lang === "es" ? "Evaluación complementaria por IA" : "Complementary AI assessment"}</span>
                        <strong>{lang === "es" ? "Gravedad:" : "Severity:"} {analysis.risk.agent_assessment.level}</strong>
                      </div>
                      <p>{analysis.risk.agent_assessment.explanation}</p>
                      <small>{lang === "es" ? "Interpreta las señales disponibles; no verifica la identidad de la tienda." : "Interprets available signals; does not verify store identity."}</small>
                    </section>
                  )}
                  <FlagSummary evidence={analysis.risk.evidence} />
                  <EvidenceList
                    evidence={analysis.risk.evidence}
                    label={lang === "es" ? "Ver detalle y fuentes de las verificaciones" : "See details and verification sources"}
                  />
                </>
              )}
              <section className="comparison">
                <div className="section-heading">
                  <h2>{lang === "es" ? "Compara tus opciones" : "Compare your options"}</h2>
                  <span>{analysis.alternatives.length} {lang === "es" ? "alternativas" : "alternatives"}</span>
                </div>
                <p className="section-description">
                  {lang === "es" ? "Mismo producto, distintas tiendas. Revisa también la variante." : "Same product, different stores. Check the variant too."}
                </p>
                {analysis.alternatives.length === 0 && (
                  <p className="empty-notice">
                    {lang === "es" ? "No hay alternativas disponibles. Puedes guardar el producto consultado." : "No alternatives available. You can save the queried product."}
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
                    <summary>{lang === "es" ? "Alcance y verificaciones no disponibles" : "Scope and unavailable verifications"}</summary>
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
              ? (lang === "es" ? "Demo · tiendas, precios y ubicaciones de ejemplo." : "Demo · fictitious stores, prices, and locations.")
              : (lang === "es" ? "Las señales orientan; confirma las condiciones antes de comprar." : "Signals guide you; confirm conditions before buying.")}
            <br />
            {lang === "es" ? "Tu lista se guarda en este navegador." : "Your list is saved in this browser."}{" "}
            <span>BuenPaso · HackMTY 2026</span>
          </footer>
        </section>
        {items.length > 0 && <section
          className="map-section"
          aria-label={lang === "es" ? "Mapa y recorrido de pickup" : "Map and pickup route"}
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
              <label htmlFor="origin">{lang === "es" ? "Origen" : "Origin"}</label>
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
                      ? (lang === "es" ? "Elegir otro punto" : "Choose another point")
                      : originName}
                  </option>
                </select>
                <button
                  className="icon-button"
                  aria-label={lang === "es" ? "Usar mi ubicación" : "Use my location"}
                  onClick={geolocate}
                >
                  <LocateFixed size={16} />
                </button>
              </div>
            </div>
            <label className="transport-control">
              {lang === "es" ? "Transporte" : "Transport"}
              <select
                aria-label={lang === "es" ? "Modo de transporte" : "Transport mode"}
                value={transport}
                onChange={(e) => setTransport(e.target.value as Transport)}
              >
                <option value="driving">{lang === "es" ? "Auto" : "Driving"}</option>
                <option value="walking">{lang === "es" ? "A pie" : "Walking"}</option>
                <option value="cycling">{lang === "es" ? "Bicicleta" : "Cycling"}</option>
              </select>
            </label>
            <button
              className={`text-button choose-point ${picking ? "selected" : ""}`}
              onClick={() => setPicking(!picking)}
            >
              {picking ? (lang === "es" ? "Toca el mapa · Cancelar" : "Tap map · Cancel") : (lang === "es" ? "Elegir origen en el mapa" : "Choose origin on map")}
            </button>
            <button
              className="text-button coordinates-toggle"
              onClick={() => setManual(!manual)}
            >
              {lang === "es" ? "Coordenadas" : "Coordinates"}
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
                  {lang === "es" ? "Latitud" : "Latitude"}
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
                  {lang === "es" ? "Longitud" : "Longitude"}
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
                  {lang === "es" ? "Aplicar" : "Apply"}
                </button>
              </form>
            )}
          </div>
          {!online && (
            <div className="map-offline">
              <WifiOff size={16} /> {lang === "es" ? "Mapa base sin conexión · paradas guardadas" : "Offline base map · saved stops"}
            </div>
          )}
          <RoutePanel
            route={route}
            stops={stops}
            originName={originName}
            loading={online && stops.length > 0 && !route}
            online={online}
            retry={() => setRetry((value) => value + 1)}
          />
        </section>}
      </main>
    </>
  );
}