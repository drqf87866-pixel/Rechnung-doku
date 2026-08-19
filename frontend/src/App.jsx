import { useCallback, useEffect, useState } from "react";
import {
  listInvoices,
  listBauvorhaben,
  updateInvoice,
  deleteInvoice,
} from "./api.js";
import UploadForm from "./components/UploadForm.jsx";
import InvoiceList from "./components/InvoiceList.jsx";

/**
 * Wurzelkomponente der Rechnungsplattform.
 * Verwaltet Rechnungsliste, Bauvorhaben-Filter und API-Fehler und
 * lädt die Daten bei Mount sowie nach Upload/Delete/Update neu.
 */
export default function App() {
  const [invoices, setInvoices] = useState([]);
  const [bauvorhabenListe, setBauvorhabenListe] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Lädt Rechnungen (gefiltert) und Bauvorhaben parallel.
  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [inv, bauvorhaben] = await Promise.all([
        listInvoices(filter || undefined),
        listBauvorhaben(),
      ]);
      setInvoices(inv);
      setBauvorhabenListe(bauvorhaben);
    } catch (err) {
      setError(err.message || "Daten konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  // Beim Mount sowie bei Filterwechsel neu laden.
  useEffect(() => {
    loadData();
  }, [loadData]);

  function handleFilterChange(value) {
    setFilter(value);
  }

  // PATCH anwenden und anschließend Liste aktualisieren.
  async function handleUpdate(id, patch) {
    await updateInvoice(id, patch);
    await loadData();
  }

  // Löschen per API und Liste aktualisieren.
  async function handleDelete(invoice) {
    try {
      await deleteInvoice(invoice.id);
      await loadData();
    } catch (err) {
      setError(err.message || "Rechnung konnte nicht gelöscht werden.");
    }
  }

  // Nach Upload: Liste + Bauvorhaben neu laden.
  function handleUploaded() {
    loadData();
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Doku-Agent – Rechnungsplattform</h1>
        <p>PDF-Rechnungen hochladen, prüfen und verwalten.</p>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")}>
            ×
          </button>
        </div>
      )}

      <main className="app-main">
        <UploadForm onUploaded={handleUploaded} />
        <InvoiceList
          invoices={invoices}
          bauvorhabenListe={bauvorhabenListe}
          filter={filter}
          onFilterChange={handleFilterChange}
          onRefresh={loadData}
          onDelete={handleDelete}
          onUpdate={handleUpdate}
          loading={loading}
        />
      </main>
    </div>
  );
}
