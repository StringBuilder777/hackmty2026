"use client";

import Image from "next/image";
import { Building2, ExternalLink, FileText, Globe2, ImageIcon, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { Product, StoreProfile } from "@/lib/types";
import { safeHref } from "@/lib/shopping";

function SourceLink({ href, label }: { href: string; label: string }) {
  const safe = safeHref(href);
  return safe ? <a href={safe} target="_blank" rel="noopener noreferrer">{label} <ExternalLink size={12} /></a> : null;
}

function MerchantLogo({ src, name }: { src: string | null | undefined; name: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="merchant-logo">
      {src && !failed ? (
        <Image
          src={src}
          alt={`Logo de ${name}`}
          width={48}
          height={48}
          unoptimized
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <Building2 size={22} aria-hidden="true" />
      )}
    </span>
  );
}

export default function InvestigationPanel({
  product,
  store,
  english,
}: {
  product: Product;
  store: StoreProfile | null;
  english: boolean;
}) {
  const title = english ? "Product & merchant investigation" : "Investigación de producto y tienda";
  const images = product.images ?? [];
  const specifications = product.specifications ?? [];
  const contacts = store?.contacts ?? [];
  const policyLinks = store?.policy_links ?? [];
  return (
    <section className="investigation-panel" aria-label={title}>
      <div className="investigation-heading">
        <div>
          <span>{title}</span>
          <small>{english ? "Only public, source-linked declarations" : "Sólo declaraciones públicas con fuente"}</small>
        </div>
        <ShieldCheck size={20} />
      </div>
      <div className="merchant-snapshot">
        <div className="merchant-card merchant-company-card">
          <MerchantLogo key={store?.image || "merchant-fallback"} src={store?.image} name={store?.name || product.store} />
          <div>
            <span>{english ? "Company / brand" : "Empresa / marca"}</span>
            <strong>{product.brand || (english ? "Not published" : "No publicada")}</strong>
            <small>{store?.name || product.store}</small>
          </div>
        </div>
        <div className="merchant-card">
          <span>{english ? "Store" : "Tienda"}</span>
          <strong>{store?.name || product.store}</strong>
        </div>
        <div className="merchant-card">
          <span>{english ? "Domain" : "Dominio"}</span>
          <strong>{store?.domain || product.store}</strong>
        </div>
        <div className="merchant-card">
          <span>{english ? "Seller" : "Vendedor"}</span>
          {store?.seller_url ? (
            <SourceLink href={store.seller_url} label={store.seller_name || (english ? "Public profile" : "Perfil público")} />
          ) : <strong>{store?.seller_name || (english ? "Not published" : "No publicado")}</strong>}
        </div>
      </div>
      <details>
        <summary>{english ? "View product, merchant and source details" : "Ver detalles del producto, tienda y fuentes"}</summary>
      <div className="investigation-grid">
        <section className="product-research">
          <div className="gallery" aria-label={english ? "Product images" : "Imágenes del artículo"}>
            {images.length ? images.slice(0, 4).map((image) => (
              <Image key={image} unoptimized width={160} height={160} src={image} alt={product.name} loading="lazy" referrerPolicy="no-referrer" />
            )) : <ImageIcon aria-label={english ? "No public image" : "Sin imagen pública"} />}
          </div>
          {product.description && <p className="product-description">{product.description}</p>}
          {specifications.length > 0 && (
            <dl className="spec-list">
              {specifications.slice(0, 8).map((spec) => <div key={`${spec.name}-${spec.value}`}><dt>{spec.name}</dt><dd>{spec.value}</dd></div>)}
            </dl>
          )}
          <SourceLink href={product.url} label={english ? "Open product source" : "Abrir fuente del producto"} />
        </section>
        <section className="merchant-research">
          <div className="merchant-title"><Building2 size={17} /><div><strong>{store?.name || product.store}</strong><small>{store?.domain || product.store}</small></div></div>
          {store?.description && <p>{store.description}</p>}
          {store?.seller_name && (
            <p className="seller-detail">
              <strong>{english ? "Seller:" : "Vendedor:"}</strong>{" "}
              {store.seller_url ? <SourceLink href={store.seller_url} label={store.seller_name} /> : store.seller_name}
            </p>
          )}
          <div className="merchant-facts">
            <div><Globe2 size={15} /><span>{english ? "Domain analyzed" : "Dominio analizado"}</span><strong>{store?.domain || product.store}</strong></div>
            <div><FileText size={15} /><span>{english ? "Public policy links" : "Enlaces públicos de política"}</span><strong>{policyLinks.length}</strong></div>
          </div>
          {store && <div className="merchant-links">
            {contacts.slice(0, 2).map((href) => <SourceLink key={href} href={href} label={english ? "Contact / support" : "Contacto / soporte"} />)}
            {policyLinks.slice(0, 2).map((href) => <SourceLink key={href} href={href} label={english ? "Policy source" : "Fuente de política"} />)}
          </div>}
          <small className="research-disclaimer">{english ? "Presence of links is not proof of legal identity or fulfillment." : "La presencia de enlaces no demuestra identidad legal ni cumplimiento."}</small>
        </section>
      </div>
      </details>
    </section>
  );
}
