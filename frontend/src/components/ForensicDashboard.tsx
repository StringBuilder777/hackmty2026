"use client";
import {
  Download,
  FileText,
  ShieldCheck,
  Database,
  Upload,
  Play,
  RotateCcw,
  AlertTriangle,
  Layers,
  FileCode,
  CheckCircle2,
  Coins,
  Sparkles,
} from "lucide-react";
import { useMemo, useState, useRef } from "react";
import { API, api } from "@/lib/api";
import type { ForensicPreflight, ForensicSubmission } from "@/lib/types";

const KEY = "buenpaso-forensic-v1";
const money = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

function save(name: string, data: string, type: string) {
  const url = URL.createObjectURL(new Blob([data], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function sqliteBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("No se pudo leer el estate SQLite."));
    reader.onload = () => {
      const value = typeof reader.result === "string" ? reader.result.split(",")[1] : "";
      if (value) resolve(value);
      else reject(new Error("El estate está vacío."));
    };
    reader.readAsDataURL(file);
  });
}

function MethodPanel() {
  return (
    <section className="forensic-method" aria-labelledby="forensic-method-title">
      <div>
        <p className="forensic-method-eyebrow">Controles contra alucinación</p>
        <h2 id="forensic-method-title">Cómo se forma cada hallazgo</h2>
        <p>El modelo no decide hechos, entidades ni montos. Esos elementos salen exclusivamente de consultas SQLite y se validan antes de mostrarse.</p>
      </div>
      <ol className="forensic-method-steps">
        <li><span>1</span><strong>Estate SQLite</strong><small>Esquema y registros reales o demostrativos.</small></li>
        <li><span>2</span><strong>Reglas deterministas</strong><small>Cinco detectores SQL; misma semilla, mismo resultado.</small></li>
        <li><span>3</span><strong>Exhibits y conciliación</strong><small>IDs existentes y pesos comprobados contra las tablas.</small></li>
        <li><span>4</span><strong>Narrativa acotada</strong><small>Solo resume evidencia validada, máximo 150 palabras; offline por defecto.</small></li>
      </ol>
      <details className="forensic-method-limits">
        <summary>Qué no hace el modelo</summary>
        <p>No consulta internet, no genera IDs, no calcula montos, no cambia el nivel de confianza y no acusa una entidad sin los exhibits mínimos. Si no hay proveedor configurado, usa una plantilla determinista y registra 0 llamadas LLM / $0 MXN.</p>
      </details>
    </section>
  );
}

