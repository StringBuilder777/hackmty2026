import { Navigation, RotateCcw, Route as RouteIcon } from "lucide-react";
import type { Route, Stop } from "@/lib/types";
import { dateLabel } from "@/lib/shopping";
export default function RoutePanel({
  route,
  stops,
  originName,
  loading,
  online,
  retry,
}: {
  route: Route | null;
  stops: Stop[];
  originName: string;
  loading: boolean;
  online: boolean;
  retry: () => void;
}) {
  return (
    <section className="route-panel" aria-live="polite">
      <div className="route-title">
        <RouteIcon size={21} />
        <h2>Tu recorrido de pickup</h2>
        {stops.length > 0 && (
          <span>
            {stops.length} parada{stops.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
      {!online ? (
        <p>
          Sin conexión. Conservamos tus paradas; la ruta no está disponible.
        </p>
      ) : !stops.length ? (
        <p>Agrega una tienda con sucursal para crear una ruta.</p>
      ) : loading ? (
        <p className="loading-line">Consultando recorrido por calles…</p>
      ) : route?.status === "available" ? (
        <>
          <div className="route-stats">
            <strong>
              <Navigation size={16} />
              {((route.distance_m || 0) / 1000).toFixed(1)} km
            </strong>
            <strong>≈ {Math.ceil((route.duration_s || 0) / 60)} min</strong>
            <span>Ruta recomendada</span>
          </div>
          <div className="route-timeline" aria-label="Orden de paradas">
            <div className="route-stop route-origin">
              <span aria-hidden="true" />
              <div>
                <strong>Origen: {originName}</strong>
                <small>Punto de salida</small>
              </div>
            </div>
            {route.ordered_stops.map((stop, index) => (
              <div className="route-stop" key={stop.id}>
                <span aria-hidden="true">{index + 1}</span>
                <div>
                  <strong>{stop.name}</strong>
                  <small>{stop.products?.join(" · ") || "Parada de pickup"}</small>
                </div>
              </div>
            ))}
          </div>
          <details className="route-method">
            <summary>Cómo calculamos esta ruta</summary>
            <p>{route.message}</p>
            <small>
              {route.provider} · {dateLabel(route.checked_at)}
              {route.demo ? " · destinos ficticios" : ""}
            </small>
          </details>
        </>
      ) : (
        <>
          <p>{route?.message || "No fue posible calcular la ruta."}</p>
          <button className="text-button" onClick={retry}>
            <RotateCcw size={13} /> Reintentar ruta
          </button>
        </>
      )}
    </section>
  );
}
