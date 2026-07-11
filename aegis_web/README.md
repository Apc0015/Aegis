# Aegis Web

React + TypeScript frontend for the Aegis enterprise RAG backend.

## Stack

- **Vite** + **React 18** + **TypeScript**
- **Tailwind CSS** + hand-rolled shadcn-style UI primitives (`src/components/ui`)
- **TanStack Query** for server state
- **React Router** for routing with auth + admin route guards
- **Axios** for REST, **fetch + ReadableStream** for authenticated SSE streaming
- **lucide-react** icons

## Features (parity with the Flutter client)

| Route | Description |
|-------|-------------|
| `/login` | JWT auth against `POST /api/v1/auth/login` |
| `/chat` | Streaming chat (SSE) with project + RAG-mode selectors, source chips, confidence / routing / firewall badges |
| `/dashboard` | Live health, project count, and recent audit activity (admin) |
| `/documents` | Drag-and-drop upload (PDF/DOCX/TXT/MD), per-project document list, delete (manager+) |
| `/projects` | List and create FAISS/BM25 projects |
| `/audit` | Audit log table with search/filter + CSV export (admin) |
| `/admin` | Users, connector status, and access-rules viewer (admin) |
| `/settings` | Live backend config + model browser (OpenRouter / Ollama) |

## Getting started

```bash
npm install
cp .env.example .env.local     # optional; defaults work with the dev proxy
npm run dev                    # http://localhost:5173
```

The dev server proxies `/api` to the FastAPI backend. Point it with:

```bash
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Start the backend separately:

```bash
# from the repo root
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Build

```bash
npm run build     # tsc -b && vite build  ->  dist/
npm run preview   # serve the production build locally
```

## Production

`dist/` is a static bundle. Serve it behind the same origin as the API (or set
`VITE_API_BASE=https://api.your-host` at build time). Because the SPA uses client
routing, configure your static host to fall back to `index.html` for unknown paths.

## Auth notes

- The JWT is stored in `localStorage` and attached as `Authorization: Bearer` to
  every request (including the SSE stream, which is why `fetch` is used instead of
  the header-less `EventSource`).
- Expired tokens are rejected on restore; a `401` clears the session.
- Admin-only routes (`/audit`, `/admin`) are guarded client-side **and** enforced
  server-side by the backend — the client guard is UX, not the security boundary.
