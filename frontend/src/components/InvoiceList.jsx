import { useState } from "react";
import { downloadInvoiceFile } from "../api.js";
import { formatBetrag, formatDatum, konfidenzInfo } from "../format.js";

/**
 * Wandelt eine Benutzereingabe in einen Betrag (float) um.
 * Akzeptiert deutsches Format ("1.234,56") wie auch Punkt-Format ("1234.56").
 * Leere Eingabe -> null.
 */
function parseBetrag(value) {
  const v = value.trim();
  if (v === "") {
    return null;
  }
  const normalized = v.includes(",")
    ? v.replace(/\./g, "").replace(",", ".")
    : v.replace(",", ".");
  const num = Number(normalized);
  return Number.isFinite(num) ? num : null;
}

/**
 * Summiert ein Betragsfeld über alle Rechnungen.
 * @param {Object[]} invoices
 * @param {string} field
 * @returns {number}
 */
function sumField(invoices, field) {
  return invoices.reduce(
    (total, invoice) => total + (invoice[field] != null ? invoice[field] : 0),
    0
  );
}

/**
 * Rechnungstabelle mit Inline-Bearbeitung, Download und Löschen.
 *
 * @param {Object} props
 * @param {Object[]} props.invoices
 * @param {(invoice: Object) => void} props.onDelete
 * @param {(id: number, patch: Object) => Promise<void>} props.onUpdate
 * @param {boolean} props.loading
 */
export default function InvoiceList({
  invoices,
  currentUserId,
  onDelete,
  onUpdate,
  loading,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editNummer, setEditNummer] = useState("");
  const [editBetrag, setEditBetrag] = useState("");
  const [saving, setSaving] = useState(false);
  const [downloadingId, setDownloadingId] = useState(null);
  const [error, setError] = useState("");

  async function handleDownload(invoice) {
    setDownloadingId(invoice.id);
    setError("");
    try {
      await downloadInvoiceFile(invoice.id, invoice.filename || "rechnung.pdf");
    } catch (err) {
      setError(err.message || "Download fehlgeschlagen.");
    } finally {
      setDownloadingId(null);
    }
  }

  function startEdit(invoice) {
    setEditingId(invoice.id);
    setEditNummer(invoice.rechnungsnummer ?? "");
    setEditBetrag(
      invoice.rechnungsbetrag != null
        ? String(invoice.rechnungsbetrag).replace(".", ",")
        : ""
    );
    setError("");
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(invoice) {
    const patch = {
      rechnungsnummer: editNummer.trim() || null,
      rechnungsbetrag: parseBetrag(editBetrag),
    };
    setSaving(true);
    setError("");
    try {
      await onUpdate(invoice.id, patch);
      setEditingId(null);
    } catch (err) {
      setError(err.message || "Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  }

  function confirmDelete(invoice) {
    if (window.confirm(`Rechnung „${invoice.filename}“ wirklich löschen?`)) {
      onDelete(invoice);
    }
  }

  if (loading) {
    return <div className="empty-state">Lade Rechnungen …</div>;
  }

  if (invoices.length === 0) {
    return (
      <div className="empty-state">Keine Rechnungen in diesem Bauvorhaben.</div>
    );
  }

  return (
    <>
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <div className="table-wrap">
        <table className="invoice-table">
          <colgroup>
            <col className="col-nummer" />
            <col className="col-betrag" />
            <col className="col-betrag" />
            <col className="col-betrag" />
            <col className="col-dateiname" />
            <col className="col-konfidenz" />
            <col className="col-upload" />
            <col className="col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>Rechnungsnummer</th>
              <th>Brutto</th>
              <th>Netto</th>
              <th>Steuer</th>
              <th>Dateiname</th>
              <th>Konfidenz</th>
              <th>Upload</th>
              <th className="actions">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => {
              const konfidenz = konfidenzInfo(invoice.konfidenz);
              const isEditing = editingId === invoice.id;
              const isOwn =
                currentUserId == null || invoice.owner_id === currentUserId;
              return (
                <tr key={invoice.id} className={isEditing ? "row-editing" : ""}>
                  <td>
                    {isEditing ? (
                      <input
                        className="input"
                        value={editNummer}
                        onChange={(event) => setEditNummer(event.target.value)}
                        aria-label="Rechnungsnummer"
                      />
                    ) : (
                      invoice.rechnungsnummer ?? "–"
                    )}
                  </td>
                  <td>
                    {isEditing ? (
                      <input
                        className="input"
                        value={editBetrag}
                        onChange={(event) => setEditBetrag(event.target.value)}
                        aria-label="Bruttobetrag"
                      />
                    ) : (
                      formatBetrag(invoice.rechnungsbetrag, invoice.waehrung)
                    )}
                  </td>
                  <td>{formatBetrag(invoice.nettobetrag, invoice.waehrung)}</td>
                  <td>{formatBetrag(invoice.steuerbetrag, invoice.waehrung)}</td>
                  <td className="cell-truncate" title={invoice.filename}>
                    {invoice.filename}
                    {!isOwn && (
                      <span className="muted shared-tag"> · geteilt</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge badge-${konfidenz.level}`}>
                      {konfidenz.label}
                    </span>
                  </td>
                  <td>{formatDatum(invoice.upload_time)}</td>
                  <td className="actions">
                    {isEditing ? (
                      <div className="actions-group">
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => saveEdit(invoice)}
                          disabled={saving}
                        >
                          {saving ? "Speichert …" : "Speichern"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={cancelEdit}
                        >
                          Abbrechen
                        </button>
                      </div>
                    ) : (
                      <div className="actions-group">
                        {isOwn && (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => startEdit(invoice)}
                          >
                            Bearbeiten
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={downloadingId === invoice.id}
                          onClick={() => handleDownload(invoice)}
                        >
                          {downloadingId === invoice.id ? "Lädt…" : "Download"}
                        </button>
                        {isOwn && (
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => confirmDelete(invoice)}
                          >
                            Löschen
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th>Gesamtsumme</th>
              <th>{formatBetrag(sumField(invoices, "rechnungsbetrag"), "EUR")}</th>
              <th>{formatBetrag(sumField(invoices, "nettobetrag"), "EUR")}</th>
              <th>{formatBetrag(sumField(invoices, "steuerbetrag"), "EUR")}</th>
              <th colSpan={4} />
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
