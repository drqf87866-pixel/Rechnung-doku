// API-Zugriff auf das Backend der Rechnungsplattform.
// VITE_API_URL wird zur Build-Zeit in Netlify gesetzt und zeigt auf das
// Render-Backend (z.B. https://doku-agent-backend.onrender.com). Ohne diese
// Variable greift der lokale Vite-Dev-Proxy (/api -> http://localhost:8000).

import { authHeaders, clearSession, getToken } from "./auth.js";

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

function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "string" ? item : item.msg || JSON.stringify(item)))
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || JSON.stringify(detail);
  }
  return null;
}

/**
 * Gemeinsame Fehlerbehandlung für fetch-Antworten.
 * Wirft einen Error mit einer menschenlesbaren Meldung, falls der
 * Statuscode außerhalb des 2xx-Bereichs liegt. Bei 204 (No Content)
 * wird null zurückgegeben, sonst die JSON-Antwort.
 */
async function handleResponse(res) {
  if (res.status === 401) {
    clearSession();
  }
  if (res.status === 204) {
    return null;
  }
  if (!res.ok) {
    let message = `API-Fehler (${res.status})`;
    try {
      const data = await res.json();
      const detail = formatDetail(data?.detail);
      if (detail) message = detail;
      else if (data && data.message) message = data.message;
    } catch {
      // Kein JSON-Body vorhanden – Standardmeldung beibehalten.
    }
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function withAuth(options = {}) {
  const headers = authHeaders(options.headers || {});
  return { ...options, headers };
}

/** @returns {Promise<{ needs_setup: boolean }>} */
export async function getSetupStatus() {
  const res = await fetchWithRetry(`${API_BASE}/auth/setup-status`);
  return handleResponse(res);
}

/** @returns {Promise<{ access_token: string, user: Object }>} */
export async function setupAdmin({ username, password, display_name }) {
  const res = await fetch(`${API_BASE}/auth/setup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, display_name }),
  });
  return handleResponse(res);
}

/** @returns {Promise<{ access_token: string, user: Object }>} */
export async function login(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return handleResponse(res);
}

/** @returns {Promise<Object>} */
export async function fetchMe() {
  const res = await fetchWithRetry(
    `${API_BASE}/auth/me`,
    withAuth()
  );
  return handleResponse(res);
}

/** @returns {Promise<Object[]>} */
export async function listUsers() {
  const res = await fetchWithRetry(`${API_BASE}/users`, withAuth());
  return handleResponse(res);
}

/** @returns {Promise<Object>} */
export async function createUser(payload) {
  const res = await fetch(`${API_BASE}/users`, withAuth({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
  return handleResponse(res);
}

/** @returns {Promise<Object>} */
export async function updateUser(id, patch) {
  const res = await fetch(`${API_BASE}/users/${id}`, withAuth({
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }));
  return handleResponse(res);
}

/** @returns {Promise<null>} */
export async function deleteUser(id) {
  const res = await fetch(`${API_BASE}/users/${id}`, withAuth({
    method: "DELETE",
  }));
  return handleResponse(res);
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

  const res = await fetch(`${API_BASE}/invoices`, withAuth({
    method: "POST",
    body: formData,
  }));
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
  const res = await fetchWithRetry(`${API_BASE}/invoices${query}`, withAuth());
  return handleResponse(res);
}

/**
 * Aktualisiert eine Rechnung teilweise.
 * @param {number} id
 * @param {Object} patch  { rechnungsnummer?, rechnungsbetrag?, bauvorhaben? }
 * @returns {Promise<Object>} Aktualisiertes InvoiceOut
 */
export async function updateInvoice(id, patch) {
  const res = await fetch(`${API_BASE}/invoices/${id}`, withAuth({
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }));
  return handleResponse(res);
}

/**
 * Löscht eine Rechnung.
 * @param {number} id
 * @returns {Promise<null>}
 */
export async function deleteInvoice(id) {
  const res = await fetch(`${API_BASE}/invoices/${id}`, withAuth({
    method: "DELETE",
  }));
  return handleResponse(res);
}

/**
 * Liefert Bauvorhaben-Infos (Name, Freigabe-Status).
 * @returns {Promise<{ name: string, is_shared: boolean, can_manage_shares: boolean }[]>}
 */
export async function listBauvorhaben() {
  const res = await fetchWithRetry(`${API_BASE}/bauvorhaben`, withAuth());
  return handleResponse(res);
}

/** @returns {Promise<{ id: number, username: string, display_name: string }[]>} */
export async function listUserDirectory() {
  const res = await fetchWithRetry(`${API_BASE}/users/directory`, withAuth());
  return handleResponse(res);
}

/** @returns {Promise<Object[]>} */
export async function listShares(bauvorhaben) {
  const query = `?bauvorhaben=${encodeURIComponent(bauvorhaben)}`;
  const res = await fetchWithRetry(`${API_BASE}/shares${query}`, withAuth());
  return handleResponse(res);
}

/** @returns {Promise<Object>} */
export async function createShare(bauvorhaben, userId) {
  const res = await fetch(`${API_BASE}/shares`, withAuth({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bauvorhaben, user_id: userId }),
  }));
  return handleResponse(res);
}

/** @returns {Promise<null>} */
export async function deleteShare(shareId) {
  const res = await fetch(`${API_BASE}/shares/${shareId}`, withAuth({
    method: "DELETE",
  }));
  return handleResponse(res);
}

/**
 * URL zum Download der Original-PDF einer Rechnung (ohne Token).
 * Bevorzugt downloadInvoiceFile() verwenden.
 * @param {number} id
 * @returns {string}
 */
export function fileUrl(id) {
  return `${API_BASE}/invoices/${id}/file`;
}

/**
 * Lädt die PDF authentifiziert und triggert einen Browser-Download.
 * @param {number} id
 * @param {string} filename
 */
export async function downloadInvoiceFile(id, filename = "rechnung.pdf") {
  const res = await fetch(fileUrl(id), withAuth());
  if (res.status === 401) {
    clearSession();
  }
  if (!res.ok) {
    let message = `Download fehlgeschlagen (${res.status})`;
    try {
      const data = await res.json();
      const detail = formatDetail(data?.detail);
      if (detail) message = detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "rechnung.pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function isLoggedIn() {
  return Boolean(getToken());
}
