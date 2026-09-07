import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The `public/` directory (which contains the PHP `api/` backend, the PWA
// manifest, the service worker, and the app icons) is copied verbatim into the
// build output root. Because the frontend is deployed on the same InfinityFree
// domain as the API, all API calls use relative `/api/...` paths (same-origin).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "dist",
  },
});