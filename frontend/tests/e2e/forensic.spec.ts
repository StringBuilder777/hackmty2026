import { expect, test } from "@playwright/test";
import path from "node:path";

const submission = {
  seed: 2026,
  findings: [{
    scheme_type: "round_tripping",
    entities: ["RFC:VENDA", "RFC:VENDB"],
    narrative: "Tres transferencias equivalentes cierran un ciclo en cuatro días.",
    rule_broken: "Políticas internas de tesorería.",
    peso_amount: 300000,
    confidence: "probable",
    money_trail: [
      { from: "COMP", to: "A", amount: 100000, date: "2026-01-02", exhibit_id: "EX-001" },
      { from: "A", to: "B", amount: 100000, date: "2026-01-03", exhibit_id: "EX-002" },
      { from: "B", to: "COMP", amount: 100000, date: "2026-01-04", exhibit_id: "EX-003" },
    ],
    exhibits: [
      { exhibit_id: "EX-001", source_table: "bank_txns", record_id: "TX-1", note: "Salida." },
      { exhibit_id: "EX-002", source_table: "bank_txns", record_id: "TX-2", note: "Intermediación." },
      { exhibit_id: "EX-003", source_table: "bank_txns", record_id: "TX-3", note: "Retorno." },
    ],
  }, {
    scheme_type: "phantom_vendor",
    entities: ["RFC:EFOS211107F05"],
    narrative: "Proveedor listado como EFOS con facturas emitidas en el periodo auditado.",
    rule_broken: "CFF Art. 69-B: operaciones con EFOS.",
    peso_amount: 580000,
    confidence: "probable",
    money_trail: [],
    exhibits: [
      { exhibit_id: "EX-004", source_table: "efos_list", record_id: "EFOS211107F05", note: "RFC listado como presunto." },
    ],
  }],
  leads_not_pursued: [{
    entity: "RFC:SAFE", signal: "threshold_splitting", reason: "Operaciones separadas fuera de ventana.",
    tool_calls_made: ["SQL invoices"], closed_by: "investigator",
  }],
  run_metadata: { llm_calls: 0, mxn_cost: 0, wall_clock_seconds: 0.012, cost_by_role: {}, deterministic: true },
};

const preflight = {
  estate_filename: "estate.db",
  estate_sha256: "a".repeat(64),
  estate_bytes: 65536,
  tables: { invoices: 5, ledger: 2, bank_txns: 3 },
  period: { from_date: "2026-01-01", to_date: "2026-01-31" },
  quality_warnings: ["invoices: 1 grupo de factura potencialmente duplicado."],
  ready: true,
};

test("forensic: demo, evidence and exports render from a bounded audit response", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.route("**/audit/demo", (route) => route.fulfill({ json: submission }));
  await page.route("**/audit/preflight", (route) => route.fulfill({ json: preflight }));
  await page.route("**/audit/case-file", (route) => route.fulfill({
    contentType: "text/markdown", body: "# Case File\n\nEvidence verified.",
  }));

  await page.goto("/#auditoria");
  await expect(page.getByRole("heading", { name: "Expediente de Auditoría Forense" })).toBeVisible();
  await expect(page.getByText("Expediente listo para ejecución")).toBeVisible();
  await page.getByLabel("Ruta local en el backend").fill("/tmp/estate.db");
  await page.getByRole("button", { name: "Verificar dataset antes de auditar" }).click();
  await expect(page.getByText("Dataset verificado: estate.db")).toBeVisible();
  await expect(page.getByText("2026-01-01 — 2026-01-31")).toBeVisible();
  await page.getByRole("button", { name: /Probar caso demostrativo/ }).click();

  await expect(page.getByText("Hallazgos detectados")).toBeVisible();
  await expect(page.getByText("RFC:VENDA · RFC:VENDB")).toBeVisible();
  const roundTrippingFinding = page.locator(".finding-card").filter({ hasText: "RFC:VENDA · RFC:VENDB" });
  await expect(roundTrippingFinding.getByRole("button", { name: "Ver detalle" })).toBeVisible();
  await roundTrippingFinding.getByRole("button", { name: "Ver detalle" }).click();
  await expect(page.getByText("Monto reclamado conciliado internamente:")).toBeVisible();
  await page.getByRole("button", { name: /Phantom vendor/ }).click();
  await expect(page.locator(".finding-card")).toHaveCount(1);
  await expect(page.getByText("RFC:EFOS211107F05")).toBeVisible();
  await page.getByRole("button", { name: "Ver detalle" }).click();
  await expect(page.getByText("Proveedor listado como EFOS con facturas emitidas en el periodo auditado.")).toBeVisible();
  await expect(page.getByText("1 cerrados")).toBeVisible();
  const leadSummary = page.locator("details.lead-accordion-item > summary");
  await leadSummary.focus();
  await leadSummary.press("Enter");
  await expect(page.getByText("Operaciones separadas fuera de ventana.")).toBeVisible();

  const jsonDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar submission.json" }).click();
  expect((await jsonDownload).suggestedFilename()).toBe("submission.json");
  const caseDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: /Descargar Case File/ }).click();
  expect((await caseDownload).suggestedFilename()).toBe("case-file.md");
  expect(errors).toEqual([]);
});

test("forensic: selects the eight official CSV files as one estate", async ({ page }) => {
  let uploadedFiles = 0;
  await page.route("**/audit/preflight/upload", async (route) => {
    const body = route.request().postDataJSON() as { estate_files?: unknown[] };
    uploadedFiles = body.estate_files?.length ?? 0;
    await route.fulfill({ json: { ...preflight, estate_filename: "CSV bundle (8 tablas)" } });
  });
  await page.goto("/#auditoria");
  const csvDirectory = path.resolve("../deliverables/forensic-inputs/csv");
  const names = [
    "vendors.csv", "invoices.csv", "ledger.csv", "bank_txns.csv",
    "purchase_orders.csv", "contracts.csv", "employees.csv", "efos_list.csv",
  ];

  await page.getByLabel("Dataset DB, ZIP o CSV").setInputFiles(names.map((name) => path.join(csvDirectory, name)));
  await expect(page.getByText("8 archivos CSV")).toBeVisible();
  await page.getByRole("button", { name: "Verificar dataset antes de auditar" }).click();

  await expect(page.getByText("Dataset verificado: CSV bundle (8 tablas)")).toBeVisible();
  expect(uploadedFiles).toBe(8);
});
