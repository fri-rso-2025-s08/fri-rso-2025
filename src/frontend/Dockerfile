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
WORKDIR /app
COPY --from=builder /app/build build/
COPY --from=builder /app/node_modules node_modules/
COPY --from=builder /app/package.json ./

ENV NODE_ENV=production
EXPOSE 3000

CMD ["node", "build"]
