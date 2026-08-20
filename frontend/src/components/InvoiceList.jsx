import { useState } from "react";
import { fileUrl } from "../api.js";
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
 * Rechnungstabelle mit Inline-Bearbeitung, Download und Löschen.
 *
 * @param {Object} props
 * @param {Object[]} props.invoices
 * @param {(invoice: Object) => void} props.onDelete
 * @param {(id: number, patch: Object) => Promise<void>} props.onUpdate
 * @param {boolean} props.loading
 */
export default function InvoiceList({ invoices, onDelete, onUpdate, loading }) {
  const [editingId, setEditingId] = useState(null);
  const [editNummer, setEditNummer] = useState("");
  const [editBetrag, setEditBetrag] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

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
        <table>
          <thead>
            <tr>
              <th>Rechnungsnummer</th>
              <th>Betrag</th>
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
                        aria-label="Rechnungsbetrag"
                      />
                    ) : (
                      formatBetrag(invoice.rechnungsbetrag, invoice.waehrung)
                    )}
                  </td>
                  <td>{invoice.filename}</td>
                  <td>
                    <span className={`badge badge-${konfidenz.level}`}>
                      {konfidenz.label}
                    </span>
                  </td>
                  <td>{formatDatum(invoice.upload_time)}</td>
                  <td className="actions">
                    {isEditing ? (
                      <>
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
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => startEdit(invoice)}
                        >
                          Bearbeiten
                        </button>
                        <a
                          className="btn btn-secondary btn-sm"
                          href={fileUrl(invoice.id)}
                          download
                        >
                          Download
                        </a>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() => confirmDelete(invoice)}
                        >
                          Löschen
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th>Gesamtsumme</th>
              <th>
                {formatBetrag(
                  invoices.reduce(
                    (total, invoice) =>
                      total +
                      (invoice.rechnungsbetrag != null
                        ? invoice.rechnungsbetrag
                        : 0),
                    0
                  ),
                  "EUR"
                )}
              </th>
              <th colSpan={4} />
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
