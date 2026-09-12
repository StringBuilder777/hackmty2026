import {
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  TriangleAlert,
} from "lucide-react";
import type { Evidence } from "@/lib/types";
import { safeHref } from "@/lib/shopping";
import { useLang } from "@/lib/i18n";
export default function EvidenceList({
  evidence,
  label,
}: {
  evidence: Evidence[];
  label?: string;
}) {
  const { t } = useLang();
  return (
    <details className="evidence">
      <summary>
        {label ?? t.evidenceList.defaultLabel} <span>{evidence.length}</span>
      </summary>
      <div className="evidence-body">
        {evidence.map((item, i) => (
          <div className="evidence-row" key={`${item.title}-${i}`}>
            {item.status === "observed" ? (
              <CheckCircle2 size={16} />
            ) : item.status === "warning" ? (
              <TriangleAlert size={16} />
            ) : (
              <CircleHelp size={16} />
            )}
            <div>
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
              {safeHref(item.source) && (
                <a
                  href={safeHref(item.source)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t.evidenceList.checkSource} <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}