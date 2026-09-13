"use client";
import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";

export type Lang = "es" | "en";

export interface Messages {
  header: {
    brand: string;
    explore: string;
    myList: string;
    cart: string;
    location: string;
    switchLanguage: string;
    install: string;
    skipLink: string;
  };
  modeBar: {
    demo: string;
    real: string;
    realBtn: string;
    demoBtn: string;
    ariaLabel: string;
  };
  offlineBar: {
    message: string;
  };
  search: {
    heroTitle: string;
    heroSubtitle: string;
    urlLabel: string;
    urlPlaceholder: string;
    analyze: string;
    analyzing: string;
  };
  welcome: {
    titleLine1: string;
    titleLine2: string;
    subLine1: string;
    subLine2: string;
    stepSignals: string;
    stepCompare: string;
    stepRoute: string;
    exploreDemo: string;
    demoNote: string;
    referencesAriaLabel: string;
    referencesTitle: string;
    officialDomain: string;
    suspiciousSimulation: string;
    amazonProduct: string;
    referencesHint: string;
  };
  progress: {
    title: string;
    stages: [string, string, string, string, string];
    hint: string;
  };
  analysis: {
    resultHeading: string;
    examplePrefix: string;
    variantPending: string;
    riskLabel: string;
    aiAssessmentTitle: string;
    aiSeverity: string;
    aiNote: string;
    evidenceHeading: string;
  };
  flagSummary: {
    ariaLabel: string;
    greenCount: (n: number) => string;
    greenEmpty: string;
    redCount: (n: number) => string;
    redEmpty: string;
    pendingCount: (n: number) => string;
    pendingNote: string;
  };
  comparison: {
    title: string;
    alternativesCount: (n: number) => string;
    subtitle: string;
    emptyNotice: string;
    limitationsSummary: string;
  };
  productCard: {
    demoAlt: string;
    imageUnavailable: string;
    branchesInfo: (n: number) => string;
    noBranches: string;
    matchIdentical: string;
    matchOriginal: string;
    matchSimilar: string;
    shippingPending: string;
    shippingLabel: (amount: string) => string;
    addAria: (added: boolean, store: string) => string;
    added: string;
    add: string;
    detailsSummary: string;
    specsPending: string;
    skuGtin: (sku: string, gtin: string) => string;
    checkedAt: (date: string) => string;
    totalWithShipping: (amount: string) => string;
    exampleLink: string;
    viewStore: string;
    unknown: string;
  };
  shoppingList: {
    title: string;
    emptyTitle: string;
    emptySub: string;
    pendingVariant: string;
    removeAria: (store: string) => string;
    branchLabel: string;
    branchAria: (store: string) => string;
    onlineOnlyOption: string;
    seeOnMap: string;
    inventoryConfirmed: (date: string | null) => string;
    inventoryPending: string;
    source: string;
    onlineOnly: string;
    totalKnown: string;
    pendingCosts: (n: number) => string;
    pricesKnown: string;
    otherCurrencies: string;
    totalDisclaimer: string;
  };
  map: {
    regionLabel: string;
    origin: string;
    originMacroplaza: string;
    originCustom: string;
    chooseOtherPoint: string;
    useMyLocation: string;
    transport: string;
    transportAria: string;
    driving: string;
    walking: string;
    cycling: string;
    chooseOnMap: string;
    cancelMap: string;
    coordinates: string;
    latitude: string;
    longitude: string;
    apply: string;
    offlineBadge: string;
    startPoint: string;
    confirmInventoryPopup: string;
    zoomIn: string;
    zoomOut: string;
    loading: string;
  };
  routePanel: {
    title: string;
    stopsCount: (n: number) => string;
    offline: string;
    noStops: string;
    loading: string;
    recommended: string;
    stopsOrderAria: string;
    origin: (name: string) => string;
    startPoint: string;
    pickupStop: string;
    howWeCalculated: string;
    fictitiousStops: string;
    noRoute: string;
    retry: string;
  };
  evidenceList: {
    defaultLabel: string;
    checkSource: string;
  };
  errors: {
    offlineSw: string;
    storageFail: string;
    routeFail: string;
    analysisFailed: string;
    connectionLost: string;
    stillRunning: string;
    fastApiFail: string;
    geoUnavailable: string;
    geoRequesting: string;
    geoDenied: string;
    retryWithAnalyze: string;
  };
  footer: {
    demoNotice: string;
    realNotice: string;
    savedInBrowser: string;
    attribution: string;
  };
}

