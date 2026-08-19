import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite-Konfiguration für das Frontend der Rechnungsplattform.
// API-Aufrufe unter /api werden im Dev-Server an das Backend
// (http://localhost:8000) weitergeleitet.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
