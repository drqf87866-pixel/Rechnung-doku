import { useState } from "react";
import { uploadInvoice } from "../api.js";
import { formatBetrag, konfidenzInfo } from "../format.js";

/**
 * Upload-Formular für PDF-Rechnungen.
 * Lädt die Datei zusammen mit dem Bauvorhaben hoch und zeigt nach Erfolg
 * die vom Backend extrahierten Daten (Rechnungsnummer, Betrag, Konfidenz) an.
 *
 * @param {Object} props
 * @param {(invoice: Object) => void} props.onUploaded  Callback nach erfolgreichem Upload
 */
export default function UploadForm({ onUploaded }) {
  const [file, setFile] = useState(null);
  const [bauvorhaben, setBauvorhaben] = useState("");
  const [showManual, setShowManual] = useState(false);
  const [rechnungsnummer, setRechnungsnummer] = useState("");
  const [rechnungsbetrag, setRechnungsbetrag] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();

    if (!file) {
      setError("Bitte wähle eine PDF-Datei aus.");
      return;
    }
    if (!bauvorhaben.trim()) {
      setError("Bitte gib ein Bauvorhaben an.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess(null);

    try {
      const overrides = {
        rechnungsnummer: rechnungsnummer.trim() || undefined,
        rechnungsbetrag: rechnungsbetrag.trim() || undefined,
      };
      const invoice = await uploadInvoice(file, bauvorhaben.trim(), overrides);

      setSuccess(invoice);
      setFile(null);
      setBauvorhaben("");
      setRechnungsnummer("");
      setRechnungsbetrag("");
      setShowManual(false);
      event.target.reset();

      onUploaded?.(invoice);
    } catch (err) {
      setError(err.message || "Upload fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }

  const konfidenz = success ? konfidenzInfo(success.konfidenz) : null;

  return (
    <section className="card">
      <h2>Neue Rechnung hochladen</h2>

      <form className="form" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="file">PDF-Datei *</label>
            <input
              id="file"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files[0] || null)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="bauvorhaben">Bauvorhaben *</label>
            <input
              id="bauvorhaben"
              type="text"
              className="input"
              placeholder="z. B. Neubau Musterstraße 12"
              value={bauvorhaben}
              onChange={(event) => setBauvorhaben(event.target.value)}
            />
          </div>
        </div>

        {/* Collapsible-Bereich für optionale manuelle Angaben */}
        <button
          type="button"
          className="manual-toggle"
          onClick={() => setShowManual((prev) => !prev)}
          aria-expanded={showManual}
        >
          {showManual
            ? "Manuelle Angaben ausblenden"
            : "Manuelle Angaben (optional) anzeigen"}
        </button>

        {showManual && (
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="rechnungsnummer">Rechnungsnummer</label>
              <input
                id="rechnungsnummer"
                type="text"
                className="input"
                value={rechnungsnummer}
                onChange={(event) => setRechnungsnummer(event.target.value)}
              />
            </div>
            <div className="form-field">
              <label htmlFor="rechnungsbetrag">Rechnungsbetrag</label>
              <input
                id="rechnungsbetrag"
                type="text"
                className="input"
                inputMode="decimal"
                placeholder="z. B. 1234,56"
                value={rechnungsbetrag}
                onChange={(event) => setRechnungsbetrag(event.target.value)}
              />
            </div>
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Wird hochgeladen …" : "Rechnung hochladen"}
        </button>
      </form>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      {success && (
        <div className="success-box" role="status">
          <strong>Upload erfolgreich.</strong>
          <ul>
            <li>
              Rechnungsnummer: {success.rechnungsnummer ?? "–"}
            </li>
            <li>
              Rechnungsbetrag:{" "}
              {formatBetrag(success.rechnungsbetrag, success.waehrung)}
            </li>
            <li>Konfidenz: {konfidenz.label}</li>
          </ul>
        </div>
      )}
    </section>
  );
}
