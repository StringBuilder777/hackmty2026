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
  PackageSearch,
  Route as RouteIcon,
  Search,
  ShieldQuestion,
  ShoppingBag,
  TriangleAlert,
  GlobeLock,
  WifiOff,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Analysis,
  AnalysisTarget,
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
import InvestigationPanel from "./InvestigationPanel";
import WebsiteAuditPanel from "./WebsiteAuditPanel";
import ForensicDashboard from "./ForensicDashboard";

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
type WorkspaceView = "explore" | "list" | "cart" | "forensic";

function viewFromHash(hash: string): WorkspaceView {
  if (hash === "#auditoria") return "forensic";
  if (hash === "#mi-lista") return "list";
  if (hash === "#carrito") return "cart";
  return "explore";
}

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
  const [target, setTarget] = useState<AnalysisTarget>("product");
  const [items, setItems] = useState<Selection[]>([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [ready, setReady] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [origin, setOrigin] = useState<Point>(DEFAULT_ORIGIN);
  const [originName, setOriginName] = useState("Macroplaza");
  const [maxRadius, setMaxRadius] = useState<number>(10); // 10 km por defecto
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
  // Keep the first client render identical to SSR. The hash is applied after
  // hydration so direct links such as /#auditoria do not produce a mismatch.
  const [view, setView] = useState<WorkspaceView>("explore");
  const [cartTransition, setCartTransition] = useState<Product | null>(null);
  const cartTransitionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
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

  useEffect(
    () => () => {
      if (cartTransitionTimer.current) clearTimeout(cartTransitionTimer.current);
    },
    [],
  );

  useEffect(() => {
    const syncViewFromHash = () => setView(viewFromHash(window.location.hash));
    syncViewFromHash();
    window.addEventListener("hashchange", syncViewFromHash);
    return () => window.removeEventListener("hashchange", syncViewFromHash);
  }, []);

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
        setTarget(snapshot.analysis?.target ?? "product");
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
          setError(t.errors.offlineSw),
        );
    return () => {
      alive.current = false;
      clearTimeout(timer);
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, [t]);

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
        setError(t.errors.storageFail);
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [items, analysis, mode, ready, t]);

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
              message: t.errors.routeFail,
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
  }, [routeKey, origin, stops, transport, mode, online, t]);

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
    const nextTarget = snapshot?.analysis?.target ?? target;
    setTarget(nextTarget);
    setSavedAt(snapshot?.savedAt || null);
    setUrl(next === "demo" ? (nextTarget === "website" ? "https://tienda-tramites.example" : "https://example.com/audifonos") : "");
  }

  function chooseTarget(next: AnalysisTarget) {
    if (next === target) return;
    generation.current++;
    setTarget(next);
    setAnalysis(null);
    setError("");
    setSavedAt(null);
    setUrl(mode === "demo" ? (next === "website" ? "https://tienda-tramites.example" : "https://example.com/audifonos") : "");
  }

  function loadReference(nextTarget: AnalysisTarget, nextUrl: string) {
    setMode("real");
    setTarget(nextTarget);
    setUrl(nextUrl);
    setAnalysis(null);
    setError("");
    setSavedAt(null);
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
      let result = await api<Analysis>("/analyses", { url, mode, target });
      for (let attempt = 0; attempt < 160; attempt++) {
        if (current !== generation.current || !alive.current) return;
        setAnalysis(result);
        if (result.status === "error")
          throw new Error(result.error || t.errors.analysisFailed);
        if (result.status === "completed") return;
        await new Promise((resolve) => setTimeout(resolve, 650));
        if (!navigator.onLine)
          throw new Error(t.errors.connectionLost);
        if (current !== generation.current || !alive.current) return;
        result = await api<Analysis>(`/analyses/${result.id}`);
      }
      throw new Error(t.errors.stillRunning);
    } catch (cause) {
      if (current === generation.current && alive.current)
        setError(
          cause instanceof Error
            ? cause.message
            : t.errors.fastApiFail
        );
    } finally {
      if (current === generation.current && alive.current) setRunning(false);
    }
  }

  const chooseOrigin = useCallback((point: Point) => {
    setOrigin({ lat: point.lat, lng: point.lng });
    setOriginName(t.map.originCustom);
    setPicking(false);
    setLocationError("");
  }, [t]);

  function geolocate() {
    if (!navigator.geolocation) {
      setLocationError(t.errors.geoUnavailable);
      return;
    }
    setLocationError(t.errors.geoRequesting);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        chooseOrigin({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
        setOriginName(t.map.useMyLocation);
      },
      () =>
        setLocationError(t.errors.geoDenied),
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
    setCartTransition(product);
    if (cartTransitionTimer.current) clearTimeout(cartTransitionTimer.current);
    cartTransitionTimer.current = setTimeout(() => {
      setView("cart");
      setCartTransition(null);
      window.history.replaceState(null, "", "#carrito");
    }, 650);
  }

  const complete = analysis?.status === "completed";

  function navigateView(
    event: React.MouseEvent<HTMLAnchorElement>,
    next: WorkspaceView,
  ) {
    // A hash navigation can remount the client surface before its state update
    // paints. Keep the URL useful without letting the browser discard the tab.
    event.preventDefault();
    setView(next);
    window.history.replaceState(null, "", next === "forensic" ? "#auditoria" : next === "cart" ? "#carrito" : next === "list" ? "#mi-lista" : "#explorar");
  }

  return (
    <>
      <a href="#resultados" className="skip-link">
        {t.header.skipLink}
      </a>
      
      <header className="header">
        <Link className="brand" href="/" aria-label="SynchroData, inicio">
          <RouteIcon size={30} />
          <span>{t.header.brand}</span>
        </Link>
        <nav aria-label="Principal">
          <a
            className={view === "explore" ? "nav-active" : undefined}
            href="#explorar"
            onClick={(event) => navigateView(event, "explore")}
          >
            {t.header.explore}
          </a>
          <a
            className={view === "list" ? "nav-active" : undefined}
            href="#mi-lista"
            onClick={(event) => navigateView(event, "list")}
          >
            {t.header.myList}
            {items.length > 0 && (
              <span className="nav-count">{items.length}</span>
            )}
          </a>
          <a
            className={view === "cart" ? "nav-active" : undefined}
            href="#carrito"
            onClick={(event) => navigateView(event, "cart")}
          >
            {t.header.cart}
            {items.length > 0 && (
              <span className="nav-count">{items.length}</span>
            )}
          </a>
          <a className={view === "forensic" ? "nav-active" : undefined} href="#auditoria" onClick={(event) => navigateView(event, "forensic")}>Auditoría</a>
        </nav>
        
        <div className="header-actions">
          {/* Apple Segmented Language Switcher */}
          <div
            className="segmented-control lang-switch"
            aria-label={t.header.switchLanguage}
          >
            <button
              type="button"
              aria-pressed={lang === "es"}
              className={`segmented-btn ${lang === "es" ? "active" : ""}`}
              onClick={() => setLang("es")}
            >
              ES
            </button>
            <button
              type="button"
              aria-pressed={lang === "en"}
              className={`segmented-btn ${lang === "en" ? "active" : ""}`}
              onClick={() => setLang("en")}
            >
              EN
            </button>
          </div>

          <div className="header-location">
            <MapPin size={15} />
            <span>{t.header.location}</span>
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
              <Download size={15} /> {t.header.install}
            </button>
          )}
        </div>
      </header>

      {cartTransition && (
        <div
          className="cart-transfer"
          role="status"
          aria-label={lang === "es" ? `Añadiendo ${cartTransition.name} al carrito` : `Adding ${cartTransition.name} to cart`}
        >
          <ShoppingBag size={18} />
          <span>{lang === "es" ? "Añadido al carrito" : "Added to cart"}</span>
        </div>
      )}

      <div className={`mode-bar ${mode}`}>
        <span>
          {mode === "demo" ? (
            <TriangleAlert size={15} />
          ) : (
            <ShieldQuestion size={15} />
          )}
          {mode === "demo" ? t.modeBar.demo : t.modeBar.real}
        </span>
        <div className="segmented-control mode-switch" aria-label={t.modeBar.ariaLabel}>
          <button
            type="button"
            aria-pressed={mode === "real"}
            className={`segmented-btn ${mode === "real" ? "active" : ""}`}
            onClick={() => switchMode("real")}
          >
            {t.modeBar.realBtn}
          </button>
          <button
            type="button"
            aria-pressed={mode === "demo"}
            className={`segmented-btn ${mode === "demo" ? "active" : ""}`}
            onClick={() => switchMode("demo")}
          >
            {t.modeBar.demoBtn}
          </button>
        </div>
      </div>

      {!online && (
        <div className="offline-bar" role="status">
          <WifiOff size={16} /> {t.offlineBar.message}
        </div>
      )}

      {view === "explore" && (
      <section id="explorar" className="search-section">
        <div className="search-copy">
          <h1>{t.search.heroTitle}</h1>
          <p>{target === "website" ? (lang === "es" ? "Audita un dominio y busca señales de phishing o suplantación." : "Audit a domain for phishing or impersonation signals.") : t.search.heroSubtitle}</p>
        </div>
        <div className="search-actions">
          <div className="analysis-targets" aria-label={lang === "es" ? "Tipo de análisis" : "Analysis type"}>
            <button type="button" className={target === "product" ? "active" : ""} aria-pressed={target === "product"} onClick={() => chooseTarget("product")}>
              <PackageSearch size={19} /><span><strong>{lang === "es" ? "Producto" : "Product"}</strong><small>{lang === "es" ? "Precio, vendedor y alternativas" : "Price, seller and alternatives"}</small></span>
            </button>
            <button type="button" className={target === "website" ? "active" : ""} aria-pressed={target === "website"} onClick={() => chooseTarget("website")}>
              <GlobeLock size={19} /><span><strong>{lang === "es" ? "Sitio web" : "Website"}</strong><small>{lang === "es" ? "Dominio, WHOIS y phishing" : "Domain, WHOIS and phishing"}</small></span>
            </button>
          </div>
        <form onSubmit={analyze} className="search-form">
          <label htmlFor="product-url" className="sr-only">
            {t.search.urlLabel}
          </label>
          <div className="url-field">
            <Link2 size={18} />
            <input
              id="product-url"
              type="url"
              required
              maxLength={2048}
            placeholder={target === "website" ? (lang === "es" ? "Pega el enlace del sitio que quieres auditar" : "Paste the website you want to audit") : t.search.urlPlaceholder}
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
            {running ? t.search.analyzing : t.search.analyze}
            <ArrowRight size={16} />
          </button>
        </form>
        </div>
      </section>
      )}

      {view === "forensic" ? <ForensicDashboard /> : <main className="workspace workspace-no-map">
        {view === "explore" && (
        <section
          className="results"
          id="resultados"
          aria-label="Resultados de la investigación"
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
                {t.errors.retryWithAnalyze}
              </p>
            </div>
          )}
          {running && (
            <div className="analysis-progress" role="status">
              <h2>{t.progress.title}</h2>
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
                    {t.progress.stages[i]}
                  </li>
                ))}
              </ol>
              <small>{t.progress.hint}</small>
            </div>
          )}
          {!analysis && !running && (
            <div className="welcome">
              <div className="welcome-icon">
                <Headphones size={42} strokeWidth={1.4} />
              </div>
              <h2>
                {t.welcome.titleLine1}
                <br />
                {t.welcome.titleLine2}
              </h2>
              <p>
                {t.welcome.subLine1}
                <br />
                {t.welcome.subLine2}
              </p>
              <div className="welcome-steps">
                <span>
                  <ShieldQuestion size={17} /> {t.welcome.stepSignals}
                </span>
                <span>
                  <Search size={17} /> {t.welcome.stepCompare}
                </span>
                <span>
                  <Navigation size={17} /> {t.welcome.stepRoute}
                </span>
              </div>
              <button
                className="text-button"
                onClick={() => {
                  switchMode("demo");
                  setUrl("https://example.com/audifonos");
                }}
              >
                {t.welcome.exploreDemo} <ArrowRight size={15} />
              </button>
              <small>
                {t.welcome.demoNote}
              </small>
              <section className="reference-examples" aria-label={t.welcome.referencesAriaLabel}>
                <p>{t.welcome.referencesTitle}</p>
                <div>
                  <button type="button" onClick={() => loadReference("website", "https://www.amazon.com.mx/")}>
                    <GlobeLock size={16} />
                    <span>{t.welcome.officialDomain}<small>amazon.com.mx</small></span>
                  </button>
                  <button type="button" className="reference-suspicious" onClick={() => loadReference("website", "https://amazon-verificacion.example/")}>
                    <TriangleAlert size={16} />
                    <span>{t.welcome.suspiciousSimulation}<small>amazon-verificacion.example</small></span>
                  </button>
                  <button type="button" onClick={() => loadReference("product", "https://www.amazon.com.mx/Sony-Aud%C3%ADfonos-inal%C3%A1mbricos-WH-CH520-duraci%C3%B3n/dp/B0BS1PRC4L")}>
                    <PackageSearch size={16} />
                    <span>{t.welcome.amazonProduct}<small>Sony WH-CH520</small></span>
                  </button>
                </div>
                <small>{t.welcome.referencesHint}</small>
              </section>
            </div>
          )}
          {complete && analysis.product && (
            <>
              <div className="section-heading result-label">
                <span>{t.analysis.resultHeading}</span>
                <small>
                  {mode === "demo" ? t.analysis.examplePrefix : ""}
                  {dateLabel(analysis.product.checked_at)}
                </small>
              </div>
              <div className="result-summary">
                <div className="result-overview">
                  <ProductImage product={analysis.product} online={online} />
                  <div>
                    <h2>{analysis.product.name}</h2>
                    <p>
                      {analysis.product.variant || t.analysis.variantPending}
                    </p>
                    <small>{analysis.product.store}</small>
                  </div>
                </div>
                {analysis.risk && !(mode === "demo" && analysis.risk.level === "información insuficiente") && (
                  <div className="risk-box">
                    <TriangleAlert size={21} />
                    <div>
                      <strong>{t.analysis.riskLabel} {analysis.risk.level}</strong>
                      <p>{analysis.risk.explanation}</p>
                    </div>
                  </div>
                )}
              </div>
              <InvestigationPanel
                product={analysis.product}
                store={analysis.store_profile}
                english={lang === "en"}
              />
              {analysis.risk && (
                <>
                  {analysis.risk.agent_assessment && (
                    <section className="agent-assessment" aria-label={t.analysis.aiAssessmentTitle}>
                      <div>
                        <span>{t.analysis.aiAssessmentTitle}</span>
                        <strong>{t.analysis.aiSeverity} {analysis.risk.agent_assessment.level}</strong>
                      </div>
                      <p>{analysis.risk.agent_assessment.explanation}</p>
                      <small>{t.analysis.aiNote}</small>
                    </section>
                  )}
                  <FlagSummary evidence={analysis.risk.evidence} />
                  <EvidenceList
                    evidence={analysis.risk.evidence}
                    label={t.analysis.evidenceHeading}
                  />
                </>
              )}
              <section className="comparison">
                <div className="section-heading">
                  <h2>{t.comparison.title}</h2>
                  <span>{t.comparison.alternativesCount(analysis.alternatives.length)}</span>
                </div>
                <p className="section-description">
                  {t.comparison.subtitle}
                </p>
                {analysis.alternatives.length === 0 && (
                  <p className="empty-notice">
                    {t.comparison.emptyNotice}
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
                    <summary>{t.comparison.limitationsSummary}</summary>
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
          {complete && (analysis.target ?? "product") === "website" && (
            <WebsiteAuditPanel analysis={analysis} english={lang === "en"} />
          )}
          <footer className="panel-footer">
            {mode === "demo" ? t.footer.demoNotice : t.footer.realNotice}
            <br />
            {t.footer.savedInBrowser}{" "}
            <span>{t.footer.attribution}</span>
          </footer>
        </section>
        )}

        {view === "list" && (
          <section
            className="results"
            id="mi-lista"
            aria-label={t.header.myList}
          >
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
              onOpenCart={() => setView("cart")}
            />
            <footer className="panel-footer">
              {mode === "demo" ? t.footer.demoNotice : t.footer.realNotice}
              <br />
              {t.footer.savedInBrowser} <span>{t.footer.attribution}</span>
            </footer>
          </section>
        )}

        {view === "cart" && items.length > 0 && (
          <section
            className="map-section"
            aria-label={t.map.regionLabel}
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
                <label htmlFor="origin">{t.map.origin}</label>
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
                        ? t.map.chooseOtherPoint
                        : originName}
                    </option>
                  </select>
                  <button
                    className="icon-button"
                    aria-label={t.map.useMyLocation}
                    onClick={geolocate}
                  >
                    <LocateFixed size={16} />
                  </button>
                </div>
              </div>
              <label className="transport-control">
                {t.map.transport}
                <select
                  aria-label={t.map.transportAria}
                  value={transport}
                  onChange={(e) => setTransport(e.target.value as Transport)}
                >
                  <option value="driving">{t.map.driving}</option>
                  <option value="walking">{t.map.walking}</option>
                  <option value="cycling">{t.map.cycling}</option>
                </select>
              </label>
              <button
                className={`text-button choose-point ${picking ? "selected" : ""}`}
                onClick={() => setPicking(!picking)}
              >
                {picking ? t.map.cancelMap : t.map.chooseOnMap}
              </button>
              <button
                className="text-button coordinates-toggle"
                onClick={() => setManual(!manual)}
              >
                {t.map.coordinates}
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
                    {t.map.latitude}
                    <input
                      name="lat"
                      aria-label={t.map.latitude}
                      type="number"
                      step="any"
                      min="-90"
                      max="90"
                      required
                      defaultValue={origin.lat}
                    />
                  </label>
                  <label>
                    {t.map.longitude}
                    <input
                      name="lng"
                      aria-label={t.map.longitude}
                      type="number"
                      step="any"
                      min="-180"
                      max="180"
                      required
                      defaultValue={origin.lng}
                    />
                  </label>
                  <button className="primary" type="submit">
                    {t.map.apply}
                  </button>
                </form>
              )}
            </div>
            {!online && (
              <div className="map-offline">
                <WifiOff size={16} /> {t.map.offlineBadge}
              </div>
            )}
            <RoutePanel
              route={route}
              stops={stops}
              originName={originName}
              loading={online && stops.length > 0 && !route}
              online={online}
              retry={() => setRetry((value) => value + 1)}
              maxRadius={maxRadius}
              setMaxRadius={setMaxRadius}
            />
          </section>
        )}
      </main>}
    </>
  );
}
