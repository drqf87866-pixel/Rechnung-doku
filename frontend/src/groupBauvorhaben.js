/**
 * Gruppiert Rechnungen nach Bauvorhaben und berechnet Stückzahl sowie Summe.
 * @param {Object[]} invoices
 * @param {{ name: string, is_shared?: boolean }[]} [bauvorhabenInfos]
 * @returns {{ name: string, invoices: Object[], summe: number, count: number, isShared: boolean }[]}
 */
export function groupByBauvorhaben(invoices, bauvorhabenInfos = []) {
  const map = new Map();
  const sharedMap = new Map(
    bauvorhabenInfos.map((info) => [info.name, Boolean(info.is_shared)])
  );

  for (const invoice of invoices) {
    const name = invoice.bauvorhaben?.trim() || "Ohne Zuordnung";
    if (!map.has(name)) {
      map.set(name, {
        name,
        invoices: [],
        summe: 0,
        count: 0,
        isShared: sharedMap.get(name) || false,
      });
    }
    const group = map.get(name);
    group.invoices.push(invoice);
    group.count += 1;
    if (invoice.rechnungsbetrag != null) {
      group.summe += invoice.rechnungsbetrag;
    }
  }

  // Bauvorhaben nur über Freigabe (noch ohne eigene Rechnungen)
  for (const info of bauvorhabenInfos) {
    if (!map.has(info.name)) {
      map.set(info.name, {
        name: info.name,
        invoices: [],
        summe: 0,
        count: 0,
        isShared: Boolean(info.is_shared),
      });
    }
  }

  return Array.from(map.values()).sort((a, b) =>
    a.name.localeCompare(b.name, "de")
  );
}
