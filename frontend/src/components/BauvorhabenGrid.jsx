import { formatBetrag } from "../format.js";

/**
 * Kachel-Übersicht aller Bauvorhaben (Name, Anzahl, Gesamtsumme).
 */
export default function BauvorhabenGrid({ groups, onSelect, loading }) {
  if (loading) {
    return (
      <section className="card">
        <h2>Bauvorhaben</h2>
        <div className="empty-state">Lade Bauvorhaben …</div>
      </section>
    );
  }

  if (groups.length === 0) {
    return (
      <section className="card">
        <h2>Bauvorhaben</h2>
        <div className="empty-state">Noch keine Rechnungen hochgeladen.</div>
      </section>
    );
  }

  return (
    <section>
      <h2 className="section-heading">Bauvorhaben</h2>
      <div className="tile-grid">
        {groups.map((group) => (
          <button
            key={group.name}
            type="button"
            className="tile"
            onClick={() => onSelect(group.name)}
          >
            <h3 className="tile-title">
              {group.name}
              {group.isShared && (
                <span className="badge badge-ok share-badge">Geteilt</span>
              )}
            </h3>
            <p className="tile-meta">
              {group.count === 1 ? "1 Rechnung" : `${group.count} Rechnungen`}
            </p>
            <p className="tile-sum">{formatBetrag(group.summe, "EUR")}</p>
          </button>
        ))}
      </div>
    </section>
  );
}
