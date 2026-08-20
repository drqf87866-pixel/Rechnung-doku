import { useState } from "react";
import { uploadInvoice } from "../api.js";
import { formatBetrag, konfidenzInfo } from "../format.js";

/**
 * Kompaktes Upload-Formular für PDF-Rechnungen.
 * Pflichtfelder stehen in einer Zeile; optionale manuelle Angaben bleiben eingeklappt.
 *
 * @param {Object} props
 * @param {(invoice: Object) => void} props.onUploaded
 * @param {string[]} [props.bauvorhabenListe]  Vorschläge für das Bauvorhaben-Feld
 */
export default function UploadForm({ onUploaded, bauvorhabenListe = [] }) {
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
    <section className="card upload-card">
      <form className="form" onSubmit={handleSubmit}>
        <div className="upload-bar">
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
              list="bauvorhaben-vorschlaege"
              placeholder="z. B. Neubau Musterstraße 12"
              value={bauvorhaben}
              onChange={(event) => setBauvorhaben(event.target.value)}
            />
            <datalist id="bauvorhaben-vorschlaege">
              {bauvorhabenListe.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>
          <div className="upload-bar-actions">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? "Wird hochgeladen …" : "Hochladen"}
            </button>
          </div>
        </div>

        <button
          type="button"
          className="manual-toggle"
          onClick={() => setShowManual((prev) => !prev)}
          aria-expanded={showManual}
        >
          {showManual
            ? "Manuelle Angaben ausblenden"
            : "Manuelle Angaben (optional)"}
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
            <li>Rechnungsnummer: {success.rechnungsnummer ?? "–"}</li>
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
