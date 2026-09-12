"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "es" | "en";

interface Messages {
  flagSummary: {
    ariaLabel: string;
    greenCount: (n: number) => string;
    greenEmpty: string;
    redCount: (n: number) => string;
    redEmpty: string;
    pendingCount: (n: number) => string;
    pendingNote: string;
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
  evidenceList: {
    defaultLabel: string;
    checkSource: string;
  };
}

export const messages: Record<Lang, Messages> = {
  es: {
    flagSummary: {
      ariaLabel: "Resumen de banderas de verificación",
      greenCount: (n: number) => `${n} bandera${n === 1 ? "" : "s"} verde${n === 1 ? "" : "s"}`,
      greenEmpty: "No hay señales positivas verificadas.",
      redCount: (n: number) => `${n} bandera${n === 1 ? "" : "s"} roja${n === 1 ? "" : "s"}`,
      redEmpty: "No se detectaron alertas con la evidencia disponible.",
      pendingCount: (n: number) => `${n} dato${n === 1 ? "" : "s"} pendiente${n === 1 ? "" : "s"}`,
      pendingNote: "Información no disponible no equivale a una señal roja.",
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
    evidenceList: {
      defaultLabel: "Ver evidencias",
      checkSource: "Consultar fuente",
    },
  },
  en: {
    flagSummary: {
      ariaLabel: "Verification flags summary",
      greenCount: (n: number) => `${n} green flag${n === 1 ? "" : "s"}`,
      greenEmpty: "No verified positive signals.",
      redCount: (n: number) => `${n} red flag${n === 1 ? "" : "s"}`,
      redEmpty: "No alerts detected with the available evidence.",
      pendingCount: (n: number) => `${n} pending item${n === 1 ? "" : "s"}`,
      pendingNote: "Unavailable information isn't the same as a red flag.",
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
    evidenceList: {
      defaultLabel: "View evidence",
      checkSource: "Check source",
    },
  },
};

const LangContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Messages;
} | null>(null);

// Default language is English; falls back to a saved choice in localStorage if present.
const DEFAULT_LANG: Lang = "en";

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);

  useEffect(() => {
    const saved = localStorage.getItem("lang");
    if (saved === "es" || saved === "en") setLangState(saved);
  }, []);

  function setLang(l: Lang) {
    setLangState(l);
    localStorage.setItem("lang", l);
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