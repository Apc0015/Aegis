# ── Aegis web console (React/Vite → nginx) ────────────────────────────────────
# Build stage: compile the SPA. Runtime stage: serve static assets via nginx and
# reverse-proxy /api to the api service.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Empty VITE_API_BASE → the app calls same-origin /api, which nginx proxies.
ENV VITE_API_BASE=""
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
