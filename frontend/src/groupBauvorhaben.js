/**
 * Gruppiert Rechnungen nach Bauvorhaben und berechnet Stückzahl sowie Summe.
 * @param {Object[]} invoices
 * @returns {{ name: string, invoices: Object[], summe: number, count: number }[]}
 */
export function groupByBauvorhaben(invoices) {
  const map = new Map();

  for (const invoice of invoices) {
    const name = invoice.bauvorhaben?.trim() || "Ohne Zuordnung";
    if (!map.has(name)) {
      map.set(name, { name, invoices: [], summe: 0, count: 0 });
    }
    const group = map.get(name);
    group.invoices.push(invoice);
    group.count += 1;
    if (invoice.rechnungsbetrag != null) {
      group.summe += invoice.rechnungsbetrag;
    }
  }

  return Array.from(map.values()).sort((a, b) =>
    a.name.localeCompare(b.name, "de")
  );
}
