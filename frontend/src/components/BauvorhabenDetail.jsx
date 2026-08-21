import { formatBetrag } from "../format.js";
import { exportBauvorhabenExcel } from "../exportExcel.js";
import InvoiceList from "./InvoiceList.jsx";
import SharePanel from "./SharePanel.jsx";

/**
 * Detailseite eines Bauvorhabens: Summe, Excel-Export und Rechnungstabelle.
 */
export default function BauvorhabenDetail({
  name,
  invoices,
  summe,
  isShared,
  canManageShares,
  currentUser,
  onBack,
  onDelete,
  onUpdate,
  onShareChanged,
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
          <h2 className="detail-title">
            {name}
            {isShared && (
              <span className="badge badge-ok share-badge">Geteilt</span>
            )}
          </h2>
          <p className="detail-sum">{formatBetrag(summe, "EUR")}</p>
          <p className="tile-meta">
            {invoices.length === 1
              ? "1 Rechnung"
              : `${invoices.length} Rechnungen`}
          </p>
        </div>
        <div className="detail-header-actions">
          <SharePanel
            bauvorhaben={name}
            currentUser={currentUser}
            canManageShares={canManageShares}
            onChanged={onShareChanged}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleExport}
            disabled={invoices.length === 0}
          >
            Excel exportieren
          </button>
        </div>
      </div>

      <InvoiceList
        invoices={invoices}
        currentUserId={currentUser?.id}
        onDelete={onDelete}
        onUpdate={onUpdate}
        loading={loading}
      />
    </section>
  );
}
