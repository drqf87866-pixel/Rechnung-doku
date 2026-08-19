// Hilfsfunktionen für die Anzeige-Formatierung (deutsche Zahlformate).

/**
 * Formatiert einen Betrag als Währungsangabe in deutscher Schreibweise,
 * z. B. "1.234,56 €". Unbekannte Währungen fallen auf EUR zurück.
 * @param {number|null} betrag
 * @param {string|null} waehrung
 * @returns {string}
 */
export function formatBetrag(betrag, waehrung) {
  if (betrag == null) {
    return "–";
  }
  const currency =
    waehrung && waehrung !== "UNKNOWN" ? waehrung : "EUR";
  try {
    return new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency,
    }).format(betrag);
  } catch {
    // Ungültige Währungsangabe (z. B. 3 Zeichen überschritten) -> EUR.
    return new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency: "EUR",
    }).format(betrag);
  }
}

/**
 * Formatiert einen ISO-Zeitstempel als lokales Datum mit Uhrzeit.
 * @param {string|null} isoString
 * @returns {string}
 */
export function formatDatum(isoString) {
  if (!isoString) {
    return "–";
  }
  const datum = new Date(isoString);
  if (Number.isNaN(datum.getTime())) {
    return isoString;
  }
  return datum.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Übersetzt einen Konfidenzwert (0..1) in ein Label mit CSS-Level für Badges.
 * @param {number|null} konfidenz
 * @returns {{ label: string, level: string }}
 */
export function konfidenzInfo(konfidenz) {
  if (konfidenz == null) {
    return { label: "–", level: "none" };
  }
  if (konfidenz >= 0.8) {
    return { label: "hoch", level: "high" };
  }
  if (konfidenz >= 0.5) {
    return { label: "mittel", level: "medium" };
  }
  return { label: "niedrig", level: "low" };
}
