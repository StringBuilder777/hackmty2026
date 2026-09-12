import { Navigation, RotateCcw, Route as RouteIcon } from "lucide-react";
import type { Route, Stop } from "@/lib/types";
import { dateLabel } from "@/lib/shopping";
import { useLang } from "@/lib/i18n";
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
  const { t } = useLang();
  return (
    <section className="route-panel" aria-live="polite">
      <div className="route-title">
        <RouteIcon size={21} />
        <h2>{t.routePanel.title}</h2>
        {stops.length > 0 && (
          <span>{t.routePanel.stopsCount(stops.length)}</span>
        )}
      </div>
      {!online ? (
        <p>{t.routePanel.offline}</p>
      ) : !stops.length ? (
        <p>{t.routePanel.noStops}</p>
      ) : loading ? (
        <p className="loading-line">{t.routePanel.loading}</p>
      ) : route?.status === "available" ? (
        <>
          <div className="route-stats">
            <strong>
              <Navigation size={16} />
              {((route.distance_m || 0) / 1000).toFixed(1)} km
            </strong>
            <strong>≈ {Math.ceil((route.duration_s || 0) / 60)} min</strong>
            <span>{t.routePanel.recommended}</span>
          </div>
          <div className="route-timeline" aria-label={t.routePanel.stopsOrderAria}>
            <div className="route-stop route-origin">
              <span aria-hidden="true" />
              <div>
                <strong>{t.routePanel.origin(originName)}</strong>
                <small>{t.routePanel.startPoint}</small>
              </div>
            </div>
            {route.ordered_stops.map((stop, index) => (
              <div className="route-stop" key={stop.id}>
                <span aria-hidden="true">{index + 1}</span>
                <div>
                  <strong>{stop.name}</strong>
                  <small>{stop.products?.join(" · ") || t.routePanel.pickupStop}</small>
                </div>
              </div>
            ))}
          </div>
          <details className="route-method">
            <summary>{t.routePanel.howWeCalculated}</summary>
            <p>{route.message}</p>
            <small>
              {route.provider} · {dateLabel(route.checked_at)}
              {route.demo ? t.routePanel.fictitiousStops : ""}
            </small>
          </details>
        </>
      ) : (
        <>
          <p>{route?.message || t.routePanel.noRoute}</p>
          <button className="text-button" onClick={retry}>
            <RotateCcw size={13} /> {t.routePanel.retry}
          </button>
        </>
      )}
    </section>
  );
}