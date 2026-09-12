import Image from "next/image";
import {
  Check,
  ExternalLink,
  Headphones,
  MapPin,
  ShoppingBag,
} from "lucide-react";
import type { Product } from "@/lib/types";
import { dateLabel, formatMoney, safeHref } from "@/lib/shopping";
import EvidenceList from "./EvidenceList";
export function ProductImage({
  product,
  online,
}: {
  product: Product;
  online: boolean;
}) {
  const source = product.demo
    ? "/headphones.png"
    : online
      ? safeHref(product.image)
      : undefined;
  return (
    <div className="product-image">
      {source ? (
        <Image
          unoptimized
          width={100}
          height={100}
          src={source}
          alt={
            product.demo
              ? "Ilustración de audífonos para el demo"
              : product.name
          }
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      ) : (
        <Headphones size={32} aria-label="Imagen no disponible" />
      )}
    </div>
  );
}
export default function ProductCard({
  product,
  added,
  online,
  onAdd,
}: {
  product: Product;
  added: boolean;
  online: boolean;
  onAdd: () => void;
}) {
  return (
    <article className={`offer ${added ? "offer-added" : ""}`}>
      <div className="offer-main">
        <ProductImage product={product} online={online} />
        <div className="offer-description">
          <strong>{product.store}</strong>
          <span className="offer-sub">
            {product.branches.length ? (
              <MapPin size={13} />
            ) : (
              <ShoppingBag size={13} />
            )}
            {product.branches.length
              ? `${product.branches.length} sucursal${product.branches.length > 1 ? "es" : ""} · inventario por verificar`
              : "Sin sucursal documentada"}
          </span>
          <span className={`match ${product.match}`}>
            {product.match === "identical"
              ? "Producto idéntico"
              : product.match === "original"
                ? "Producto consultado"
                : "Producto similar"}
          </span>
        </div>
        <div className="offer-price">
          <strong>{formatMoney(product.price, product.currency)}</strong>
          <small>
            {product.shipping === null
              ? "Envío por verificar"
              : `Envío ${formatMoney(product.shipping, product.currency)}`}
          </small>
        </div>
        <button
          className="add-button"
          aria-label={`${added ? "Agregado" : "Agregar"} ${product.store}`}
          disabled={added}
          onClick={onAdd}
        >
          {added && <Check size={16} />}
          <span>{added ? "Agregado" : "Agregar"}</span>
        </button>
      </div>
      <details className="offer-details">
        <summary>Detalles del producto y fuente</summary>
        <div>
          <strong>{product.name}</strong>
          <p>
            {[product.brand, product.model, product.variant, product.condition]
              .filter(Boolean)
              .join(" · ") || "Marca, modelo, variante y condición pendientes."}
          </p>
          <p>
            SKU: {product.sku || "desconocido"} · GTIN:{" "}
            {product.gtin || "desconocido"}
          </p>
          <p>{product.match_reason}</p>
          <p>
            {product.availability}. Consulta: {dateLabel(product.checked_at)}.
          </p>
          <p>Total con envío: {formatMoney(product.total, product.currency)}</p>
          {safeHref(product.url) && (
            <a
              href={safeHref(product.url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {product.demo ? "Enlace de ejemplo" : "Ver tienda"}{" "}
              <ExternalLink size={12} />
            </a>
          )}
          <EvidenceList evidence={product.evidence} />
        </div>
      </details>
    </article>
  );
}
