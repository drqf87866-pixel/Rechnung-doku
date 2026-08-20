import * as XLSX from "xlsx";
import { formatDatum } from "./format.js";

/**
 * Erzeugt einen Dateinamen-sicheren Teil aus dem Bauvorhaben-Namen.
 * @param {string} name
 * @returns {string}
 */
function safeFilenamePart(name) {
  const cleaned = name.replace(/[\\/:*?"<>|]+/g, "_").trim();
  return (cleaned || "Bauvorhaben").slice(0, 80);
}

/**
 * Exportiert die Rechnungen eines Bauvorhabens als .xlsx-Datei.
 * @param {string} bauvorhaben
 * @param {Object[]} invoices
 */
export function exportBauvorhabenExcel(bauvorhaben, invoices) {
  const rows = invoices.map((invoice) => ({
    Rechnungsnummer: invoice.rechnungsnummer ?? "",
    Betrag: invoice.rechnungsbetrag ?? "",
    Währung: invoice.waehrung && invoice.waehrung !== "UNKNOWN" ? invoice.waehrung : "EUR",
    Dateiname: invoice.filename ?? "",
    Upload: formatDatum(invoice.upload_time),
  }));

  const summe = invoices.reduce(
    (total, invoice) =>
      total + (invoice.rechnungsbetrag != null ? invoice.rechnungsbetrag : 0),
    0
  );
  const waehrung = invoices.find((invoice) => invoice.waehrung)?.waehrung;

  rows.push({
    Rechnungsnummer: "Gesamtsumme",
    Betrag: summe,
    Währung: waehrung && waehrung !== "UNKNOWN" ? waehrung : "EUR",
    Dateiname: "",
    Upload: "",
  });

  const worksheet = XLSX.utils.json_to_sheet(rows);
  worksheet["!cols"] = [
    { wch: 22 },
    { wch: 14 },
    { wch: 10 },
    { wch: 36 },
    { wch: 20 },
  ];

  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Rechnungen");
  XLSX.writeFile(workbook, `${safeFilenamePart(bauvorhaben)}.xlsx`);
}
