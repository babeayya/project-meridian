# ── Frontend image (Next.js standalone) ─────────────────────────────────────
# NOTE: NEXT_PUBLIC_* vars are inlined at BUILD time, so the backend URL must
# be passed as a build arg, not a runtime env var:
#   docker build --build-arg NEXT_PUBLIC_API_BASE=https://api.example.com/api/v1 .
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000/api/v1
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN addgroup -g 10001 app && adduser -u 10001 -G app -S app
COPY --from=builder /app/public ./public
COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static ./.next/static
USER app
# Next standalone server honours PORT and HOSTNAME
ENV PORT=3000 HOSTNAME=0.0.0.0
EXPOSE 3000
CMD ["node", "server.js"]
