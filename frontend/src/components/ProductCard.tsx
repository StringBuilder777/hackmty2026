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
import { useLang } from "@/lib/i18n";
import EvidenceList from "./EvidenceList";
export function ProductImage({
  product,
  online,
}: {
  product: Product;
  online: boolean;
}) {
  const { t } = useLang();
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
              ? t.productCard.demoAlt
              : product.name
          }
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      ) : (
        <Headphones size={32} aria-label={t.productCard.imageUnavailable} />
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
  const { t } = useLang();
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
              ? t.productCard.branchesInfo(product.branches.length)
              : t.productCard.noBranches}
          </span>
          <span className={`match ${product.match}`}>
            {product.match === "identical"
              ? t.productCard.matchIdentical
              : product.match === "original"
                ? t.productCard.matchOriginal
                : t.productCard.matchSimilar}
          </span>
        </div>
        <div className="offer-price">
          <strong>{formatMoney(product.price, product.currency)}</strong>
          <small>
            {product.shipping === null
              ? t.productCard.shippingPending
              : t.productCard.shippingLabel(formatMoney(product.shipping, product.currency))}
          </small>
        </div>
        <button
          className="add-button"
          aria-label={t.productCard.addAria(added, product.store)}
          disabled={added}
          onClick={onAdd}
        >
          {added && <Check size={16} />}
          <span>{added ? t.productCard.added : t.productCard.add}</span>
        </button>
      </div>
      <details className="offer-details">
        <summary>{t.productCard.detailsSummary}</summary>
        <div>
          <strong>{product.name}</strong>
          <p>
            {[product.brand, product.model, product.variant, product.condition]
              .filter(Boolean)
              .join(" · ") || t.productCard.specsPending}
          </p>
          <p>
            {t.productCard.skuGtin(
              product.sku || t.productCard.unknown,
              product.gtin || t.productCard.unknown,
            )}
          </p>
          <p>{product.match_reason}</p>
          <p>
            {product.availability}. {t.productCard.checkedAt(dateLabel(product.checked_at))}
          </p>
          <p>{t.productCard.totalWithShipping(formatMoney(product.total, product.currency))}</p>
          {safeHref(product.url) && (
            <a
              href={safeHref(product.url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {product.demo ? t.productCard.exampleLink : t.productCard.viewStore}{" "}
              <ExternalLink size={12} />
            </a>
          )}
          <EvidenceList evidence={product.evidence} />
        </div>
      </details>
    </article>
  );
}