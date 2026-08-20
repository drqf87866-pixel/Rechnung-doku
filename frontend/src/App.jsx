import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listInvoices,
  listBauvorhaben,
  updateInvoice,
  deleteInvoice,
} from "./api.js";
import { groupByBauvorhaben } from "./groupBauvorhaben.js";
import UploadForm from "./components/UploadForm.jsx";
import BauvorhabenGrid from "./components/BauvorhabenGrid.jsx";
import BauvorhabenDetail from "./components/BauvorhabenDetail.jsx";

/**
 * Wurzelkomponente der Rechnungsplattform.
 * Übersicht: Kacheln je Bauvorhaben. Klick öffnet die Detailseite.
 */
export default function App() {
  const [invoices, setInvoices] = useState([]);
  const [bauvorhabenListe, setBauvorhabenListe] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [inv, bauvorhaben] = await Promise.all([
        listInvoices(),
        listBauvorhaben(),
      ]);
      setInvoices(inv);
      setBauvorhabenListe(bauvorhaben);
    } catch (err) {
      setError(err.message || "Daten konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const groups = useMemo(() => groupByBauvorhaben(invoices), [invoices]);
  const selectedGroup = groups.find((group) => group.name === selected);

  async function handleUpdate(id, patch) {
    await updateInvoice(id, patch);
    await loadData();
  }

  async function handleDelete(invoice) {
    try {
      await deleteInvoice(invoice.id);
      await loadData();
    } catch (err) {
      setError(err.message || "Rechnung konnte nicht gelöscht werden.");
    }
  }

  function handleUploaded(invoice) {
    if (invoice?.bauvorhaben) {
      setSelected(invoice.bauvorhaben);
    }
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
        <UploadForm
          onUploaded={handleUploaded}
          bauvorhabenListe={bauvorhabenListe}
        />
        {selected ? (
          <BauvorhabenDetail
            name={selected}
            invoices={selectedGroup?.invoices ?? []}
            summe={selectedGroup?.summe ?? 0}
            onBack={() => setSelected(null)}
            onDelete={handleDelete}
            onUpdate={handleUpdate}
            loading={loading}
          />
        ) : (
          <BauvorhabenGrid
            groups={groups}
            onSelect={setSelected}
            loading={loading}
          />
        )}
      </main>
    </div>
  );
}
