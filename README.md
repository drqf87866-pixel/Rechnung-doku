# Doku-Agent

Rechnungsplattform: PDF-Rechnungen hochladen, einem Bauvorhaben (Projektname) zuordnen und Rechnungsnummer sowie Rechnungsbetrag automatisch extrahieren. Digitale PDFs werden per PyMuPDF direkt gelesen und per Regex-Heuristik ausgewertet; gescannte PDFs (ohne Textschicht) werden per Gemini Flash (LLM Vision) extrahiert. Datenhaltung über SQLAlchemy (lokal SQLite, produktiv Supabase Postgres), PDF-Ablage lokal oder in Supabase Storage. Zugang über Login (JWT); Administratoren verwalten Benutzer unter **Benutzer**.

## Struktur

```
doku-agent/
├── backend/          # FastAPI-Backend (Python)
│   ├── app/          # Anwendungscode (Config, Modelle, Router, Services, Storage)
│   ├── scripts/      # Wartungsskripte (z. B. Storage-Migration)
│   ├── tests/        # Unit-Tests
│   └── uploads/      # Hochgeladene PDF-Dateien (nur lokaler Fallback)
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

## Benutzerverwaltung / Login

Beim ersten Start ohne Benutzer erscheint im Frontend ein **Setup-Formular** für den ersten Administrator. Alternativ per Env (nur wenn die Tabelle `users` leer ist):

```env
JWT_SECRET=langes-zufaelliges-geheimnis
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=sicheres-passwort
```

- Rollen: `admin` (Benutzerverwaltung) und `user` (Rechnungen)
- Alle Rechnungs-APIs erfordern ein Bearer-Token
- Admins legen unter **Benutzer** weitere Zugänge an, setzen Passwörter zurück oder deaktivieren Konten
- Jeder Benutzer sieht standardmäßig nur **eigene** Rechnungen
- Bauvorhaben können unter **Teilen** freigegeben werden – dann sehen Owner und Empfänger gegenseitig die Rechnungen dieses Bauvorhabens (Bearbeiten/Löschen bleibt beim jeweiligen Eigentümer)

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

## Scan-PDFs (Gemini Flash)

PDFs ohne Textschicht (Scans) werden automatisch per **Gemini Flash** extrahiert. Dafür wird der API-Key aus [Google AI Studio](https://aistudio.google.com/apikey) benötigt.

Lokal in `backend/.env`:

```env
GEMINI_API_KEY=dein-api-key
# optional:
# GEMINI_MODEL=gemini-3.6-flash
```

Auf Render als Secret `GEMINI_API_KEY` setzen. Der Free Tier von Gemini Flash reicht für typische Upload-Volumina (ca. 500–1.500 Anfragen/Tag).

**Hinweise:**
- Digitale PDFs werden weiterhin lokal per PyMuPDF + Regex verarbeitet (schnell, kostenlos, datenschutzfreundlich).
- Scan-PDFs werden als Ganzes an Gemini gesendet; auf Render entfällt damit der speicherintensive OCR-Pfad (RapidOCR/OpenCV).
- Die Extraktion dauert bei Scan-PDFs typisch 2–8 Sekunden pro Rechnung.
- Rechnungsdaten aus Scans verlassen den Server Richtung Google API.

## Deployment

Backend auf Render (Python-Webservice), Datenbank als Supabase Postgres, PDF-Ablage in Supabase Storage, Frontend auf Netlify. Eine ausführliche Schritt-für-Schritt-Anleitung gibt es in der Session-Doku bzw. siehe Abschnitte unten.

### Supabase (Datenbank + Storage)

1. Supabase-Projekt anlegen → **Connect** → **Connection string** → **"Transaction pooler"** (Port 6543) kopieren.
2. Die URL später als `DATABASE_URL` in Render eintragen, z.B.:

```bash
postgresql://postgres.<ref>:<passwort>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Die Tabellen werden beim ersten Start automatisch von FastAPI angelegt (`Base.metadata.create_all`).

3. **Storage für die PDFs (empfohlen):** In **Project Settings → API** den **service_role secret** kopieren (nur für das Backend, niemals ins Frontend!). Render-Variablen:
   - `SUPABASE_URL` = `https://<projekt-ref>.supabase.co`
   - `SUPABASE_SERVICE_KEY` = der service_role secret
   - `SUPABASE_STORAGE_BUCKET` = `invoices` (Standard)

   Der Bucket wird beim ersten Backend-Start **automatisch als privater Bucket** angelegt (`storage.ensure_bucket` in `app/main.py`). Existiert bereits ein Bucket mit diesem Namen, wird er beim Start auf **privat** gesetzt bzw. der Start bricht mit klarer Fehlermeldung ab, falls das nicht möglich ist. Optional manuell: **Storage → New bucket** → Name `invoices`, **Public bucket: aus**.

   Ohne `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` speichert das Backend weiterhin lokal unter `UPLOAD_DIR` (Standard `./uploads`) – praktisch für die lokale Entwicklung.

4. **Migration von Altbeständen (nur einmalig nötig):** Rechnungen, die vor dem Umstieg auf Supabase Storage hochgeladen wurden, liegen nur lokal in `./uploads`. Nach dem Umstieg verweist die DB zwar weiter auf die gleichen `stored_filename`s, die Datei ist dort aber nicht mehr. Das Skript `backend/scripts/migrate_local_uploads.py` lädt alle lokal noch vorhandenen PDFs in den Bucket (idempotent, Upload mit Upsert):

```powershell
.venv\Scripts\python scripts/migrate_local_uploads.py
# optional: lokale Dateien nach erfolgreichem Upload löschen:
.venv\Scripts\python scripts/migrate_local_uploads.py --delete-local
```

### Render (Backend)

- `render.yaml` wird als Blueprint unterstützt (New → Blueprint). Alternativ manuell: New Web Service → Root-Directory `backend` wählen (wenn das Repo an der Wurzel liegt), Build Command `pip install -r requirements.txt`, Start Command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Env-Variablen in Render setzen:
  - `DATABASE_URL` (Supabase-Pooler-URL)
  - `CORS_ORIGINS` (z.B. `https://rechnung-doku.netlify.app,http://localhost:5173`)
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, optional `SUPABASE_STORAGE_BUCKET=invoices`
  - `GEMINI_API_KEY` (für Scan-PDF-Extraktion)
  - `JWT_SECRET` (Pflicht in Produktion)
  - optional `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD` (erster Admin)
  - optional `GEMINI_MODEL=gemini-3.6-flash`
  - optional `UPLOAD_DIR=./uploads` (nur lokaler Fallback relevant)
- **Upload-Persistenz:** Mit Supabase Storage überleben die PDFs jeden Redeploy und sind über alle Instanzen geteilt. Der lokale Fallback (`./uploads`) ist auf dem Free-Tier von Render ephemer – dort gehen hochgeladene PDFs bei jedem Restart/Deploy verloren.
- Automatische Deployments: Repo auf GitHub, Render verbindet sich.

### Netlify (Frontend)

- `frontend/netlify.toml` liegt im Repo; beim "Import an existing project" Root-Directory `frontend` wählen (Build Command `npm run build`, Publish directory `dist` – ist durch netlify.toml gesetzt).
- Env-Variable in Netlify setzen: `VITE_API_URL=https://<dein-render-backend>.onrender.com/api` (**mit `/api`**, ohne trailing slash). Ohne diese Variable nutzt das Frontend lokal den `/api`-Proxy.
- CORS: Die Render-Domain (`https://<dein-render-backend>.onrender.com`) muss in der `CORS_ORIGINS`-Liste von Render die Netlify-Domain enthalten.