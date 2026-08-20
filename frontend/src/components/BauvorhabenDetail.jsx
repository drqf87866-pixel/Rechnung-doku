import { formatBetrag } from "../format.js";
import { exportBauvorhabenExcel } from "../exportExcel.js";
import InvoiceList from "./InvoiceList.jsx";

/**
 * Detailseite eines Bauvorhabens: Summe, Excel-Export und Rechnungstabelle.
 *
 * @param {Object} props
 * @param {string} props.name
 * @param {Object[]} props.invoices
 * @param {number} props.summe
 * @param {() => void} props.onBack
 * @param {(invoice: Object) => void} props.onDelete
 * @param {(id: number, patch: Object) => Promise<void>} props.onUpdate
 * @param {boolean} props.loading
 */
export default function BauvorhabenDetail({
  name,
  invoices,
  summe,
  onBack,
  onDelete,
  onUpdate,
  loading,
}) {
  function handleExport() {
    exportBauvorhabenExcel(name, invoices);
  }

  return (
    <section className="card">
      <button type="button" className="back-link" onClick={onBack}>
        ← Zurück zur Übersicht
      </button>

      <div className="detail-header">
        <div>
          <h2 className="detail-title">{name}</h2>
          <p className="detail-sum">{formatBetrag(summe, "EUR")}</p>
          <p className="tile-meta">
            {invoices.length === 1
              ? "1 Rechnung"
              : `${invoices.length} Rechnungen`}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleExport}
          disabled={invoices.length === 0}
        >
          Excel exportieren
        </button>
      </div>

      <InvoiceList
        invoices={invoices}
        onDelete={onDelete}
        onUpdate={onUpdate}
        loading={loading}
      />
    </section>
  );
}
