import { CheckCircle2, CircleHelp, TriangleAlert } from "lucide-react";
import type { Evidence } from "@/lib/types";
import { useLang } from "@/lib/i18n";

export default function FlagSummary({ evidence }: { evidence: Evidence[] }) {
  const { t } = useLang();
  const green = evidence.filter((item) => item.status === "observed");
  const red = evidence.filter((item) => item.status === "warning");
  const pending = evidence.filter((item) => item.status === "unavailable");

  return (
    <section className="flag-summary" aria-label={t.flagSummary.ariaLabel}>
      <div className="flag flag-green">
        <CheckCircle2 size={18} />
        <div>
          <strong>{t.flagSummary.greenCount(green.length)}</strong>
          <span>{green.length ? green.map((item) => item.title).join(" · ") : t.flagSummary.greenEmpty}</span>
        </div>
      </div>
      <div className="flag flag-red">
        <TriangleAlert size={18} />
        <div>
          <strong>{t.flagSummary.redCount(red.length)}</strong>
          <span>{red.length ? red.map((item) => item.title).join(" · ") : t.flagSummary.redEmpty}</span>
        </div>
      </div>
      {pending.length > 0 && (
        <div className="flag flag-pending">
          <CircleHelp size={18} />
          <div>
            <strong>{t.flagSummary.pendingCount(pending.length)}</strong>
            <span>{t.flagSummary.pendingNote}</span>
          </div>
        </div>
      )}
    </section>
  );
}