# ── Dependencies ──────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --frozen-lockfile

# ── Build ─────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# ── Runtime ───────────────────────────────────────────────────
FROM node:20-alpine AS runtime
LABEL description="LexRAG — Next.js Frontend"

RUN addgroup -S lexrag && adduser -S lexrag -G lexrag
WORKDIR /app

COPY --from=builder /app/public ./public
COPY --from=builder --chown=lexrag:lexrag /app/.next/standalone ./
COPY --from=builder --chown=lexrag:lexrag /app/.next/static ./.next/static

USER lexrag
EXPOSE 3000
ENV NODE_ENV=production
ENV PORT=3000

CMD ["node", "server.js"]
