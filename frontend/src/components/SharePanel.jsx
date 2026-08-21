import { useCallback, useEffect, useState } from "react";
import {
  createShare,
  deleteShare,
  listShares,
  listUserDirectory,
} from "../api.js";

/**
 * Freigabe-Verwaltung für ein Bauvorhaben.
 */
export default function SharePanel({
  bauvorhaben,
  currentUser,
  canManageShares,
  onChanged,
}) {
  const [shares, setShares] = useState([]);
  const [directory, setDirectory] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [shareList, users] = await Promise.all([
        listShares(bauvorhaben),
        canManageShares ? listUserDirectory() : Promise.resolve([]),
      ]);
      setShares(shareList);
      setDirectory(users);
    } catch (err) {
      setError(err.message || "Freigaben konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [bauvorhaben, canManageShares]);

  useEffect(() => {
    if (open) {
      load();
    }
  }, [open, load]);

  const sharedIds = new Set(shares.map((s) => s.shared_with_user_id));
  // Auch Owner der Freigabe anzeigen, wenn ich Empfänger bin
  const availableUsers = directory.filter((u) => !sharedIds.has(u.id));

  async function handleShare(event) {
    event.preventDefault();
    if (!selectedUserId) return;
    setBusy(true);
    setError("");
    try {
      await createShare(bauvorhaben, Number(selectedUserId));
      setSelectedUserId("");
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message || "Freigabe fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(share) {
    const label =
      share.owner_id === currentUser.id
        ? share.shared_with_display_name
        : "diese Freigabe";
    if (!window.confirm(`Freigabe für „${label}“ wirklich entfernen?`)) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await deleteShare(share.id);
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message || "Entfernen fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="share-panel">
      <button
        type="button"
        className={`btn btn-sm ${open ? "btn-primary" : "btn-secondary"}`}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Freigabe schließen" : "Teilen"}
      </button>

      {open && (
        <div className="share-panel-body">
          <p className="share-hint">
            Geteilte Bauvorhaben sind für beide Seiten sichtbar – inklusive
            aller zugehörigen Rechnungen.
          </p>

          {error && (
            <div className="error-box" role="alert">
              {error}
            </div>
          )}

          {loading ? (
            <p className="muted">Lade Freigaben…</p>
          ) : (
            <>
              {shares.length === 0 ? (
                <p className="muted">Noch mit niemandem geteilt.</p>
              ) : (
                <ul className="share-list">
                  {shares.map((share) => {
                    const isMine = share.owner_id === currentUser.id;
                    const label = isMine
                      ? share.shared_with_display_name
                      : share.owner_display_name;
                    const sub = isMine
                      ? `@${share.shared_with_username}`
                      : `@${share.owner_username} · mit Ihnen geteilt`;
                    return (
                      <li key={share.id} className="share-list-item">
                        <div className="user-cell">
                          <strong>{label}</strong>
                          <span className="muted">{sub}</span>
                        </div>
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost"
                          disabled={busy}
                          onClick={() => handleRemove(share)}
                        >
                          {isMine ? "Entziehen" : "Verlassen"}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              {canManageShares && (
                <form className="share-form" onSubmit={handleShare}>
                  <select
                    className="input"
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    required
                    disabled={availableUsers.length === 0}
                  >
                    <option value="">
                      {availableUsers.length === 0
                        ? "Keine weiteren Benutzer"
                        : "Benutzer wählen…"}
                    </option>
                    {availableUsers.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name} (@{u.username})
                      </option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    className="btn btn-primary btn-sm"
                    disabled={busy || !selectedUserId}
                  >
                    Freigeben
                  </button>
                </form>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