export const messages: Record<Lang, Messages> = {
  es: {
    header: {
      brand: "SynchroData",
      explore: "Explorar",
      myList: "Mi lista",
      cart: "Carrito",
      location: "Monterrey, NL",
      switchLanguage: "Cambiar idioma",
      install: "Instalar",
      skipLink: "Saltar a resultados",
    },
    modeBar: {
      demo: "Modo demo · Datos de ejemplo, no verificados.",
      real: "Análisis real · Evidencia disponible, sin garantías de seguridad.",
      realBtn: "Real",
      demoBtn: "Demo",
      ariaLabel: "Modo de datos",
    },
    offlineBar: {
      message: "Sin conexión · Consulta tu lista guardada. Análisis y rutas requieren red.",
    },
    search: {
      heroTitle: "Compra con más contexto.",
      heroSubtitle: "Revisa una tienda, compara opciones y planea tu recorrido.",
      urlLabel: "URL de producto o tienda",
      urlPlaceholder: "Pega el enlace de un producto o tienda",
      analyze: "Analizar",
      analyzing: "Analizando…",
    },
    welcome: {
      titleLine1: "Encuentra una mejor",
      titleLine2: "forma de comprar.",
      subLine1: "Empezamos con audífonos en Monterrey.",
      subLine2: "Un enlace es el primer paso.",
      stepSignals: "Revisa señales",
      stepCompare: "Compara opciones",
      stepRoute: "Organiza paradas",
      exploreDemo: "Explorar el modo demo",
      demoNote: "Selecciona Demo y pulsa Analizar. Tiendas y precios ficticios.",
      referencesAriaLabel: "Ejemplos para comparar enlaces",
      referencesTitle: "Prueba ejemplos para comparar",
      officialDomain: "Dominio oficial",
      suspiciousSimulation: "Simulación sospechosa",
      amazonProduct: "Producto Amazon MX",
      referencesHint: "Al elegir uno, revisa la URL y pulsa Analizar. El dominio de alerta es reservado y solo sirve como práctica.",
    },
    progress: {
      title: "Revisando tu enlace",
      stages: [
        "En cola",
        "Leyendo la página",
        "Evaluando señales",
        "Buscando alternativas",
        "Análisis listo",
      ],
      hint: "Las etapas reflejan el estado del backend.",
    },
    analysis: {
      resultHeading: "Resultado del análisis",
      examplePrefix: "Ejemplo · ",
      variantPending: "Variante por identificar",
      riskLabel: "Riesgo:",
      aiAssessmentTitle: "Evaluación complementaria por IA",
      aiSeverity: "Gravedad:",
      aiNote: "Interpreta las señales disponibles; no verifica la identidad de la tienda.",
      evidenceHeading: "Ver detalle y fuentes de las verificaciones",
    },
    flagSummary: {
      ariaLabel: "Resumen de banderas de verificación",
      greenCount: (n: number) => `${n} bandera${n === 1 ? "" : "s"} verde${n === 1 ? "" : "s"}`,
      greenEmpty: "No hay señales positivas verificadas.",
      redCount: (n: number) => `${n} bandera${n === 1 ? "" : "s"} roja${n === 1 ? "" : "s"}`,
      redEmpty: "No se detectaron alertas con la evidencia disponible.",
      pendingCount: (n: number) => `${n} dato${n === 1 ? "" : "s"} pendiente${n === 1 ? "" : "s"}`,
      pendingNote: "Información no disponible no equivale a una señal roja.",
    },
    comparison: {
      title: "Compara tus opciones",
      alternativesCount: (n: number) => `${n} alternativa${n === 1 ? "" : "s"}`,
      subtitle: "Mismo producto, distintas tiendas. Revisa también la variante.",
      emptyNotice: "No hay alternativas disponibles. Puedes guardar el producto consultado.",
      limitationsSummary: "Alcance y verificaciones no disponibles",
    },
    productCard: {
      demoAlt: "Ilustración de audífonos para el demo",
      imageUnavailable: "Imagen no disponible",
      branchesInfo: (n: number) => `${n} sucursal${n > 1 ? "es" : ""} · inventario por verificar`,
      noBranches: "Sin sucursal documentada",
      matchIdentical: "Producto idéntico",
      matchOriginal: "Producto consultado",
      matchSimilar: "Producto similar",
      shippingPending: "Envío por verificar",
      shippingLabel: (amount: string) => `Envío ${amount}`,
      addAria: (added: boolean, store: string) => `${added ? "Agregado" : "Agregar"} ${store}`,
      added: "Agregado",
      add: "Agregar",
      detailsSummary: "Detalles del producto y fuente",
      specsPending: "Marca, modelo, variante y condición pendientes.",
      skuGtin: (sku: string, gtin: string) => `SKU: ${sku} · GTIN: ${gtin}`,
      checkedAt: (date: string) => `Consulta: ${date}.`,
      totalWithShipping: (amount: string) => `Total con envío: ${amount}`,
      exampleLink: "Enlace de ejemplo",
      viewStore: "Ver tienda",
      unknown: "desconocido",
    },
    shoppingList: {
      title: "Mi lista",
      emptyTitle: "Tu próxima compra empieza aquí.",
      emptySub: "Agrega una opción para organizar tu recorrido.",
      pendingVariant: "Variante pendiente",
      removeAria: (store: string) => `Quitar ${store}`,
      branchLabel: "Sucursal",
      branchAria: (store: string) => `Sucursal de ${store}`,
      onlineOnlyOption: "Solo compra en línea",
      seeOnMap: "Ver en mapa",
      inventoryConfirmed: (date: string | null) =>
        `Inventario reportado el ${date}; confirma antes de salir.`,
      inventoryPending: "Inventario en sucursal pendiente de verificar.",
      source: "Fuente",
      onlineOnly: "En línea · no genera una parada",
      totalKnown: "Total conocido",
      pendingCosts: (n: number) => `${n} costo(s) pendiente(s) de verificar.`,
      pricesKnown: "Precios y envíos conocidos.",
      otherCurrencies: " Otras monedas no se convierten ni se suman.",
      totalDisclaimer: "El total final puede cambiar al comprar.",
    },
    map: {
      regionLabel: "Mapa y recorrido de pickup en Monterrey",
      origin: "Origen",
      originMacroplaza: "Macroplaza",
      originCustom: "Punto personalizado",
      chooseOtherPoint: "Elegir otro punto",
      useMyLocation: "Usar mi ubicación",
      transport: "Transporte",
      transportAria: "Modo de transporte",
      driving: "Auto",
      walking: "A pie",
      cycling: "Bicicleta",
      chooseOnMap: "Elegir origen en el mapa",
      cancelMap: "Toca el mapa · Cancelar",
      coordinates: "Coordenadas",
      latitude: "Latitud",
      longitude: "Longitud",
      apply: "Aplicar",
      offlineBadge: "Mapa base sin conexión · paradas guardadas",
      startPoint: "Punto de partida",
      confirmInventoryPopup: "Confirma el inventario antes de salir.",
      zoomIn: "Acercar mapa",
      zoomOut: "Alejar mapa",
      loading: "Cargando mapa...",
    },
    routePanel: {
      title: "Tu recorrido de pickup",
      stopsCount: (n: number) => `${n} parada${n > 1 ? "s" : ""}`,
      offline: "Sin conexión. Conservamos tus paradas; la ruta no está disponible.",
      noStops: "Agrega una tienda con sucursal para crear una ruta.",
      loading: "Consultando recorrido por calles…",
      recommended: "Ruta recomendada",
      stopsOrderAria: "Orden de paradas",
      origin: (name: string) => `Origen: ${name}`,
      startPoint: "Punto de salida",
      pickupStop: "Parada de pickup",
      howWeCalculated: "Cómo calculamos esta ruta",
      fictitiousStops: " · destinos ficticios",
      noRoute: "No fue posible calcular la ruta.",
      retry: "Reintentar ruta",
    },
    evidenceList: {
      defaultLabel: "Ver evidencias",
      checkSource: "Consultar fuente",
    },
    errors: {
      offlineSw: "No fue posible activar el soporte sin conexión. Reintenta recargando.",
      storageFail: "El navegador no pudo guardar la lista. Revisa el almacenamiento disponible.",
      routeFail: "No se pudo conectar con el proveedor de rutas. Reintenta.",
      analysisFailed: "No se pudo completar el análisis.",
      connectionLost: "Se perdió la conexión. Tus productos guardados siguen disponibles.",
      stillRunning: "El análisis sigue en curso. Reintenta en unos momentos.",
      fastApiFail: "No se pudo conectar con FastAPI. Verifica que esté activo.",
      geoUnavailable: "La geolocalización no está disponible. Elige un punto manualmente.",
      geoRequesting: "Solicitando ubicación…",
      geoDenied: "No se pudo obtener permiso o ubicación. Puedes elegir el origen en el mapa o con coordenadas.",
      retryWithAnalyze: "Puedes reintentar con el botón Analizar.",
    },
    footer: {
      demoNotice: "Demo · tiendas, precios y ubicaciones de ejemplo.",
      realNotice: "Las señales orientan; confirma las condiciones antes de comprar.",
      savedInBrowser: "Tu lista se guarda en este navegador.",
      attribution: "SynchroData · HackMTY 2026",
    },
  },
  en: {
    header: {
      brand: "SynchroData",
      explore: "Explore",
      myList: "My list",
      cart: "Cart",
      location: "Monterrey, NL",
      switchLanguage: "Switch language",
      install: "Install",
      skipLink: "Skip to results",
    },
    modeBar: {
      demo: "Demo mode · Example data, not verified.",
      real: "Real analysis · Evidence available, no safety guarantees.",
      realBtn: "Real",
      demoBtn: "Demo",
      ariaLabel: "Data mode",
    },
    offlineBar: {
      message: "Offline · Check your saved list. Analysis and routes require network.",
    },
    search: {
      heroTitle: "Shop with more context.",
      heroSubtitle: "Check a store, compare options and plan your route.",
      urlLabel: "Product or store URL",
      urlPlaceholder: "Paste a product or store link",
      analyze: "Analyze",
      analyzing: "Analyzing...",
    },
    welcome: {
      titleLine1: "Find a better",
      titleLine2: "way to shop.",
      subLine1: "We start with headphones in Monterrey.",
      subLine2: "A link is the first step.",
      stepSignals: "Check signals",
      stepCompare: "Compare options",
      stepRoute: "Organize stops",
      exploreDemo: "Explore demo mode",
      demoNote: "Select Demo and click Analyze. Fictitious stores and prices.",
      referencesAriaLabel: "Link comparison examples",
      referencesTitle: "Try examples to compare",
      officialDomain: "Official domain",
      suspiciousSimulation: "Suspicious simulation",
      amazonProduct: "Amazon MX product",
      referencesHint: "After selecting one, review the URL and click Analyze. The alert domain is reserved and only for practice.",
    },
    progress: {
      title: "Checking your link",
      stages: [
        "Queued",
        "Reading page",
        "Evaluating signals",
        "Finding alternatives",
        "Analysis ready",
      ],
      hint: "Stages reflect backend status.",
    },
    analysis: {
      resultHeading: "Analysis result",
      examplePrefix: "Example · ",
      variantPending: "Variant to be identified",
      riskLabel: "Risk:",
      aiAssessmentTitle: "Complementary AI assessment",
      aiSeverity: "Severity:",
      aiNote: "Interprets available signals; does not verify store identity.",
      evidenceHeading: "See details and verification sources",
    },
    flagSummary: {
      ariaLabel: "Verification flags summary",
      greenCount: (n: number) => `${n} green flag${n === 1 ? "" : "s"}`,
      greenEmpty: "No verified positive signals.",
      redCount: (n: number) => `${n} red flag${n === 1 ? "" : "s"}`,
      redEmpty: "No alerts detected with the available evidence.",
      pendingCount: (n: number) => `${n} pending item${n === 1 ? "" : "s"}`,
      pendingNote: "Unavailable information isn't the same as a red flag.",
    },
    comparison: {
      title: "Compare your options",
      alternativesCount: (n: number) => `${n} alternative${n === 1 ? "" : "s"}`,
      subtitle: "Same product, different stores. Check the variant too.",
      emptyNotice: "No alternatives available. You can save the queried product.",
      limitationsSummary: "Scope and unavailable verifications",
    },
    productCard: {
      demoAlt: "Headphones illustration for the demo",
      imageUnavailable: "Image unavailable",
      branchesInfo: (n: number) => `${n} branch${n > 1 ? "es" : ""} · inventory to verify`,
      noBranches: "No documented branch",
      matchIdentical: "Identical product",
      matchOriginal: "Consulted product",
      matchSimilar: "Similar product",
      shippingPending: "Shipping to verify",
      shippingLabel: (amount: string) => `Shipping ${amount}`,
      addAria: (added: boolean, store: string) => `${added ? "Added" : "Add"} ${store}`,
      added: "Added",
      add: "Add",
      detailsSummary: "Product details and source",
      specsPending: "Brand, model, variant, and condition pending.",
      skuGtin: (sku: string, gtin: string) => `SKU: ${sku} · GTIN: ${gtin}`,
      checkedAt: (date: string) => `Checked: ${date}.`,
      totalWithShipping: (amount: string) => `Total with shipping: ${amount}`,
      exampleLink: "Example link",
      viewStore: "View store",
      unknown: "unknown",
    },
    shoppingList: {
      title: "My list",
      emptyTitle: "Your next purchase starts here.",
      emptySub: "Add an option to plan your route.",
      pendingVariant: "Variant pending",
      removeAria: (store: string) => `Remove ${store}`,
      branchLabel: "Branch",
      branchAria: (store: string) => `Branch for ${store}`,
      onlineOnlyOption: "Online purchase only",
      seeOnMap: "View on map",
      inventoryConfirmed: (date: string | null) =>
        `Inventory reported on ${date}; confirm before heading out.`,
      inventoryPending: "In-store inventory pending verification.",
      source: "Source",
      onlineOnly: "Online only · doesn't create a stop",
      totalKnown: "Known total",
      pendingCosts: (n: number) => `${n} pending cost(s) to verify.`,
      pricesKnown: "Prices and shipping known.",
      otherCurrencies: " Other currencies aren't converted or added.",
      totalDisclaimer: "The final total may change at checkout.",
    },
    map: {
      regionLabel: "Map and pickup route in Monterrey",
      origin: "Origin",
      originMacroplaza: "Macroplaza",
      originCustom: "Custom point",
      chooseOtherPoint: "Choose another point",
      useMyLocation: "Use my location",
      transport: "Transport",
      transportAria: "Transport mode",
      driving: "Driving",
      walking: "Walking",
      cycling: "Cycling",
      chooseOnMap: "Choose origin on map",
      cancelMap: "Tap map · Cancel",
      coordinates: "Coordinates",
      latitude: "Latitude",
      longitude: "Longitude",
      apply: "Apply",
      offlineBadge: "Offline base map · saved stops",
      startPoint: "Starting point",
      confirmInventoryPopup: "Confirm inventory before heading out.",
      zoomIn: "Zoom in",
      zoomOut: "Zoom out",
      loading: "Loading map...",
    },
    routePanel: {
      title: "Your pickup route",
      stopsCount: (n: number) => `${n} stop${n > 1 ? "s" : ""}`,
      offline: "Offline. Your stops are saved; the route isn't available.",
      noStops: "Add a store with a branch to build a route.",
      loading: "Checking the route by streets…",
      recommended: "Recommended route",
      stopsOrderAria: "Stop order",
      origin: (name: string) => `Origin: ${name}`,
      startPoint: "Starting point",
      pickupStop: "Pickup stop",
      howWeCalculated: "How we calculated this route",
      fictitiousStops: " · fictitious destinations",
      noRoute: "Couldn't calculate the route.",
      retry: "Retry route",
    },
    evidenceList: {
      defaultLabel: "View evidence",
      checkSource: "Check source",
    },
    errors: {
      offlineSw: "Could not activate offline support. Try reloading.",
      storageFail: "The browser couldn't save the list. Check available storage.",
      routeFail: "Could not connect to the route provider. Retry.",
      analysisFailed: "Analysis could not be completed.",
      connectionLost: "Connection lost. Your saved products are still available.",
      stillRunning: "Analysis is still ongoing. Retry in a moment.",
      fastApiFail: "Could not connect to FastAPI. Verify it is running.",
      geoUnavailable: "Geolocation is not available. Choose a point manually.",
      geoRequesting: "Requesting location...",
      geoDenied: "Could not get permission or location. Choose origin on the map or via coordinates.",
      retryWithAnalyze: "You can retry with the Analyze button.",
    },
    footer: {
      demoNotice: "Demo · fictitious stores, prices, and locations.",
      realNotice: "Signals guide you; confirm conditions before buying.",
      savedInBrowser: "Your list is saved in this browser.",
      attribution: "SynchroData · HackMTY 2026",
    },
  },
};

const LangContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Messages;
} | null>(null);

// Default to Spanish (primary locale for HackMTY Monterrey)
const DEFAULT_LANG: Lang = "es";
const LANGUAGE_EVENT = "buenpaso-language-change";
let memoryLang: Lang = DEFAULT_LANG;

function readBrowserLanguage(): Lang {
  try {
    const saved = localStorage.getItem("buenpaso_lang") || localStorage.getItem("lang");
    if (saved === "es" || saved === "en") return saved;
  } catch {
    // Fall back to the in-memory preference when storage is unavailable.
  }
  return memoryLang;
}

function subscribeLanguage(callback: () => void) {
  const notify = () => callback();
  window.addEventListener("storage", notify);
  window.addEventListener(LANGUAGE_EVENT, notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(LANGUAGE_EVENT, notify);
  };
}

export function LangProvider({ children }: { children: ReactNode }) {
  // The server and the client's first render must use the same language.
  // useSyncExternalStore applies the browser snapshot after hydration.
  const lang = useSyncExternalStore(subscribeLanguage, readBrowserLanguage, () => DEFAULT_LANG);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  function setLang(l: Lang) {
    memoryLang = l;
    try {
      localStorage.setItem("buenpaso_lang", l);
      localStorage.setItem("lang", l);
    } catch {
      // Storage unavailable
    }
    document.documentElement.lang = l;
    window.dispatchEvent(new Event(LANGUAGE_EVENT));
  }

  return (
    <LangContext.Provider value={{ lang, setLang, t: messages[lang] }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  return ctx;
}
