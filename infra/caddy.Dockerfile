# Builds the web app, then serves it from Caddy. Build context is the repo root.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY contracts/ /contracts/
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=web /web/dist /srv
