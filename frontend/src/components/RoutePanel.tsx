import { Navigation, RotateCcw, Route as RouteIcon } from "lucide-react";
import type { Route, Stop } from "@/lib/types";
import { dateLabel } from "@/lib/shopping";
export default function RoutePanel({
  route,
  stops,
  loading,
  online,
  retry,
}: {
  route: Route | null;
  stops: Stop[];
  loading: boolean;
  online: boolean;
  retry: () => void;
}) {
  return (
    <section className="route-panel" aria-live="polite">
      <div className="route-title">
        <RouteIcon size={21} />
        <h2>Tu recorrido</h2>
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
        <p>Agrega una tienda para crear una ruta.</p>
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
          <details>
            <summary>Ver orden de paradas y cálculo</summary>
            <ol>
              {route.ordered_stops.map((stop) => (
                <li key={stop.id}>{stop.name}</li>
              ))}
            </ol>
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
