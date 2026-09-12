import {
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  TriangleAlert,
} from "lucide-react";
import type { Evidence } from "@/lib/types";
import { safeHref } from "@/lib/shopping";
export default function EvidenceList({
  evidence,
  label = "Ver evidencias",
}: {
  evidence: Evidence[];
  label?: string;
}) {
  return (
    <details className="evidence">
      <summary>
        {label} <span>{evidence.length}</span>
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
                  Consultar fuente <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
