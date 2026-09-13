"use client";

import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  Circle,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { BranchId, Point, Stop, Route } from "@/lib/types";
import { useLang } from "@/lib/i18n";

const originIcon = L.divIcon({
  className: "origin-icon",
  html: "<span className='origin-dot'></span>",
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

function Controller({
  stops,
  origin,
  active,
  picking,
  onOrigin,
}: {
  stops: Stop[];
  origin: Point;
  active: BranchId | null;
  picking: boolean;
  onOrigin: (point: Point) => void;
}) {
  const map = useMap();

  useMapEvents({
    click(event) {
      if (picking) onOrigin(event.latlng);
    },
  });

  useEffect(() => {
    const coordinates: L.LatLngTuple[] = [
      [origin.lat, origin.lng],
      ...stops.map((s) => [s.lat, s.lng] as L.LatLngTuple),
    ];
    if (coordinates.length > 1) {
      map.fitBounds(coordinates, { padding: [70, 90], maxZoom: 14 });
    } else {
      map.setView([origin.lat, origin.lng], 12);
    }
  }, [map, stops, origin]);

  useEffect(() => {
    const target = stops.find((s) => s.id === active);
    if (target) {
      map.flyTo([target.lat, target.lng], 14, { duration: 0.5 });
    }
  }, [active, map, stops]);

  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container);
    return () => observer.disconnect();
  }, [map]);

  return null;
}

function ZoomButtons() {
  const map = useMap();
  const { t } = useLang();
  const zoomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (zoomRef.current) {
      L.DomEvent.disableClickPropagation(zoomRef.current);
    }
  }, []);

  return (
    <div
      ref={zoomRef}
      className="map-zoom leaflet-top leaflet-right"
      style={{ zIndex: 1000, pointerEvents: "auto" }}
    >
      <button aria-label={t.map.zoomIn} onClick={() => map.zoomIn()}>
        +
      </button>
      <button aria-label={t.map.zoomOut} onClick={() => map.zoomOut()}>
        −
      </button>
    </div>
  );
}

export default function ShoppingMap({
  stops,
  origin,
  route,
  online,
  active,
  picking,
  radiusKm = 11, // <-- Agregado: prop con valor por defecto de 11 km
  onOrigin,
  onFocus,
}: {
  stops: Stop[];
  origin: Point;
  route: Route | null;
  online: boolean;
  active: BranchId | null;
  picking: boolean;
  radiusKm?: number; // <-- Agregado
  onOrigin: (point: Point) => void;
  onFocus: (id: BranchId) => void;
}) {
  const { t } = useLang();

  return (
    <MapContainer
      center={[origin.lat || 25.67, origin.lng || -100.32]}
      zoom={12}
      className={`leaflet-map w-full h-full relative ${picking ? "picking" : ""}`}
      scrollWheelZoom={false}
      zoomControl={false}
    >
      {online && (
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      )}

      {/* NUEVO: Círculo del radio de cobertura (conversión de KM a metros) */}
      <Circle
        center={[origin.lat, origin.lng]}
        radius={radiusKm * 1000}
        pathOptions={{
          color: "#2563eb",
          fillColor: "#3b82f6",
          fillOpacity: 0.12,
          weight: 2,
          dashArray: "5, 5",
        }}
      />

      <Controller
        stops={stops}
        origin={origin}
        active={active}
        picking={picking}
        onOrigin={onOrigin}
      />

      <ZoomButtons />

      <Marker position={[origin.lat, origin.lng]} icon={originIcon}>
        <Popup>{t.map.startPoint}</Popup>
      </Marker>

      {stops.map((stop, index) => (
        <Marker
          key={`${stop.id}-${index}`}
          position={[stop.lat, stop.lng]}
          eventHandlers={{ click: () => onFocus(stop.id) }}
          icon={L.divIcon({
            className: `stop-icon ${active === stop.id ? "selected" : ""}`,
            html: `<span><b>${index + 1}</b></span>`,
            iconSize: [34, 42],
            iconAnchor: [17, 40],
          })}
        >
          <Popup>
            <div className="p-1">
              <strong className="block text-sm font-bold">{stop.name}</strong>
              {stop.products && stop.products.length > 0 && (
                <p className="text-xs text-gray-600 mt-1">
                  {stop.products.join(", ")}
                </p>
              )}
              <small className="block text-[10px] text-gray-500 mt-1">
                {t.map.confirmInventoryPopup}
              </small>
            </div>
          </Popup>
        </Marker>
      ))}

      {online && route?.status === "available" && route.coordinates && (
        <Polyline
          positions={route.coordinates.map(([lng, lat]) => [lat, lng])}
          pathOptions={{ color: "#007a53", weight: 5, opacity: 0.9 }}
        />
      )}
    </MapContainer>
  );
}