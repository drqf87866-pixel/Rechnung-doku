import { useCallback, useEffect, useState } from "react";
import { createUser, deleteUser, listUsers, updateUser } from "../api.js";

/**
 * Admin-UI zur Benutzerverwaltung.
 */
export default function UserAdmin({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [creating, setCreating] = useState(false);

  const [editPasswordId, setEditPasswordId] = useState(null);
  const [editPassword, setEditPassword] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setUsers(await listUsers());
    } catch (err) {
      setError(err.message || "Benutzer konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate(event) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      await createUser({
        username: username.trim(),
        display_name: displayName.trim() || username.trim(),
        password,
        role,
      });
      setUsername("");
      setDisplayName("");
      setPassword("");
      setRole("user");
      await load();
    } catch (err) {
      setError(err.message || "Anlegen fehlgeschlagen.");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(user) {
    setBusyId(user.id);
    setError("");
    try {
      await updateUser(user.id, { is_active: !user.is_active });
      await load();
    } catch (err) {
      setError(err.message || "Status konnte nicht geändert werden.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRoleChange(user, nextRole) {
    if (nextRole === user.role) return;
    setBusyId(user.id);
    setError("");
    try {
      await updateUser(user.id, { role: nextRole });
      await load();
    } catch (err) {
      setError(err.message || "Rolle konnte nicht geändert werden.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleResetPassword(user) {
    if (!editPassword || editPassword.length < 8) {
      setError("Neues Passwort muss mindestens 8 Zeichen haben.");
      return;
    }
    setBusyId(user.id);
    setError("");
    try {
      await updateUser(user.id, { password: editPassword });
      setEditPasswordId(null);
      setEditPassword("");
    } catch (err) {
      setError(err.message || "Passwort konnte nicht gesetzt werden.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(user) {
    if (
      !window.confirm(
        `Benutzer „${user.username}“ wirklich löschen?`
      )
    ) {
      return;
    }
    setBusyId(user.id);
    setError("");
    try {
      await deleteUser(user.id);
      await load();
    } catch (err) {
      setError(err.message || "Löschen fehlgeschlagen.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2>Benutzerverwaltung</h2>
      </div>

      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}

      <form className="user-create-form" onSubmit={handleCreate}>
        <label className="field">
          <span>Benutzername</span>
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
          />
        </label>
        <label className="field">
          <span>Anzeigename</span>
          <input
            className="input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Optional"
          />
        </label>
        <label className="field">
          <span>Passwort</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        <label className="field">
          <span>Rolle</span>
          <select
            className="input"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="user">Benutzer</option>
            <option value="admin">Administrator</option>
          </select>
        </label>
        <div className="field field-action">
          <span>&nbsp;</span>
          <button className="btn btn-primary" type="submit" disabled={creating}>
            {creating ? "Anlegen…" : "Benutzer anlegen"}
          </button>
        </div>
      </form>

      {loading ? (
        <p className="muted">Lade Benutzer…</p>
      ) : users.length === 0 ? (
        <p className="muted">Keine Benutzer vorhanden.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Benutzer</th>
                <th>Rolle</th>
                <th>Status</th>
                <th>Passwort</th>
                <th>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isSelf = user.id === currentUser?.id;
                const busy = busyId === user.id;
                return (
                  <tr key={user.id} className={!user.is_active ? "row-inactive" : undefined}>
                    <td>
                      <div className="user-cell">
                        <strong>{user.display_name}</strong>
                        <span className="muted">@{user.username}</span>
                      </div>
                    </td>
                    <td>
                      <select
                        className="input input-inline"
                        value={user.role}
                        disabled={busy || isSelf}
                        onChange={(e) => handleRoleChange(user, e.target.value)}
                      >
                        <option value="user">Benutzer</option>
                        <option value="admin">Administrator</option>
                      </select>
                    </td>
                    <td>
                      <span className={`badge ${user.is_active ? "badge-ok" : "badge-warn"}`}>
                        {user.is_active ? "Aktiv" : "Deaktiviert"}
                      </span>
                    </td>
                    <td>
                      {editPasswordId === user.id ? (
                        <div className="inline-actions">
                          <input
                            className="input input-inline"
                            type="password"
                            value={editPassword}
                            onChange={(e) => setEditPassword(e.target.value)}
                            placeholder="Neues Passwort"
                            minLength={8}
                          />
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={busy}
                            onClick={() => handleResetPassword(user)}
                          >
                            Speichern
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-ghost"
                            onClick={() => {
                              setEditPasswordId(null);
                              setEditPassword("");
                            }}
                          >
                            Abbrechen
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost"
                          onClick={() => {
                            setEditPasswordId(user.id);
                            setEditPassword("");
                            setError("");
                          }}
                        >
                          Zurücksetzen
                        </button>
                      )}
                    </td>
                    <td>
                      <div className="inline-actions">
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost"
                          disabled={busy || isSelf}
                          onClick={() => handleToggleActive(user)}
                        >
                          {user.is_active ? "Deaktivieren" : "Aktivieren"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          disabled={busy || isSelf}
                          onClick={() => handleDelete(user)}
                        >
                          Löschen
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
