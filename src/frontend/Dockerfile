FROM node:25-alpine AS builder
RUN npm install -g pnpm
ENV CI=true
WORKDIR /app
COPY package.json pnpm-* ./
RUN pnpm install
COPY . .
RUN pnpm run build
RUN pnpm prune --prod

FROM node:25-alpine
RUN npm install -g pnpm
WORKDIR /app
COPY --from=builder /app/build build/
COPY --from=builder /app/node_modules node_modules/
COPY --from=builder /app/package.json ./
COPY --from=builder /app/drizzle.config.ts ./
COPY --from=builder /app/src/lib/server/db/schema.ts src/lib/server/db/
COPY --from=builder /app/docker-entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENV NODE_ENV=production
EXPOSE 3000

ENTRYPOINT ["/app/entrypoint.sh"]
