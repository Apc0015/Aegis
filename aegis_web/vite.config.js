import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
// The Aegis API base URL is read at build/runtime from VITE_API_BASE.
// In dev we proxy /api to the FastAPI backend so cookies/CORS stay simple.
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
});
