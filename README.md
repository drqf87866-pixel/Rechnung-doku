# Doku-Agent

Rechnungsplattform: PDF-Rechnungen hochladen, einem Bauvorhaben (Projektname) zuordnen und Rechnungsnummer sowie Rechnungsbetrag automatisch per Regex-Heuristik extrahieren. Datenhaltung über SQLite (SQLAlchemy 2.0), PDF-Text-Extraktion per PyMuPDF.

## Struktur

```
doku-agent/
├── backend/          # FastAPI-Backend (Python)
│   ├── app/          # Anwendungscode (Config, Modelle, Router, Services)
│   ├── tests/        # Unit-Tests
│   └── uploads/      # Hochgeladene PDF-Dateien
└── frontend/         # Frontend (Vite)
```

## Backend einrichten

Windows PowerShell, aus dem Verzeichnis `backend/`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Backend starten

```powershell
uvicorn app.main:app --reload --port 8000
```

Die interaktive API-Doku ist unter http://localhost:8000/docs erreichbar.

## Frontend einrichten

Aus dem Verzeichnis `frontend/`:

```powershell
npm install
```

## Frontend starten

```powershell
npm run dev
```

Vite läuft auf http://localhost:5173, ein Proxy leitet `/api` an http://localhost:8000 weiter.

## Tests

```powershell
.venv\Scripts\python -m pytest tests/ -v
```

## Deployment

Backend auf Render (Python-Webservice), Datenbank als Supabase Postgres, Frontend auf Netlify.

### Supabase (Datenbank)

1. Supabase-Projekt anlegen → "Connect" → "Connection string" → **"Transaction pooler"** (Port 6543) kopieren.
2. Die URL später als `DATABASE_URL` in Render eintragen, z.B.:

```bash
postgresql://postgres.<ref>:<passwort>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Die Tabellen werden beim ersten Start automatisch von FastAPI angelegt (`Base.metadata.create_all`).

### Render (Backend)

- `render.yaml` wird als Blueprint unterstützt (New → Blueprint). Alternativ manuell: New Web Service → Root-Directory `backend` wählen (wenn das Repo an der Wurzel liegt), Build Command `pip install -r requirements.txt`, Start Command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Env-Variablen in Render setzen: `DATABASE_URL` (Supabase-Pooler-URL), `CORS_ORIGINS` (z.B. `https://doku-agent.netlify.app,http://localhost:5173`), optional `UPLOAD_DIR=./uploads`.
- **WICHTIG (Upload-Persistenz):** Der Dateispeicher (`./uploads`) ist auf dem Free-Tier von Render ephemer – hochgeladene PDFs gehen bei jedem Restart/Deploy verloren und sind nicht über mehrere Instanzen geteilt. Empfohlene Folge-Optionen: Supabase Storage für die PDFs (Adapter in `app/storage.py` austauschbar) oder Render Persistent Disk (bezahltes Add-on).
- Automatische Deployments: Repo auf GitHub, Render verbindet sich.

### Netlify (Frontend)

- `frontend/netlify.toml` liegt im Repo; beim "Import an existing project" Root-Directory `frontend` wählen (Build Command `npm run build`, Publish directory `dist` – ist durch netlify.toml gesetzt).
- Env-Variable in Netlify setzen: `VITE_API_URL=https://<dein-render-backend>.onrender.com` (ohne trailing slash). Ohne diese Variable nutzt das Frontend lokal den `/api`-Proxy.
- CORS: Die Render-Domain (`https://<dein-render-backend>.onrender.com`) muss in der `CORS_ORIGINS`-Liste von Render die Netlify-Domain enthalten.
