import { CheckCircle2, CircleHelp, TriangleAlert } from "lucide-react";
import type { Evidence } from "@/lib/types";

export default function FlagSummary({ evidence }: { evidence: Evidence[] }) {
  const green = evidence.filter((item) => item.status === "observed");
  const red = evidence.filter((item) => item.status === "warning");
  const pending = evidence.filter((item) => item.status === "unavailable");

  return (
    <section className="flag-summary" aria-label="Resumen de banderas de verificación">
      <div className="flag flag-green">
        <CheckCircle2 size={18} />
        <div>
          <strong>{green.length} bandera{green.length === 1 ? "" : "s"} verde{green.length === 1 ? "" : "s"}</strong>
          <span>{green.length ? green.map((item) => item.title).join(" · ") : "No hay señales positivas verificadas."}</span>
        </div>
      </div>
      <div className="flag flag-red">
        <TriangleAlert size={18} />
        <div>
          <strong>{red.length} bandera{red.length === 1 ? "" : "s"} roja{red.length === 1 ? "" : "s"}</strong>
          <span>{red.length ? red.map((item) => item.title).join(" · ") : "No se detectaron alertas con la evidencia disponible."}</span>
        </div>
      </div>
      {pending.length > 0 && (
        <div className="flag flag-pending">
          <CircleHelp size={18} />
          <div>
            <strong>{pending.length} dato{pending.length === 1 ? "" : "s"} pendiente{pending.length === 1 ? "" : "s"}</strong>
            <span>Información no disponible no equivale a una señal roja.</span>
          </div>
        </div>
      )}
    </section>
  );
}
