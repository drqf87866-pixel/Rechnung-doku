import { useState } from "react";

/**
 * Login- bzw. Erst-Setup-Formular.
 */
export default function LoginScreen({ mode, onSuccess }) {
  const isSetup = mode === "setup";
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("Administrator");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    if (isSetup && password !== password2) {
      setError("Passwörter stimmen nicht überein.");
      return;
    }
    if (password.length < 8) {
      setError("Passwort muss mindestens 8 Zeichen haben.");
      return;
    }
    setBusy(true);
    try {
      await onSuccess({
        username: username.trim(),
        password,
        display_name: displayName.trim() || "Administrator",
      });
    } catch (err) {
      setError(err.message || "Anmeldung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card card">
        <div className="brand auth-brand">
          <div className="brand-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 7V5a2 2 0 0 1 2-2h2" />
              <path d="M17 3h2a2 2 0 0 1 2 2v2" />
              <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
              <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
              <path d="M9 12h6" />
              <path d="M9 8h6" />
              <path d="M9 16h4" />
            </svg>
          </div>
          <h1>Doku-Agent</h1>
        </div>
        <h2>{isSetup ? "Ersten Administrator anlegen" : "Anmelden"}</h2>
        <p className="auth-hint">
          {isSetup
            ? "Noch keine Benutzer vorhanden. Legen Sie den ersten Admin-Zugang an."
            : "Melden Sie sich an, um Rechnungen zu verwalten."}
        </p>

        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Benutzername</span>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              minLength={3}
            />
          </label>
          {isSetup && (
            <label className="field">
              <span>Anzeigename</span>
              <input
                className="input"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                autoComplete="name"
                required
              />
            </label>
          )}
          <label className="field">
            <span>Passwort</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSetup ? "new-password" : "current-password"}
              required
              minLength={8}
            />
          </label>
          {isSetup && (
            <label className="field">
              <span>Passwort wiederholen</span>
              <input
                className="input"
                type="password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
              />
            </label>
          )}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Bitte warten…" : isSetup ? "Admin anlegen" : "Anmelden"}
          </button>
        </form>
      </div>
    </div>
  );
}
