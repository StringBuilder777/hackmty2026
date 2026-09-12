"use client";

import Image from "next/image";
import { Building2, CalendarDays, ExternalLink, Globe2, ShieldAlert, UserRoundSearch } from "lucide-react";
import type { Analysis } from "@/lib/types";
import { safeHref } from "@/lib/shopping";
import EvidenceList from "./EvidenceList";
import FlagSummary from "./FlagSummary";

function value(value: string | number | null | undefined, fallback: string): string {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

export default function WebsiteAuditPanel({ analysis, english }: { analysis: Analysis; english: boolean }) {
  const site = analysis.website_profile;
  const store = analysis.store_profile;
  const registration = analysis.domain_registration;
  const risk = analysis.risk;
  if (!site || !risk) return null;
  const unavailable = english ? "Not available" : "No disponible";
  const lookup = registration ? safeHref(registration.lookup_url) : null;
  return (
    <>
      <div className="website-audit-header">
        <div className="website-identity">
          <span className="website-logo">
            {site.image ? <Image src={site.image} alt="" width={58} height={58} unoptimized referrerPolicy="no-referrer" /> : <Globe2 size={25} />}
          </span>
          <div><h2>{site.title}</h2><p>{site.domain}</p><small>{site.description}</small></div>
        </div>
        <div className={`risk-box website-risk risk-${risk.level}`}>
          <ShieldAlert size={21} />
          <div><strong>{english ? "Phishing risk:" : "Riesgo de phishing:"} {risk.level}</strong><p>{risk.explanation}</p></div>
        </div>
      </div>

      <section className="web-facts" aria-label={english ? "Website identity and registration" : "Identidad y registro del sitio"}>
        <article><Building2 size={18} /><span>{english ? "Declared organization" : "Organización declarada"}</span><strong>{value(site.declared_organization || store?.name, unavailable)}</strong></article>
        <article><UserRoundSearch size={18} /><span>{english ? "Seller / operator" : "Vendedor u operador"}</span><strong>{value(store?.seller_name, unavailable)}</strong></article>
        <article><CalendarDays size={18} /><span>{english ? "Domain age" : "Antigüedad del dominio"}</span><strong>{registration?.age_days !== null && registration?.age_days !== undefined ? `${registration.age_days} ${english ? "days" : "días"}` : unavailable}</strong></article>
        <article><Globe2 size={18} /><span>{english ? "Registrar" : "Registrador"}</span><strong>{value(registration?.registrar, unavailable)}</strong></article>
      </section>

      <details className="rdap-details">
        <summary>{english ? "View RDAP / WHOIS registration data" : "Ver datos de registro RDAP / WHOIS"}</summary>
        <dl>
          <div><dt>{english ? "Created" : "Creado"}</dt><dd>{value(registration?.created_at, unavailable)}</dd></div>
          <div><dt>{english ? "Updated" : "Actualizado"}</dt><dd>{value(registration?.updated_at, unavailable)}</dd></div>
          <div><dt>{english ? "Expires" : "Expira"}</dt><dd>{value(registration?.expires_at, unavailable)}</dd></div>
          <div><dt>Nameservers</dt><dd>{registration?.nameservers?.join(", ") || unavailable}</dd></div>
        </dl>
        {lookup && <a href={lookup} target="_blank" rel="noopener noreferrer">{english ? "Open public RDAP source" : "Abrir fuente pública RDAP"} <ExternalLink size={12} /></a>}
        <small>{registration?.note}</small>
      </details>

      {risk.agent_assessment && <section className="agent-assessment"><div><span>{english ? "Bedrock agent assessment" : "Evaluación del agente Bedrock"}</span><strong>{risk.agent_assessment.level}</strong></div><p>{risk.agent_assessment.explanation}</p><small>{english ? "The agent interprets collected evidence; it does not browse or certify the site." : "El agente interpreta la evidencia recolectada; no navega ni certifica el sitio."}</small></section>}
      <FlagSummary evidence={risk.evidence} />
      <EvidenceList evidence={risk.evidence} label={english ? "View phishing evidence and sources" : "Ver evidencias y fuentes de phishing"} />
      {analysis.limitations.length > 0 && <details className="limitations"><summary>{english ? "Scope and limitations" : "Alcance y limitaciones"}</summary><ul>{analysis.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details>}
    </>
  );
}
