import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
// Requiring this also loads webapp/.env into process.env (see server/api.cjs).
const { handleApi } = require("./server/api.cjs");

export default defineConfig({
  plugins: [
    react(),
    {
      name: "steel-city-firestore-api",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (!req.url?.startsWith("/api/")) {
            next();
            return;
          }

          handleApi(req, res);
        });
      },
    },
  ],
});
