import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listInvoices,
  listBauvorhaben,
  updateInvoice,
  deleteInvoice,
  getSetupStatus,
  login,
  setupAdmin,
  fetchMe,
} from "./api.js";
import {
  clearSession,
  getStoredUser,
  getToken,
  setSession,
} from "./auth.js";
import { groupByBauvorhaben } from "./groupBauvorhaben.js";
import UploadForm from "./components/UploadForm.jsx";
import BauvorhabenGrid from "./components/BauvorhabenGrid.jsx";
import BauvorhabenDetail from "./components/BauvorhabenDetail.jsx";
import LoginScreen from "./components/LoginScreen.jsx";
import UserAdmin from "./components/UserAdmin.jsx";

/**
 * Wurzelkomponente der Rechnungsplattform.
 * Übersicht: Kacheln je Bauvorhaben. Klick öffnet die Detailseite.
 */
export default function App() {
  const [authReady, setAuthReady] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [user, setUser] = useState(null);
  const [view, setView] = useState("invoices"); // invoices | users

  const [invoices, setInvoices] = useState([]);
  const [bauvorhabenListe, setBauvorhabenListe] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [inv, bauvorhaben] = await Promise.all([
        listInvoices(),
        listBauvorhaben(),
      ]);
      setInvoices(inv);
      setBauvorhabenListe(bauvorhaben);
    } catch (err) {
      if (err.status === 401) {
        setUser(null);
        return;
      }
      setError(err.message || "Daten konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function initAuth() {
      try {
        const status = await getSetupStatus();
        if (cancelled) return;
        setNeedsSetup(status.needs_setup);

        const token = getToken();
        if (!token || status.needs_setup) {
          if (!cancelled) {
            setUser(null);
            setAuthReady(true);
          }
          return;
        }

        try {
          const me = await fetchMe();
          if (!cancelled) {
            setUser(me);
            setSession(token, me);
          }
        } catch {
          clearSession();
          if (!cancelled) setUser(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Auth-Status konnte nicht geladen werden.");
          // Fallback: gespeicherten User nutzen, falls Backend kurz offline.
          setUser(getStoredUser());
        }
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    }
    initAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (user && view === "invoices") {
      loadData();
    }
  }, [user, view, loadData]);

  const groups = useMemo(
    () => groupByBauvorhaben(invoices, bauvorhabenListe),
    [invoices, bauvorhabenListe]
  );
  const selectedGroup = groups.find((group) => group.name === selected);
  const selectedInfo = bauvorhabenListe.find((b) => b.name === selected);

  async function handleAuthSuccess(credentials) {
    const result = needsSetup
      ? await setupAdmin(credentials)
      : await login(credentials.username, credentials.password);
    setSession(result.access_token, result.user);
    setUser(result.user);
    setNeedsSetup(false);
    setView("invoices");
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setInvoices([]);
    setBauvorhabenListe([]);
    setSelected(null);
    setView("invoices");
  }

  async function handleUpdate(id, patch) {
    await updateInvoice(id, patch);
    await loadData();
  }

  async function handleDelete(invoice) {
    try {
      await deleteInvoice(invoice.id);
      await loadData();
    } catch (err) {
      setError(err.message || "Rechnung konnte nicht gelöscht werden.");
    }
  }

  function handleUploaded(invoice) {
    if (invoice?.bauvorhaben) {
      setSelected(invoice.bauvorhaben);
    }
    loadData();
  }

  if (!authReady) {
    return (
      <div className="app">
        <p className="muted">Lade…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <LoginScreen
        mode={needsSetup ? "setup" : "login"}
        onSuccess={handleAuthSuccess}
      />
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-top">
          <div className="brand">
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
          <div className="header-user">
            <nav className="header-nav" aria-label="Hauptnavigation">
              <button
                type="button"
                className={`nav-link ${view === "invoices" ? "active" : ""}`}
                onClick={() => {
                  setView("invoices");
                  setSelected(null);
                }}
              >
                Rechnungen
              </button>
              {user.role === "admin" && (
                <button
                  type="button"
                  className={`nav-link ${view === "users" ? "active" : ""}`}
                  onClick={() => setView("users")}
                >
                  Benutzer
                </button>
              )}
            </nav>
            <span className="user-chip" title={`@${user.username}`}>
              {user.display_name}
              {user.role === "admin" ? " · Admin" : ""}
            </span>
            <button type="button" className="btn btn-sm btn-ghost" onClick={handleLogout}>
              Abmelden
            </button>
          </div>
        </div>
        <p>
          {view === "users"
            ? "Benutzer anlegen, Rollen vergeben und Zugänge verwalten."
            : "PDF-Rechnungen hochladen, prüfen und verwalten."}
        </p>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")}>
            ×
          </button>
        </div>
      )}

      <main className="app-main">
        {view === "users" ? (
          <UserAdmin currentUser={user} />
        ) : (
          <>
            <UploadForm
              onUploaded={handleUploaded}
              bauvorhabenListe={bauvorhabenListe.map((b) => b.name)}
            />
            {selected ? (
              <BauvorhabenDetail
                name={selected}
                invoices={selectedGroup?.invoices ?? []}
                summe={selectedGroup?.summe ?? 0}
                isShared={Boolean(selectedInfo?.is_shared || selectedGroup?.isShared)}
                canManageShares={Boolean(selectedInfo?.can_manage_shares)}
                currentUser={user}
                onBack={() => setSelected(null)}
                onDelete={handleDelete}
                onUpdate={handleUpdate}
                onShareChanged={loadData}
                loading={loading}
              />
            ) : (
              <BauvorhabenGrid
                groups={groups}
                onSelect={setSelected}
                loading={loading}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