export default function ForensicDashboard() {
  const [estatePath, setEstatePath] = useState("");
  const [estateFile, setEstateFile] = useState<File | null>(null);
  const [seed, setSeed] = useState("2026");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [report, setReport] = useState<ForensicSubmission | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw: unknown = JSON.parse(localStorage.getItem(KEY) || "null");
      return raw && typeof raw === "object" ? (raw as ForensicSubmission) : null;
    } catch {
      return null;
    }
  });

  const [loading, setLoading] = useState(false);
  const [preflighting, setPreflighting] = useState(false);
  const [preflight, setPreflight] = useState<ForensicPreflight | null>(null);
  const [error, setError] = useState("");

  const totals = useMemo(
    () => ({
      exposure: (report?.findings ?? []).reduce((sum, f) => sum + f.peso_amount, 0),
      proven: (report?.findings ?? []).filter((f) => f.confidence === "proven").length,
    }),
    [report]
  );

  async function inspectEstate(): Promise<boolean> {
    if (!estateFile && !estatePath.trim()) {
      setError("Selecciona un archivo SQLite o indica una ruta local del backend.");
      return false;
    }
    setPreflighting(true);
    setError("");
    try {
      if (estateFile && estateFile.size > 14 * 1024 * 1024) {
        throw new Error("El estate supera 14 MB; usa una ruta local del backend o un archivo menor.");
      }
      const input = estateFile
        ? { path: "/audit/preflight/upload", body: { estate_base64: await sqliteBase64(estateFile), seed: Number(seed) } }
        : { path: "/audit/preflight", body: { estate_path: estatePath.trim(), seed: Number(seed) } };

      const result = await api<ForensicPreflight>(input.path, input.body);
      setPreflight(result);
      return result.ready;
    } catch (cause) {
      setPreflight(null);
      setError(cause instanceof Error ? cause.message : "No fue posible verificar el estate.");
      return false;
    } finally {
      setPreflighting(false);
    }
  }

  async function run(event: React.FormEvent) {
    event.preventDefault();
    if (!(await inspectEstate())) return;
    setLoading(true);
    setError("");
    try {
      const input = estateFile
        ? { path: "/audit/upload", body: { estate_base64: await sqliteBase64(estateFile), seed: Number(seed) } }
        : { path: "/audit/run", body: { estate_path: estatePath.trim(), seed: Number(seed) } };

      const result = await api<ForensicSubmission>(input.path, input.body);
      setReport(result);
      localStorage.setItem(KEY, JSON.stringify(result));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No fue posible ejecutar la auditoría.");
    } finally {
      setLoading(false);
    }
  }

  async function caseFile() {
    try {
      const response = await fetch(`${API}/audit/case-file`);
      if (!response.ok) throw new Error("El expediente Markdown no está disponible.");
      save("case-file.md", await response.text(), "text/markdown;charset=utf-8");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No fue posible descargar el expediente.");
    }
  }

  async function runDemo() {
    setLoading(true);
    setError("");
    try {
      const result = await api<ForensicSubmission>("/audit/demo", { seed: Number(seed) });
      setReport(result);
      localStorage.setItem(KEY, JSON.stringify(result));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No fue posible ejecutar el caso demostrativo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="forensic-page" id="auditoria">
      {/* Hero Section with Context and Controls */}
      <div className="forensic-hero">
        <div className="forensic-hero-copy">
          <div className="forensic-badge-row">
            <span className="forensic-track-pill">Track 2 · HackMTY 2026</span>
            <span className="forensic-sub-pill">Auditoría Forense Determinista</span>
          </div>
          <h1>Expediente de Auditoría Forense</h1>
          <p className="forensic-subtitle">
            Detección determinista, reproducible y auditable sobre SQLite, sin dependencias de red externa.
          </p>

          <div className="forensic-highlights">
            <div className="forensic-highlight-item">
              <ShieldCheck size={16} />
              <span>Detección determinista (Seed fija)</span>
            </div>
            <div className="forensic-highlight-item">
              <Database size={16} />
              <span>Ejecución local sobre SQLite</span>
            </div>
            <div className="forensic-highlight-item">
              <FileCode size={16} />
              <span>Case File y evidencia auditable</span>
            </div>
          </div>
        </div>

        <form className="audit-runner" onSubmit={run}>
          <div className="audit-field">
            <div className="audit-field-header">
              <label className="audit-label" htmlFor="estate-file-input">
                <Database size={14} /> Estate SQLite (.db)
              </label>
              <span className="audit-label-badge">Recomendado</span>
            </div>

            <div
              className={`audit-dropzone ${estateFile ? "has-file" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const file = e.dataTransfer.files?.[0];
                if (file) setEstateFile(file);
              }}
            >
              <input
                id="estate-file-input"
                ref={fileInputRef}
                type="file"
                accept=".db,application/vnd.sqlite3,application/x-sqlite3"
                onChange={(e) => { setEstateFile(e.target.files?.[0] ?? null); setPreflight(null); }}
                className="audit-hidden-file"
              />

              {estateFile ? (
                <div className="audit-file-selected">
                  <div className="audit-file-info">
                    <Database size={20} className="audit-file-icon" />
                    <div>
                      <strong className="audit-file-name">{estateFile.name}</strong>
                      <small className="audit-file-size">{(estateFile.size / (1024 * 1024)).toFixed(2)} MB</small>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="audit-remove-file"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEstateFile(null);
                      setPreflight(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                  >
                    Cambiar
                  </button>
                </div>
              ) : (
                <div className="audit-dropzone-prompt">
                  <div className="audit-upload-circle">
                    <Upload size={18} />
                  </div>
                  <div>
                    <span className="dropzone-title">Seleccionar o arrastrar archivo .db</span>
                    <small className="dropzone-subtitle">Máximo 14 MB para carga en navegador</small>
                  </div>
                </div>
              )}
            </div>
            <small className="audit-hint">El archivo se analiza en memoria y no se almacena en el servidor.</small>
          </div>

          <div className="audit-divider">
            <span>o ruta local del servidor</span>
          </div>

          <div className="audit-field">
            <label className="audit-label" htmlFor="backend-estate-path">
              Ruta local en el backend
            </label>
            <input
              id="backend-estate-path"
              value={estatePath}
              onChange={(e) => { setEstatePath(e.target.value); setPreflight(null); }}
              placeholder="/ruta/al/estate.db"
              className="audit-input"
            />
          </div>

          <div className="audit-runner-row">
            <div className="audit-field audit-seed-field">
              <label className="audit-label" htmlFor="audit-seed">
                Semilla
              </label>
              <input
                id="audit-seed"
                required
                type="number"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                className="audit-input"
              />
            </div>

            <button
              type="submit"
              className="audit-submit-button"
              disabled={loading || preflighting || (!estateFile && !estatePath.trim())}
            >
              {loading ? (
                <>
                  <span className="audit-spinner" aria-hidden="true" />
                  Auditando…
                </>
              ) : (
                <>
                  <Play size={16} fill="currentColor" />
                  Ejecutar auditoría
                </>
              )}
            </button>
          </div>
          <button type="button" className="audit-preflight-button" disabled={loading || preflighting || (!estateFile && !estatePath.trim())} onClick={() => void inspectEstate()}>
            <ShieldCheck size={15} /> {preflighting ? "Verificando dataset…" : "Verificar dataset antes de auditar"}
          </button>
          <button type="button" className="audit-demo-button" disabled={loading} onClick={runDemo}>
            <Sparkles size={15} /> Probar caso demostrativo (5 esquemas)
          </button>
        </form>

        {error ? (
          <div className="forensic-error-banner" role="alert">
            <AlertTriangle size={18} />
            <p>{error}</p>
          </div>
        ) : null}
      </div>

      <MethodPanel />

      {preflight ? (
        <section className="forensic-preflight" aria-labelledby="preflight-title">
          <div>
            <p className="forensic-method-eyebrow">Preflight local</p>
            <h2 id="preflight-title">Dataset verificado: {preflight.estate_filename}</h2>
            <p>SHA-256: <code>{preflight.estate_sha256}</code></p>
          </div>
          <dl className="preflight-facts">
            <div><dt>Tablas</dt><dd>{Object.values(preflight.tables).reduce((sum, count) => sum + count, 0)} registros</dd></div>
            <div><dt>Periodo</dt><dd>{preflight.period.from_date ?? "Sin fecha"} — {preflight.period.to_date ?? "Sin fecha"}</dd></div>
            <div><dt>Archivo</dt><dd>{(preflight.estate_bytes / 1024).toFixed(1)} KB · listo</dd></div>
          </dl>
          {preflight.quality_warnings.length ? <ul className="preflight-warnings">{preflight.quality_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : <p className="preflight-ok">Sin advertencias de calidad que bloqueen las reglas.</p>}
        </section>
      ) : null}

      {report ? (
        <>
          {/* Executive Summary Stat Cards */}
          <div className="forensic-summary">
            <article className="stat-card exposure">
              <div className="stat-icon-wrap">
                <Coins size={20} />
              </div>
              <div className="stat-body">
                <span className="stat-title">Exposición total calculada</span>
                <strong className="stat-metric">{money.format(totals.exposure)}</strong>
              </div>
            </article>

            <article className="stat-card findings">
              <div className="stat-icon-wrap">
                <AlertTriangle size={20} />
              </div>
              <div className="stat-body">
                <span className="stat-title">Hallazgos detectados</span>
                <strong className="stat-metric">
                  {report.findings.length}
                  <span className="stat-badge proven">{totals.proven} comprobados</span>
                </strong>
              </div>
            </article>

            <article className="stat-card replay">
              <div className="stat-icon-wrap">
                <RotateCcw size={20} />
              </div>
              <div className="stat-body">
                <span className="stat-title">Replay & Rendimiento</span>
                <strong className="stat-metric">
                  Seed {report.seed}
                  <span className="stat-subtext">
                    {report.run_metadata.wall_clock_seconds.toFixed(3)}s · {report.run_metadata.llm_calls} LLM
                  </span>
                </strong>
              </div>
            </article>

            <article className="stat-card leads">
              <div className="stat-icon-wrap">
                <Layers size={20} />
              </div>
              <div className="stat-body">
                <span className="stat-title">Leads descartados</span>
                <strong className="stat-metric">
                  {report.leads_not_pursued.length}
                  <span className="stat-subtext">analizados y cerrados</span>
                </strong>
              </div>
            </article>
          </div>

          {/* Export and Action Toolbar */}
          <div className="forensic-actions">
            <button
              type="button"
              className="forensic-action-btn primary"
              onClick={() => save("submission.json", JSON.stringify(report, null, 2), "application/json")}
            >
              <Download size={16} /> Exportar submission.json
            </button>
            <button type="button" className="forensic-action-btn secondary" onClick={caseFile}>
              <FileText size={16} /> Descargar Case File (.md)
            </button>
            <button
              type="button"
              className="forensic-action-btn ghost"
              onClick={() => {
                setReport(null);
                localStorage.removeItem(KEY);
              }}
            >
              <RotateCcw size={15} /> Nueva auditoría
            </button>
          </div>

          {/* Findings List */}
          <div className="finding-list">
            {report.findings.length > 0 ? (
              report.findings.map((f, index) => (
                <article className="finding-card" key={`${f.scheme_type}-${index}`}>
                  <header className="finding-header">
                    <div className="finding-title-group">
                      <div className="finding-pill-row">
                        <span className={`scheme-badge scheme-${f.scheme_type}`}>
                          {f.scheme_type.replaceAll("_", " ")}
                        </span>
                        <span className={`confidence-badge ${f.confidence}`}>
                          {f.confidence === "proven" ? "✓ Comprobado" : "Probable"}
                        </span>
                      </div>
                      <h2>{f.entities.join(" · ")}</h2>
                    </div>
                    <div className="finding-amount-card">
                      <span className="amount-label">Monto expuesto</span>
                      <strong className="amount-value">{money.format(f.peso_amount)}</strong>
                    </div>
                  </header>

                  <div className="finding-rule-callout">
                    <strong>Regla infringida:</strong>
                    <span>{f.rule_broken}</span>
                  </div>

                  <p className="finding-narrative">{f.narrative}</p>

                  <div className="finding-section">
                    <h3>Rastro del dinero</h3>
                    {f.money_trail.length ? (
                      <ol className="money-trail">
                        {f.money_trail.map((s) => (
                          <li key={s.exhibit_id} className="money-trail-item">
                            <div className="trail-route">
                              <span className="trail-entity from">{s.from}</span>
                              <span className="trail-arrow">→</span>
                              <span className="trail-entity to">{s.to}</span>
                            </div>
                            <div className="trail-val">{money.format(s.amount)}</div>
                            <div className="trail-footer">
                              <span>{s.date}</span>
                              <span className="trail-exhibit-id">{s.exhibit_id}</span>
                            </div>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="finding-muted">No aplica un rastro bancario para este hallazgo documental.</p>
                    )}
                  </div>

                  <div className="finding-section">
                    <h3>Evidencias y conciliación</h3>
                    <div className="table-scroll">
                      <table className="evidence-table">
                        <thead>
                          <tr>
                            <th>ID Exhibición</th>
                            <th>Tabla Origen</th>
                            <th>ID Registro</th>
                            <th>Qué prueba</th>
                          </tr>
                        </thead>
                        <tbody>
                          {f.exhibits.map((e) => (
                            <tr key={e.exhibit_id}>
                              <td>
                                <span className="exhibit-id-badge">{e.exhibit_id}</span>
                              </td>
                              <td>
                                <span className="source-table-tag">{e.source_table}</span>
                              </td>
                              <td>
                                <code className="record-id-code">{e.record_id}</code>
                              </td>
                              <td className="note-cell">{e.note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="reconciliation-box">
                    <CheckCircle2 size={18} className="recon-icon" />
                    <span>
                      Monto reclamado conciliado internamente: <strong>{money.format(f.peso_amount)}</strong>. El Case File
                      exportado muestra la ecuación auditable y los identificadores de cotejo.
                    </span>
                  </div>
                </article>
              ))
            ) : (
              <div className="finding-empty">
                <p>No se encontraron patrones que superaran el umbral determinista de irregularidad.</p>
              </div>
            )}
          </div>

          {/* Leads Not Pursued */}
          <section className="leads-card">
            <div className="leads-header">
              <div>
                <h2>Leads no perseguidos</h2>
                <p>Señales preliminares investigadas y cerradas determinísticamente por las reglas de validación.</p>
              </div>
              <span className="leads-count-badge">{report.leads_not_pursued.length} cerrados</span>
            </div>

            {report.leads_not_pursued.length > 0 ? (
              <div className="leads-list">
                {report.leads_not_pursued.map((lead, i) => (
                  <details key={`${lead.entity}-${i}`} className="lead-accordion-item">
                    <summary className="lead-summary">
                      <span className="lead-summary-text">
                        <strong>{lead.entity}</strong>
                        <span className="lead-summary-signal"> — {lead.signal}</span>
                      </span>
                      <span className="lead-closed-pill">Cerrado por: {lead.closed_by}</span>
                    </summary>
                    <div className="lead-body">
                      <p className="lead-reason">{lead.reason}</p>
                      <div className="lead-meta-row">
                        <span className="lead-meta-label">Herramientas:</span>
                        <div className="lead-tools-list">
                          {lead.tool_calls_made.length ? (
                            lead.tool_calls_made.map((tool) => (
                              <span key={tool} className="tool-badge">
                                {tool}
                              </span>
                            ))
                          ) : (
                            <span className="muted-text">No aplica</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <p className="finding-muted">No hubo leads preliminares que debieran cerrarse.</p>
            )}
          </section>
        </>
      ) : (
        /* Empty State with Apple Aesthetics */
        <div className="forensic-empty-card">
          <div className="forensic-empty-icon-wrap">
            <ShieldCheck size={38} />
          </div>
          <h2>Expediente listo para ejecución</h2>
          <p className="forensic-empty-desc">
            Carga un estate SQLite (.db) o ingresa una ruta local del backend para generar y conservar un expediente
            reproducible, con detección determinista de irregularidades, rastro financiero y conciliación de evidencias.
          </p>

          <div className="forensic-empty-grid">
            <div className="forensic-feature-card">
              <div className="feature-icon-badge">
                <Database size={20} />
              </div>
              <strong>SQLite Local</strong>
              <p>Análisis de esquemas sobre tablas de transacciones, contratos y proveedores sin conexión a internet.</p>
            </div>

            <div className="forensic-feature-card">
              <div className="feature-icon-badge">
                <Sparkles size={20} />
              </div>
              <strong>Detección determinista</strong>
              <p>Heurísticas precisas para proveedores fantasma, sobornos, round tripping y división de umbrales.</p>
            </div>

            <div className="forensic-feature-card">
              <div className="feature-icon-badge">
                <FileCode size={20} />
              </div>
              <strong>Expediente reproducible</strong>
              <p>Exportación de submission.json y Case File en Markdown con ecuación matemática exacta.</p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
