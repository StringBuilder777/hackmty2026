"use client";
import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { BranchId, Point, Stop, Route } from "@/lib/types";
const originIcon = L.divIcon({
  className: "origin-icon",
  html: "<span></span>",
  iconSize: [18, 18],
  iconAnchor: [9, 9],
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
    if (coordinates.length > 1)
      map.fitBounds(coordinates, { padding: [70, 90], maxZoom: 14 });
    else map.setView([origin.lat, origin.lng], 12);
  }, [map, stops, origin]);
  useEffect(() => {
    const target = stops.find((s) => s.id === active);
    if (target) map.flyTo([target.lat, target.lng], 14, { duration: 0.5 });
  }, [active, map, stops]);
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}
export default function ShoppingMap({
  stops,
  origin,
  route,
  online,
  active,
  picking,
  onOrigin,
  onFocus,
}: {
  stops: Stop[];
  origin: Point;
  route: Route | null;
  online: boolean;
  active: BranchId | null;
  picking: boolean;
  onOrigin: (point: Point) => void;
  onFocus: (id: BranchId) => void;
}) {
  return (
    <MapContainer
      center={[25.67, -100.32]}
      zoom={12}
      className={`leaflet-map ${picking ? "picking" : ""}`}
      scrollWheelZoom={false}
      zoomControl={false}
    >
      {online && (
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      )}
      <Controller
        stops={stops}
        origin={origin}
        active={active}
        picking={picking}
        onOrigin={onOrigin}
      />
      <ZoomButtons />
      <Marker position={[origin.lat, origin.lng]} icon={originIcon}>
        <Popup>Punto de partida</Popup>
      </Marker>
      {stops.map((stop, index) => (
        <Marker
          key={stop.id}
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
            <strong>{stop.name}</strong>
            <p>{stop.products?.join(", ")}</p>
            <small>Confirma el inventario antes de salir.</small>
          </Popup>
        </Marker>
      ))}
      {online && route?.status === "available" && (
        <Polyline
          positions={route.coordinates.map(([lng, lat]) => [lat, lng])}
          pathOptions={{ color: "#147d68", weight: 5, opacity: 0.85 }}
        />
      )}
    </MapContainer>
  );
}
function ZoomButtons() {
  const map = useMap();
  return (
    <div
      className="map-zoom leaflet-top leaflet-right"
      ref={(element) => {
        if (element) L.DomEvent.disableClickPropagation(element);
      }}
    >
      <button aria-label="Acercar mapa" onClick={() => map.zoomIn()}>
        +
      </button>
      <button aria-label="Alejar mapa" onClick={() => map.zoomOut()}>
        −
      </button>
    </div>
  );
}
