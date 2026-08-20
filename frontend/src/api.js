// API-Zugriff auf das Backend der Rechnungsplattform.
// VITE_API_URL wird zur Build-Zeit in Netlify gesetzt und zeigt auf das
// Render-Backend (z.B. https://doku-agent-backend.onrender.com). Ohne diese
// Variable greift der lokale Vite-Dev-Proxy (/api -> http://localhost:8000).

export const API_BASE = import.meta.env.VITE_API_URL || "/api";

const RETRYABLE_STATUSES = [502, 503, 504];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithRetry(url, options = {}) {
  const maxAttempts = 3;
  for (let attempt = 1; ; attempt++) {
    let res;
    try {
      res = await fetch(url, options);
    } catch (err) {
      if (attempt < maxAttempts) {
        await sleep(1500 * attempt);
        continue;
      }
      throw err;
    }
    if (attempt < maxAttempts && RETRYABLE_STATUSES.includes(res.status)) {
      await sleep(1500 * attempt);
      continue;
    }
    return res;
  }
}

/**
 * Gemeinsame Fehlerbehandlung für fetch-Antworten.
 * Wirft einen Error mit einer menschenlesbaren Meldung, falls der
 * Statuscode außerhalb des 2xx-Bereichs liegt. Bei 204 (No Content)
 * wird null zurückgegeben, sonst die JSON-Antwort.
 */
async function handleResponse(res) {
  if (res.status === 204) {
    return null;
  }
  if (!res.ok) {
    let message = `API-Fehler (${res.status})`;
    try {
      const data = await res.json();
      if (data && data.detail) message = data.detail;
      else if (data && data.message) message = data.message;
    } catch {
      // Kein JSON-Body vorhanden – Standardmeldung beibehalten.
    }
    throw new Error(message);
  }
  return res.json();
}

/**
 * Lädt eine PDF-Rechnung hoch (multipart/form-data).
 * @param {File} file          Die PDF-Datei
 * @param {string} bauvorhaben Name des Bauvorhabens
 * @param {Object} overrides   Optional: { rechnungsnummer, rechnungsbetrag }
 * @returns {Promise<Object>}  InvoiceOut vom Backend
 */
export async function uploadInvoice(file, bauvorhaben, overrides = {}) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("bauvorhaben", bauvorhaben);

  if (overrides.rechnungsnummer) {
    formData.append("rechnungsnummer", overrides.rechnungsnummer);
  }
  if (overrides.rechnungsbetrag !== undefined && overrides.rechnungsbetrag !== "") {
    formData.append("rechnungsbetrag", String(overrides.rechnungsbetrag));
  }

  const res = await fetch(`${API_BASE}/invoices`, {
    method: "POST",
    body: formData,
  });
  return handleResponse(res);
}

/**
 * Listet Rechnungen auf, optional gefiltert nach Bauvorhaben.
 * @param {string} [bauvorhaben]
 * @returns {Promise<Object[]>} Array von InvoiceOut
 */
export async function listInvoices(bauvorhaben) {
  const query = bauvorhaben
    ? `?bauvorhaben=${encodeURIComponent(bauvorhaben)}`
    : "";
  const res = await fetchWithRetry(`${API_BASE}/invoices${query}`);
  return handleResponse(res);
}

/**
 * Aktualisiert eine Rechnung teilweise.
 * @param {number} id
 * @param {Object} patch  { rechnungsnummer?, rechnungsbetrag?, bauvorhaben? }
 * @returns {Promise<Object>} Aktualisiertes InvoiceOut
 */
export async function updateInvoice(id, patch) {
  const res = await fetch(`${API_BASE}/invoices/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return handleResponse(res);
}

/**
 * Löscht eine Rechnung.
 * @param {number} id
 * @returns {Promise<null>}
 */
export async function deleteInvoice(id) {
  const res = await fetch(`${API_BASE}/invoices/${id}`, {
    method: "DELETE",
  });
  return handleResponse(res);
}

/**
 * Liefert die Liste aller bekannten Bauvorhaben.
 * @returns {Promise<string[]>}
 */
export async function listBauvorhaben() {
  const res = await fetchWithRetry(`${API_BASE}/bauvorhaben`);
  return handleResponse(res);
}

/**
 * URL zum Download der Original-PDF einer Rechnung.
 * @param {number} id
 * @returns {string}
 */
export function fileUrl(id) {
  return `${API_BASE}/invoices/${id}/file`;
}
